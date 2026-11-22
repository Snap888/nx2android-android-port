#define _GNU_SOURCE
#include <android/log.h>
#include <android/native_activity.h>
#include <dlfcn.h>
#include <jni.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <elf.h>
#include <stdio.h>
#include <stdarg.h>
#include <time.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "ngr_profile.h"

#define TAG "NGRRuntime"
static char g_runtime_log_path[1400];
static char g_runtime_log_dir[1200];

static void runtime_log_emit(int priority, const char *fmt, ...) {
    char message[4096];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(message, sizeof(message), fmt, ap);
    va_end(ap);
    __android_log_write(priority, TAG, message);

    if (!g_runtime_log_path[0]) return;
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    struct tm tmv;
    localtime_r(&ts.tv_sec, &tmv);
    char stamp[64];
    strftime(stamp, sizeof(stamp), "%Y-%m-%d %H:%M:%S", &tmv);
    char line[4352];
    int len = snprintf(line, sizeof(line), "%s.%03ld [%s] pid=%ld %s\n",
        stamp, ts.tv_nsec / 1000000L, priority >= ANDROID_LOG_ERROR ? "E" : "I",
        (long)getpid(), message);
    if (len <= 0) return;
    if ((size_t)len >= sizeof(line)) len = (int)sizeof(line) - 1;
    int fd = open(g_runtime_log_path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) return;
    size_t off = 0;
    while (off < (size_t)len) {
        ssize_t n = write(fd, line + off, (size_t)len - off);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) break;
        off += (size_t)n;
    }
    close(fd);
}
#define LOGE(...) runtime_log_emit(ANDROID_LOG_ERROR, __VA_ARGS__)
#define LOGI(...) runtime_log_emit(ANDROID_LOG_INFO, __VA_ARGS__)

typedef void (*game_on_create_fn)(ANativeActivity *, void *, size_t);
static void *g_game_handles[64];
static char g_game_loaded_names[64][256];
static size_t g_game_handle_count;

static void toast(ANativeActivity *activity, const char *message) {
    if (!activity || !activity->env || !activity->clazz) return;
    JNIEnv *env = activity->env;
    jclass cls = (*env)->FindClass(env, "android/widget/Toast");
    if (!cls) { (*env)->ExceptionClear(env); return; }
    jmethodID make = (*env)->GetStaticMethodID(env, cls, "makeText",
        "(Landroid/content/Context;Ljava/lang/CharSequence;I)Landroid/widget/Toast;");
    if (!make) { (*env)->ExceptionClear(env); return; }
    jstring text = (*env)->NewStringUTF(env, message);
    jobject obj = (*env)->CallStaticObjectMethod(env, cls, make, activity->clazz, text, 1);
    if ((*env)->ExceptionCheck(env)) { (*env)->ExceptionClear(env); return; }
    jmethodID show = (*env)->GetMethodID(env, cls, "show", "()V");
    if (show && obj) (*env)->CallVoidMethod(env, obj, show);
    if ((*env)->ExceptionCheck(env)) (*env)->ExceptionClear(env);
}

static int valid_game_id(const char *id) {
    if (!id || strlen(id) != 20) return 0;
    for (size_t i = 0; i < 20; ++i)
        if (!((id[i] >= '0' && id[i] <= '9') || (id[i] >= 'a' && id[i] <= 'f'))) return 0;
    return 1;
}

static jstring game_id_from_intent(ANativeActivity *activity) {
    JNIEnv *env = activity->env;
    jclass activity_cls = (*env)->GetObjectClass(env, activity->clazz);
    if (!activity_cls) return NULL;
    jmethodID get_intent = (*env)->GetMethodID(env, activity_cls, "getIntent", "()Landroid/content/Intent;");
    if (!get_intent) return NULL;
    jobject intent = (*env)->CallObjectMethod(env, activity->clazz, get_intent);
    if (!intent || (*env)->ExceptionCheck(env)) { (*env)->ExceptionClear(env); return NULL; }
    jclass intent_cls = (*env)->GetObjectClass(env, intent);
    jmethodID get_extra = (*env)->GetMethodID(env, intent_cls, "getStringExtra", "(Ljava/lang/String;)Ljava/lang/String;");
    if (!get_extra) return NULL;
    jstring key = (*env)->NewStringUTF(env, "game_id");
    return (jstring)(*env)->CallObjectMethod(env, intent, get_extra, key);
}

