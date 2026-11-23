#define _GNU_SOURCE
#include <android/log.h>
#include <android/native_activity.h>
#include <android/native_window.h>
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

#ifndef DT_ANDROID_RELR
#define DT_ANDROID_RELR   0x6fffe000
#define DT_ANDROID_RELRSZ  0x6fffe001
#define DT_ANDROID_RELRENT 0x6fffe003
#endif

#define TAG "NGRRuntime"
static char g_runtime_log_path[1400];
static char g_runtime_log_dir[1200];
static char g_gameplay_log_path[1400];

static void append_log_line(const char *path, const char *line, size_t len);

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
    append_log_line(g_runtime_log_path, line, (size_t)len);
    if (g_gameplay_log_path[0]) append_log_line(g_gameplay_log_path, line, (size_t)len);
}
static void append_log_line(const char *path, const char *line, size_t len) {
    if (!path || !path[0] || !line || !len) return;
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) return;
    size_t off = 0;
    while (off < len) {
        ssize_t n = write(fd, line + off, len - off);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) break;
        off += (size_t)n;
    }
    close(fd);
}
#define LOGE(...) runtime_log_emit(ANDROID_LOG_ERROR, __VA_ARGS__)
#define LOGI(...) runtime_log_emit(ANDROID_LOG_INFO, __VA_ARGS__)

typedef void (*game_on_create_fn)(ANativeActivity *, void *, size_t);
static ANativeActivityCallbacks g_game_callbacks;

static void ngr_window_created(ANativeActivity *activity, ANativeWindow *window) {
    LOGI("[window] created window=%p size=%dx%d", (void *)window, window ? ANativeWindow_getWidth(window) : 0, window ? ANativeWindow_getHeight(window) : 0);
    if (g_game_callbacks.onNativeWindowCreated) g_game_callbacks.onNativeWindowCreated(activity, window);
    LOGI("[window] created callback returned");
}
static void ngr_window_resized(ANativeActivity *activity, ANativeWindow *window) {
    LOGI("[window] resized window=%p size=%dx%d", (void *)window, window ? ANativeWindow_getWidth(window) : 0, window ? ANativeWindow_getHeight(window) : 0);
    if (g_game_callbacks.onNativeWindowResized) g_game_callbacks.onNativeWindowResized(activity, window);
    LOGI("[window] resized callback returned");
}
static void ngr_window_redraw(ANativeActivity *activity, ANativeWindow *window) {
    LOGI("[window] redraw requested window=%p", (void *)window);
    if (g_game_callbacks.onNativeWindowRedrawNeeded) g_game_callbacks.onNativeWindowRedrawNeeded(activity, window);
    LOGI("[window] redraw callback returned");
}
static void ngr_window_destroyed(ANativeActivity *activity, ANativeWindow *window) {
    LOGI("[window] destroyed window=%p", (void *)window);
    if (g_game_callbacks.onNativeWindowDestroyed) g_game_callbacks.onNativeWindowDestroyed(activity, window);
    LOGI("[window] destroyed callback returned");
}
static void ngr_window_focus(ANativeActivity *activity, int focused) {
    LOGI("[window] focus changed focused=%d", focused);
    if (g_game_callbacks.onWindowFocusChanged) g_game_callbacks.onWindowFocusChanged(activity, focused);
    LOGI("[window] focus callback returned");
}

/* Trace the complete NativeActivity lifecycle as well as the Surface callbacks.
 * A focus-loss/window-destroy pair alone cannot distinguish a user exit from an
 * Activity being stopped by Android while the game is still initializing. */
