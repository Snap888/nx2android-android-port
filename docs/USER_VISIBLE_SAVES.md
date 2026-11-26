# NGR user-visible game saves

## Default location

NGR stores each game's save data in:

`Download/NX2A/Saves/<game-id>/`

For Metro 2033 Redux the directory is:

`Download/NX2A/Saves/9383b4fd4e8540ed5d6e/`

The directory is created before NativeActivity starts. The native runtime mounts this directory as `DM_SAVE`; temporary runtime files remain under the app-private per-game directory.

## Migration

Before launching a game, the launcher performs a one-time background migration from:

`<app-private-files>/games/<game-id>/save/`

Migration copies only files that do not already exist in the public save directory. It never overwrites a public save, and it keeps the original private save tree intact. A marker is written next to the per-game public directory only after migration succeeds.

The copy runs on a background thread at Android background priority, not on the UI thread. If storage permission or directory creation fails, launch continues with the existing private save directory and a warning is logged/shown.

## Safety

- The launcher does not delete the legacy private save tree.
- Existing public files win over legacy files during migration.
- Individual files are copied to a temporary sibling and renamed into place only after the copy is complete.
- Save transactions and commits continue to be handled by the game's existing filesystem implementation.
- `DM_TEMP` remains private; only `DM_SAVE` is redirected.

## Device validation checklist

1. Install the APK and update/recompile the game's data pack so it contains the updated `libdmhost.so`.
2. Launch Metro and confirm runtime log contains `[NGR save] using user-visible save directory`.
3. Confirm the game log shows `DM_SAVE=.../Download/NX2A/Saves/<game-id>` or the corresponding save mount path.
4. Create a save/checkpoint, exit normally, and verify files appear in the Download directory.
5. Relaunch and load the save.
6. Verify no EACCES/read-only fallback and no save data disappears.
7. Deny storage permission in a separate test and confirm private fallback still launches safely.

## Important distinction

This first implementation uses Android's legacy shared-storage file access because the application intentionally targets SDK 28 for its existing native runtime compatibility. It does not yet use SAF tree URIs or cloud document providers. A future selectable-folder feature should use SAF with a Java-side document stream bridge rather than passing a `content://` URI to the native game filesystem.