static int mkdirs(const char *path) {
    char tmp[1200];
    if (!path || strlen(path) >= sizeof(tmp)) return -1;
    strcpy(tmp, path);
    for (char *p = tmp + 1; *p; ++p) if (*p == '/') {
        *p = 0; if (mkdir(tmp, 0700) && errno != EEXIST) return -1; *p = '/';
    }
    if (mkdir(tmp, 0700) && errno != EEXIST) return -1;
    return 0;
}

static int runtime_log_init(const char *internal_root, const char *game_id) {
    if (!internal_root || !*internal_root || !game_id || !*game_id) return -1;
    int a = snprintf(g_runtime_log_dir, sizeof(g_runtime_log_dir), "%s/ngr-logs", internal_root);
    int b = snprintf(g_runtime_log_path, sizeof(g_runtime_log_path), "%s/%s.log", g_runtime_log_dir, game_id);
    if (a < 0 || (size_t)a >= sizeof(g_runtime_log_dir) || b < 0 || (size_t)b >= sizeof(g_runtime_log_path)) {
        g_runtime_log_path[0] = 0; return -1;
    }
    if (mkdirs(g_runtime_log_dir)) { g_runtime_log_path[0] = 0; return -1; }
    char pid_path[1500];
    int n = snprintf(pid_path, sizeof(pid_path), "%s/%s.pid", g_runtime_log_dir, game_id);
    if (n > 0 && (size_t)n < sizeof(pid_path)) {
        int fd = open(pid_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0600);
        if (fd >= 0) {
            char pid[48]; int plen = snprintf(pid, sizeof(pid), "%ld\n", (long)getpid());
            if (plen > 0) (void)write(fd, pid, (size_t)plen);
            close(fd);
        }
    }
    int fd = open(g_runtime_log_path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) { g_runtime_log_path[0] = 0; return -1; }
    close(fd);
    /* Capture printf/fprintf(stderr) from the game host as well as our tagged logs. */
    fd = open(g_runtime_log_path, O_WRONLY | O_APPEND | O_CLOEXEC | O_NOFOLLOW);
    if (fd >= 0) {
        (void)dup2(fd, STDOUT_FILENO);
        (void)dup2(fd, STDERR_FILENO);
        if (fd > STDERR_FILENO) close(fd);
        setvbuf(stdout, NULL, _IONBF, 0);
        setvbuf(stderr, NULL, _IONBF, 0);
    }
    return 0;
}

static int copy_file(const char *src, const char *dst) {
    int in = open(src, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (in < 0) return -1;
    struct stat source_stat;
    if (fstat(in, &source_stat) || !S_ISREG(source_stat.st_mode)) {
        int saved = errno ? errno : EINVAL; close(in); errno = saved; return -1;
    }
    int out = open(dst, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0700);
    if (out < 0) { close(in); return -1; }
    char buf[128 * 1024]; int ok = 0;
    for (;;) {
        ssize_t n = read(in, buf, sizeof(buf));
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) { ok = -1; break; }
        if (n == 0) break;
        ssize_t off = 0;
        while (off < n) {
            ssize_t w = write(out, buf + off, (size_t)(n - off));
            if (w < 0 && errno == EINTR) continue;
            if (w <= 0) { ok = -1; break; }
            off += w;
        }
        if (ok) break;
    }
    if (!ok && fsync(out)) ok = -1;
    int saved = errno;
    close(in);
    if (close(out) && !ok) { ok = -1; saved = errno; }
    if (!ok && chmod(dst, 0700)) { ok = -1; saved = errno; }
    if (ok) errno = saved;
    return ok;
}

static char *read_small_file(const char *path, size_t max_size, size_t *size_out) {
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return NULL;
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size <= 0 || (uint64_t)st.st_size > max_size) {
        close(fd);
        errno = EFBIG;
        return NULL;
    }
    size_t size = (size_t)st.st_size;
    char *data = (char *)malloc(size + 1);
    if (!data) { close(fd); return NULL; }
    size_t done = 0;
    while (done < size) {
        ssize_t n = read(fd, data + done, size - done);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { free(data); close(fd); errno = EIO; return NULL; }
        done += (size_t)n;
    }
    close(fd);
    data[size] = 0;
    if (size_out) *size_out = size;
    return data;
}