static void ngr_activity_start(ANativeActivity *a) {
    LOGI("[activity] onStart begin");
    if (g_game_callbacks.onStart) g_game_callbacks.onStart(a);
    LOGI("[activity] onStart returned");
}
static void ngr_activity_resume(ANativeActivity *a) {
    LOGI("[activity] onResume begin");
    if (g_game_callbacks.onResume) g_game_callbacks.onResume(a);
    LOGI("[activity] onResume returned");
}
static void ngr_activity_pause(ANativeActivity *a) {
    LOGI("[activity] onPause begin");
    if (g_game_callbacks.onPause) g_game_callbacks.onPause(a);
    LOGI("[activity] onPause returned");
}
static void ngr_activity_stop(ANativeActivity *a) {
    LOGI("[activity] onStop begin");
    if (g_game_callbacks.onStop) g_game_callbacks.onStop(a);
    LOGI("[activity] onStop returned");
}
static void ngr_activity_destroy(ANativeActivity *a) {
    LOGI("[activity] onDestroy begin");
    if (g_game_callbacks.onDestroy) g_game_callbacks.onDestroy(a);
    LOGI("[activity] onDestroy returned");
}
static void *ngr_activity_save_state(ANativeActivity *a, size_t *size) {
    LOGI("[activity] onSaveInstanceState begin");
    void *state = g_game_callbacks.onSaveInstanceState
        ? g_game_callbacks.onSaveInstanceState(a, size) : NULL;
    LOGI("[activity] onSaveInstanceState returned size=%zu state=%s",
         size ? *size : 0, state ? "present" : "none");
    return state;
}
static void ngr_activity_content_rect(ANativeActivity *a, const ARect *rect) {
    LOGI("[activity] onContentRectChanged begin rect=%d,%d-%d,%d",
         rect ? rect->left : 0, rect ? rect->top : 0,
         rect ? rect->right : 0, rect ? rect->bottom : 0);
    if (g_game_callbacks.onContentRectChanged) g_game_callbacks.onContentRectChanged(a, rect);
    LOGI("[activity] onContentRectChanged returned");
}
static void ngr_install_window_tracing(ANativeActivity *activity) {
    if (!activity || !activity->callbacks) { LOGE("[activity] cannot install callback tracing: callbacks missing"); return; }
    g_game_callbacks = *activity->callbacks;
    activity->callbacks->onStart = ngr_activity_start;
    activity->callbacks->onResume = ngr_activity_resume;
    activity->callbacks->onPause = ngr_activity_pause;
    activity->callbacks->onStop = ngr_activity_stop;
    activity->callbacks->onDestroy = ngr_activity_destroy;
    activity->callbacks->onSaveInstanceState = ngr_activity_save_state;
    activity->callbacks->onContentRectChanged = ngr_activity_content_rect;
    activity->callbacks->onNativeWindowCreated = ngr_window_created;
    activity->callbacks->onNativeWindowResized = ngr_window_resized;
    activity->callbacks->onNativeWindowRedrawNeeded = ngr_window_redraw;
    activity->callbacks->onNativeWindowDestroyed = ngr_window_destroyed;
    activity->callbacks->onWindowFocusChanged = ngr_window_focus;
    LOGI("[activity] lifecycle and Surface tracing installed");
}
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
    int c = snprintf(g_gameplay_log_path, sizeof(g_gameplay_log_path), "%s/gameplay-%s.log", g_runtime_log_dir, game_id);
    if (a < 0 || (size_t)a >= sizeof(g_runtime_log_dir) || b < 0 || (size_t)b >= sizeof(g_runtime_log_path) ||
        c < 0 || (size_t)c >= sizeof(g_gameplay_log_path)) {
        g_runtime_log_path[0] = 0; g_gameplay_log_path[0] = 0; return -1;
    }
    if (mkdirs(g_runtime_log_dir)) { g_runtime_log_path[0] = 0; g_gameplay_log_path[0] = 0; return -1; }
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
    int fd = open(g_runtime_log_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) { g_runtime_log_path[0] = 0; return -1; }
    close(fd);
    fd = open(g_gameplay_log_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) { g_gameplay_log_path[0] = 0; return -1; }
    close(fd);
    /* Keep raw game stdout/stderr in a separate file; structured NGR events
       are mirrored there with timestamps for a single chronological trace. */
    fd = open(g_gameplay_log_path, O_WRONLY | O_APPEND | O_CLOEXEC | O_NOFOLLOW);
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

