# NGR user-visible game saves

## Storage layout

The game writes and commits saves in app-private storage:

`<app-private-files>/games/<game-id>/save/`

This is intentional: the NGR filesystem implements transactional save commits with directory exchange/rename semantics. Android's emulated Download filesystem does not reliably support those operations.

A user-visible mirror is maintained at:

`Download/NX2A/Saves/<game-id>/`

For Metro 2033 Redux:

`Download/NX2A/Saves/9383b4fd4e8540ed5d6e/`

## Synchronization

- Before launch, files in Download are imported only when they are clearly newer than the private committed copy.
- Private saves are also published to Download before launch when they are newer or absent there.
- After NativeActivity returns to the launcher, the private committed tree is copied to Download on a background thread.
- Files are copied to sibling temporary files, flushed and synced, then moved into place. Partial copies are not exposed as completed save files.
- The private tree is the source of truth during gameplay. Download is a backup/export mirror, not the live mount.
- If external storage is unavailable, gameplay and save commits continue privately.

## Why this design

The previous implementation mounted Download directly as `DM_SAVE`. The gameplay log showed repeated `errno=95` on optional xattr removal and `errno=22` on `RENAME_EXCHANGE`. Those are external-storage compatibility issues, not game-save format failures. The fix restores the transaction to app-private storage and treats unsupported xattr removal as optional metadata when the physical and guest filenames already match.

## Device validation

1. Install the APK and update/recompile the Metro data pack so its `libdmhost.so` contains the updated private-save patch.
2. Confirm the runtime log reports `DM_SAVE=<app-private>/games/<game-id>/save`.
3. Create a checkpoint, exit to the launcher, and confirm files appear under Download.
4. Relaunch and load the checkpoint.
5. Check that `errno=95` and `atomic swap failed errno=22` no longer occur.
6. Modify a public save externally with a newer timestamp, launch again, and confirm it is imported without overwriting a newer private save.

This is a two-location backup workflow. If Android terminates the process before it returns to the launcher, the latest private save remains safe; the Download mirror is refreshed on the next successful return or launch.
