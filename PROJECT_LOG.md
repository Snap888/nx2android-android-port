# PROJECT_LOG — NGR Universal Game Launcher

**Дата обновления:** 2026-11-24  
**Текущий этап:** Исправление повторной синхронизации Porter, кеша обновлений и постоянного системного журнала.  
**Главная цель сейчас:** Запуск GUI без повторной загрузки уже установленного Porter и с сохранением истории системных событий.

## Сделано

- Базовая архитектура NGR: рекомпилятор, встроенный runtime, NativeActivity и библиотека игр.
- Добавлены настройки каждой игры и пять независимых режимов диагностического логирования.
- Логирование по умолчанию выключено; исправлено создание PID-файла для каждой диагностической сессии.
- Найдены причины проблем обложек:
  - автоматический поиск/загрузка обложек ранее не был реализован;
  - выбор файла во встроенном проводнике не вызывал `saveGameCover()`;
  - Android SAF возвращает `content://`, а старый код принимал только преобразуемые в обычный путь URI;
  - окно выбора файлов имело меньший stacking order, чем окно настроек игры.
- Добавлен Android SAF picker для обложек: выбирает `image/*`, копирует выбранный JPEG/PNG/WebP в app-specific external files, ограничивает размер 8 MiB и передаёт путь Web UI.
- Исправлен встроенный проводник: выбор допустимого файла вызывает единый `nx2aPicked()` и сохранение обложки; неподходящие расширения отклоняются.
- Исправлены уровни окон: game details z-index 12, file manager 13, picker 14, confirmation dialog 20. Добавлены закрытие по Escape и нажатию на backdrop.
- Добавлено автоматическое фоновое получение Switch icons по 16-значному Title ID через публичный Nlib API; изображения кэшируются в каталоге конфигурации, ручные обложки имеют приоритет. Автоматический источник отдаёт квадратные иконки, а не гарантированные вертикальные retail box covers.
- Добавлена кнопка ручного запуска повторного поиска обложек и обновление UI после завершения фоновой загрузки. Ошибочные/пустые ответы Nlib ограничены backoff, чтобы не повторять сетевые запросы при каждом открытии библиотеки.
- Обновлён payload manifest до версии 168; SHA-256 `porter_sync.py` и `webgui/server.py` пересчитаны.
- Устранена причина повторной синхронизации Porter: на каждом старте launcher запускал upstream HEAD check и повторную проверку патчей. Добавлена локальная offline-проверка `.nx2a_patched`, связанная с SHA checkout и patch script; валидный кеш используется без сети.
- OTA update check сохраняет время/результат в `/root/.config/nx2android/update-check.json`: успешная проверка кешируется на 6 часов, ошибка — на 10 минут; ручная проверка обходит кеш. Удалён дублирующий updater в launcher; оставлен один фоновый цикл GUI с интервалом 6 часов.
- Системный журнал сохраняется между рестартами в app-private `files/launcher-logs/system.log`, содержит временные метки и ротируется при 2 MiB; launcher/Porter/OTA выводы попадают в этот журнал.
- Коммиты UI/artwork:
  - `0f1e1c2b2a9da02cab5daea176dfa30cc61e514e` — SAF image picker и копирование обложек.
  - `e3ef6ca40d93067ba8a3f89ea9330402d7f9a435` — выбор обложек и stacking order окон.
  - `afe6f91052da5be32191052181837050616e5196` — фоновая загрузка Switch icons.
  - `f787889edb73a3c7f79a7cfc906c6490b75411b7` — отображение квадратных автоматических иконок без обрезки.
  - `cfccb5ae5b5269693516a04e1eb0a8c579354484` — освобождение polling guard после таймаута.
  - `7e37476fa671263f1c507664336a0d957821e950` — проверка MIME типов загружаемых изображений.
  - `a5eefa8ad0fcdfffa21f8c438cde9f568929f879` — ограничение повторных запросов при ошибках Nlib.
  - `bf315cf338b9b3d734edef5f129d3c596805cbd8` — ручной принудительный повтор поиска обложек.
  - `fb030c3084ebcd00d70d6d672ba66e8a91cf42ff` — исправлены SHA-256 payload manifest, версия 167.

## Следующие шаги (приоритет)

1. Проверить CI для HEAD `585b421` / payload 168: manifest, Python, JS, Java и Release APK.
2. На Android выполнить два последовательных запуска: второй должен показать `porter cache ... no download or network check`.
3. Проверить OTA: кешированный статус на обычном старте и принудительная проверка по кнопке.
4. Перезапустить приложение и проверить восстановление предыдущего системного журнала.
5. Продолжить Android-проверку SAF и обложек.

## Ключевые решения и данные

