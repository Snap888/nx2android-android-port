#define _GNU_SOURCE
#include <android/log.h>
#include <android/native_activity.h>
#include <dlfcn.h>
#include <jni.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define TAG "NGRRuntime"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

typedef void (*game_on_create_fn)(ANativeActivity *, void *, size_t);
static void *g_game_handles[32];
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
    int in = open(src, O_RDONLY | O_CLOEXEC);
    if (in < 0) return -1;
    int out = open(dst, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0700);
    if (out < 0) { close(in); return -1; }
    char buf[128 * 1024]; ssize_t n; int ok = 0;
    while ((n = read(in, buf, sizeof(buf))) > 0) {
        ssize_t off = 0;
        while (off < n) { ssize_t w = write(out, buf + off, (size_t)(n - off)); if (w <= 0) { ok = -1; break; } off += w; }
        if (ok) break;
    }
    if (n < 0) ok = -1;
    if (fsync(out)) ok = -1;
    close(in); close(out);
    if (!ok && chmod(dst, 0700)) ok = -1;
    return ok;
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
    DIR *dir = opendir(private_game_dir);
    if (!dir) return -1;
    struct dirent *ent; int loaded = 0;
    while ((ent = readdir(dir))) {
        size_t n = strlen(ent->d_name);
        if (n < 4 || strcmp(ent->d_name + n - 3, ".so") || !strcmp(ent->d_name, "libdmhost.so")) continue;
        if (g_game_handle_count >= sizeof(g_game_handles) / sizeof(g_game_handles[0])) break;
        char path[1400]; snprintf(path, sizeof(path), "%s/%s", private_game_dir, ent->d_name);
        dlerror(); void *h = dlopen(path, RTLD_NOW | RTLD_GLOBAL); const char *err = dlerror();
        if (h) { g_game_handles[g_game_handle_count++] = h; loaded++; LOGI("preloaded game dependency %s", ent->d_name); }
        else LOGE("optional game dependency %s failed to load: %s", ent->d_name, err ? err : "unknown");
    }
    closedir(dir);
    return loaded;
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
    snprintf(game_dir, sizeof(game_dir), "%s/games/%s", external, id);
    snprintf(private_dir, sizeof(private_dir), "%s/games/%s", internal, id);
    snprintf(external_lib, sizeof(external_lib), "%s/libdmhost.so", game_dir);
    snprintf(lib_path, sizeof(lib_path), "%s/libdmhost.so", private_dir);
    if (access(external_lib, R_OK) != 0) {
        LOGE("game runtime library missing: %s", external_lib);
        toast(activity, "Game runtime is not installed. Open the game card and choose Install runtime.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }
    if (stage_native_libs(game_dir, private_dir)) {
        toast(activity, "Cannot copy game runtime to private storage. Check free space.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }

    setenv("DM_GAME_DIR", game_dir, 1);
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
    g_game_handles[g_game_handle_count++] = game_handle;
    LOGI("dispatching NativeActivity to game runtime");
    on_create(activity, saved_state, saved_state_size);
}
