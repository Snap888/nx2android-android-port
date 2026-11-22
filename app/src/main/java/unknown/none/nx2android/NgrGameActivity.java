package unknown.none.nx2android;

import android.app.NativeActivity;
import android.os.Bundle;
import android.os.Process;
import android.util.Log;

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

    @Override protected void onDestroy() {
        NgrApplication.writeLifecycle("NgrGameActivity.onDestroy");
        super.onDestroy();
    }
}