static int valid_aarch64_elf(const char *path) {
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return 0;
    Elf64_Ehdr eh;
    ssize_t n;
    do { n = read(fd, &eh, sizeof(eh)); } while (n < 0 && errno == EINTR);
    close(fd);
    return n == (ssize_t)sizeof(eh) &&
           eh.e_ident[EI_MAG0] == ELFMAG0 &&
           eh.e_ident[EI_MAG1] == ELFMAG1 &&
           eh.e_ident[EI_MAG2] == ELFMAG2 &&
           eh.e_ident[EI_MAG3] == ELFMAG3 &&
           eh.e_ident[EI_CLASS] == ELFCLASS64 &&
           eh.e_ident[EI_DATA] == ELFDATA2LSB &&
           eh.e_machine == EM_AARCH64;
}


/* Inspect the generated runtime before handing it to bionic's linker. This is
 * deliberately read-only: malformed constructor metadata must be diagnosed
 * before dlopen can execute it and take down the Android process. */
static uint64_t elf_vaddr_to_offset(const Elf64_Phdr *phdrs, size_t phnum,
                                    uint64_t vaddr, uint64_t length) {
    for (size_t i = 0; i < phnum; ++i) {
        const Elf64_Phdr *p = &phdrs[i];
        if (p->p_type != PT_LOAD || vaddr < p->p_vaddr) continue;
        uint64_t delta = vaddr - p->p_vaddr;
        if (delta <= p->p_filesz && length <= p->p_filesz - delta)
            return p->p_offset + delta;
    }
    return UINT64_MAX;
}