- Репозиторий: https://github.com/Snap888/nx2android-android-port
- Ветка: `feature/ngr-universal-library`
- Пакет: `unknown.none.nx2android`
- JDK 17; CI NDK 27.2.12479018.
- Основные файлы:
  - `app/src/main/java/unknown/none/nx2android/MainActivity.java`
  - `app/src/main/assets/nx2a/payload/webgui/index.html`
  - `app/src/main/assets/nx2a/payload/webgui/server.py`
  - `app/src/main/assets/nx2a/payload/payload.json`
- Nlib: `GET https://api.nlib.cc/nx/{TITLE_ID}?fields=name,icon`; API docs: https://api.nlib.cc/nx/
- Лимит обложки: 8 MiB; форматы: JPEG, PNG, WebP.
- Предыдущая сборка до текущих изменений: Actions run `45485157910`.

## Проблемы / Блокеры

- Исправлена ошибка CI: `payload.json` был сериализован не в каноническом формате `json.dumps(indent=1)`, из-за чего `tools/make_manifest.py` считал его устаревшим. Манифест пересохранён в точном формате штатного генератора.
- Новый CI run `45487557361` для HEAD `585b421` выполняется; manifest check ещё не завершён.
- Поведение кеша и постоянного журнала требует проверки на физическом Android-устройстве.
- Автоматический источник Nlib отдаёт квадратную иконку. Это не эквивалент вертикальной обложке коробки из SteamGridDB/retail database.
- Требуется проверить сохранность `.nx2a_patched` и OTA cache между запусками приложения.
- Нельзя подтвердить работу облачных SAF providers только по компиляции.

## Открытые вопросы

- Нужен ли отдельный экран истории обновлений или достаточно сохраняемого системного журнала?

- Достаточны ли квадратные официальные Switch icons как автоматический fallback или требуется обязательная вертикальная box-art обложка?
- Нужна ли интеграция SteamGridDB с необязательным пользовательским API key для расширенного каталога?


## 2026-11-25 — Metro 2033 Redux: audio underruns and frame pacing

### Сделано / результаты анализа
- Изучены свежие логи игры `9383b4fd4e8540ed5d6e` (Title ID `0100D4900E82C000`), runtime и контрольной игры `9798990324b4ecc6efce`.
- Metro запускается из внешней папки `/storage/emulated/0/Download/0ut/Metro2033Redux-data`; используется legacy compiled profile, отдельный `profile.json` отсутствует; Vulkan override — `libvulkan_freedreno.so`.
- В Metro аудиостатистика показывает массовые underrun: callback 10 000 — 1 019 underrun / 5 091.5 ms zero-padded; callback 18 000 — 2 000 из 2 000 / 10 000 ms zero-padded; callback 20 000 — 891 / 4 454.6 ms. Начиная с callback 24 000 до конца доступного лога underrun не фиксируются. Это подтверждает истощение очереди аудио в раннем/нагруженном участке, а не только субъективные пропуски.
- В Metro frame-work p50/p90 держится примерно 18.9–25.7 / 22.4–26.9 ms при целевых 60 FPS (16.67 ms на кадр). Контрольная игра показывает p90 8.5–17.7 ms в приведённых интервалах и 0 underrun в первых 6 000 callback.
- Metro gameplay log содержит 11 749 `NGR_SYNC lock-wait`, 11 749 `lock-wake` и 21 279 `unlock` сообщений (около 5.47 MB gameplay log). Такая подробная трассировка сама способна усиливать I/O/CPU нагрузку; пока не доказано, что сами lock wait являются первопричиной.
- Runtime log также содержит задержки доставки main looper до 15.8 s. Это отдельный признак тяжёлой блокировки/перегрузки Android-процесса; не считать автоматически причиной игрового аудио.

### Следующие шаги
1. Разобрать реализацию аудиопроизводителя и очереди AAudio/аудиомоста: почему producer не успевает подавать данные во время ранней нагрузки; проверить период callback, глубину очереди и thread scheduling.
2. Сопоставить моменты underrun с thread snapshots, NGR_SYNC wait/wake и frame-work интервалами, не меняя синхронизацию игры вслепую.
3. Убрать или ограничить по умолчанию подробный per-operation NGR_SYNC вывод; оставить агрегированные счётчики/сэмплированные события, чтобы диагностика не ухудшала игровой процесс.
4. После исправления проверить Metro с минимальным логированием и повторно сравнить аудио underrun и frame pacing с игрой `9798990324b4ecc6efce`.

### Проблемы / блокеры
- Подтверждены аудио underrun и превышение frame-work бюджета; первопричина на стороне аудиопроизводителя, CPU scheduling или синхронизации ещё не локализована.
- Исправление кода и APK для этого анализа пока не выполнялись.


## 2026-11-25 — Metro 2033 Redux: исправлен abort при выключенном FS trace

