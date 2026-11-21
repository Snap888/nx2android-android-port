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
