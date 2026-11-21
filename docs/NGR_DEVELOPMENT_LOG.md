# NGR development log

## 2026-11-21 — Adopt existing Android app repository

- Audited `Snap888/nx2android-android-port` rather than creating a second Android application.
- Confirmed the app already has Java MainActivity + WebView, foreground ProotService, Ubuntu/proot setup, authenticated loopback Python web server, asynchronous porter jobs, OTA payload verification/rollback and GitHub Actions APK packaging.
- Created `feature/ngr-universal-library` from `main`.
- Added a cover-first three-column Library screen as the app's first tab. The + button opens the existing Recompiler/Port screen.
- Added persistent per-game catalog API, automatic registration from successful porter result events, cover selection, per-game settings storage, search, remove-shortcut action and recompile/update prefill.
- Added an explicit legacy status and disabled Run action. The existing porter still builds per-game APKs and its native host embeds profile-specific compile-time headers; enabling Run now would falsely imply that the one-APK shared runtime exists.
- Updated OTA payload manifest to version 95 and recalculated hashes for the web UI/backend.
- Updated CI to run for the feature branch and validate Python payload syntax and payload hashes. APK release publication remains restricted to main.
- Added `docs/NGR_UNIVERSAL_LAUNCHER.md` with source-derived architecture, implemented scope, hard runtime gates and next actions.

## Current status

- Branch: `feature/ngr-universal-library`
- Library UI/catalog: first implementation committed.
- Recompiler: existing on-device porter retained and opened from Add Game.
- Per-game settings: persisted in catalog; saved touch and 60 FPS options are carried back into the existing recompiler form. Resolution/graphics/controller runtime application remains pending shared-runtime integration.
- Cover selection: implemented for shared-storage PNG/JPG/WebP.
- Shared runtime/profile loader: not implemented.
- Launch dispatcher: not implemented; Run is intentionally disabled.
- APK/CI: feature-branch workflow triggered. The first manifest check caught stale SHA-256 entries; values were corrected against the exact output of `tools/make_manifest.py`.
- Device validation: not performed in this development session.

## Next steps

1. Verify branch CI payload syntax and manifest hash check.
2. Add automated catalog/backend tests.
3. Complete native profile-consumer audit.
4. Introduce versioned runtime profile serialization and validation.
5. Refactor the host to a shared runtime without generated per-game headers.
6. Implement library launch dispatcher and test two games in one installed APK.

- CI note: Python and WebView JavaScript syntax checks passed; final manifest validation is pending for the corrected payload commit.

- Latest UI adjustment: saving Touch / 60 FPS now maps those options back to the existing porter when Recompile / update is selected; other visual/runtime presets remain catalog-only until native integration.

- CI follow-up: Python and JavaScript syntax checks are green. The previous manifest failure was for the preceding commit; the branch now contains the exact `make_manifest.py` hash (`284875cc…`) for the latest UI file and is being revalidated.

## 2026-11-21 — Library launch and game-data deployment fix

### Confirmed defects
- The game details dialog explicitly disabled Run while shared-runtime migration was pending, even though the legacy per-game APK is already built and registered in the catalog.
- The APK and its data pack are separate outputs. Unless the data pack is installed/copied into `/sdcard/Android/data/<package>/files/`, the NativeActivity cannot find its `RomFS`, modules, shaders and environment files.
- The existing `porter install` path already knows how to install the APK and copy the data pack over adb; the Library did not expose that workflow.
- The generated per-game APK manifest already declares `MANAGE_EXTERNAL_STORAGE` and the Android 10 legacy read permission. Native code checks access when `DM_ROMFS` points outside the app-owned files folder. The normal app-owned data-pack path does not require broad storage access; it requires the data pack to be copied to the package's own files directory.

### Changes
- Added a real Library **Launch game** action through the Android bridge. It starts the installed package's launcher activity and reports clearly when the APK is not installed.
- Added Android package visibility for launcher activities so Android 11+ can discover the installed game package.
- Added **Install APK + data (ADB)** in each game's details dialog. It calls the existing validated `/api/install` flow with that game's recorded APK and data-pack paths. This installs the APK if needed and copies the data pack into the app-owned directory.
- Updated `docs/COPY_DATA.md` to document the one-tap Library workflow and retained manual-copy instructions for users without adb.
- Updated the OTA payload manifest for the changed WebView file.