static int elf_relr_has_slot(int fd, const Elf64_Phdr *phdrs, size_t phnum,
                              uint64_t relr_addr, uint64_t relr_size,
                              uint64_t relr_ent, uint64_t slot_vaddr) {
    if (!relr_addr || !relr_size || relr_ent != sizeof(Elf64_Addr) ||
        relr_size % sizeof(Elf64_Addr) || relr_size > 64u * 1024u * 1024u)
        return 0;
    uint64_t off = elf_vaddr_to_offset(phdrs, phnum, relr_addr, relr_size);
    if (off == UINT64_MAX) return 0;
    uint64_t base = 0;
    for (uint64_t pos = 0; pos < relr_size; pos += sizeof(Elf64_Addr)) {
        Elf64_Addr entry = 0;
        if (pread(fd, &entry, sizeof(entry), (off_t)(off + pos)) != (ssize_t)sizeof(entry))
            return 0;
        if ((entry & 1u) == 0) {
            if (entry == slot_vaddr) return 1;
            if (entry > UINT64_MAX - sizeof(Elf64_Addr)) return 0;
            base = entry + sizeof(Elf64_Addr);
        } else {
            uint64_t bitmap = entry >> 1;
            if (slot_vaddr >= base && slot_vaddr - base < 63u * sizeof(Elf64_Addr) &&
                ((slot_vaddr - base) % sizeof(Elf64_Addr)) == 0) {
                unsigned bit = (unsigned)((slot_vaddr - base) / sizeof(Elf64_Addr));
                if (bitmap & (UINT64_C(1) << bit)) return 1;
            }
            if (base > UINT64_MAX - 63u * sizeof(Elf64_Addr)) return 0;
            base += 63u * sizeof(Elf64_Addr);
        }
    }
    return 0;
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
            else if (dyn.d_tag == DT_RELRENT || dyn.d_tag == DT_ANDROID_RELRENT) relr_ent = dyn.d_un.d_val;
            else if (dyn.d_tag == DT_ANDROID_RELR) relr_addr = dyn.d_un.d_ptr;
            else if (dyn.d_tag == DT_ANDROID_RELRSZ) relr_size = dyn.d_un.d_val;
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
                if (!found && elf_relr_has_slot(fd, phdrs, eh.e_phnum,
                                                relr_addr, relr_size, relr_ent, slot_vaddr))
                    found = 1;
                if (value && !found) missing_constructor_reloc = 1;
                LOGI("[ELF preflight] init_array[%llu] slot=0x%llx raw=0x%llx relocation=%s",
                     (unsigned long long)i, (unsigned long long)slot_vaddr,
                     (unsigned long long)value, found ? "present" : "MISSING");
            }
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

/* Only the exact libdmhost.so is the selected NativeActivity host.
 * Old diagnostic/repaired copies must never be dlopened as companion libraries:
 * their constructors may be incompatible with the current runtime ABI. */
static int is_main_runtime_alias(const char *name) {
    /* The canonical host is libdmhost.so. Do not classify it as an alias:
       the dot-prefix test below also matches the canonical ".so" suffix. */
    if (!name || !strcmp(name, "libdmhost.so")) return 0;
    return !strncmp(name, "libdmhost.", 10) ||
           !strncmp(name, "libdmhost-", 10) ||
           !strncmp(name, "libdmhost_", 10);
}

/* AdrenoTools-owned DSOs must not be preloaded into the app namespace.
 * In particular, preloading libvulkan_freedreno.so here creates a default-
 * namespace driver instance before AdrenoTools can open Turnip in its private
 * namespace. AdrenoTools explicitly cannot apply its hooks once a Vulkan
 * driver instance is already loaded. Its hook DSOs are also private: loading
 * another copy here can leave hook_params uninitialized and crash in
 * hook_impl (observed at offset 0x1aabc while reading the game's env.txt).
 * Keep libadrenotools.so itself available; libdmhost uses it to create and
 * initialize the isolated driver namespace.
 */