static int log_runtime_elf_metadata(const char *path) {
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) { LOGE("[ELF preflight] open failed: %s", strerror(errno)); return -1; }
    Elf64_Ehdr eh;
    if (pread(fd, &eh, sizeof(eh), 0) != (ssize_t)sizeof(eh) ||
        memcmp(eh.e_ident, ELFMAG, SELFMAG) != 0 ||
        eh.e_ident[EI_CLASS] != ELFCLASS64 || eh.e_machine != EM_AARCH64 ||
        eh.e_phentsize != sizeof(Elf64_Phdr) || eh.e_phnum == 0 || eh.e_phnum > 128) {
        LOGE("[ELF preflight] invalid ELF/program-header table");
        close(fd); return -1;
    }
    LOGI("[ELF preflight] type=%u machine=%u entry=0x%llx phnum=%u",
         eh.e_type, eh.e_machine, (unsigned long long)eh.e_entry, eh.e_phnum);
    if (eh.e_type != ET_DYN) {
        LOGE("[ELF preflight] refusing non-ET_DYN runtime (type=%u)", eh.e_type);
        close(fd); return -1;
    }
    Elf64_Phdr phdrs[128];
    size_t phbytes = (size_t)eh.e_phnum * sizeof(Elf64_Phdr);
    if (pread(fd, phdrs, phbytes, (off_t)eh.e_phoff) != (ssize_t)phbytes) {
        LOGE("[ELF preflight] cannot read program headers");
        close(fd); return -1;
    }
    uint64_t init_addr = 0, array_addr = 0, array_size = 0;
    uint64_t rela_addr = 0, rela_size = 0, rela_ent = sizeof(Elf64_Rela);
    uint64_t relr_addr = 0, relr_size = 0, relr_ent = sizeof(Elf64_Addr);
    for (size_t i = 0; i < eh.e_phnum; ++i) {
        if (phdrs[i].p_type != PT_DYNAMIC) continue;
        uint64_t off = phdrs[i].p_offset, size = phdrs[i].p_filesz;
        for (uint64_t pos = 0; pos + sizeof(Elf64_Dyn) <= size; pos += sizeof(Elf64_Dyn)) {
            Elf64_Dyn dyn;
            if (pread(fd, &dyn, sizeof(dyn), (off_t)(off + pos)) != (ssize_t)sizeof(dyn)) break;
            if (dyn.d_tag == DT_NULL) break;
            if (dyn.d_tag == DT_INIT) init_addr = dyn.d_un.d_ptr;
            else if (dyn.d_tag == DT_INIT_ARRAY) array_addr = dyn.d_un.d_ptr;
            else if (dyn.d_tag == DT_INIT_ARRAYSZ) array_size = dyn.d_un.d_val;
            else if (dyn.d_tag == DT_RELA) rela_addr = dyn.d_un.d_ptr;
            else if (dyn.d_tag == DT_RELASZ) rela_size = dyn.d_un.d_val;
            else if (dyn.d_tag == DT_RELAENT) rela_ent = dyn.d_un.d_val;
            else if (dyn.d_tag == DT_RELR) relr_addr = dyn.d_un.d_ptr;
            else if (dyn.d_tag == DT_RELRSZ) relr_size = dyn.d_un.d_val;
            else if (dyn.d_tag == DT_RELRENT) relr_ent = dyn.d_un.d_val;
        }
    }
    LOGI("[ELF preflight] DT_INIT=0x%llx INIT_ARRAY=0x%llx INIT_ARRAYSZ=%llu",
         (unsigned long long)init_addr, (unsigned long long)array_addr,
         (unsigned long long)array_size);
    LOGI("[ELF preflight] DT_RELA=0x%llx RELASZ=%llu RELAENT=%llu DT_RELR=0x%llx RELRSZ=%llu RELRENT=%llu",
         (unsigned long long)rela_addr, (unsigned long long)rela_size,
         (unsigned long long)rela_ent, (unsigned long long)relr_addr,
         (unsigned long long)relr_size, (unsigned long long)relr_ent);
    if (array_size && array_size <= 4096 && array_size % sizeof(Elf64_Addr) == 0) {
        uint64_t array_off = elf_vaddr_to_offset(phdrs, eh.e_phnum, array_addr, array_size);
        if (array_off == UINT64_MAX) {
            LOGE("[ELF preflight] init array is outside file-backed PT_LOAD segments");
        } else {
            uint64_t count = array_size / sizeof(Elf64_Addr);
            uint64_t rela_off = rela_addr ? elf_vaddr_to_offset(phdrs, eh.e_phnum, rela_addr, rela_size) : UINT64_MAX;
            int rela_table_valid = rela_size && rela_size <= 64u * 1024u * 1024u &&
                                   rela_ent == sizeof(Elf64_Rela) &&
                                   rela_size % sizeof(Elf64_Rela) == 0 &&
                                   rela_off != UINT64_MAX;
            int missing_constructor_reloc = 0;
            if (rela_addr && !rela_table_valid)
                LOGE("[ELF preflight] DT_RELA table has invalid bounds/entry size");
            if (rela_table_valid)
                LOGI("[ELF preflight] DT_RELA mapped file offset=0x%llx entries=%llu",
                     (unsigned long long)rela_off,
                     (unsigned long long)(rela_size / sizeof(Elf64_Rela)));
            for (uint64_t i = 0; i < count; ++i) {
                Elf64_Addr value = 0;
                uint64_t slot_vaddr = array_addr + i * sizeof(value);
                if (pread(fd, &value, sizeof(value),
                          (off_t)(array_off + i * sizeof(value))) != (ssize_t)sizeof(value)) break;
                int found = 0;
                if (rela_table_valid) {
                    for (uint64_t ro = 0; ro < rela_size; ro += sizeof(Elf64_Rela)) {
                        Elf64_Rela rel;
                        if (pread(fd, &rel, sizeof(rel), (off_t)(rela_off + ro)) != (ssize_t)sizeof(rel)) break;
                        if (rel.r_offset == slot_vaddr) {
                            found = 1;
                            LOGI("[ELF preflight] init_array[%llu] relocation: type=%u symbol=%u addend=0x%llx",
                                 (unsigned long long)i,
                                 (unsigned)ELF64_R_TYPE(rel.r_info),
                                 (unsigned)ELF64_R_SYM(rel.r_info),
                                 (unsigned long long)rel.r_addend);
                            break;
                        }
                    }
                }
                if (value && !found && !relr_size) missing_constructor_reloc = 1;
                LOGI("[ELF preflight] init_array[%llu] slot=0x%llx raw=0x%llx rela=%s",
                     (unsigned long long)i, (unsigned long long)slot_vaddr,
                     (unsigned long long)value,
                     found ? "present" : (relr_size ? "not-in-RELA-check-RELR-may-cover" : "MISSING"));
            }
            if (relr_size)
                LOGI("[ELF preflight] packed RELR relocations present; init-array coverage requires RELR decoding");
            if (missing_constructor_reloc) {
                LOGE("[ELF preflight] refusing malformed shared object: non-null init_array entries have no dynamic relocation");
                close(fd);
                return -1;
            }
        }
    } else if (array_size) {
        LOGE("[ELF preflight] unusual init array size=%llu", (unsigned long long)array_size);
    }
    close(fd);
    return 0;
}

