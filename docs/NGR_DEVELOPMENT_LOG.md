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


## 2026-11-22 — Runtime dispatcher hardening and installer tests

### Changes
- Hardened `libngrhost.so` native-library staging: source and destination files are opened with no-follow semantics, copies handle interrupted reads/writes, and the dispatcher verifies the extracted main library is a 64-bit little-endian AArch64 ELF before calling the Android linker.
- Added explicit path-length and installed-payload marker checks. Incomplete installs now fail before attempting `dlopen`, with actionable log/toast messages.
- Reworked companion-library loading to retry unresolved libraries in multiple passes. This avoids depending on the order in which native libraries appear in the temporary APK ZIP.
- Increased the tracked native-handle table and added bounds checks so an unexpectedly large native library set cannot corrupt memory.
- Refactored `runtime_install.py` into a testable transactional installer. It validates the game ID and NGR package name, restores an interrupted previous payload, stages the new payload, verifies required files, atomically promotes it, and rolls back on failure.
- Added Python unit tests for initial install, replacement, interrupted-install recovery, invalid game IDs and incomplete payload rejection.
- CI now runs the installer unit tests and compiles the runtime installer during payload validation. Test-only changes do not trigger an unnecessary Android APK rebuild.
- Bumped OTA payload version to 107 for the installer update.

### Validation status
- Python unit tests and Android native compilation are now part of the active GitHub Actions run; the current run must complete before this stage is called build-verified.
- No physical-device result is claimed. The next device test must install runtime + data with ADB/Wireless debugging disabled, then launch from Library and collect the NGRRuntime + dmhost logs if it fails.

### Architecture boundary
- Still one installed NGR APK and no per-game APK installation.
- The native host library is still compiled per game against generated profile headers. The true shared/profile-agnostic host remains the next major milestone; the current dispatcher is not being mislabeled as that completed architecture.


## 2026-11-22 — Versioned runtime profile JSON export (schema v1)

### Source audit
- Re-audited the live porter source at upstream main `581ca540f7b2214d47aee1e9be6156fc36809426`, because it has advanced beyond the earlier pinned profile audit.
- Added the missing profile fields to the migration inventory: FPS ceiling, loopback sockets, sparse small virtual pools, CPU-uncached textures, NVN order-keep, and the per-build FPS-lock / Unreal allocator tables.
- Added the newer Android profile fields: ROMFS compression, Vulkan-driver preference, pacing presets, frame-counter settings and README metadata.

### Implementation
- Added `profile_export.py`. It imports the exact porter `game.py` and `android_profile.py` parsers and exports the parsed source rows plus normalized runtime data to `profile.json` schema v1.
- The JSON includes game identity, modules, build/version map, per-build tables, Android profile settings, resolved pacing/environment, ROMFS/Vulkan choices and the complete tablet/phone overlay layout.
- Exporter verifies `nx2a-data.json.profile_h` against a freshly generated `game_profile.h` hash. It searches the base repository profile and the build's provisional/derived/memory profile folders. A mismatched profile is refused rather than silently attached to the wrong native library.
- Profile export is optional for the current legacy compiled host: failures are reported in the Recompiler log, while the existing native host payload remains usable.
- Library details now show whether the exact profile JSON was captured. This is not yet a claim that the native host consumes JSON.

### Validation
- Added three profile-export tests (exact hash match and serialization, mismatched profile rejection, missing hash rejection).
- Combined with the five transactional installer tests, all 8 Python tests pass in GitHub Actions.
- WebView JavaScript syntax and OTA payload manifest validation pass.
- OTA payload is version 109. The profile exporter and backend/UI changes are delivered by the existing branch OTA mechanism; the shared dispatcher APK does not need rebuilding for payload-only changes.

### Remaining native migration
- The dispatcher still loads a per-game compiled `libdmhost.so`; the JSON file is not parsed by native code yet.
- Next: add a bounded/versioned C JSON parser, define `dm_game_profile`, and convert the host/HLE/NVN consumers in groups while preserving legacy macro builds for A/B verification.


## 2026-11-22 — Native schema-v1 profile validation

### Implementation
- Added a small bounded C JSON tokenizer/validator (`ngr_profile.c/.h`) to the NGR NativeActivity dispatcher; no third-party JSON library is required.
- Before staging/loading the game's native libraries, the dispatcher reads `profile.json` and `nx2a-data.json` with a 4 MiB per-file limit and no-follow file opens.
- The validator checks schema version, 16-digit title ID, compiled `game_profile.h` SHA-256 binding, module count, ordered profile rows, per-build table shapes, Android environment/settings and overlay row limits.
- The validator produces a compact summary for the `NGRRuntime` log. Missing JSON keeps legacy compiled-profile games launchable; an invalid/mismatched JSON document is logged and the compiled host remains the fallback. The JSON is validated but not yet used to configure HLE/NVN behavior.
- Added native C tests for valid profile, header-hash mismatch, unsupported schema and malformed JSON. CI compiles the parser with `-Wall -Wextra -Werror` and runs the test binary.
- Added the parser to the NGR NativeActivity library build.

### Validation
- Android Release APK build succeeded in GitHub Actions run 44994407946 (artifact `nx2android-apk`, 35.8 MB).
- CI run 44994441650 passed: 8 Python tests, native C profile-validator tests, WebView JavaScript syntax and OTA manifest verification.
- OTA payload remains version 109. The app's update config points at this feature branch, so payload-only changes are fetched by the existing updater.

### Remaining work
- The native dispatcher now verifies the JSON artifact but the game host still reads the compiled profile macros.
- Next convert the module list/startup args/environment and memory contract into a session-owned profile structure, then migrate HLE/NVN flags, per-build tables and dynamic overlay layouts. Keep the legacy path available until A/B and multi-game device tests pass.