static int is_adrenotools_namespace_library(const char *name) {
    return name &&
        (!strcmp(name, "libvulkan_freedreno.so") ||
         !strcmp(name, "libhook_impl.so") ||
         !strcmp(name, "libmain_hook.so") ||
         !strcmp(name, "libfile_redirect_hook.so") ||
         !strcmp(name, "libgsl_alloc_hook.so"));
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

    /* The installed payload may have been recompiled with a different runtime.
       Remove only previously staged top-level .so files; keep per-game save/temp
       directories intact. Otherwise a library removed from the new build could
       still be dlopened from the private staging directory. */
    DIR *stale = opendir(private_game_dir);
    if (!stale) { LOGE("cannot inspect private runtime directory %s: %s", private_game_dir, strerror(errno)); return -1; }
    struct dirent *old_ent; int removed = 0;
    while ((old_ent = readdir(stale))) {
        size_t old_n = strlen(old_ent->d_name);
        if (old_n < 4 || strcmp(old_ent->d_name + old_n - 3, ".so")) continue;
        char old_path[1400];
        int old_len = snprintf(old_path, sizeof(old_path), "%s/%s", private_game_dir, old_ent->d_name);
        if (old_len < 0 || (size_t)old_len >= sizeof(old_path)) continue;
        struct stat old_st;
        if (lstat(old_path, &old_st) == 0 && (S_ISREG(old_st.st_mode) || S_ISLNK(old_st.st_mode))) {
            if (unlink(old_path) == 0) removed++;
            else { LOGE("cannot remove stale staged library %s: %s", old_path, strerror(errno)); closedir(stale); return -1; }
        }
    }
    closedir(stale);
    if (removed) LOGI("removed %d stale staged native libraries before refreshing runtime", removed);

    DIR *dir = opendir(external_game_dir);
    if (!dir) { LOGE("cannot open game data directory %s: %s", external_game_dir, strerror(errno)); return -1; }
    struct dirent *ent; int copied = 0;
    while ((ent = readdir(dir))) {
        size_t n = strlen(ent->d_name);
        if (n < 4 || strcmp(ent->d_name + n - 3, ".so")) continue;
        char src[1400], dst[1400];
        if (is_main_runtime_alias(ent->d_name)) {
            int alias_len = snprintf(dst, sizeof(dst), "%s/%s", private_game_dir, ent->d_name);
            if (alias_len > 0 && (size_t)alias_len < sizeof(dst) && unlink(dst) == 0)
                LOGI("removed stale private runtime alias %s", ent->d_name);
            LOGI("skipping non-canonical main runtime copy %s; only libdmhost.so may be dispatched", ent->d_name);
            continue;
        }
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
                is_main_runtime_alias(ent->d_name) ||
                game_library_loaded(ent->d_name)) continue;
            if (is_adrenotools_namespace_library(ent->d_name)) {
                LOGI("[stage 3/8] leaving %s for AdrenoTools isolated linker namespace; do not preload into app namespace",
                     ent->d_name);
                continue;
            }
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
            /* Remaining libraries are ordinary game companions. AdrenoTools
             * hook DSOs were deliberately excluded above and are loaded/initialized
             * only by adrenotools_open_libvulkan in its dedicated linker namespace. */
            int load_flags = RTLD_NOW | RTLD_GLOBAL;
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

static void log_game_graphics_config(const char *game_dir) {
    char path[1200];
    int n = snprintf(path, sizeof(path), "%s/env.txt", game_dir ? game_dir : "");
    if (n < 0 || (size_t)n >= sizeof(path)) {
        LOGE("[config] env.txt path is too long");
        return;
    }
    FILE *f = fopen(path, "r");
    if (!f) {
        LOGI("[config] no env.txt at %s (%s)", path, strerror(errno));
        return;
    }
    char line[1024];
    unsigned logged = 0;
    while (fgets(line, sizeof(line), f)) {
        size_t len = strlen(line);
        while (len && (line[len - 1] == '\\n' || line[len - 1] == '\\r')) line[--len] = 0;
        if (!len || line[0] == '#') continue;
        if (!strncmp(line, "DM_VK_", 6) || !strncmp(line, "DM_NVN_", 7) ||
            !strncmp(line, "DM_GPU_", 7) || !strncmp(line, "DM_SLOWFRAME=", 13) ||
            !strncmp(line, "DM_OPMODE=", 10) || !strncmp(line, "DM_PRESENT_", 11)) {
            LOGI("[config] env.txt: %s", line);
            ++logged;
        }
    }
    fclose(f);
    if (!logged) LOGI("[config] env.txt contains no explicit Vulkan/NVN/GPU overrides");
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
    /* The active game profile is a data-pack env.txt; log only graphics-related switches. */
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
    log_game_graphics_config(game_dir);

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
    LOGI("[stage 6/8] dispatching NativeActivity_onCreate to libdmhost.so; activity=%p env=%p clazz=%p assetManager=%p internal=%s external=%s sdk=%d",
         (void *)activity, (void *)activity->env, (void *)activity->clazz,
         (void *)activity->assetManager,
         activity->internalDataPath ? activity->internalDataPath : "(null)",
         activity->externalDataPath ? activity->externalDataPath : "(null)",
         activity->sdkVersion);
    on_create(activity, saved_state, saved_state_size);
    LOGI("[stage 7/8] game NativeActivity_onCreate returned; game runtime initialization continues asynchronously");
    ngr_install_window_tracing(activity);
    LOGI("[stage 8/8] dispatcher handoff complete; window lifecycle events will be captured from this point");

}
