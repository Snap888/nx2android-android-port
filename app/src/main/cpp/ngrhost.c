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
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "ngr_profile.h"

#define TAG "NGRRuntime"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

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
            dlerror();
            void *h = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
            const char *err = dlerror();
            if (h) {
                g_game_handles[g_game_handle_count] = h;
                snprintf(g_game_loaded_names[g_game_handle_count], sizeof(g_game_loaded_names[0]), "%s", ent->d_name);
                g_game_handle_count++;
                loaded_this_pass++;
                total_loaded++;
                LOGI("preloaded game dependency %s", ent->d_name);
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
    LOGI("starting game %s; data=%s; native runtime=%s", id, game_dir, lib_path);
    preload_game_dependencies(private_dir);

    dlerror();
    void *game_handle = dlopen(lib_path, RTLD_NOW | RTLD_LOCAL);
    const char *err = dlerror();
    if (!game_handle) {
        LOGE("dlopen failed for %s: %s", lib_path, err ? err : "unknown linker error");
        toast(activity, "Cannot load game runtime. See NGR runtime log.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }
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
    LOGI("dispatching NativeActivity to game runtime");
    on_create(activity, saved_state, saved_state_size);
}