### Подтверждённая причина
- Новый `Logs/ngr-gameplay-9383b4fd4e8540ed5d6e.log (1).txt` содержит точную последовательность: `fs mount host` → `FATAL cannot open DM_FSLOG` → `CRASH sig=6` (`abort`).
- Причина: `ngrhost.c` выставлял `DM_FSLOG=""`, когда чекбокс Filesystem / RomFS trace выключен. Runtime открывает `DM_FSLOG` на старте даже при `DM_FS=0`, поэтому пустое значение приводило к аварийному `abort()`.
- Это объясняет, почему Metro запускался только при включённом FS trace.

### Исправление
- Коммит `c68c8503d89eb2046aa135b337cf79f440559aa9` — при выключенном FS trace теперь передаётся `DM_FSLOG=/dev/null`; реальный TSV-путь устанавливается только при включённом чекбоксе.
- При выключенном FS trace ` /dev/null ` служит безопасным sink для обязательного открытия файла runtime, без записи диагностического TSV на диск.

### Следующие шаги
1. Проверить CI и собрать APK для коммита исправления.
2. На устройстве запустить Metro с выключенным Filesystem / RomFS trace: игра должна пройти инициализацию без abort.
3. Повторить запуск с включённым FS trace: должен создаваться обычный `fs-<game_id>.tsv`.
4. Если игра всё ещё падает, приложить новый gameplay/runtime export — причину предыдущего abort нужно считать устранённой, а дальнейшую ошибку разбирать отдельно.

### Статус
- Исправление внесено в `feature/ngr-universal-library`; проверка CI и реального запуска на Android ещё не выполнена.


## 2026-11-25 — Vulkan driver picker audit and Metro audio runtime analysis

### Vulkan driver selection audit
- Audited the current HEAD `4fdedb4f960cc6824b0c6f98360cd35fb256578a`.
- The shortcut settings already contain a Browse button and a local file browser; Android's ACTION_OPEN_DOCUMENT picker is also available for local files/SD cards/USB providers that expose a filesystem path. Non-filesystem cloud providers are not supported by the native runtime path flow.
- Confirmed the end-to-end path in source: WebView `settings.vulkan_driver` → `NX2A.launchGame(...vulkanDriver)` → Java intent extra `ngr_vulkan_driver_path` → native validation/copy to private per-game directory → `NGR_DM_VK_DRIVER_OVERRIDE`.
- The pinned porter patch `NX2A_DM_VK_DRIVER_OVERRIDE` applies the override after reading `env.txt`, by setting `DM_VK_DRIVER`; `gfx_vk_core.c` then loads the selected library through `adrenotools_open_libvulkan`, validates a Vulkan 1.3 GPU and falls back to system Vulkan if custom loading fails.
- This confirms the implementation chain exists in source. Device proof still requires a runtime log containing both `[Vulkan] using per-launch driver override` and `Vulkan driver <name> through adrenotools`. The uploaded successful Metro log confirms Turnip Adreno 740 / Vulkan 1.4.363 / driver 26.2.99, but does not by itself prove that a different manually selected driver was applied.

### Metro audio analysis
- Inspected the exact pinned runtime source at porter SHA `468937822219a56eb81da1aa2e40f05e8c453af2`, including `nxnative/dm/host/hle_audio.c`, `nxnative/dm/host/hle_audren.c` and `nxnative/dm/android/compat/audiotoolbox_aaudio.c`.
- AAudio requests low-latency shared output with fixed 5 ms callbacks (240 frames at 48 kHz). The HLE AudioRenderer path has four 1024-frame buffers in flight and blocks on released-buffer notifications; the AudioOut path uses a bounded SPSC queue.
- Metro's successful gameplay log shows severe queue starvation: callback interval 8k had 94 underruns, 10k had 1,845, 12k had 927, 14k had 607, 16k had 1,559; average queue depth collapsed to 0.3 blocks at 10k. The log also shows frame-work stalls and high synchronization activity.
- No audio code has been changed yet. Increasing the buffer count or thread priority without identifying whether Metro uses AudioOut or AudioRenderer, and which producer thread stalls, risks adding latency or masking the root cause. Next diagnostic step is to map Metro's audio open call sites and correlate producer-thread snapshots with underrun intervals.

### CI / manifest
- CI run `45503091419` for HEAD `4fdedb4` failed only at the payload-manifest freshness check; Python tests, porter patch validation and WebView JavaScript syntax passed.
- Commit `0343d1afff47ddb20cd96201b9bbf10497a9a0b5` refreshes `payload.json` hashes for the current `apply_patches.py` and `webgui/index.html`, bumping payload version from 168 to 170. A new CI run must confirm the manifest check and build.

