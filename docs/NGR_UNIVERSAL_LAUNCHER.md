# NGR universal launcher — repository audit and implementation plan

## Decision

Develop NGR inside this repository and keep its existing Android application as the only app shell. Do not add a second Gradle application module.

The repository already provides the phone-side execution environment:
- Java `MainActivity` hosts the WebView and exposes a narrow JavaScript bridge for the Android file picker, APK install and app lifecycle.
- `ProotService` owns the foreground service, wake lock, Ubuntu unpack/setup, proot process and local web server lifecycle.
- `app/src/main/assets/nx2a/launcher.py` selects and verifies the bundled/OTA payload, downloads updates, rolls back a crashing payload and synchronizes the porter.
- `app/src/main/assets/nx2a/payload/webgui/server.py` is the authenticated loopback API and runs `python -m porter` jobs asynchronously.
- `webgui/index.html` is the current Setup / Port / Device / Log UI.
- `porter_sync.py` tracks the upstream porter; the Android app does not vendor the full porter source in its APK.
- `.github/workflows/build.yml` validates the payload manifest and builds/publishes the Android APK when shell-level files change.

This is a better base than a new app module: it already has the real Android-side porter workflow, Linux environment, file access, background execution, job progress and OTA update mechanism.

## Current port architecture (source-derived)

The current pipeline still creates a separate APK and data pack for each game. The porter result event contains `title_id`, `name`, `package`, `version`, `display`, `language`, `apk` and `data`. The Android host build also consumes profile-generated compile-time headers. The current native host therefore is not yet a single profile-agnostic runtime that can load arbitrary game profiles.

The new library must not label these legacy outputs as shared-runtime-ready. The legacy Port / Install flow remains intact while the runtime ABI migration is developed and tested.

## Implemented in this branch

### Library UI and persistence
- New first tab named Library, with a three-column cover-first grid, search and Add Game (+).
- Add Game opens the existing Recompiler/Port screen; the porter is not duplicated.
- Successful port result events automatically create or update a library record.
- Catalog is stored atomically at the app's private `~/.config/nx2android/library.json`, schema version 1.
- Each record stores stable ID, title, platform, package, APK/data paths, original source folder, status, settings, cover path and timestamps.
- Per-game settings are stored separately: resolution, graphics preset, FPS, controller and Vulkan driver path. Existing porter-supported touch/FPS60/Vulkan-driver values are retained when available.
- User can choose a PNG/JPG/WebP cover from shared storage (8 MB limit).
- User can remove a shortcut without deleting game files, APK or data.
- Recompile/update opens the existing porter form prefilled with the saved source folder, title, package and supported per-game options.
- The Run action is deliberately disabled while the shared runtime is not implemented.

### Backend
- Added authenticated local API routes for library list, cover image, per-game settings, cover selection and shortcut removal.
- Catalog writes use a temporary file and atomic replace.
- Cover paths are restricted to shared storage and image extensions; cover size is capped.
- A successful porter result is recorded before optional cleanup of working files.

### OTA / CI
- Updated the OTA payload manifest and hashes (payload version 95).
- CI now watches this feature branch and validates Python syntax and payload hashes.
- APK publishing remains restricted to `main`; feature-branch builds must never replace the public latest release.

## Not yet implemented

- Runtime-loaded native game-profile ABI.
- Removal of per-game compile-time profile dependencies from the shared host.
- One reusable `libdmhost.so` / NGR runtime that accepts a validated per-game profile and payload.
- Runtime launch dispatcher from a library entry.
- Per-game graphics/controller settings applied to the native runtime.
- Import/migration of previously ported games not yet represented by a new successful port result.
- Android device tests for catalog, covers, persistence, runtime launch and two-game isolation.

## Required runtime migration

1. Map every consumer of `game_profile.h` and `android_profile.h` across host, HLE, NVN, graphics, Android input, services and build scripts.
2. Define a versioned profile schema and serializer that represents all compile-time profile fields, including module list, startup arguments/environment, memory contract, HLE flags, frame pacing, input/overlay data, graphics workarounds and generated tables.
3. Add native parsing/validation with strict schema and range checks; keep the existing macro path as a legacy build mode.
4. Convert profile consumers to a runtime context incrementally. Do not silently drop profile fields or change legacy behavior.
5. Build a shared native host with no per-game generated profile header. Keep per-game modules, profile JSON, RomFS, shaders and saves in each library payload.
6. Implement a launch dispatcher that passes app-private file descriptors/paths to the native runtime and reports lifecycle/errors to the Android UI.
7. Test at least two materially different game profiles from one installed NGR APK. Verify Vulkan, input, saves, memory settings and no cross-game state leakage.
8. Only after these gates pass, mark catalog entries `ready` and enable Run.

## Next actions

1. Inspect the first GitHub Actions run for the feature branch; require the payload manifest check to pass.
2. Add automated tests for library persistence, duplicate update, settings, cover validation and shortcut-only deletion.
3. Audit all native generated-profile header consumers and record a complete field-to-runtime-context mapping.
4. Implement the profile serializer and a native validation test target while preserving the legacy build.
5. Build the first shared host prototype and compare it byte/behavior-wise against a legacy profile build.
6. Connect the library Run button only after the shared host is genuinely launchable.