### Validation still required
- CI must compile Java, validate Python/WebView syntax and OTA hashes, then produce a new APK.
- Device test: install APK + data through Library, launch game, verify `/Android/data/<package>/files/nx2a-data.json`, `RomFS`, `mods`, and `shaders.dmsv` are present and readable.
- Device test: launch an already-installed game directly from Library.
- If the game uses an external `DM_ROMFS` folder instead of the app-owned data pack, verify the game's own **All files access** toggle is enabled. This is distinct from nx2android's storage permission.

## 2026-11-22 — Single NGR APK runtime dispatcher

### User-reported failure
- Library launch showed `Invalid game package name`. The Java bridge had a malformed escaped-dot regular expression and still attempted to launch a separately installed game package.
- The previous workflow required ADB to install the per-game APK and copy its data into that package's `Android/data` directory. This did not meet the requested one-app launcher design.

### Implemented
- Added an NDK/CMake-built `libngrhost.so` to the NGR application. The app's own `android.app.NativeActivity` receives the stable library game ID and dispatches into the selected game's native host library.
- The Java bridge now validates the 20-character catalog ID and starts NGR's own NativeActivity. It no longer validates package names or calls `getLaunchIntentForPackage`.
- On successful port, the backend extracts all arm64 native libraries from the temporary build APK into the game's data pack, extracts per-game APK assets (including the gamepad overlay theme), and deletes the per-game APK. It is not installed and is not retained as a library launch target.
- Added an upstream porter patch so `front_android.c` uses `DM_GAME_DIR` as the selected game's data root. Game RomFS, save inputs, shaders, env and cache paths are now isolated per game.
- The NGR native dispatcher copies game `.so` files from app-specific external storage into NGR's private internal files directory before `dlopen`; this avoids attempting executable mappings from shared storage.
- Added a no-ADB runtime installer. Proot runs under the NGR app UID and copies the data pack into NGR's own `Android/data/unknown.none.nx2android/files/games/<id>` directory. Copy uses a staging folder and rename, verifies the runtime/data manifest, and retains the previous payload if promotion fails.
- Updated the overlay theme loader to read per-game theme assets from `DM_GAME_DIR/assets` instead of depending on the old per-game APK's AssetManager.
- The library now distinguishes a built runtime payload from a runtime installed into NGR. Successful install updates the catalog's `runtime_installed` flag.
- Bumped app versionCode to 2/versionName 0.2.0 and pinned NDK r27c. GitHub Actions built the shared dispatcher APK successfully in run 44952528283.

### Architecture status / explicit limitation
- The installed Android application is now a single NGR APK; game-specific APKs are temporary packaging containers only and are deleted after native library/assets extraction.
- The native game host itself is still compiled with game-specific profile headers. This first dispatcher stage removes per-game APK installation, but it is not yet the final profile-agnostic single `libdmhost.so`.
- Next native stage: serialize every `game_profile.h` / `android_profile.h` field into validated JSON, migrate consumers incrementally, then compile one common host with no game-specific profile header.

### Device acceptance tests still required
- Recompile a game; verify no game APK remains in output and the library shows `RUNTIME BUILT`.
- Tap Install runtime + data with wireless debugging disabled; verify the game payload is copied into NGR's app-specific files directory and catalog changes to `NGR READY`.
- Launch from Library; verify dispatcher log, successful private-library staging, game-specific `DM_GAME_DIR`, RomFS and theme loading.
- Repeat for a second game and verify no save/cache/RomFS cross-contamination.
- Confirm Vulkan, input, gamepad theme, pause/resume, storage use and clean process exit on the target phone.

### Runtime process and save isolation follow-up
- Registered NGR's NativeActivity in the dedicated Android process `:game`. Upstream's NativeActivity teardown uses `_exit(0)`; without process isolation this would kill the launcher and ProotService as well as the game. The separate process keeps the Library alive and lets the game process exit cleanly.
- Added `NGR_PRIVATE_GAME_DIR` and patched `front_android.c` so each title gets its own private `save/` and `temp/` directories alongside staged native libraries. Game files, shaders and overlay assets remain under that game's external files directory.
