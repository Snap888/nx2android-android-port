#define _GNU_SOURCE
#include <android/log.h>
#include <android/native_activity.h>
#include <dlfcn.h>
#include <jni.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define TAG "NGRRuntime"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

typedef void (*game_on_create_fn)(ANativeActivity *, void *, size_t);
static void *g_game_handle;

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

__attribute__((visibility("default")))
void ANativeActivity_onCreate(ANativeActivity *activity, void *saved_state, size_t saved_state_size) {
    (void)saved_state; (void)saved_state_size;
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

    const char *base = activity->externalDataPath ? activity->externalDataPath : activity->internalDataPath;
    char game_dir[1024], lib_path[1200];
    snprintf(game_dir, sizeof(game_dir), "%s/games/%s", base, id);
    snprintf(lib_path, sizeof(lib_path), "%s/libdmhost.so", game_dir);
    if (access(lib_path, R_OK) != 0) {
        LOGE("game runtime library missing: %s", lib_path);
        toast(activity, "Game runtime is not installed. Open its card and choose Install runtime.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }

    // The upstream Android frontend reads DM_GAME_DIR to select the per-game data root.
    setenv("DM_GAME_DIR", game_dir, 1);
    setenv("NGR_GAME_ID", id, 1);
    LOGI("loading game %s from %s", id, game_dir);

    dlerror();
    g_game_handle = dlopen(lib_path, RTLD_NOW | RTLD_LOCAL);
    const char *err = dlerror();
    if (!g_game_handle) {
        LOGE("dlopen failed for %s: %s", lib_path, err ? err : "unknown linker error");
        toast(activity, "Cannot load game runtime. Check NGR runtime log.");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }
    dlerror();
    game_on_create_fn on_create = (game_on_create_fn)dlsym(g_game_handle, "ANativeActivity_onCreate");
    err = dlerror();
    if (!on_create || err) {
        LOGE("game runtime has no ANativeActivity_onCreate: %s", err ? err : "symbol missing");
        toast(activity, "Invalid game runtime library");
        (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
        ANativeActivity_finish(activity);
        return;
    }

    (*activity->env)->ReleaseStringUTFChars(activity->env, jid, id);
    LOGI("dispatching NativeActivity to game runtime");
    on_create(activity, saved_state, saved_state_size);
}