static int game_library_loaded(const char *name) {
    for (size_t i = 0; i < g_game_handle_count; ++i)
        if (!strcmp(g_game_loaded_names[i], name)) return 1;
    return 0;
}

/* Android shared storage is not a safe executable mapping location. Copy native libraries
 * into this app's private files directory before dlopen; game data itself stays in its
 * app-specific external files directory and remains readable through DM_GAME_DIR. */
static int stage_native_libs(const char *external_game_dir, const char *private_game_dir) {
    if (mkdirs(private_game_dir)) { LOGE("cannot create private runtime directory %s: %s", private_game_dir, strerror(errno)); return -1; }
    DIR *dir = opendir(external_game_dir);
    if (!dir) { LOGE("cannot open game data directory %s: %s", external_game_dir, strerror(errno)); return -1; }
    struct dirent *ent; int copied = 0;
    while ((ent = readdir(dir))) {
        size_t n = strlen(ent->d_name);
        if (n < 4 || strcmp(ent->d_name + n - 3, ".so")) continue;
        char src[1400], dst[1400];
        snprintf(src, sizeof(src), "%s/%s", external_game_dir, ent->d_name);
        snprintf(dst, sizeof(dst), "%s/%s", private_game_dir, ent->d_name);
        struct stat st;
        if (stat(src, &st) || !S_ISREG(st.st_mode)) continue;
        if (copy_file(src, dst)) { LOGE("cannot stage %s: %s", ent->d_name, strerror(errno)); closedir(dir); return -1; }
        copied++;
    }
    closedir(dir);
    LOGI("staged %d native libraries in private app storage", copied);
    return copied > 0 ? 0 : -1;
}

static int preload_game_dependencies(const char *private_game_dir) {
    int total_loaded = 0;
    /* APK ZIP order is not a dependency order. Retry failed libraries so a
       dependency that initially missed another bundled .so can now resolve. */
    for (int pass = 0; pass < 8; ++pass) {
        DIR *dir = opendir(private_game_dir);
        if (!dir) { LOGE("cannot enumerate staged native libraries: %s", strerror(errno)); return -1; }
        struct dirent *ent; int loaded_this_pass = 0;
        while ((ent = readdir(dir))) {
            size_t n = strlen(ent->d_name);
            if (n < 4 || strcmp(ent->d_name + n - 3, ".so") ||
                !strcmp(ent->d_name, "libdmhost.so") ||
                game_library_loaded(ent->d_name)) continue;
            if (g_game_handle_count >= (sizeof(g_game_handles) / sizeof(g_game_handles[0])) - 1) {
                LOGE("too many game native libraries; refusing to overflow runtime handle table");
                closedir(dir);
                return -1;
            }
            char path[1400];
            int len = snprintf(path, sizeof(path), "%s/%s", private_game_dir, ent->d_name);
            if (len < 0 || (size_t)len >= sizeof(path)) {
                LOGE("native library path is too long: %s", ent->d_name);
                continue;
            }
            /* The GSL allocator shim overrides allocation entry points. Keep it
               out of the process-wide symbol scope: making it RTLD_GLOBAL can
               replace allocator symbols used by bionic's linker while the main
               runtime is being relocated. The game runtime may still load it
               through its own DT_NEEDED dependency group. */
            int load_flags = RTLD_NOW | RTLD_GLOBAL;
            if (!strcmp(ent->d_name, "libgsl_alloc_hook.so")) {
                load_flags = RTLD_NOW | RTLD_LOCAL;
                LOGI("[stage 3/8] isolating allocator shim from global linker scope");
            }
            LOGI("[stage 3/8] dlopen companion begin: %s flags=%s",
                 ent->d_name, (load_flags & RTLD_GLOBAL) ? "GLOBAL" : "LOCAL");
            dlerror();
            void *h = dlopen(path, load_flags);
            const char *err = dlerror();
            if (h) {
                g_game_handles[g_game_handle_count] = h;
                snprintf(g_game_loaded_names[g_game_handle_count], sizeof(g_game_loaded_names[0]), "%s", ent->d_name);
                g_game_handle_count++;
                loaded_this_pass++;
                total_loaded++;
                LOGI("preloaded game dependency %s handle=%p", ent->d_name, h);
            } else {
                LOGI("dependency load deferred (%s): %s", ent->d_name, err ? err : "unknown");
            }
        }
        closedir(dir);
        if (!loaded_this_pass) break;
    }
    LOGI("preloaded %d companion game libraries", total_loaded);
    return total_loaded;
}

