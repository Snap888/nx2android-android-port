# NGR native runtime profile audit

Source inspected: the porter revision pinned by this app payload (`468937822219a56eb81da1aa2e40f05e8c453af2`), especially:

- `nxnative/dm/games/game.py`
- `nxnative/dm/android/tools/android_profile.py`
- `nxnative/dm/android/build.py`
- `nxnative/dm/host/main.c`
- `nxnative/dm/android/front_android.c`
- `nxnative/dm/android/apk/mkapk.py`

## Confirmed current behavior

### Per-game profile compilation

`dm/android/build.py` runs both profile generators for the selected game:
- `dm/games/game.py header <game> <gen>/<game>/game_profile.h`
- `dm/android/tools/android_profile.py header <game> <gen>/<game>/android_profile.h`

It then compiles the native host with `-I<gen>/<game>`. This means the generated profile headers are available to every native translation unit and are compiled into the game-specific `libdmhost.so`.

The main host reads the profile's `DM_GAME_ARGS` when command-line arguments are absent, and uses `DM_GAME_MODULES` when no module list is supplied. These are real startup defaults and must be preserved by a dynamic profile implementation.

### Game profile fields emitted by game.py

The current generated `game_profile.h` represents:

| Group | Fields |
|---|---|
| Identity | `DM_GAME_ID`, `DM_GAME_NAME`, `DM_GAME_PROGRAM_ID` |
| Module loading | `DM_GAME_MODULES`, `DM_GAME_NMOD`, `DM_GAME_ROMFS_MARKER` |
| Memory contract | `DM_GAME_MEM_RESERVE`, `DM_GAME_MEM_ALIAS`, `DM_GAME_MEM_STACK`, `DM_GAME_APP_POOL`, `DM_GAME_MEM_USED`, `DM_GAME_SYS_RESOURCE` |
| Startup | `DM_GAME_ARGS`, `DM_GAME_ENV`, `DM_GAME_DISPLAY_VERSIONS`, `DM_GAME_PRESENT_DISPLAY` |
| System behavior | `DM_GAME_MEM_MAP_LIMIT`, `DM_GAME_CORE_PREEMPT`, `DM_GAME_ALLOC_BIG_ALIGN` |
| Frame pacing | `DM_GAME_FPS_TARGET`, `DM_GAME_FPS_HOLD` |
| Font / input / performance | optional `DM_GAME_SHARED_FONT_TTF`, `DM_GAME_PAD_LAYOUT`, `DM_GAME_OPMODE`, `DM_GAME_PERF_BOOST` |
| Shader / NVN workarounds | `DM_GAME_FEEDBACK_SNAP`, `DM_GAME_ALPHA_FROM_RED`, `DM_GAME_TEX_FLUSH_UPLOAD`, `DM_GAME_RENDER_COND`, `DM_GAME_TEX_DIRTY_UPLOAD`, `DM_GAME_TEX_DYN_SLOTS`, `DM_GAME_GPU_TS_SEGMENT`, `DM_GAME_VCONV_RANGE` |
| API version | optional `DM_GAME_NVN_API_MAJOR`, `DM_GAME_NVN_API_MINOR` |

The generator validates several enums and dependencies before emitting the header (for example FPS target 0/30/60, pad layout, operation mode, texture dirty upload requiring texture flush upload, and NVN API major/minor format). A runtime parser must retain equivalent validation; it must not silently coerce invalid profile data.

### Android profile fields emitted by android_profile.py

The generated `android_profile.h` contains:
- `DM_ANDROID_STATUS` — profile status.
- `DM_AOV_N` — number of controls in the tablet layout.
- `DM_AOV_TABLET` and `DM_AOV_PHONE` — compile-time control layout tables.

The Android profile also has package name, orientation, required device features, firmware system-data title IDs, pause-menu defaults, environment entries, overlay adjustments and a gamepad theme. The theme is separately packaged as an APK asset by the existing pipeline.

`front_android.c` currently declares a static array with a dimension based on `DM_AOV_N` (`g_cust[2][2][DM_AOV_N][3]`). The overlay table therefore needs a dynamic representation or a bounded validated profile structure before the Android header can be removed.

### APK identity and packaging

`mkapk.py` packages a code-less NativeActivity APK around the selected native library. Its package, label, library name, orientation and version metadata are APK build inputs. This is why the current flow produces a per-game APK rather than registering a game in the launcher process.

## Runtime conversion strategy

1. Add a JSON serializer alongside the two existing profile generators. It must be generated from the same parsed profile objects, not a second hand-maintained interpretation of TSV files.
2. Add tests comparing the JSON representation with the generated headers for every available profile. Include optional fields and repeated rows.
3. Add a versioned C profile structure and a parser that owns all strings, arrays and overlay rows for the lifetime of a game session. Validate schema version, integer ranges, enum values, module count, string lengths and table dimensions before native startup.
4. Convert `main.c` first: module list and default arguments must match current macro behavior exactly.
5. Convert memory/system fields and then NVN/graphics workarounds in small groups. Keep the macro implementation behind a legacy build switch for A/B tests.
6. Replace static Android overlay tables and `DM_AOV_N`-sized storage with runtime-owned, bounded arrays.
7. Build a single stable NGR package containing the common NativeActivity host and shared `libdmhost.so`. Put game-specific modules, profile JSON, RomFS, shader bundle, environment and save data in per-game payload directories.
8. Add an Android launch dispatcher that selects a catalog entry and passes its validated payload/profile to the host. Keep each game isolated in a separate process initially; do not attempt unsafe same-process profile switching until global native state is audited.
9. Verify two different profiles on a physical Adreno device from one installed NGR APK, including launch, input, Vulkan, shader cache, saves, memory, suspend/resume and process cleanup.

## Hard acceptance gates

- No per-game `game_profile.h` or `android_profile.h` is required to build the shared runtime.
- All fields listed above have a runtime representation or an explicit, reviewed reason they are build-only.
- Profile parser rejects corrupt or unsupported data with a readable error before native initialization.
- Legacy per-game APK builds still pass during migration.
- Two different games launch from the same installed NGR APK with no cross-game state leakage.
- Only then may the launcher enable the Run action and mark a catalog record as `ready`.
