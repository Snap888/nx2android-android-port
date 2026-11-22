package unknown.none.nx2android;

import android.app.NativeActivity;
import android.os.Bundle;
import android.util.Log;

/**
 * App-owned NativeActivity entry point. Keeping the activity class inside the
 * application avoids relying on a framework-class component declaration and
 * gives us lifecycle breadcrumbs before NativeActivity loads libngrhost.so.
 */
public final class NgrGameActivity extends NativeActivity {
    private static final String TAG = "NGRRuntime";

    @Override
    protected void onCreate(Bundle state) {
        Log.i(TAG, "NgrGameActivity.onCreate entered; process=" + android.os.Process.myPid());
        super.onCreate(state);
        Log.i(TAG, "NgrGameActivity.onCreate completed; native host should be initialized");
    }

    @Override
    protected void onStart() {
        Log.i(TAG, "NgrGameActivity.onStart");
        super.onStart();
    }

    @Override
    protected void onResume() {
        Log.i(TAG, "NgrGameActivity.onResume");
        super.onResume();
    }

    @Override
    protected void onDestroy() {
        Log.i(TAG, "NgrGameActivity.onDestroy");
        super.onDestroy();
    }
}