__attribute__((visibility("default")))
void ANativeActivity_onCreate(ANativeActivity *activity, void *saved_state, size_t saved_state_size) {
    LOGI("NativeActivity_onCreate entered; saved_state=%s", saved_state ? "present" : "none");
    jstring jid = game_id_from_intent(activity);
    if (!jid) {
        LOGE("launch intent has no game_id extra");
        toast(activity, "NGR: no game selected");
        ANativeActivity_finish(activity);
        return;
    }
    const char *id = (*activity->env)->GetStringUTFChars(activity->env, jid, NULL);
    if (!valid_game_id(id)) {
        LOGE("invalid game id: %s", id ? id : "(null)");
        toast(activity, "NGR: invalid game shortcut");
        if (id) (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }

    const char *external = activity->externalDataPath ? activity->externalDataPath : activity->internalDataPath;
    const char *internal = activity->internalDataPath ? activity->internalDataPath : activity->externalDataPath;
    if (runtime_log_init(internal, id)) {
        __android_log_print(ANDROID_LOG_ERROR, TAG, "cannot initialize persistent runtime log under %s: %s", internal ? internal : "(null)", strerror(errno));
    }
    LOGI("============================================================");
    LOGI("NGR launch session started: game_id=%s sdk=%d abi=arm64-v8a", id, activity->sdkVersion);
    LOGI("NativeActivity paths: internal=%s external=%s", internal ? internal : "(null)", external ? external : "(null)");
    char game_dir[1024], private_dir[1024], lib_path[1200], external_lib[1200];
    int a = snprintf(game_dir, sizeof(game_dir), "%s/games/%s", external, id);
    int b = snprintf(private_dir, sizeof(private_dir), "%s/games/%s", internal, id);
    int d = snprintf(external_lib, sizeof(external_lib), "%s/libdmhost.so", game_dir);
    int e = snprintf(lib_path, sizeof(lib_path), "%s/libdmhost.so", private_dir);
    if (a < 0 || (size_t)a >= sizeof(game_dir) || b < 0 || (size_t)b >= sizeof(private_dir) ||
        d < 0 || (size_t)d >= sizeof(external_lib) || e < 0 || (size_t)e >= sizeof(lib_path)) {
        LOGE("game storage path exceeds supported length");
        toast(activity, "Game storage path is too long");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }
    char marker[1200];
    int m = snprintf(marker, sizeof(marker), "%s/nx2a-data.json", game_dir);
    if (m < 0 || (size_t)m >= sizeof(marker) || access(marker, R_OK) != 0 || access(external_lib, R_OK) != 0) {
        LOGE("game payload is incomplete: marker=%s runtime=%s", marker, external_lib);
        toast(activity, "Game payload is incomplete. Install runtime + data from its Library card.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }
    if (!valid_aarch64_elf(external_lib)) {
        LOGE("game runtime is not a valid 64-bit ARM ELF: %s", external_lib);
        toast(activity, "Game runtime is corrupt or not ARM64. Recompile the game.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }

    /* Schema-v1 JSON is an intermediate ABI artifact. Validate that it is the
       exact profile used for this data pack; legacy payloads still use macros. */
    char profile_path[1200];
    int pp = snprintf(profile_path, sizeof(profile_path), "%s/profile.json", game_dir);
    if (pp >= 0 && (size_t)pp < sizeof(profile_path) && access(profile_path, R_OK) == 0) {
        size_t manifest_size = 0, profile_size = 0;
        char *manifest_json = read_small_file(marker, 4u * 1024u * 1024u, &manifest_size);
        char *profile_json = read_small_file(profile_path, 4u * 1024u * 1024u, &profile_size);
        if (manifest_json && profile_json) {
            ngr_profile_summary summary;
            char profile_error[256] = {0};
            if (ngr_profile_validate(profile_json, profile_size, manifest_json, manifest_size,
                                     id, &summary, profile_error, sizeof(profile_error)) == 0) {
                LOGI("[NGR profile] schema v%d validated: title=%s modules=%zu rows=%zu build-table-rows=%zu overlay=%zu",
                     summary.schema_version, summary.title_id, summary.module_count,
                     summary.profile_row_count, summary.game_table_row_count, summary.overlay_count);
            } else {
                LOGE("[NGR profile] JSON rejected; continuing with compiled legacy profile: %s", profile_error);
            }
        } else {
            LOGE("[NGR profile] cannot read profile/manifest JSON; continuing with compiled legacy profile: %s", strerror(errno));
        }
        free(manifest_json);
        free(profile_json);
    } else {
        LOGI("[NGR profile] no profile.json; using the compiled game profile (legacy payload)");
    }

    if (stage_native_libs(game_dir, private_dir)) {
        toast(activity, "Cannot copy game runtime to private storage. Check free space.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }

    setenv("DM_GAME_DIR", game_dir, 1);
    setenv("NGR_PRIVATE_GAME_DIR", private_dir, 1);
    setenv("NGR_GAME_ID", id, 1);
    LOGI("[stage 1/8] payload validated; game_dir=%s private_dir=%s", game_dir, private_dir);
    LOGI("[stage 2/8] native libraries staged; runtime=%s", lib_path);
    LOGI("[stage 3/8] preloading companion dependencies");
    int preloaded = preload_game_dependencies(private_dir);
    LOGI("[stage 3/8] dependency preload finished: %d companion libraries", preloaded);

    LOGI("[stage 4/8] inspecting main runtime ELF before dlopen: %s", lib_path);
    if (log_runtime_elf_metadata(lib_path) != 0) {
        LOGE("[stage 4/8] runtime ELF preflight rejected the library");
        toast(activity, "Game runtime ELF is invalid. See NGR runtime log.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }
    LOGI("[stage 4/8] main runtime dlopen begin: %s (RTLD_LAZY|RTLD_LOCAL)", lib_path);
    dlerror();
    /* Defer function relocations until first use. This avoids resolving optional
       hook entry points during the loader constructor phase. */
    void *game_handle = dlopen(lib_path, RTLD_LAZY | RTLD_LOCAL);
    const char *err = dlerror();
    if (!game_handle) {
        LOGE("[stage 4/8] dlopen failed for %s: %s", lib_path, err ? err : "unknown linker error");
        toast(activity, "Cannot load game runtime. See NGR runtime log.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }
    LOGI("[stage 4/8] main runtime dlopen succeeded: handle=%p", game_handle);
    dlerror();
    game_on_create_fn on_create = (game_on_create_fn)dlsym(game_handle, "ANativeActivity_onCreate");
    err = dlerror();
    if (!on_create || err) {
        LOGE("game runtime has no ANativeActivity_onCreate: %s", err ? err : "symbol missing");
        toast(activity, "Invalid game runtime library");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }
    LOGI("[stage 5/8] resolved ANativeActivity_onCreate at %p", (void *)on_create);
    (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
    if (g_game_handle_count >= sizeof(g_game_handles) / sizeof(g_game_handles[0])) {
        LOGE("runtime handle table is full; refusing to dispatch game");
        toast(activity, "Too many native runtime libraries were loaded");
        ANativeActivity_finish(activity);
        return;
    }
    g_game_handles[g_game_handle_count] = game_handle;
    snprintf(g_game_loaded_names[g_game_handle_count], sizeof(g_game_loaded_names[0]), "%s", "libdmhost.so");
    g_game_handle_count++;
    LOGI("[stage 6/8] dispatching NativeActivity_onCreate to libdmhost.so");
    on_create(activity, saved_state, saved_state_size);
    LOGI("[stage 7/8] game NativeActivity_onCreate returned; game runtime initialization continues asynchronously");
    LOGI("[stage 8/8] dispatcher handoff complete; subsequent native output is captured from stdout/stderr and Logcat");

}
