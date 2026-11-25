package unknown.none.nx2android;

import android.app.NativeActivity;
import android.os.Bundle;
import android.os.Process;
import android.util.Log;
import android.os.Build;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

/** App-owned NativeActivity with persistent breadcrumbs around native library loading. */
public final class NgrGameActivity extends NativeActivity {
    private static final String TAG = "NGRRuntime";

    @Override
    protected void onCreate(Bundle state) {
        NgrApplication.writeLifecycle("NgrGameActivity.onCreate ENTER extras=" +
                (getIntent() == null || getIntent().getExtras() == null
                        ? "none" : getIntent().getExtras().keySet())
                + " pid=" + Process.myPid());
        Log.i(TAG, "NgrGameActivity.onCreate entered; process=" + Process.myPid());
        try {
            super.onCreate(state);
            applyImmersiveMode();
            NgrApplication.writeLifecycle("NgrGameActivity.onCreate EXIT super completed");
            Log.i(TAG, "NgrGameActivity.onCreate completed; native host initialized");
        } catch (Throwable error) {
            NgrApplication.writeLifecycle("NgrGameActivity.onCreate FAILED " + error);
            Log.e(TAG, "NativeActivity super.onCreate failed", error);
            throw error;
        }
    }

    @Override protected void onStart() {
        NgrApplication.writeLifecycle("NgrGameActivity.onStart");
        super.onStart();
    }

    @Override protected void onResume() {
        NgrApplication.writeLifecycle("NgrGameActivity.onResume");
        super.onResume();
    }

    /** Keep the NativeActivity Surface full-panel in Handheld and Docked modes. */
    private void applyImmersiveMode() {
        try {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
            if (Build.VERSION.SDK_INT >= 30) {
                getWindow().setDecorFitsSystemWindows(false);
                WindowInsetsController controller = getWindow().getInsetsController();
                if (controller != null) {
                    controller.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
                    controller.setSystemBarsBehavior(
                            WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
                }
            } else {
                getWindow().getDecorView().setSystemUiVisibility(
                        View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
            }
        } catch (Throwable error) {
            Log.w(TAG, "Could not apply immersive fullscreen mode", error);
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) applyImmersiveMode();
    }

    /** Called from the native overlay input thread; finish must run on Android's UI thread. */
    public void finishFromNative() {
        runOnUiThread(() -> {
            NgrApplication.writeLifecycle("NgrGameActivity.finishFromNative requested");
            if (!isFinishing()) finish();
        });
    }

    @Override protected void onDestroy() {
        NgrApplication.writeLifecycle("NgrGameActivity.onDestroy");
        super.onDestroy();
    }
}