### Следующие шаги
1. Confirm CI success and retrieve the signed APK artifact.
2. On device, select a different known-good ARM64 driver using Browse; verify the two explicit Vulkan override log lines and GPU identity/version. Test fallback to system Vulkan after clearing the field.
3. For Metro, collect a fresh gameplay/runtime log with main runtime diagnostics and NVN/Vulkan lifecycle enabled, but leave FS trace and per-operation synchronization tracing disabled. Capture thread snapshots around the first audio underruns.
4. Identify whether Metro's output is AudioOut or AudioRenderer and patch only the proven producer/scheduling bottleneck; then compare underrun counts and frame pacing against the control game.

### Проблемы / блокеры
- Driver picker and intent/native override are present; no real-device A/B confirmation yet.
- Audio underruns are confirmed, but the exact producer-side cause is not isolated. No runtime audio patch has been made.
- APK for manifest refresh is pending CI.



## 2026-11-25 — Runtime log PID correction and Vulkan log attribution

### Дополнительные результаты проверки загруженных логов
- `Logs/ngr-gameplay-9383b4fd4e8540ed5d6e.log.txt` в текущем обновлении пустой (0 bytes); файл с суффиксом `(1)` содержит старую сессию с прежним `DM_FSLOG` abort, поэтому по нему нельзя оценивать новый запуск и аудио.
- В `ngr-runtime-9383... (1).txt` PID в заголовке был `1461\\n` как буквальная последовательность `\\n`. Причина найдена в `ngrhost.c`: PID-файл записывался форматом `"%ld\\\\n"`, а при отключённых всех чекбоксах `runtime_log_init()` вообще не обновлял PID-файл. Из-за этого экспорт мог фильтровать Logcat по PID предыдущей сессии.
- Исправлено в `5851dc23b4f37f5103aabcc8f3455a2f3b28b648`: PID теперь записывается с настоящим переводом строки; PID marker обновляется при каждом запуске, даже если все диагностические переключатели выключены. Само подробное логирование при этом остаётся выключенным.
- Строки `AdrenoVK-0` в этом экспорте имеют `Application Name: android framework` или `Chromium`; сообщения `Shader compilation failed` / `Pipeline create failed` относятся к Vulkan-контексту Android/WebView, а не доказывают ошибку Vulkan-рендера Metro. Их нельзя использовать как основание для изменения игрового shader pipeline.

### Актуальное состояние Vulkan picker / override
- UI ярлыка получил кнопку Browse; путь `.so` сохраняется в `settings.vulkan_driver` и передаётся в NativeActivity.
- `ngrhost.c` проверяет ARM64 ELF, копирует выбранный DSO в private game runtime directory, проверяет наличие `libadrenotools.so` и hook DSOs и передаёт basename через `NGR_DM_VK_DRIVER_OVERRIDE`.
- `apply_patches.py` добавляет в `front_android.c` применение override после чтения `env.txt`, чтобы конфигурация игры не затирала выбор из ярлыка.
- При отсутствии AdrenoTools helper libraries выбранный драйвер отклоняется с понятной ошибкой; игра не должна молча делать вид, что переключение применилось. Для старого runtime потребуется пересборка игры с custom-driver support, если helper DSOs в её data pack отсутствуют.
- Проверка реального применения требует свежего игрового runtime log со строками `[Vulkan] using per-launch driver override` и `Vulkan driver <name> through adrenotools`; Logcat AdrenoVK/Chromium для этого не подходит.

### Аудио / производительность
- По исходникам pinned porter подтверждены два разных пути: AudioOut (AAudio 5 ms callbacks / SPSC queue) и AudioRenderer (отдельный render thread, 5 ms frame budget). Пока нет достоверного свежего gameplay export, нельзя установить, какой путь использует проблемный участок Metro и какой producer thread не успевает.
- Аудиокод пока не менялся: увеличение буфера или приоритета без подтверждения пути может добавить задержку и замаскировать первопричину.

### Следующие шаги
1. Дождаться CI для HEAD `b223e35` и забрать APK только после успешной сборки.
2. Установить APK; проверить Metro с FS trace выключенным и без выбранного custom driver — это контрольный запуск.
3. Для следующего диагностического запуска включить только `Main runtime + game stdout/stderr`; FS trace оставить выключенным. Новый PID marker должен совпадать с PID текущей NgrGameActivity, а gameplay log должен быть непустым.
4. По игровому stderr определить AudioOut или AudioRenderer; затем связать underrun с render-time/catch-up/producer scheduling и только после этого менять audio runtime.
5. Для проверки picker выбрать ARM64 `.so`, сохранить ярлык и проверить, что лог содержит per-launch override и успешную загрузку через AdrenoTools. Затем очистить поле и проверить возврат к `env.txt`.

### Статус
- UI, intent/native staging, runtime override patch и PID marker correction внесены в ветку.
- APK и реальная проверка на устройстве ещё не подтверждены.
