package unknown.none.nx2android;

import android.Manifest;
import android.app.Activity;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import java.io.File;

public class MainActivity extends Activity {
    private WebView web;
    private TextView logView;
    private ScrollView scroll;
    private final Handler h = new Handler(Looper.getMainLooper());
    private String loadedToken = "";

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF0D0D10);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(32, 72, 32, 32);
        TextView title = new TextView(this);
        title.setText("nx2android: setting up");
        title.setTextColor(0xFFECECF1);
        title.setTextSize(18);
        col.addView(title);
        scroll = new ScrollView(this);
        logView = new TextView(this);
        logView.setTextColor(0xFFBBBBCC);
        logView.setTextSize(11);
        logView.setTypeface(Typeface.MONOSPACE);
        scroll.addView(logView);
        col.addView(scroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        LinearLayout bar = new LinearLayout(this);
        Button copy = new Button(this);
        copy.setText("Copy log");
        copy.setOnClickListener(v -> {
            ((ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("nx2android log", ProotService.snapshot()));
            Toast.makeText(this, "Log copied", Toast.LENGTH_SHORT).show();
        });
        Button retry = new Button(this);
        retry.setText("Retry");
        retry.setOnClickListener(v -> {
            Intent i = new Intent(this, ProotService.class);
            stopService(i);
            startForegroundService(i);
        });
        bar.addView(copy, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        bar.addView(retry, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        col.addView(bar);
        root.addView(col);

        web = new WebView(this);
        web.setVisibility(View.GONE);
        web.setBackgroundColor(0xFF0D0D10);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        web.setWebViewClient(new WebViewClient());
        web.addJavascriptInterface(new Bridge(), "NX2A");
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        startForegroundService(new Intent(this, ProotService.class));
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.READ_EXTERNAL_STORAGE, Manifest.permission.WRITE_EXTERNAL_STORAGE}, 1);
        } else {
            askBattery();
        }
        h.post(tick);
    }

    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (ProotService.ready) {
                if (!loadedToken.equals(ProotService.token)) {
                    loadedToken = ProotService.token;
                    web.loadUrl("http://127.0.0.1:" + ProotService.PORT + "/?t=" + loadedToken);
                    web.setVisibility(View.VISIBLE);
                }
            } else {
                if (!loadedToken.isEmpty()) { loadedToken = ""; web.setVisibility(View.GONE); }
                logView.setText(ProotService.snapshot());
                scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
            }
            h.postDelayed(this, 800);
        }
    };

    @Override public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        askBattery();
    }

    /** Explains why first, then shows Android's own prompt. Asked again at most once if the user cancels. */
    private void askBattery() {
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        final SharedPreferences sp = getSharedPreferences("nx2a", MODE_PRIVATE);
        if (pm.isIgnoringBatteryOptimizations(getPackageName()) || sp.getInt("battery_declined", 0) >= 2) return;
        new AlertDialog.Builder(this)
                .setTitle("Allow background activity?")
                .setMessage("nx2android needs the battery setting \"Unrestricted\" (no limit) so that setup, downloads and porting keep running in the background while the screen is off or you use other apps. Without it Android can stop them halfway.\n\nTap OK to open Android's prompt for it.")
                .setPositiveButton("OK", (d, w) -> {
                    try {
                        startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + getPackageName())));
                    } catch (Exception e) {
                        startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
                    }
                })
                .setNegativeButton("Cancel", (d, w) -> sp.edit().putInt("battery_declined", sp.getInt("battery_declined", 0) + 1).apply())
                .show();
    }

    @Override public void onBackPressed() {
        if (web.getVisibility() == View.VISIBLE && web.canGoBack()) web.goBack();
        else moveTaskToBack(true);
    }

    private void doInstall(String path) {
        try {
            String p = path.startsWith("/sdcard/") ? Environment.getExternalStorageDirectory().getAbsolutePath() + path.substring(7) : path;
            File f = new File(p);
            if (!f.isFile()) { Toast.makeText(this, "APK not found: " + p, Toast.LENGTH_LONG).show(); return; }
            if (!getPackageManager().canRequestPackageInstalls()) {
                Toast.makeText(this, "Allow installs from nx2android, then tap Install APK again", Toast.LENGTH_LONG).show();
                startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName())));
                return;
            }
            Uri u = FileProvider.getUriForFile(this, getPackageName() + ".files", f);
            Intent i = new Intent(Intent.ACTION_VIEW).setDataAndType(u, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (Exception e) {
            Toast.makeText(this, "Install failed: " + e, Toast.LENGTH_LONG).show();
        }
    }

    private String pickId = "";
    private boolean pickDir = false;

    /** Android's own file picker (it lists SD cards, USB drives and every storage app); the answer is turned into a path the porter can read. */
    private void startPick(String id, boolean dir) {
        pickId = id; pickDir = dir;
        Intent i = new Intent(dir ? Intent.ACTION_OPEN_DOCUMENT_TREE : Intent.ACTION_OPEN_DOCUMENT);
        if (!dir) { i.addCategory(Intent.CATEGORY_OPENABLE); i.setType("*/*"); }
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        if (dir) i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
        try { startActivityForResult(i, 4711); }
        catch (Exception e) { Toast.makeText(this, "No file picker on this phone", Toast.LENGTH_LONG).show(); }
    }

    /** content://.../primary:Games/x or .../1234-ABCD:Games/x -> /sdcard/Games/x or /storage/1234-ABCD/Games/x; "" when the picker's choice has no real path (Downloads, cloud apps). */
    private String pathOf(Uri u) {
        try {
            String id = pickDir ? android.provider.DocumentsContract.getTreeDocumentId(u) : android.provider.DocumentsContract.getDocumentId(u);
            if (id == null) return "";
            if (id.startsWith("raw:")) return id.substring(4);
            int k = id.indexOf(':');
            if (k < 0) return "";
            String vol = id.substring(0, k), rest = id.substring(k + 1);
            String base = vol.equals("primary") ? Environment.getExternalStorageDirectory().getAbsolutePath() : "/storage/" + vol;
            return rest.isEmpty() ? base : base + "/" + rest;
        } catch (Exception e) { return ""; }
    }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != 4711 || res != RESULT_OK || data == null || data.getData() == null) return;
        try {
            int grantFlags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            getContentResolver().takePersistableUriPermission(data.getData(), grantFlags);
        } catch (SecurityException ignored) { }
        String p = pathOf(data.getData());
        if (p.isEmpty()) { Toast.makeText(this, "That location has no file path. Pick it from Internal storage or the SD card.", Toast.LENGTH_LONG).show(); return; }
        web.evaluateJavascript("nx2aPicked(" + org.json.JSONObject.quote(pickId) + "," + org.json.JSONObject.quote(p) + ")", null);
    }

    /** Publish a private diagnostic staging file into the user-visible Download/launcher folder.
     * MediaStore is required on Android 10+; direct filesystem paths are used only on legacy Android. */
    private Uri publishLogToDownloads(File source, String displayName) throws Exception {
        if (source == null || !source.isFile()) throw new java.io.IOException("Log source is missing");
        if (Build.VERSION.SDK_INT >= 29) {
            android.content.ContentResolver resolver = getContentResolver();
            Uri collection = android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI;
            String relativePath = Environment.DIRECTORY_DOWNLOADS + "/launcher/";
            resolver.delete(collection,
                    android.provider.MediaStore.MediaColumns.DISPLAY_NAME + "=? AND "
                            + android.provider.MediaStore.MediaColumns.RELATIVE_PATH + "=?",
                    new String[]{displayName, relativePath});
            android.content.ContentValues values = new android.content.ContentValues();
            values.put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME, displayName);
            values.put(android.provider.MediaStore.MediaColumns.MIME_TYPE, "text/plain");
            values.put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH, relativePath);
            values.put(android.provider.MediaStore.MediaColumns.IS_PENDING, 1);
            Uri item = resolver.insert(collection, values);
            if (item == null) throw new java.io.IOException("MediaStore could not create Download/launcher/" + displayName);
            boolean published = false;
            try {
                try (java.io.InputStream in = new java.io.FileInputStream(source);
                     java.io.OutputStream out = resolver.openOutputStream(item, "w")) {
                    if (out == null) throw new java.io.IOException("Could not open exported log");
                    byte[] buffer = new byte[64 * 1024]; int n;
                    while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
                    out.flush();
                }
                android.content.ContentValues ready = new android.content.ContentValues();
                ready.put(android.provider.MediaStore.MediaColumns.IS_PENDING, 0);
                if (resolver.update(item, ready, null, null) <= 0)
                    throw new java.io.IOException("Could not publish exported log");
                published = true;
                return item;
            } finally {
                if (!published) resolver.delete(item, null, null);
            }
        }
        File folder = new File(Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_DOWNLOADS), "launcher");
        if (!folder.isDirectory() && !folder.mkdirs())
            throw new java.io.IOException("Cannot create " + folder);
        File target = new File(folder, displayName);
        try (java.io.InputStream in = new java.io.FileInputStream(source);
             java.io.OutputStream out = new java.io.FileOutputStream(target, false)) {
            byte[] buffer = new byte[64 * 1024]; int n;
            while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
            out.flush();
        }
        return FileProvider.getUriForFile(this, getPackageName() + ".files", target);
    }

    /** Remove the public copy too, so Clear logs and the next launch clean Download/launcher. */
    private boolean deletePublishedLog(String displayName) {
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                int count = getContentResolver().delete(
                        android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI,
                        android.provider.MediaStore.MediaColumns.DISPLAY_NAME + "=? AND "
                                + android.provider.MediaStore.MediaColumns.RELATIVE_PATH + "=?",
                        new String[]{displayName, Environment.DIRECTORY_DOWNLOADS + "/launcher/"});
                return count >= 0;
            }
            File file = new File(new File(Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_DOWNLOADS), "launcher"), displayName);
            return !file.exists() || file.delete();
        } catch (Exception error) {
            android.util.Log.w("NGRRuntime", "Could not delete public log " + displayName, error);
            return false;
        }
    }

    private void deletePublishedLogsForGame(String gameId) {
        deletePublishedLog("ngr-runtime-" + gameId + ".log");
        deletePublishedLog("ngr-gameplay-" + gameId + ".log");
    }

    private void appendRuntimeLog(String gameId, String message) {
        try {
            File dir = new File(getFilesDir(), "ngr-logs");
            if (!dir.isDirectory() && !dir.mkdirs()) return;
            File log = new File(dir, gameId + ".log");
            String line = System.currentTimeMillis() + " [JAVA] pid=" + android.os.Process.myPid() + " " + message + "\n";
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(log, true)) {
                out.write(line.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            }
        } catch (Exception error) {
            android.util.Log.e("NGRRuntime", "Could not append per-game runtime log for " + gameId, error);
        }
    }

    /** Copy a bounded tail of a per-game diagnostic file into the shareable gameplay export. */
    private void appendGameDiagnosticFile(java.io.FileOutputStream out, File source,
                                          String label, long maxBytes) throws java.io.IOException {
        out.write(("\n\n===== " + label + " =====\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
        if (source == null || !source.isFile()) {
            out.write("[not present]\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));
            return;
        }
        long length = source.length();
        long start = Math.max(0L, length - maxBytes);
        if (start > 0) {
            out.write(("[truncated: showing last " + (length - start) + " of " + length + " bytes]\n")
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
        try (java.io.RandomAccessFile in = new java.io.RandomAccessFile(source, "r")) {
            in.seek(start);
            byte[] buffer = new byte[32 * 1024];
            int n;
            while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
        }
    }

    /** Export the gameplay stream, the host's redirected stderr, game config/manifest and Logcat. */
    private void exportGameplayLog(String gameId) {
        if (gameId == null || !gameId.matches("[0-9a-f]{20}")) {
            Toast.makeText(this, "Invalid game ID", Toast.LENGTH_LONG).show();
            return;
        }
        File dir = new File(getFilesDir(), "ngr-logs");
        if (!dir.isDirectory() && !dir.mkdirs()) {
            Toast.makeText(this, "Cannot access the diagnostic log folder.", Toast.LENGTH_LONG).show();
            return;
        }
        File source = new File(dir, "gameplay-" + gameId + ".log");
        try { if (!source.exists()) source.createNewFile(); }
        catch (Exception error) {
            Toast.makeText(this, "Cannot prepare gameplay log export: " + error.getMessage(), Toast.LENGTH_LONG).show();
            return;
        }
        File exported = new File(dir, "gameplay-" + gameId + "-export.log");
        try {
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(exported, false)) {
                out.write(("NGR gameplay diagnostic log\nGame ID: " + gameId
                        + "\n\n===== Game stdout/stderr + runtime timeline =====\n")
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8));
                try (java.io.FileInputStream in = new java.io.FileInputStream(source)) {
                    byte[] buffer = new byte[64 * 1024]; int n;
                    while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
                }
                // front_android.c redirects the game's native stderr to <game_dir>/log.txt.
                // It is separate from NGR's dispatcher stream; omitting it hid NVN,
                // Vulkan, ROMFS and host-thread initialization from previous exports.
                String savedGamePath = getSharedPreferences("nx2a", MODE_PRIVATE)
                        .getString("game_data_path_" + gameId, "");
                File gameDir;
                if (!savedGamePath.isEmpty()) {
                    gameDir = new File(savedGamePath);
                } else {
                    File externalFiles = getExternalFilesDir(null);
                    gameDir = externalFiles == null ? null : new File(new File(externalFiles, "games"), gameId);
                }
                appendGameDiagnosticFile(out, gameDir == null ? null : new File(gameDir, "log.txt"),
                        "Native host stderr / game log", 4L * 1024 * 1024);
                appendGameDiagnosticFile(out, new File(dir, "fs-" + gameId + ".tsv"),
                        "RomFS ReadFile trace (DM_FSLOG)", 8L * 1024 * 1024);
                appendGameDiagnosticFile(out, gameDir == null ? null : new File(gameDir, "env.txt"),
                        "Per-game environment overrides", 64L * 1024);
                appendGameDiagnosticFile(out, gameDir == null ? null : new File(gameDir, "nx2a-data.json"),
                        "Game data manifest", 128L * 1024);
                appendGameDiagnosticFile(out, gameDir == null ? null : new File(gameDir, "profile.json"),
                        "Compiled game profile metadata", 1024L * 1024);
                out.write("\n\n===== Crash / linker / NativeActivity Logcat =====\n"
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8));
                try {
                    Process p = new ProcessBuilder("logcat", "-d", "-v", "threadtime", "-t", "5000")
                            .redirectErrorStream(true).start();
                    try (java.io.BufferedReader reader = new java.io.BufferedReader(
                            new java.io.InputStreamReader(p.getInputStream(), java.nio.charset.StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = reader.readLine()) != null) {
                            if (line.contains("NGRRuntime") || line.contains("AndroidRuntime")
                                    || line.contains("linker") || line.contains("libc")
                                    || line.contains("DEBUG") || line.contains("crash_dump")
                                    || line.contains(getPackageName()) || line.contains("NativeActivity")
                                    || line.contains("FATAL") || line.contains("SIGSEGV")
                                    || line.contains("backtrace") || line.contains("hook_impl")
                                    || line.contains("libdmhost")) {
                                out.write((line + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
                            }
                        }
                    }
                    int code = p.waitFor();
                    if (code != 0) out.write(("\n[logcat exited with code " + code + "]\n")
                            .getBytes(java.nio.charset.StandardCharsets.UTF_8));
                } catch (Exception error) {
                    out.write(("\n[logcat capture failed: " + error + "]\n")
                            .getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
            }
            Uri uri = publishLogToDownloads(exported, "ngr-gameplay-" + gameId + ".log");
            Intent share = new Intent(Intent.ACTION_SEND).setType("text/plain")
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .putExtra(Intent.EXTRA_SUBJECT, "NGR gameplay log " + gameId)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            Toast.makeText(this, "Saved to Download/launcher/ngr-gameplay-" + gameId + ".log", Toast.LENGTH_LONG).show();
            startActivity(Intent.createChooser(share, "Export gameplay log"));
        } catch (Exception error) {
            Toast.makeText(this, "Could not export gameplay log: " + error.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void clearRuntimeLog(String gameId) {
        if (gameId == null || !gameId.matches("[0-9a-f]{20}")) {
            Toast.makeText(this, "Invalid game ID", Toast.LENGTH_LONG).show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Clear runtime log?")
                .setMessage("Clear this game's runtime log and remove its exported copy? New runtime messages may appear after clearing.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Clear", (dialog, which) -> {
                    File dir = new File(getFilesDir(), "ngr-logs");
                    int cleared = 0;
                    int removed = 0;
                    int failed = 0;
                    File runtime = new File(dir, gameId + ".log");
                    File gameplay = new File(dir, "gameplay-" + gameId + ".log");
                    File fsTrace = new File(dir, "fs-" + gameId + ".tsv");
                    for (File logFile : new File[]{runtime, gameplay, fsTrace}) {
                        if (logFile.exists()) {
                            if (logFile.isFile()) {
                                try (java.io.FileOutputStream out = new java.io.FileOutputStream(logFile, false)) {
                                    out.getFD().sync();
                                    cleared++;
                                } catch (Exception e) { failed++; }
                            } else failed++;
                        }
                    }
                    for (File exported : new File[]{new File(dir, gameId + "-export.log"),
                            new File(dir, "gameplay-" + gameId + "-export.log")}) {
                        if (exported.exists()) {
                            if (exported.isFile() && exported.delete()) removed++;
                            else failed++;
                        }
                    }
                    File pid = new File(dir, gameId + ".pid");
                    if (pid.exists() && pid.isFile() && pid.delete()) removed++;
                    if (!deletePublishedLog("ngr-runtime-" + gameId + ".log")) failed++;
                    if (!deletePublishedLog("ngr-gameplay-" + gameId + ".log")) failed++;
                    String message = "Runtime log cleared";
                    if (cleared == 0 && !runtime.exists()) message += " (no log file existed)";
                    message += "; " + removed + " auxiliary file(s) removed";
                    if (failed > 0) message += "; " + failed + " operation(s) failed";
                    Toast.makeText(this, message, failed > 0 ? Toast.LENGTH_LONG : Toast.LENGTH_SHORT).show();
                })
                .show();
    }

    /** Start every launch with a fresh per-game diagnostic session.
     * Truncate in place (never unlink) so any inherited native stdout/stderr
     * descriptor still targets the same inode. */
    private boolean resetRuntimeLogForLaunch(String gameId) {
        if (gameId == null || !gameId.matches("[0-9a-f]{20}")) return false;
        File dir = new File(getFilesDir(), "ngr-logs");
        if (!dir.isDirectory() && !dir.mkdirs()) {
            android.util.Log.e("NGRRuntime", "Cannot create runtime log directory " + dir);
            return false;
        }
        // Each new game session also removes the previous user-visible exports.
        deletePublishedLogsForGame(gameId);
        File[] files = {
                new File(dir, gameId + ".log"),
                new File(dir, "gameplay-" + gameId + ".log"),
                new File(dir, gameId + "-export.log"),
                new File(dir, gameId + ".pid"),
                new File(dir, "android-lifecycle.log"),
                new File(dir, "fs-" + gameId + ".tsv")
        };
        try {
            for (int i = 0; i < files.length; i++) {
                File file = files[i];
                if (i == 2 || i == 3) {
                    if (file.exists() && !file.delete())
                        android.util.Log.w("NGRRuntime", "Could not remove stale diagnostic file " + file);
                    continue;
                }
                try (java.io.FileOutputStream out = new java.io.FileOutputStream(file, false)) {
                    out.getFD().sync();
                }
            }
            return true;
        } catch (Exception error) {
            android.util.Log.e("NGRRuntime", "Could not reset runtime log for " + gameId, error);
            return false;
        }
    }

    /** Share the per-game native log plus this runtime process's Logcat (linker/Vulkan/driver messages). */
    private void exportRuntimeLog(String gameId) {
        if (gameId == null || !gameId.matches("[0-9a-f]{20}")) {
            Toast.makeText(this, "Invalid game ID", Toast.LENGTH_LONG).show();
            return;
        }
        File dir = new File(getFilesDir(), "ngr-logs");
        if (!dir.isDirectory() && !dir.mkdirs()) {
            Toast.makeText(this, "Cannot access the diagnostic log folder.", Toast.LENGTH_LONG).show();
            return;
        }
        File source = new File(dir, gameId + ".log");
        try { if (!source.exists()) source.createNewFile(); }
        catch (Exception error) {
            Toast.makeText(this, "Cannot prepare runtime log export: " + error.getMessage(), Toast.LENGTH_LONG).show();
            return;
        }
        File exported = new File(dir, gameId + "-export.log");
        try {
            dir.mkdirs();
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(exported, false)) {
                out.write(("NGR runtime diagnostic export\nGame ID: " + gameId + "\n\n===== Native dispatcher + game stdout/stderr =====\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
                try (java.io.FileInputStream in = new java.io.FileInputStream(source)) {
                    byte[] buffer = new byte[64 * 1024]; int n;
                    while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
                }
                File lifecycle = new File(dir, "android-lifecycle.log");
                out.write("\n\n===== Persistent Android process/activity lifecycle =====\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                if (lifecycle.isFile()) {
                    try (java.io.FileInputStream lifecycleIn = new java.io.FileInputStream(lifecycle)) {
                        byte[] lifecycleBuffer = new byte[32 * 1024]; int lifecycleN;
                        while ((lifecycleN = lifecycleIn.read(lifecycleBuffer)) > 0) out.write(lifecycleBuffer, 0, lifecycleN);
                    }
                } else {
                    out.write("[No Application/Activity lifecycle marker was written]\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
                File pidFile = new File(dir, gameId + ".pid");
                String pid = "";
                if (pidFile.isFile()) pid = new String(java.nio.file.Files.readAllBytes(pidFile.toPath()), java.nio.charset.StandardCharsets.UTF_8).trim();
                out.write(("\n\n===== Android Logcat (recent system + NGR process events; game pid="
                        + (pid.isEmpty() ? "not-reached" : pid) + ") =====\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
                try {
                    Process p = new ProcessBuilder("logcat", "-d", "-v", "threadtime", "-t", "5000")
                            .redirectErrorStream(true).start();
                    try (java.io.BufferedReader reader = new java.io.BufferedReader(
                            new java.io.InputStreamReader(p.getInputStream(), java.nio.charset.StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = reader.readLine()) != null) {
                            // Keep every line emitted by the game process, not only crash tags.
                            // Vulkan/Turnip/NVN diagnostics often use their own tags and were
                            // previously filtered out, hiding the first failing graphics call.
                            boolean gameProcessLine = !pid.isEmpty() && line.contains(" " + pid + " ");
                            if (gameProcessLine
                                    || line.contains("NGRRuntime") || line.contains("AndroidRuntime")
                                    || line.contains("ActivityTaskManager") || line.contains("ActivityManager")
                                    || line.contains("linker") || line.contains("libc")
                                    || line.contains("DEBUG") || line.contains("crash_dump")
                                    || line.contains(getPackageName()) || line.contains("NativeActivity")
                                    || line.contains("NgrGameActivity") || line.contains("Permission Denial")
                                    || line.contains("Unable to") || line.contains("FATAL")
                                    || line.contains("START ") || line.contains("Displayed ")
                                    || line.contains("Process ") || line.contains("not found")
                                    || line.contains("Vulkan") || line.contains("vulkan")
                                    || line.contains("Adreno") || line.contains("Turnip")
                                    || line.contains("freedreno") || line.contains("adrenotools")
                                    || line.contains("hook_impl") || line.contains("main_hook")
                                    || line.contains("file_redirect_hook") || line.contains("NVN")
                                    || line.contains("nvn") || line.contains("dmhost")
                                    || line.contains("[dm]") || line.contains("KGSL")
                                    || line.contains("kgsl") || line.contains("gfx_vk")
                                    || line.contains("swapchain") || line.contains("SurfaceFlinger")
                                    || line.contains("BufferQueue") || line.contains("pipeline")) {
                                out.write((line + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
                            }
                        }
                    }
                    int code = p.waitFor();
                    if (code != 0) out.write(("\n[logcat exited with code " + code + "]\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
                } catch (Exception e) {
                    out.write(("\n[logcat capture failed: " + e + "]\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
            }
            Uri uri = publishLogToDownloads(exported, "ngr-runtime-" + gameId + ".log");
            Intent share = new Intent(Intent.ACTION_SEND).setType("text/plain")
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .putExtra(Intent.EXTRA_SUBJECT, "NGR runtime log " + gameId)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            Toast.makeText(this, "Saved to Download/launcher/ngr-runtime-" + gameId + ".log", Toast.LENGTH_LONG).show();
            startActivity(Intent.createChooser(share, "Export NGR runtime log"));
        } catch (Exception e) {
            Toast.makeText(this, "Could not export runtime log: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    /** Resolve a proot path to its host path without copying the game data pack. */
    private String resolveNgrGameDataPath(String path) {
        if (path == null || path.isEmpty()) return null;
        try {
            File game;
            if (path.startsWith("/root/")) {
                File root = new File(new File(getFilesDir(), "ubuntu"), "root").getCanonicalFile();
                game = new File(root, path.substring("/root/".length())).getCanonicalFile();
                String prefix = root.getPath() + File.separator;
                if (!game.getPath().startsWith(prefix)) return null;
            } else if (path.startsWith("/sdcard/") || path.startsWith("/storage/emulated/0/")) {
                if (Build.VERSION.SDK_INT >= 23 &&
                        checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
                    Toast.makeText(this, "Allow storage access, then launch the game again.", Toast.LENGTH_LONG).show();
                    requestPermissions(new String[]{Manifest.permission.READ_EXTERNAL_STORAGE, Manifest.permission.WRITE_EXTERNAL_STORAGE}, 1);
                    return null;
                }
                File root = Environment.getExternalStorageDirectory().getCanonicalFile();
                game = new File(path).getCanonicalFile();
                String prefix = root.getPath() + File.separator;
                if (!game.getPath().startsWith(prefix)) return null;
            } else {
                return null;
            }
            if (!game.isDirectory() || !new File(game, "nx2a-data.json").isFile()
                    || !new File(game, "libdmhost.so").isFile()) return null;
            return game.getAbsolutePath();
        } catch (Exception error) {
            android.util.Log.e("NGRRuntime", "Could not resolve in-place game payload path", error);
            return null;
        }
    }

    private class Bridge {
        @JavascriptInterface public void pick(String id, boolean dir) { runOnUiThread(() -> startPick(id, dir)); }
        @JavascriptInterface public void runProotExperiments() {
            startForegroundService(new Intent(MainActivity.this, ProotService.class).setAction("experiments"));
        }

        @JavascriptInterface public void traceDotnet() {
            startForegroundService(new Intent(MainActivity.this, ProotService.class).setAction("trace"));
        }

        @JavascriptInterface public void installApk(String path) { runOnUiThread(() -> doInstall(path)); }
        @JavascriptInterface public void exportRuntimeLog(String gameId) { runOnUiThread(() -> MainActivity.this.exportRuntimeLog(gameId)); }
        @JavascriptInterface public void exportGameplayLog(String gameId) { runOnUiThread(() -> MainActivity.this.exportGameplayLog(gameId)); }
        @JavascriptInterface public void clearRuntimeLog(String gameId) { runOnUiThread(() -> MainActivity.this.clearRuntimeLog(gameId)); }

        /** Launch a game through NGR's own NativeActivity; no per-game Android package is installed. */
        @JavascriptInterface public void launchGame(String gameId, String dataPath, String logOptionsJson) {
            runOnUiThread(() -> {
                if (gameId == null || !gameId.matches("[0-9a-f]{20}")) {
                    Toast.makeText(MainActivity.this, "Invalid game shortcut ID", Toast.LENGTH_LONG).show();
                    return;
                }
                org.json.JSONObject logOptions;
                try { logOptions = new org.json.JSONObject(logOptionsJson == null ? "{}" : logOptionsJson); }
                catch (org.json.JSONException invalidOptions) { logOptions = new org.json.JSONObject(); }
                final boolean logRuntime = logOptions.optBoolean("runtime", false);
                final boolean logSlowframe = logOptions.optBoolean("slowframe", false);
                final boolean logNvn = logOptions.optBoolean("nvn", false);
                final boolean logWatchdog = logOptions.optBoolean("watchdog", false);
                final boolean logFs = logOptions.optBoolean("fs", false);
                if ((logRuntime || logFs) && !resetRuntimeLogForLaunch(gameId)) {
                    Toast.makeText(MainActivity.this, "Could not start a fresh runtime log. Check app storage.", Toast.LENGTH_LONG).show();
                    return;
                }
                if (logRuntime) appendRuntimeLog(gameId, "NEW LAUNCH SESSION; previous per-game log truncated; appPid="
                        + android.os.Process.myPid() + " package=" + getPackageName()
                        + " sdk=" + Build.VERSION.SDK_INT);
                try {
                    File nativeHost = new File(getApplicationInfo().nativeLibraryDir, "libngrhost.so");
                    if (logRuntime) appendRuntimeLog(gameId, "Native host library: " + nativeHost.getAbsolutePath()
                            + " exists=" + nativeHost.isFile() + " readable=" + nativeHost.canRead());
                    android.content.ComponentName gameComponent = new android.content.ComponentName(MainActivity.this, NgrGameActivity.class);
                    try {
                        android.content.pm.ActivityInfo info = getPackageManager().getActivityInfo(gameComponent, 0);
                        if (logRuntime) appendRuntimeLog(gameId, "Resolved NGR activity: name=" + info.name + " process="
                                + info.processName + " enabled=" + info.enabled + " exported=" + info.exported);
                    } catch (Exception resolveError) {
                        if (logRuntime) appendRuntimeLog(gameId, "NGR activity resolution failed: " + resolveError);
                        throw resolveError;
                    }
                    Intent launch = new Intent().setComponent(gameComponent);
                    launch.putExtra("game_id", gameId);
                    launch.putExtra("ngr_log_runtime", logRuntime);
                    launch.putExtra("ngr_log_slowframe", logSlowframe);
                    launch.putExtra("ngr_log_nvn", logNvn);
                    launch.putExtra("ngr_log_watchdog", logWatchdog);
                    launch.putExtra("ngr_log_fs", logFs);
                    String resolvedDataPath = resolveNgrGameDataPath(dataPath);
                    if (resolvedDataPath == null) {
                        throw new IllegalStateException("Game data path is missing or outside NGR storage: " + dataPath);
                    }
                    launch.putExtra("game_data_path", resolvedDataPath);
                    getSharedPreferences("nx2a", MODE_PRIVATE).edit()
                            .putString("game_data_path_" + gameId, resolvedDataPath).apply();
                    if (logRuntime) appendRuntimeLog(gameId, "Starting explicit component " + launch.getComponent()
                            + " with game_id=" + launch.getStringExtra("game_id")
                            + " game_data_path=" + resolvedDataPath);
                    startActivity(launch);
                    if (logRuntime) appendRuntimeLog(gameId, "NativeActivity startActivity returned successfully");
                    h.postDelayed(() -> {
                        try {
                            ActivityManager am = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
                            boolean found = false;
                            if (am != null && am.getRunningAppProcesses() != null) {
                                for (ActivityManager.RunningAppProcessInfo p : am.getRunningAppProcesses()) {
                                    if (p.processName.startsWith(getPackageName())) {
                                        if (logRuntime) appendRuntimeLog(gameId, "Observed process after launch: name=" + p.processName
                                                + " pid=" + p.pid + " importance=" + p.importance);
                                        found = true;
                                    }
                                }
                            }
                            if (!found && logRuntime) appendRuntimeLog(gameId, "No NGR app process visible 1500ms after startActivity");
                        } catch (Exception e) {
                            if (logRuntime) appendRuntimeLog(gameId, "Process snapshot failed: " + e);
                        }
                    }, 1500);
                } catch (Exception e) {
                    if (logRuntime) appendRuntimeLog(gameId, "NativeActivity startActivity failed: " + e);
                    Toast.makeText(MainActivity.this, "Could not start NGR runtime: " + e.getMessage(), Toast.LENGTH_LONG).show();
                }
            });
        }

        @JavascriptInterface public void quit() {
            runOnUiThread(() -> {
                stopService(new Intent(MainActivity.this, ProotService.class));
                finishAffinity();
                h.postDelayed(() -> android.os.Process.killProcess(android.os.Process.myPid()), 600);
            });
        }
    }
}
