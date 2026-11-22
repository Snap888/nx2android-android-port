package unknown.none.nx2android;

import android.app.Application;
import android.os.Process;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/** Records process startup independently of Logcat and NativeActivity native loading. */
public final class NgrApplication extends Application {
    private static final String TAG = "NGRRuntime";

    @Override public void onCreate() {
        super.onCreate();
        writeLifecycle("Application.onCreate pid=" + Process.myPid()
                + " process=" + Application.getProcessName()
                + " package=" + getPackageName());
        Log.i(TAG, "Application.onCreate process=" + Application.getProcessName());
    }

    static void writeLifecycle(String message) {
        try {
            File dir = new File("/data/user/0/" + "unknown.none.nx2android", "files/ngr-logs");
            if (!dir.isDirectory() && !dir.mkdirs()) {
                Log.e(TAG, "Cannot create lifecycle log directory " + dir);
                return;
            }
            File file = new File(dir, "android-lifecycle.log");
            String line = System.currentTimeMillis() + " [ANDROID] pid=" + Process.myPid()
                    + " " + message + "\n";
            try (FileOutputStream out = new FileOutputStream(file, true)) {
                out.write(line.getBytes(StandardCharsets.UTF_8));
                out.getFD().sync();
            }
        } catch (Throwable error) {
            Log.e(TAG, "Lifecycle file logging failed", error);
        }
    }
}
