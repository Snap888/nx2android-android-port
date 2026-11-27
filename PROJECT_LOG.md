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


## 2026-11-25 — Disable synchronization trace during normal gameplay

### Причина лишней нагрузки
- Подтверждено, что Porter patch `NX2A_SYNC_TRACE` / `NX2A_SYNC_WAIT_TRACE` писал `[NGR_SYNC]` и `[NGR_SYNC_WAIT]` на каждом выбранном lock/unlock/wait/wake без проверки диагностического флага.
- В ранее загруженном Metro gameplay log было более 21 000 таких событий. Они попадали в stderr/log.txt и создавали лишние форматирование, syscalls и файловый I/O даже при выключенных пользовательских логах.

### Исправление
- Добавлен patch `NGR synchronization trace default-off gate` в `apply_patches.py`: все per-lock и condition-variable trace calls теперь требуют `DM_SYNC_TRACE=1`; при отсутствии переменной или значении `0` логирующие ветки не выполняются.
- `ngrhost.c` устанавливает `DM_SYNC_TRACE=1` только при включённом существующем чекбоксе `Hang watchdog / thread snapshots`; без чекбокса трассировка выключена.
- Уточнена подпись чекбокса: он включает также synchronization trace.
- Payload manifest обновлён до версии 171; SHA-256 для `apply_patches.py` и `webgui/index.html` обновлены.
- Синхронизацию, блокировки, приоритеты и поведение condition variables не менял — только отключил диагностические записи в обычном режиме.

### Проверка
- Требуется CI validation на pinned Porter: patch 16/17 должны примениться, затем patch 19 должен заменить старые trace calls и добавить gate; повторный запуск patch script должен быть idempotent.
- После установки APK проверить Metro с выключенным watchdog/thread checkbox: в новом gameplay log не должно быть `[NGR_SYNC]` / `[NGR_SYNC_WAIT]`; звук и frame pacing сравнить с предыдущим запуском.
- При включении checkbox эти строки должны появиться для диагностики.

### Статус
- Код и manifest обновлены в `feature/ngr-universal-library`; CI и тест на устройстве ожидаются.


## 2026-11-25 — Metro gameplay log: Turnip verified, AudioOut starvation and hot yield loops

### Факты из полного gameplay blob `95e1e4d7aebcb3242cd649b293c6947b5b758950`
- Файл содержит 3,823,554 символа / 49,897 строк; предыдущая попытка `fetch_file` вернула пустой контент из-за размера, поэтому полный анализ выполнен через Git blob.
- Vulkan в самой игре работает через custom driver: `Vulkan driver libvulkan_freedreno.so through adrenotools, not the system's`; GPU `Turnip Adreno (TM) 740`, Vulkan 1.4.363, driver 26.2.99 (`0x6802063`). Значит, предыдущие `AdrenoVK`/Chromium сообщения из Logcat не отражали игровой Vulkan, но gameplay log подтверждает успешный Turnip.
- Metro использует `AudioOut` (2 канала, real output), AAudio callback получает ровно 240 frames = 5 ms. Это не AudioRenderer output path.
- AudioOut queue начинается с 4.0 блоков и без underrun на callback 2k/4k/6k. Затем очередь истощается: callback 8k — 94/2000 underrun; 10k — 1845/2000 (9,225 ms zero-padded); 12k — 927; 14k — 607; 16k — 1559; 18k–24k — 2000/2000 в каждом окне, очередь 0.0 блока; 26k — 282; с 28k до 32k underrun снова 0. Это подтверждает временное starvation producer/очереди, а не постоянную неисправность AAudio callback.
- В том же логе 30,672 `[NGR_SYNC]` событий; они действительно писались при обычном запуске. Новая patch 19 теперь отключает их без `DM_SYNC_TRACE=1`.
- Yield watchdog фиксирует три Unity-потока (`uEngine :: PhysX simulator`, `uEngine :: Secondary`, `main thread`) с 2.2–3.84 млн yield/s, один и тот же SDK callsite `sdk+0xd688c0`. Thread CPU time около 30 секунд за 30 секунд наблюдения у PhysX/Secondary. Это сильный признак CPU busy-yield/poll loop; default `DM_YIELD_BACKOFF` не обязательно помогает, потому что `thr_yield` трактует меняющиеся callee-saved registers как прогресс и пропускает backoff.
- На первых 600 кадрах frame work p50 около 33.3 ms, GPU p50 около 0.36 ms; позже (900–1800) GPU p50 растёт примерно до 17–23 ms. Игра фактически держит present interval 2 / около 30 FPS; сначала заметна CPU-side нагрузка, позднее добавляется GPU-side нагрузка.
- В логе есть отдельные NVN unimplemented warnings и present thread time-constraint policy failure; это не объясняет AudioOut starvation само по себе.

### Диагноз / решение
- Vulkan chain для текущей сборки Metro проверен и исправен: Turnip действительно загружается через AdrenoTools. Не следует менять драйвер/шейдерный backend ради этих аудио underrun.
- Самый безопасный первый runtime шаг — убрать безусловный per-lock `[NGR_SYNC]` I/O (сделано patch 19). Синхронизацию и scheduler пока не меняли.
- Если после gate аудио всё ещё проваливается, следующий кандидат — точечный backoff для повторного `YieldThread` на `sdk+0xd688c0`; нельзя включать глобальный forced backoff без проверки, поскольку другие игры используют yield для реального прогресса.
- Буфер AAudio пока не увеличивать: очередь пустеет потому, что guest producer перестаёт подавать блоки; дополнительная задержка не устраняет первопричину.

### Следующий A/B тест после APK
1. Установить APK с default-off sync trace.
2. Metro: `Main runtime + game stdout/stderr` ON; `Hang watchdog / thread snapshots + synchronization trace` OFF; `Filesystem / RomFS read trace` OFF; остальные категории OFF.
3. Проверить, что `[NGR_SYNC]`/`[NGR_SYNC_WAIT]` отсутствуют, сравнить AudioOut underrun окна и frame work/GPU stats.
4. Если starvation остаётся, подготовить адресный backoff для `sdk+0xd688c0` и A/B тестировать только на Metro.


### Важное условие применения runtime patch
- Изменения `hle_thread.c` (default-off `NGR_SYNC`) и `front_android.c` (per-launch Vulkan override) входят в исходники Porter. Установка нового NGR APK сама по себе не переписывает уже скомпилированный `libdmhost.so` в data pack игры.
- После установки APK нужно один раз выполнить `Recompile / update` для Metro, чтобы пересобрать его runtime из обновлённого Porter checkout. Импортировать/копировать заново 6.7 GB game data не требуется, если recompile использует уже установленный data pack и кэш.
- PID marker correction и UI/native file picker находятся в самом NGR APK и применяются сразу после установки.


### CI / APK result — 2026-11-25
- Successful signed APK build: Actions run `45505253009` (HEAD `3a45b10c52bbd90ee22b979263c4019d64e4db3a`), all APK job steps passed.
- Artifact: `nx2android-apk`, artifact ID `14973406319`; extracted `app-release.apk` size 36,927,577 bytes.
- Test APK SHA-256: `99463d28c5c42fbd63c5e4c68e3adce3e0550ad63aacdac6e3ce2742fcb4bfbe`.
- Later commit `80155c53c4c7b392ca5cdf9f9e84db65d41d8b6d` updates documentation only; no code changed after the successful APK build.
- Device test and one-time Metro recompile are still pending.


## 2026-11-25 — Import precompiled games from a selected folder

### Реализовано
- В библиотеку добавлена отдельная кнопка **Import folder**; она не запускает вкладку Recompiler и не вызывает Porter.
- Используется существующий Android SAF picker с выбором каталога. Пользователь выбирает непосредственно готовую папку игры, содержащую `nx2a-data.json` и `libdmhost.so`.
- Новый API `POST /api/library/import` проверяет папку, JSON manifest и наличие непустого NGR native runtime, затем регистрирует игру в общей `library.json`.
- Если manifest содержит корректный 20-символьный `game_id`, он сохраняется; иначе создаётся стабильный ID от канонического пути папки. Проверяется конфликт ID в manifest.
- Запись игры использует тот же формат каталога, что и результат рекомпилятора: `data_path`, `runtime_so_path`, `runtime_libs`, `runtime_ready`, настройки и обложка. Существующие настройки/обложка сохраняются при повторном импорте.
- Игровые файлы не копируются и не перепаковываются: runtime работает с выбранной папкой на месте; подготовка runtime остаётся существующим действием в карточке игры.
- Payload manifest поднят до версии 172; обновлены SHA-256 для `webgui/server.py` и `webgui/index.html`.

### Ограничения / важные детали
- Импортируется именно готовый NGR data pack, а не произвольная папка исходных файлов. Обязательны `nx2a-data.json` и `libdmhost.so`.
- Выбирать нужно каталог самой игры (обычно заканчивается на `-data`), а не родительскую папку с несколькими играми.
- Для папок на SD-карте/USB доступ зависит от того, предоставляет ли Android SAF реальный filesystem path, который текущий Python runtime может читать. Облачные провайдеры без filesystem path не поддерживаются.
- Импорт добавляет shortcut в библиотеку, но не доказывает, что payload полностью совместим с текущей версией runtime. Это подтверждается на этапе Prepare runtime и реального запуска.

### Следующие шаги
1. Проверить GitHub Actions для коммитов импорта и manifest; исправить ошибки Python/JS/manifest freshness, если появятся.
2. Установить APK и импортировать ранее собранную папку `*-data` с `nx2a-data.json` и `libdmhost.so`.
3. Проверить, что игра появляется в Library без запуска рекомпилятора, проходит Prepare runtime и запускается.
4. Проверить повторный импорт той же папки: не должно появляться дубликата.
5. Проверить импорт с отсутствующим manifest и с отсутствующим `libdmhost.so`: UI должен показать понятную ошибку, библиотека не должна измениться.

### Изменённые файлы
- `app/src/main/assets/nx2a/payload/webgui/server.py`
- `app/src/main/assets/nx2a/payload/webgui/index.html`
- `app/src/main/assets/nx2a/payload/payload.json`

### Коммиты
- `460cd0a1` — Add import for precompiled NGR game folders
- `60f66684` — Add precompiled game folder import to library
- `f607eaf4` — Correct payload hashes for precompiled import

### Статус
- Реализация внесена в `feature/ngr-universal-library`.
- CI, APK artifact и тест на устройстве пока не подтверждены.


### CI manifest correction
- Первый CI для manifest выявил расхождение SHA-256 (Python syntax, Porter patch validation и WebView JS syntax до этого прошли).
- Взяты контрольные SHA-256 непосредственно из diff шага `tools/make_manifest.py`; manifest исправлен коммитом `d7fc6b2d`.
- Новый CI должен подтвердить актуальный manifest и собрать APK; предыдущий run `45507296557` завершился failure только на manifest freshness check, APK не создавался.


## 2026-11-25 — Peanuts Native comparison and game-embedded cover extraction

### Сравнительный аудит
- NGR уже использует единый launcher/NativeActivity и общий native dispatcher; библиотеки runtime по игре лежат в data pack. Переписывать архитектуру под Peanuts Generic Host не требуется.
- NGR уже валидирует schema-v1 profile.json относительно nx2a-data.json и сохраняет legacy compiled-profile fallback; бинарный формат Peanuts переносить не нужно.
- Импорт NGR *-data папки пока проверяет manifest и наличие libdmhost.so, затем регистрирует путь без копирования. В отличие от Peanuts PackImport, здесь ещё нет проверки build identity/ABI/hash всей сборки и staged atomic replace; это отдельный следующий этап.
- Per-game Vulkan override и выборочные диагностические категории уже реализованы. Из Peanuts полезно адаптировать каталог известных проблемных GPU-драйверов.
- Обложки NGR до этого поддерживали ручной SAF import и Nlib fallback. Peanuts LibraryScanner извлекает NACP icon из исходной игры или .nup и кеширует PNG локально.

### Сделано — встроенная иконка игры
- Добавлен патч Porter pipeline: при NGR-сборке извлекается уже расшифрованный icon.jpg из extraction output (self.game / self.base) и добавляется в data pack как ngr-cover.jpg. Дополнительная расшифровка NSP/XCI не запускается.
- Server кэширует встроенную иконку в локальном cover cache по стабильному game ID и помечает источник game-nacp.
- Приоритет обложек: существующая пользовательская обложка > встроенная NACP-иконка > ранее загруженная Nlib-иконка. Ручной выбор явно помечается manual.
- В настройках игры добавлена команда Use game icon: она назначает встроенную NACP-иконку текущей обложкой; если старый data pack ещё не содержит файл, UI сообщает о необходимости пересобрать игру.
- Импорт готовой NGR data-папки также распознаёт sidecar ngr-cover.*, icon.* и cover.* (JPEG/PNG/WebP до 8 MiB); неизвестные/повреждённые файлы игнорируются.
- В библиотеке встроенная квадратная иконка отображается без обрезки, как и Nlib fallback. Уже существующие сборки без встроенного файла продолжают использовать текущую обложку/Nlib fallback; новая иконка будет доступна после сборки с обновлённым Porter patch.

### Файлы
- app/src/main/assets/nx2a/payload/apply_patches.py
- app/src/main/assets/nx2a/payload/webgui/server.py
- app/src/main/assets/nx2a/payload/webgui/index.html
- app/src/main/assets/nx2a/payload/payload.json
- PROJECT_LOG.md

### Следующие шаги
1. Проверить manifest hashes, Python syntax, patch idempotency, WebView JavaScript syntax и APK build в GitHub Actions.
2. На устройстве собрать игру и проверить, что *-data/ngr-cover.jpg появляется и библиотека показывает её без сетевого Nlib запроса.
3. Проверить ручную обложку: после повторной сборки она должна сохранять приоритет над NACP.
4. Отдельным этапом усилить импорт готовых сборок: build ID/ABI/hash validation и staged atomic registration.

### Ограничения
- NACP icon — встроенная квадратная иконка игры, а не скриншот игрового кадра и не вертикальная retail box art.
- Импорт старого data pack без ngr-cover.* не может восстановить иконку из исходного NSP/XCI, если оригинальные файлы/извлечённые данные недоступны.
- GitHub Actions run `45571346972` для HEAD `bb74ae7d3cca43953dcfa66919d595838cf2f5a7` завершился `success`: Python syntax/runtime tests, Porter patch validation, WebView JS syntax, payload manifest, signed APK build и artifact upload прошли.
- Artifact `nx2android-apk` (ID `15002925365`), размер 35,855,289 bytes; SHA-256 `5899a1da8ba6c50ca157fd90ea45fc7c66b4166de234316135f5359d62b23500`; archive: https://api.github.com/repos/Snap888/nx2android-android-port/actions/artifacts/15002925365/zip (expires 2027-02-23).
- On-device validation is still required: confirm that a newly ported game contains `ngr-cover.jpg`, that Use game icon switches to it, and that a manually chosen cover remains higher priority.

## 2026-11-25 — Android scheduling balance for audio starvation / UI responsiveness

### Анализ
- В доступной Library-сборке `ngr-gameplay-2f92dce8597c52f2717c.log.txt` обнаружен manifest с Title ID `0100CD701434C000` и названием **Twelve Minutes**. Это не Metro 2033 Redux; его audio/frame цифры нельзя переносить на Metro.
- Metro-специфичный свежий лог в доступной Library не найден. Предыдущие наблюдения из отдельной Metro-сессии остаются контекстом, но требуют повторной проверки по точному свежему gameplay/runtime export.
- Проверен Porter AAudio путь на pinned commit `468937822219a56eb81da1aa2e40f05e8c453af2`: AAudio low-latency shared stream, callback 240 frames / 5 ms; callback вызывает AudioOut pull. AudioOut producer публикует блоки в SPSC очередь QMAX=64, callback не захватывает producer mutex. Значит, простое увеличение размера AAudio callback или очереди не доказывает устранение producer starvation и может увеличить latency.
- Проверен Android QoS compatibility shim: `USER_INTERACTIVE → nice -10`, `USER_INITIATED → nice -4`, `UTILITY → nice +4`. До этого `DM_QOS_MAP` был выключен, поэтому guest-потоки получали один класс QoS; низкоприоритетные worker threads не уступали CPU Android UI как задумано Horizon priority.

### Изменено
- В `ngrhost.c` включён стандартный маппинг guest priorities в Android QoS, если профиль явно не задал `DM_QOS_MAP`:
  - приоритеты <=44 — User Interactive (main/audio/game-critical threads);
  - 45–58 — User Initiated;
  - >58 — Utility (фоновые worker threads получают nice +4 и уступают CPU системе).
- Явный `DM_QOS_MAP` / `DM_QOS_EDGES` остаётся override. Добавлен runtime log marker `[scheduler] Android QoS mapping enabled...`.
- Не менялись AAudio callback period, AudioOut queue depth, sample rate и audio producer synchronization: без свежего Metro-лога эти изменения были бы спекулятивными.
- Commit: `0281eebfa00ebbc831ae0b66d38e652265975887` — `Map guest thread priorities to Android QoS`.

### Проверки / блокеры
- Source audit completed; Android device A/B and audio validation are not yet available.
- CI for commit `0281eebfa00ebbc831ae0b66d38e652265975887` must be checked before distributing an APK.
- Need the current Metro 2033 Redux gameplay + runtime diagnostic export (game ID previously tracked as `9383b4fd4e8540ed5d6e`, confirm from manifest) to identify AudioOut producer thread, queue starvation intervals, lock waits, frame stalls and actual Android ANR cause.

### Следующие шаги
1. Verify GitHub Actions APK build for the scheduler commit and publish only a successful artifact.
2. Run Metro A/B with scheduler mapping on; compare audio underruns, queue depth, frame-time p95/p99, Android UI input latency and battery/thermal state.
3. From the fresh Metro log, confirm whether the producer is FMOD/AudioOut or AudioRenderer before changing callback buffering or queue semantics.
4. If underruns persist, instrument only sampled producer enqueue/release timing and thread wait state; keep per-lock trace and filesystem/NVN verbose logs off by default.
5. Inspect the ANR/tombstone section to distinguish CPU starvation from deadlock, GPU wait or memory pressure.


## 2026-11-25 — Metro 2033 Redux: CPU yield storm and audio starvation

### Лог и подтверждённые причины
- Новый пользовательский gameplay log: Game ID `9383b4fd4e8540ed5d6e`, profile / Title ID `0100D4900E82C000`, Android package `unknown.none.nx2android`, Vulkan Turnip Adreno 740 driver 26.2.99.
- Важная коррекция прежней гипотезы: это не просто малый аудиобуфер. Два гостевых потока Unity/uEngine выполняют патологически частые progressing `SleepThread` yields, которые текущий `thr_yield()` намеренно пропускает без host scheduling point, когда меняются callee-saved регистры.
- Watchdog зафиксировал `uEngine :: PhysX simulator` до 2.92 млн yields/s и `uEngine :: Secondary` до 2.36 млн yields/s. На снимке через 74.3 s CPU time составлял PhysX 58.15 s и Secondary 44.96 s.
- В снимке на 30 s `Audio Render` и `main thread` оба ждут mutex, owner которого — `uEngine :: Secondary`. Это прямой механизм starvation аудиопроизводителя и основного потока.
- AAudio запрашивает 240 frames / 5 ms. Аудиоочередь имела 4.0 блока в среднем в начале; позже:
  - callbacks 10000: 544 underruns, 2714.9 ms zero-padded;
  - 12000: 78 underruns, 389.4 ms;
  - 14000: 133 underruns, 665.0 ms;
  - 18000: 293 underruns, 1462.8 ms;
  - 20000: 169 underruns, 844.1 ms;
  - 22000: 747 underruns, 3731.2 ms.
- Callback 24000: 2000 underruns / 10000 ms совпадает с явным `audio suspended (background / interruption)`; это не считаем обычным игровым underrun.
- Frame interval p50 около 33.33 ms (present interval 2 / примерно 30 FPS). На frame 1294 `submit+present` занял 1177.5 ms при GPU 1.4 ms; на frame 1707 — 788.1 ms при GPU 1.4 ms. Это отдельные задержки presentation/driver/Surface, а не время выполнения GPU. В некоторых других длинных кадрах submit+present был быстрым, что дополнительно указывает на starvation/блокировку.
- Появляются повторные `[vk] [alias] stale read` для 1280x720 sampled texture и перекрывающей её 640x360 render texture. Это отдельная графическая hazard-сигнатура; не объявляем её причиной аудио, требуется отдельная проверка захватом кадров.
- NVN verbose logging генерировал повторяющиеся per-call `DeviceGetInteger` сообщения; для Metro это лишняя нагрузка на log I/O.

### Изменено в исходниках
- `apply_patches.py`: добавлен опциональный `DM_YIELD_PROGRESS_LIMIT` для progressing yields. Он учитывает частоту отдельно на каждом guest thread; после лимита применяет короткий nanosleep и отмечает thread как sleeping. По умолчанию выключен — другие игры не меняют поведение.
- `ngrhost.c`: только для стабильного Metro Game ID `9383b4fd4e8540ed5d6e`:
  - включён QoS mapping с edges `42,58`, чтобы игровые guest threads priority 43 были User-Initiated, а не User-Interactive;
  - `DM_YIELD_PROGRESS_LIMIT=50000` в секунду;
  - `DM_YIELD_PROGRESS_SLEEP_US=50`;
  - verbose `DM_NVN_LOG` и filesystem trace отключены; frame timing и watchdog aggregates сохраняются.
- AAudio callback period, sample rate, AudioOut queue layout и producer locking пока не менялись: лог указывает на starvation выше по цепочке, а увеличение буфера без исправления владельца mutex лишь маскировало бы причину.
- Payload manifest version увеличен до 175; SHA-256 `apply_patches.py`: `7c97388ea6eaf97f4071afbb7471e98fe3e6974eed8e8a66a0e4cce8180e2069`.

### Коммиты
- `d2a86c38451326f4f92b86b571d3ac24ab693ebd` — Add per-game guard for pathological yield storms.
- `39f360c12da36aa21fbf866063896cfd15678618` — Apply Metro 2033 CPU yield guard.
- `0ca1a7d71dda5e2f8754122e79c0f467be442dd9` — Clamp invalid yield limiter configuration.
- `15cf9991fe19dd21db7e5cb61aa19749e0041488` — Disable verbose traces for Metro 2033.
- `0e4d3cc35086779d5aafa98665748f1ab6065fbb` — Update payload manifest for Metro scheduler guard.

### Проверки и ограничения
- Источник pinned Porter: `shirai91/nx2android` commit `468937822219a56eb81da1aa2e40f05e8c453af2`.
- CI patch validation и APK build ещё должны подтвердить, что новый патч применяется к Porter и Android C-код собирается.
- Rate limiter — адресный workaround по наблюдаемой Metro-сессии, не доказательство устранения всех зависаний. Нужен A/B запуск на устройстве.
- Длинные Vulkan present stalls и stale texture aliases остаются отдельными пунктами для повторной проверки после снижения CPU starvation.
- APK не публиковать до успешного GitHub Actions run и проверки artifact.

### Следующие шаги
1. Проверить GitHub Actions для HEAD `0e4d3cc35086779d5aafa98665748f1ab6065fbb`: Python syntax, patch validation/idempotency, manifest, CMake/NDK build, APK artifact.
2. Установить APK и запустить Metro в том же месте/сцене; проверить responsiveness Android UI.
3. Сравнить watchdog yield rate (цель — убрать миллионы yields/s), AudioOut underruns/queue depth, frame p95/p99 и presentation stalls.
4. Если звук продолжает заикаться, снять новый gameplay log с Metro profile; не включать verbose NVN/FS trace в обычном A/B.
5. Если `submit+present` продолжит превышать 100 ms при низком GPU time, отдельно исследовать `vkQueuePresentKHR`, BufferQueue/SurfaceFlinger и очередь presentation.
6. Отдельно исследовать texture alias stale reads (1280x720 ↔ 640x360) с pass/frame capture; пока не менять alias eviction без доказательства неверного содержимого кадра.


### Дополнение — исправление payload manifest
- CI patch validation подтвердил, что новый Porter patch применяется к upstream `e9bd2b764608facf841e39292d868ee657eaf634` и повторный запуск patch script идемпотентен.
- Run `45658097886` для commit `0e4d3cc` показал, что SHA `apply_patches.py` `7c97388ea6eaf97f4071afbb7471e98fe3e6974eed8e8a66a0e4cce8180e2069` совпадает с `tools/make_manifest.py`; failure был только из-за отсутствующей завершающей LF.
- Промежуточный commit `00a63e1b2769c3ac4f1bd851ede6a11bd5d42f1b` с неверным ручным SHA заменён корректным manifest.
- Commit `1e75ad6039aa142f3dadee93f1aa4f79e8a46ff1` добавил лишнюю пустую строку; финальный commit `8688b4ccb4204513d7da9402e20ecb5f48a6bc5d` нормализовал файл ровно до одной завершающей LF.
- Следующий CI run должен подтвердить manifest и продолжить APK build; APK пока не подтверждён.


## 2026-11-25 — Metro 2033 Redux: avoid sleeping inside contended guest locks

### Уточнение по новому логу
- Подтверждён Game ID 9383b4fd4e8540ed5d6e, Title ID 0100D4900E82C000.
- На watchdog snapshot около 30 s Audio Render и main thread одновременно ждут mutex, owner — uEngine :: Secondary (0x100f). Это прямее указывает на задержку владельца mutex, чем общая гипотеза о недостаточном AAudio буфере.
- PhysX simulator (0x1010) и Secondary (0x100f) имеют guest priority 43 и выполняют 2.9M / 1.7M SleepThread(0) вызовов в секунду. Upstream fast path для progressing yields возвращает управление без host scheduling point.
- В NVN trace обнаружено, что DM_NVN_LOG=0 всё равно включает OLOG: upstream использовал getenv("DM_NVN_LOG") != NULL, то есть любое непустое значение, включая "0", считалось включённым. Это объясняет повторяющиеся per-call DeviceGetInteger сообщения несмотря на настройку выключения.
- Vulkan submit+present достигал 1177.5 ms при GPU 1.4 ms; это отдельный CPU/Surface presentation stall, вероятно усиливаемый starvation, но не доказанная первопричина аудиопроблемы.

### Изменено
- apply_patches.py:
  - Добавлен name-based QoS override только для uEngine :: PhysX simulator и uEngine :: Secondary: эти два worker thread работают с Utility QoS.
  - Основной и аудиопотоки priority 43 остаются User Interactive. Существующий ArbitrateLock QoS inheritance повышает владельца mutex до класса ожидающего потока, пока тот не освободит lock.
  - Metro progressing-yield guard больше не делает nanosleep(50us) на каждом yield сверх лимита: это могло искусственно удерживать mutex дольше. После 50k progressing yields/s выполняется sched_yield() один раз на каждые 256 дополнительных yield-вызовов.
  - DM_NVN_LOG теперь трактует "0" как выключено, пустое значение как выключено, а ненулевое значение как включено.
  - Scheduler profile повторно применяется в front_android.c после чтения env.txt, поэтому сохранённый пользовательский env-файл не отменит защиту Metro.
- ngrhost.c задаёт Metro edges 44,58, список двух worker names и новый cooperative handoff. Общая политика для остальных игр не меняется.
- Payload manifest обновлён до версии 175 с актуальным SHA-256 apply_patches.py: a66635c3556d27fd9337e3561a30520a625789bc2664656b780e1f53842467b4.

### Коммиты
- 514298e3aa810ce68aa015e00f0facc8d5ca5813 — Improve Metro worker scheduling and disable NVN log flood
- 7f97db0fcfb628db5c2cf5747574807a662d85c6 — Configure Metro worker QoS and cooperative yield handoff
- e888f5d35096cae8278c0f6a9cadda486f91108a — intermediate manifest update (version bump corrected)
- 197ad30311dc5a8e992c2880cb824d0800036a8e — Keep payload version while refreshing Metro patch hash

### Проверки / статус
- Porter patch validation на pinned source 468937822219a56eb81da1aa2e40f05e8c453af2 прошла; повторный запуск patcher подтвердил идемпотентность всех новых patch blocks.
- Первая manifest CI проверка выявила только ошибочное увеличение version с 175 до 177; hash apply_patches.py совпал с вычисленным CI SHA. Version возвращён к 175.
- GitHub Actions run 45660491976 для code HEAD 197ad30311dc5a8e992c2880cb824d0800036a8e завершился success: Python tests, Porter patch validation + idempotency, WebView JS, manifest check и signed Release APK build прошли. Artifact nx2android-apk ID 15044364571, 35,857,049 bytes, SHA-256 4f48814f15f09df852f3344e6ac16ba306f81fe4ec9c0157b6bdb2519a8c82e6; archive https://api.github.com/repos/Snap888/nx2android-android-port/actions/artifacts/15044364571/zip (expires 2027-02-23).
- APK готов для тестирования; исправление пока не подтверждено на устройстве. Важно: обновление APK само по себе не заменяет уже существующий data-pack libdmhost.so. Новый Porter runtime patch попадёт в Metro только после повторной сборки/рекомпиляции Metro из исходного NSP/XCI (отдельного runtime-only rebuild для существующего data pack пока нет). CI проверил patch application/idempotency и собрал APK, но не компилировал сам patched Porter runtime C-код на устройстве. После повторной сборки нужен A/B запуск: сравнить yield rate двух worker threads, AudioOut underruns/queue depth, Android UI responsiveness и p95/p99 frame time.
- Не менялись AAudio callback period, AudioOut QMAX/queue semantics и Vulkan texture aliasing. Presentation stalls и stale texture alias warnings остаются отдельными задачами, если сохранятся после снижения CPU starvation.

### Следующие шаги
1. Дождаться CI на commit 197ad30311dc5a8e992c2880cb824d0800036a8e и проверить APK artifact.
2. Установить APK, запустить Metro в той же сцене и проверить, что лог содержит DM_YIELD_PROGRESS_LIMIT, DM_QOS_UTILITY_NAMES / Metro scheduler marker, а per-call DeviceGetInteger не спамит при DM_NVN_LOG=0.
3. Сравнить аудио underruns, queue depth, watchdog CPU time двух worker threads и отклик Android UI.
4. Если submit+present остаётся >100 ms при GPU <5 ms, отдельно исследовать Vulkan queue present / Android BufferQueue; если stale alias reads сохраняются — записать A/B кадры и проверить alias lifetime.
## 25.11.2026 — Metro 2033 Redux: audio ABI и starvation игровых потоков

**Свежие доказательства из Logs:**
- Gameplay log от 25.11, сессия 21:23:58–21:26:38.
- uEngine :: PhysX simulator: до 2,112,630 progressing yields/s; около 28,53 с CPU за 30 с.
- uEngine :: Secondary: до 2,105,423 progressing yields/s; около 24,45 с CPU за 30 с.
- Аудиовывод: при 10 000 callback зафиксировано 1 966 underruns из последних 2 000 интервалов и 9 829,4 мс zero-padding; ранее 620/2 000 и 332/2 000.
- Кадры доходили до 422 мс, 1,8 с и 5,44 с при GPU около 0,4–0,5 мс; один кадр тратил 389,5 мс в submit+present. Это указывает на CPU/thread starvation и ожидание present, а не на тяжёлую GPU-работу.
- Android Looper фиксировал задержки доставки 2,8–14,5 с.
- Отдельный Logs/1 — это не gameplay logcat, а лог неудачного портирования: стадия host прошла, data pack завершился NameError: ui_font_assets is not defined.

**Найденная причина повторяющегося звука:**
- Porter описывал nn::audio::AudioOutBuffer как 24-байтовый префикс, но Metro SDK использует 40-байтовую структуру: next +0x00, data +0x08, capacity +0x10, data size +0x18, offset +0x20.
- Из-за несовпадения SDK читал data size как capacity; ресемплер Metro мог повторно отправлять каждый четвёртый блок со старым PCM примерно на 170,6 мс позади.
- Основа исправления: upstream seedds/nxnative PR #2739 (AudioOutBuffer ABI fix).

**Изменения в NGR patcher:**
- Добавлен единый aout_buf в hle.h с _Static_assert размера 40 байт и всех критичных offsets.
- hle_audio.c и hle_audren.c переведены на aout_buf; HLE-перехваты descriptor-функций удалены, их выполняет SDK.
- Обновлены host audio tests и positional initializers переведены на designated fields.
- Исправлен progressing-yield limiter: после 50 000 yields/s только два именованных Metro worker (uEngine :: PhysX simulator, uEngine :: Secondary) получают 100 мкс back-off каждые 256 excess yields. Для остальных игр/потоков fast path не меняется.
- Back-off включён только в Metro profile; текущий Utility QoS и priority inheritance сохранены.
- UI font helper теперь является обязательной зависимостью даже при NX2A_PATCH_ONLY, чтобы старый pinned Porter не доходил до data pack без ui_font_assets().

**Коммиты:**
- 273c2a47c3187fa107a0f55ed2f19d195ac4f755 — audio ABI + named-worker yield back-off + UI helper dependency.
- 87c1c412173b3cd2545f3f0f4f46b7cca6efc0d0 — payload manifest version 176; SHA-256 apply_patches.py 6edd99149aedd617b18db3623b0edd63b17f734fb6bd9cb4ca18083c1dd2eb58.

**Важное ограничение проверки:**
- Новый APK обновит patcher, но уже установленный Metro data pack содержит старый libdmhost.so. После установки APK Metro необходимо повторно портировать/пересобрать из исходного NSP/XCI, чтобы новый AudioOut ABI и scheduler попали в игровые native libraries.
- Исправления ещё не подтверждены на устройстве. Не считать повтор звука, зависания или underruns устранёнными до A/B теста.

**Следующие шаги:**
1. Проверить CI: patcher должен примениться к pinned Porter и пройти повторный idempotency run.
2. Проверить, что host native compile и APK build проходят; если нет — исправить ошибки по логу CI.
3. Установить APK и повторно портировать Metro.
4. Снять gameplay log и проверить, что повтор PCM исчез, а worker yield rate и аудио underruns резко снизились.
5. Сравнить p95/p99 frame time, Android Looper delivery и CPU usage до/после.
6. Если submit+present остаётся большим при низком GPU time, отдельно профилировать Android BufferQueue/Vulkan present.
### CI correction — 25.11.2026
- First CI attempt on 273c2a47 failed in the Python unit tests because the synthetic test checkout intentionally omits porter/pipeline.py; the newly forced UI-font dependency treated that as a production failure.
- Corrected the guard: skip that porter-only helper when the porter source tree is not staged in a unit test, but force it when the real Porter tree exists.
- Patch commit: 75f12caad8c3952922109247cfc80febb140bf2b.
- Manifest commit: 6b1b650993af6d702faef0640666587f313ed573 (payload version 177; apply_patches.py SHA-256 3a676be3b6c2964d6b8e0226a99b9251616b82ad20ca7e3df628d1c2e24d8b33).
- Re-run validation against this exact branch head is still required; do not use the failed/cancelled earlier run as validation.
### Patcher execution-order correction — 25.11.2026
- Audit of the first patch-set verification showed the new AudioOutBuffer and named-worker patches had been appended after the terminal sys.exit, so that verification only exercised the pre-existing patch set. They are now moved before sys.exit and will execute.
- The audio patch block skips only when the Porter source tree is absent in a synthetic unit-test fixture; real Porter checkouts still receive all ABI edits.
- Active patcher commit: ef7864cf306ec28286b7a40bfa13b7c4e753a656.
- Payload manifest commit: e51d319ea4d4cd7ac4a7c19bf3642e4fb065d2ea (version 178; apply_patches.py SHA-256 29659d71d890ece1014f6d93a9810a9089c37b49030b56c2b6357bb618d660a3).
- Previous "Verify NGR patch set" success is not evidence for these new patches; require a fresh run on this exact manifest commit and inspect that it prints NGR AudioOutBuffer ABI and NGR named-worker back-off as applied.
### Payload manifest canonicalization — 25.11.2026
- The next CI run confirmed all new patches apply to the pinned Porter and are idempotent, including the 40-byte AudioOutBuffer changes and named-worker 100us back-off.
- That run stopped only at manifest verification: payload versions are intentionally odd and the canonical writer uses json.dumps(indent=1). The previous hand-written manifest used even version 178 and two-space indentation.
- Corrected to version 179, one-space canonical indentation, and the exact SHA-256 of apply_patches.py.
- Manifest commit: df527a58ff468ba956381a5ef20015c443eb27e5.
- Await a fresh CI run on the exact latest branch head before treating the APK as built.

## 2026-11-25 — Сетевая активность: offline-first и аудит HTTP

### Найденные источники лишней сетевой активности
- porter_sync.sync() вызывался из need_porter() перед Inspect и другими командами Porter. При porter_track=main он каждый раз запрашивал upstream HEAD через GitHub API, даже если локальный Porter уже был полностью установлен и пропатчен.
- Фоновый auto_porter() стартовал через 60 секунд после запуска GUI и затем каждые 6 часов проверял upstream; при смене SHA мог скачать архив Porter.
- auto_update() запускал OTA-проверку через 20 секунд после старта и затем каждые 6 часов.
- GET /api/library автоматически запускал поиск обложек Nlib для игр без локальных изображений. Ошибочные ответы могли повторяться после перезапуска, потому что retry backoff был только в памяти процесса.
- При отсутствии или несовпадении кеша prebuilt .NET tools и NDK действительно могут скачиваться при подготовке рекомпиляции; эти загрузки не следует путать с фоновым polling.

### Исправления в ветке
- porter_sync.sync() теперь сначала проверяет локальный stamp .nx2a_sha + .nx2a_patched + SHA patcher. Если кеш валиден, возвращает porter cache ...; no network check без обращения к GitHub.
- need_porter() для Inspect/analysis/recompile использует только локальную проверку и больше не делает повторный patch pass поверх уже валидного stamp.
- Автоматические OTA и upstream Porter polling отключены при старте GUI. Проверки и обновление остаются доступны вручную через Update и Setup → Update / repair porter.
- Переключение Porter mode и ручной Repair выполняют принудительную сетевую проверку, поскольку это явное действие пользователя.
- Автопоиск Nlib обложек при открытии библиотеки отключён; загрузка обложек остаётся только по кнопке Covers. Убран и стартовый цикл локального polling обложек при каждом открытии библиотеки.
- Добавлены network_log.py и sitecustomize.py: Python HTTP-запросы записывают метод, хост/путь, HTTP status, отправленные/полученные байты, длительность и ошибку. Значения query-параметров редактируются, чтобы не записывать токены.
- Журнал: /sdcard/Switch/nx2android-network.log, ротация при 2 MiB; события также идут в stderr/общий системный журнал. PYTHONPATH наследуется дочерними Python-процессами Porter.

### Ограничения и проверка
- HTTP-аудит покрывает Python urllib-запросы launcher/Porter/tools и их дочерних Python-процессов. Он не перехватывает произвольный native socket traffic и внешние процессы вроде apt/pip; их нужно отдельно сопоставлять с Android per-app data usage, если после патча останется необъяснимый трафик.
- Пока не подтверждено на устройстве: требуется CI build, затем тест с включённым интернетом — открыть библиотеку, выполнить Inspect, начать анализ/рекомпиляцию и проверить, что до ручных Update/Repair/Covers в журнале нет фоновых HTTP-запросов.
- Если рекомпиляция всё ещё загружает инструменты, [NET]-строки покажут конкретный URL, объём и длительность. Сопоставить их с сообщениями prebuilt / fast_tools / Porter в логе задачи.

## 2026-11-25 — Metro: анализ нового зависания и исправление yield-классификации

### Что показал свежий gameplay log
- Аудио ABI-повтор/дублирование пользователь считает исправленным. Однако во время полных зависаний runtime всё ещё заполняет аудиовыход нулями: отдельные окна дают 1,889–2,000 underruns из 2,000 callbacks. Это выглядит как следствие остановки игрового producer, а не доказательство возврата старой ошибки AudioOutBuffer.
- `uEngine :: PhysX simulator` и `uEngine :: Secondary` продолжают вызывать YieldThread примерно 0.59–0.79 млн раз/с. Примеры watchdog: 585,224/s, 788,607/s, 763,804/s, 786,795/s.
- В снимке на ~138 с: PhysX накопил 40.58 CPU-секунд, Secondary — 32.67 CPU-секунды. Это значительная постоянная нагрузка двух worker threads.
- Кадр 694: 43.53 s total, 35.69 s в submit+present, GPU всего 143 ms. Кадр 693: 31.61 s total при 42 ms submit+present и 0.4 ms GPU. Значит, это не обычная shader/GPU saturation; длинные блокировки/планировщик guest threads и GPU-submit/present synchronization остаются главными направлениями.
- Android Looper сообщил Slow delivery 5.115 s; audio clock сообщил DSP timestamp ~64 ms late. Это согласуется с системной деградацией под нагрузкой.
- Vulkan отдельно выдаёт растущий диагностический счётчик `index ranges across a memory pool chunk's end` (1, 2, 4, ... 1024). Это отдельный подозрительный сигнал; пока не объявлять его причиной CPU-spinning без трассировки места чтения/записи.

### Корневая ошибка в текущем scheduler patch
- Проверен именно pinned Porter commit `468937822219a56eb81da1aa2e40f05e8c453af2`: `thr_t` хранит только один `yrun_sig`, а `thr_yield()` считает прогрессом любой yield, у которого x19–x28 отличаются от непосредственно предыдущего yield.
- Цикл, который чередует два состояния регистров A/B/A/B, поэтому ошибочно классифицируется как бесконечный прогресс. Он обходит штатный `yield_for()` backoff. Текущий 100-us sleep раз в 256 excess yields — только слабый предохранитель и не устраняет ошибочную классификацию.
- Добавлен патч `NX2A_YIELD_TWO_SIG`: хранить две последние сигнатуры, считать yield прогрессом только если он отличается от обеих. Настоящие рабочие циклы с новым третьим состоянием продолжают проходить fast path; повторяющийся A/B poll loop начинает использовать штатный 2-ms → 250-us backoff.
- Добавлен unit test патча на точные строки pinned Porter и проверку идемпотентности.

### Что ещё не доказано
- Новый yield patch пока не проверен на устройстве; требуются CI, APK, повторная рекомпиляция Metro (чтобы новый libdmhost.so попал в data pack) и A/B измерение.
- Нельзя пока утверждать, что исправлена причина 35.69-секундного submit/present stall. После снижения yield rate нужно проверить, исчезает ли этот stall; если останется — снимать GPU queue/fence/present wait owner отдельно.
- Отдельно исследовать `[vk] index ranges across a memory pool chunk's end`: проверить вычисление range end, chunk boundary, и fallback/copy path. Не менять memory bounds вслепую.

### Проверка после сборки
1. Повторно портировать Metro с новым APK.
2. Снять 2–3 минуты одинаковой сцены.
3. Сравнить PhysX/Secondary yield/s, CPU seconds, back-off sleeps, main-thread frame_ms, submit+present, GPU ms и Looper Slow delivery.
4. Ожидаемый результат scheduler patch: alternating A/B loop перестаёт давать сотни тысяч yield/s и начинает накапливать back-off sleeps; frame submit/present stall должен заметно уменьшиться, если он был следствием starvation.
5. Звук оценивать отдельно: дублирование/хрипы и underruns во время заморозки — разные метрики.

## 2026-11-25 — Исправление импорта data pack и диагностика Handheld display

### Импорт готовой игры из папки
- Найдена конкретная ошибка в import_precompiled_game(): _select_game_cover(existing, ...) вызывался до присваивания existing. Это давало UnboundLocalError, который не обрабатывался API handler-ом, и валидный импорт завершался HTTP 500.
- Исправлен порядок: сначала читается library.json и ищется существующая запись по game_id/пути, затем выбирается обложка и собирается запись shortcut. Повторный импорт обновляет прежнюю запись, не создавая дубль.
- Runtime/data pack по-прежнему не копируется и не пересобирается.

### Metro: зависания и нагрузка CPU
- В актуальном gameplay log видны повторные yield watchdog: PhysX simulator до 2.92 млн/s, Secondary до 2.37 млн/s, main thread около 1.96 млн/s; callsite одинаковый: sdk+0xd688c0. Это CPU busy-yield, а не GPU shader time.
- В том же log DM_YIELD_PROGRESS_* отсутствует. Следовательно, этот конкретный libdmhost.so не показывает, что Metro-specific backoff из новых Porter patches был включён. Патчи Porter не меняют уже собранный data pack автоматически: после нового APK требуется Recompile / update для пересборки libdmhost.so.
- Пользователь сообщает, что звук сейчас чистый. Аудиоподсистему в этом изменении не трогал; аудио нужно считать отдельным уже улучшенным направлением, но оставлять underrun counters в следующем A/B log.

### Handheld / Docked и 1280x720
- Свежий gameplay log фиксирует VI layer 1920x1080, crop 1280x720, Android window 2448x1080 и swapchain 1080x2448 с pre-rotation. По текущему aspect-fit алгоритму 1280x720 должен масштабироваться до 1920x1080 и центрироваться с боковыми полями x=264 px в окне 2448x1080; код не должен рисовать 1280x720 пикселей в левом верхнем углу.
- Поэтому пока не меняю aspect ratio на принудительное растяжение: это исказило бы 16:9 картинку на широком экране и могло бы скрыть настоящую ошибку surface/viewport.
- Добавлен малозатратный [display] trace, который пишет только при изменении геометрии: guest image, crop, Android window, swapchain target и рассчитанный destination rect. Это покажет, на каком этапе размеры перестают совпадать.
- Для точного исправления нужен свежий лог после переключения в Handheld и Docked на одной и той же сцене; особенно строки [display], [vk] swapchain и vi::CreateLayer/SetLayerCrop.

### Статус
- Import bug исправлен в source.
- Display geometry tracing добавлен в Porter patcher.
- APK/CI и повторная рекомпиляция на устройстве ещё не проверены.

## 2026-11-25 — Metro scheduler v2 и Handheld fullscreen

### Metro 2033 Redux: зависания и CPU
- Повторно разобран актуальный gameplay log: PhysX simulator до 788,607 YieldThread/s, Secondary до 763,804/s; main thread также выполняет около 1.96 млн yield/s и в snapshots владеет mutex, на котором ждёт Audio Render. В другом snapshot Secondary ждёт mutex владельца main thread. GPU на одном из длинных кадров 0.4 ms, тогда как whole frame 31.6 s; это не GPU-bound stall.
- Runtime log показывает app-side '[scheduler] Metro 2033 guard enabled', но не показывает marker из patched Porter '[scheduler] Metro patch v2' / DM_YIELD_PROGRESS_LIMIT. Значит активный libdmhost.so не подтверждает наличие последних Porter yield patches; одних изменений APK недостаточно для уже собранного data pack.
- Исправлен Metro profile в Porter: после порога 50k progressing yields/s named back-off применяется к PhysX, Secondary и main thread; добавлен DM_YIELD_BACKOFF=250:500 для non-progressing yield loops, чтобы A/B polling loop main thread попадал в обычный back-off раньше. Только Game ID Metro 2033 Redux.
- Добавлен новый runtime marker '[scheduler] Metro patch v2'. После повторной рекомпиляции его отсутствие означает, что используется старый/непропатченный libdmhost.so. Не считать фиксом до device A/B подтверждения.

### Handheld 1280x720 и fullscreen
- Android NgrGameActivity теперь скрывает status/navigation bars в immersive sticky режиме и разворачивает content под system bars; окно должно занимать всю панель, а не только inset content rect.
- Vulkan present: Handheld (DM_OPMODE=0) растягивает guest 1280x720 на полный ANativeWindow surface; Docked сохраняет aspect-fit. Это убирает маленькое изображение в левом верхнем углу и заполняет панель; Handheld stretch может слегка менять геометрию 16:9 на широком дисплее.
- Сохранён change-triggered [display] trace для guest/crop/window/swapchain/destination geometry.

### Импорт готовой игры
- Ранее исправлен UnboundLocalError в import_precompiled_game(): existing теперь находится до _select_game_cover(). CI уже проверил syntax, manifest и сборку APK в run 45698896569.

### Проверка
- Нужна установка свежего APK и Recompile/Update Metro data pack. После этого в runtime/gameplay log проверить '[scheduler] Metro patch v2' и 'DM_YIELD_PROGRESS_LIMIT'. Сравнить yield/s, CPU seconds, main-thread mutex waits, longframe и Audio Render underruns.
- Проверить Handheld и Docked на одной сцене; ожидание: Handheld window/surface full-screen, destination 0,0 width,height; Docked aspect-fit centered. APK пока не подтверждает реальное поведение на устройстве.

- Follow-up correction: keep Utility QoS limited to PhysX/Secondary; include `main thread` only in the Metro named yield back-off list (it must retain interactive QoS). Payload version 195 refreshes the patcher manifest.


## 2026-11-26 — Handheld final-surface fix and Android RomFS lookup stalls

### Handheld image output
- Previous full-screen override was applied before the ov_band() calculation. When the gamepad overlay was visible, that later calculation could replace the full-surface destination; the earlier patch therefore did not guarantee full-screen output.
- Added a final Handheld override after all overlay-band geometry is calculated and immediately before vk_pic_set() / present blit. Handheld now forces destination (0,0,g_sext.width,g_sext.height) regardless of overlay visibility; Docked keeps aspect-fit.
- The guest crop/render dimensions remain unchanged (for example 1280×720); only the destination rectangle changes.
- Display diagnostics now include mode=handheld|docked, full destination x/y/width/height, swapchain target and overlay visibility.

### Metro 2033 Redux: reduce synchronous RomFS lookup stalls
- Audited pinned Porter source nxnative/dm/host/hle_fs.c. Read-only RomFS path resolution enumerated directory entries to resolve each component; the first lookup also built a sorted directory index while callers held the global PATH_LOCK.
- That lock serialized unrelated filesystem operations. A first lookup into a large asset directory could therefore pause other loader threads and audio asset opens, matching the observed pattern of long location/asset-loading stalls more closely than a GPU bottleneck.
- Android app-private/external RomFS is case-sensitive. Added an Android-only exact lstat(parent/name) fast path for read-only mounts, bypassing directory enumeration and lazy index construction. Writable save mounts and non-Android builds retain their existing behavior.
- Added one-time marker: [fs] Android RomFS lookup v1: exact path lookup; serialized directory scans/index builds bypassed. This does not add worker threads or per-file logging.

### Проверка / статус
- Patcher changes are committed; payload manifest bumped to version 196 and SHA-256 refreshed.
- CI must validate the new patches against the pinned Porter, compile the Android C sources and produce a signed APK before device testing.
- After installing the APK, Metro's data pack must be recompiled/updated so its libdmhost.so contains the new filesystem and display patches.
- Expected Handheld log: mode=handheld destination=0,0 <full-window-width>x<full-window-height>; Docked should report mode=docked and centered aspect-fit.
- Expected Metro marker: [fs] Android RomFS lookup v1. Compare long-frame duration, file-open/read timing, yield rates and audio underruns against the previous build. Audio code was not changed.


## 2026-11-26 — Handheld final blit and Android save-clone optimization

### Handheld output: final Vulkan blit guard
- The previous v2 patch forced dx/dy/dw/dh before constructing VkImageBlit. Added a second guard directly on the actual blit's dstOffsets, immediately before vkCmdBlitImage.
- In Handheld (dm_opmode()==0), the actual transfer destination is explicitly (0,0) → (g_sext.width,g_sext.height) on every present. Docked keeps the original aspect-fit destination.
- Added change-triggered [display-blit] diagnostics with mode, window extent and final Vulkan destination. This distinguishes a wrong calculated rect from a later surface/rotation issue.
- Guest crop/source resolution is not changed.

### Metro 2033 Redux: checkpoint commit stalls
- Audited pinned upstream darwin_compat.c: Android's clonefile() recursively walks directories and copy_file() copies every file through a 64 KiB read/write loop. It does not use copy-on-write.
- Audited hle_fs.c: nn::fs::Commit invokes clonefile(work, .new) synchronously inside commit_mount_locked() while the caller holds both global PATH_LOCK and the mount lock. The operation can therefore block unrelated game file operations during a checkpoint.
- Added Android FICLONE attempt per file. Filesystems that support reflinks get a copy-on-write clone; unsupported filesystems keep the existing byte-copy fallback. The first attempt logs one of:
  - [fs] Android save clone: FICLONE copy-on-write enabled
  - [fs] Android save clone: FICLONE unsupported (errno=...); byte-copy fallback active
- Existing save commit #... (clone + swap ... us) timing remains the authoritative duration measurement. This change does not add threads or weaken save atomicity.
- Limitation: if the device's /data filesystem rejects FICLONE, the fallback still copies bytes while Commit holds the global locks. A per-mount lock/snapshot redesign would then be the next step; do not make it without measuring correctness and lock ordering.

### Validation / status
- Exact patch anchors were checked against pinned Porter 468937822219a56eb81da1aa2e40f05e8c453af2: compat include, copy_file() and Vulkan VkImageBlit anchors each occur exactly once.
- Payload patcher updated; payload version bumped to 198 and apply_patches.py SHA-256 refreshed.
- CI build and on-device test are still pending. No APK from these changes is confirmed yet.
- After installing a new APK, recompile/update Metro's data pack so the newly patched libdmhost.so is actually used.
- Compare save commit duration and FICLONE marker against the previous build; also verify Handheld [display-blit] mode=handheld ... dst=0,0-<window width>,<window height> over multiple consecutive frames. Confirm Docked remains aspect-fit.
- Audio pipeline remains untouched.

### Next actions
1. Wait for/inspect GitHub Actions build; resolve compile or patch-anchor failures before distributing an APK.
2. Install APK and rebuild Metro data pack; test the same checkpoint transition and record save commit duration.
3. Test Handheld over at least 30 seconds, including after overlay/menu visibility changes; if the final blit log stays full-size but the displayed image shrinks, inspect swapchain transform and Android surface lifecycle rather than repeating the destination-rectangle patch.


## 2026-11-26 — Metro 2033 Redux log analysis and second scheduler/save fix

### Log evidence (game ID 9383b4fd4e8540ed5d6e)
- Runtime log: Logs/ngr-runtime-9383b4fd4e8540ed5d6e.log.txt
- Gameplay log: Logs/ngr-gameplay-9383b4fd4e8540ed5d6e.log.txt
- RomFS direct lookup v1 is active, but the save clone FICLONE marker is absent.
- Save mount fails before gameplay: clonefile(save → save.work) returns EACCES (errno=13), then the runtime mounts the committed save read-only. Thus this run does not demonstrate a slow checkpoint commit; it demonstrates that the save transaction could not even be initialized.
- Root cause in Android darwin_compat.c clonefile(): directory clones used the source directory's exact mode for mkdir(dst). A read-only committed save directory (e.g. 0555) creates a read-only work directory, so the first child creation fails with EACCES. File clones could also preserve a non-writable mode.
- Runtime freeze is independently demonstrated as CPU-side: frame 913 = 1642.3 ms total / 17.9 ms GPU; frame 915 = 14036.9 ms total / 17.6 ms GPU, with about 12.84 CPU-seconds charged to the process. No shader/pipeline creation or texture upload occurred during these long frames.
- Repeated watchdogs report 660,968–723,053 progressing yields/s in PhysX simulator, 445,137/s in Secondary, and 250,259/s in main thread. Scheduler v2 only called sched_yield once per 256 excess yields, which did not meaningfully throttle pinned workers.
- Audio underruns are downstream symptoms: at the end, 2,000/2,000 callbacks had zero queued blocks. Audio implementation is deliberately unchanged.

### Fixes committed
- Commit 6aaeee8d0619e853e4e811a7ab53cd41e07b15af: added owner-writable mode to cloned save directories/files. clonefile() now adds owner rwx to destination directories and owner rw to files, while preserving other mode bits. This allows a writable transactional work tree even if the committed source is read-only.
- Commit 25f59a11ce0cacc7021af70e1589e6fa142878a3: removed a superseded intermediate scheduler patch that had an incompatible anchor.
- Commit 746774e0f137ba4304bbc1bc7e01c26a5ac92458: add per-yield cap patch; once the configured 50,000 progressing yields/s per-thread budget is exceeded, named Metro workers use the configured 100 µs sleep on each further progressing yield instead of one sched_yield per 256 excess yields. The sleep applies only to the named PhysX simulator, Secondary and main thread. This is a targeted CPU/thermal mitigation; it may trade some worker throughput for stable scheduling and must be measured.
- Commit 4608260f42f00f944f99b09059a3e584fb09e051: payload version 200; apply_patches.py SHA-256 refreshed to 5ee1f95d4a01515aebf9fb63e6c22db552b88c01cabd31c57b0ad40054cf3bd9.

### Validation / limitations
- Log analysis confirms the current build has the filesystem direct-lookup patch and scheduler v2, but not enough evidence that FICLONE code was invoked (empty save directory can produce no copy_file marker).
- New source patch anchors have not yet been run through a complete NDK/CI build. CI and real-device validation are pending; no APK is claimed.
- After a new APK, rebuild/update Metro's data pack to regenerate libdmhost.so.
- Verify save mount logs no longer show EACCES/read-only fallback; exercise a save write and checkpoint, then confirm save commit success.
- Verify watchdog rates fall substantially and the same checkpoint/location no longer produces 1.6s/14s CPU frames. Check thermal status and audio queue depth after scheduler change.
- If the named workers still burn CPU, next step is symbolicate sdk+0xd688c0 and inspect exact guest loop / lock protocol before more aggressive scheduling changes.

### Next actions
1. Validate patcher anchors and compile/CI build; correct any patch application or NDK errors.
2. Install APK, rebuild Metro data pack, verify save mount is transactional and writable.
3. Re-test the same gameplay path; compare long-frame CPU/GPU split, watchdog yields/s and audio underruns.


### CI correction — 2026-11-26
- First validation run for commit 6aaeee8 (Actions run 45855256664, job apk) failed in "Verify NGR patch set against the pinned porter", before native compilation. It identified two patch-anchor issues in the new save-permission and yield-cap edits.
- The yield-cap patch was subsequently simplified to a condition-only replacement after patch 25's named-worker wrapper; the superseded incompatible patch block was removed.
- The save-permission patch anchor was corrected to match the exact post-FICLONE copy_file tail (the close/read errno handling is on one source line).
- Latest patcher correction commit: 4a536f052e8792e9f7f4b3399bd84d7c5cd7e97c.
- Payload manifest correction commit: 85b02a755829d0d5f9da35aff314f58cd4e5ed74; payload version 202; apply_patches.py SHA-256 7e3769f7ba5a9e668fbdbe903771ee2ebde0bd40bc74e402f96b2a1a1cae3bba.
- Latest CI status must be checked on the version-202 manifest commit. Do not use earlier failed/cancelled runs as proof of build success.


### CI fix — reflink patch idempotence — 2026-11-26
- Diagnosed run 45855491169: patch-set verification passed on first application, then failed on the idempotence pass. Patch 32 rewrote copy_file() but did not leave its declared marker; patch 34 subsequently altered that same function, so the generic replacement-verification fallback could no longer match the complete replacement block.
- Fixed patch 32 by embedding its explicit NX2A_ANDROID_REFLINK_CLONE marker beside the FICLONE state declaration. Patch 34's writable-mode edit does not touch this marker. The second patcher invocation can now recognize the already-patched source and skip safely.
- Updated payload manifest hash refreshed from the authoritative CI manifest generator output (version remains 202; apply_patches.py SHA-256 e74998702e142e36bc7868487d05d648311b7145ea3f5baedc8d2e2ac96722e8).
- CI run 45855491169 failed before native compilation; no APK from that run is valid. Await a fresh run for patch-set validation, native compilation, and artifact upload.

- Follow-up CI run 45856075092 confirms the patch-set verification now passes on both applications. It then caught a stale payload hash; the manifest is corrected to the exact SHA-256 emitted by `tools/make_manifest.py` (version 202, no unnecessary version bump).


## 2026-11-26 — Latest Metro Redux gameplay log / CPU stall follow-up

### New evidence from Logs/ngr-gameplay-9383b4fd4e8540ed5d6e.log.txt
- Session 2026-11-26 19:37, game time ~528–830 s, 9,300 frames sampled. On-screen frame stats show dropped frames rising rapidly and p99 at frame 900 reaching 5,680 ms; after the severe stall window it stabilizes around 32.85 ms. Footprint grows from ~699 MiB to ~866 MiB then plateaus.
- Extreme frames with GPU time far below wall duration: frame 599 2,347.6 ms / GPU 0.4 ms; frame 858 5,395.2 ms / GPU 40.7 ms; frame 860 45,499.3 ms / GPU 38.1 ms; frame 861 5,875.6 ms / GPU 43.1 ms; frame 862 8,704.9 ms / GPU 39.9 ms; frame 863 18,424.5 ms / GPU 37.9 ms. Pipeline/shader-library creation and texture uploads are zero on these events. Frame 913 is 983.1 ms with 14.5 ms GPU.
- Named threads remain pathological: PhysX simulator 745,115–776,085 progressing yields/s, Secondary 741,440–817,728/s, main 672,695/s. Same return site sdk+0xd688c0. Thread dumps show running/not waiting, later mutex wait. CPU totals reach ~146.6 s per PhysX and Secondary thread over ~304 s elapsed. Previous 50k progressing-yield budget and 100 us setting did not stop this signature-changing loop.
- Audio is starved during the same interval: callback batches 6k–24k show 589–2,000 underruns per 2,000 callbacks, peak 100% underruns in batch 22,000 (10,000 ms zero-padded). Later recovers to zero underruns as frame pacing stabilizes. This is secondary evidence of CPU scheduling starvation; audio implementation remains untouched.
- Save initialization still fails with EACCES errno=13 and committed save is mounted read-only. The previous writable-clone patch did not fix it on-device. No FICLONE success/fallback marker appears; failure is at root clone directory before per-file copy.
- Android main looper reports slow deliveries of 23.5 s and 24.8 s, consistent with system-wide starvation.

### New source changes
- Patch 37 hard-throttles only Metro's named PhysX/Secondary/main threads at the yield SVC boundary with a 250 us sleep per yield (~4k SVC/s). This bypasses the previous progress-signature detector that allowed changing-signature loops to run at >670k/s. Other games and threads remain on the existing path.
- Patch 38 adds stage-specific clonefile diagnostics for stat/access/mkdir/opendir/recursive child failures. It is diagnostic, not another guessed permission change; the next run should expose the exact operation/path/mode.
- Payload manifest bumped to version 203 and apply_patches.py SHA-256 refreshed to 7e40347d2ebcc1f444a943e1e9b298181b0e9b021014e136e9f6071bfe76a222.
- CI patch validation/NDK build and on-device validation are pending. No APK is available yet. Install the next APK and recompile/update Metro data pack to regenerate libdmhost.so; verify the one-time hard-throttle message, named yield rates reduced to thousands/s, and the precise clonefile failure diagnostic.

- CI run 45862916716 validated patch-set application successfully, then stopped at payload-manifest verification. Its authoritative generator reported apply_patches.py SHA-256 `e5fbfe281cabc8144c4c5c549e50ea1eede99db25138135a2153980ffa00cbff`; manifest corrected in commit 6019b38, version 203. Fresh CI is pending.

- Critical discovery: appended patch blocks 36+ were below the patcher's earlier sys.exit(), so they were never executed. Moved sys.exit to the actual file end in commit 079bdd3. CI run 45863166529 now verifies all appended patches (37 hot-yield throttle and 38 clone diagnostics) successfully; it only failed on the payload hash. Manifest hash corrected to CI-authoritative 62ab1a48c8e59ad8c537884199befd557ae607194880201b175008fb78a5c16f, payload version 203, commit ca415ef.


## 2026-11-26 — SDK 8.2.0 yield-site isolation
- Identified the exact Metro SDK from the game profile/diagnostics: Nintendo SDK 8.2.0, SDK NSO build ID `3ae34e689d7a35f13cbf42bfd672af8b`; Metro game main build ID `85c362cc9790f0edf23749b041953c51`. No subsdk modules.
- SDK source patch table already contains only the two AddressRegionManager memory cuts for this SDK build (offsets 0x336b50 and 0x336bf0); these are unrelated to the observed hang. No speculative memory cut was added.
- Log stack evidence: hot worker SVC #0x0b (YieldThread) returns at `sdk+0xd688c0`; backtraces point into the game main at `main+0x1e92f4` (PhysX simulator) and `main+0x539ec` (Secondary), followed by `sdk+0x3344b8 sdk+0x338984`. The SDK address is the YieldThread SVC return stub, not proof that the SDK's implementation itself is defective. The tight polling loops are in the game-side callers.
- The latest uploaded runtime log was captured at 19:37 and still reports the old 50k/s + 256-yield handoff configuration. It predates the later successful CI build that contains patch 37, so it cannot validate or falsify that hard-throttle patch.
- Narrowed patch 37: it now sleeps 250 µs only when (a) the thread is one of Metro's named PhysX/Secondary/main workers and (b) LR resolves to the exact SDK 8.2.0 `sdk+0xd688c0` YieldThread site. Other SDK calls and other games retain the normal scheduler path.
- Next validation: rebuild APK, install it, then recompile/update Metro's data pack. Confirm the one-time `SDK 8.2.0 YieldThread sdk+0xd688c0 hard throttle` log appears and the three targeted threads' yield rate falls from ~670k–776k/s to roughly 4k/s or less. Compare CPU time, long frames, Looper delays and audio underruns.

- CI run 45866670330: Python validation and NGR patch-set verification (including the exact SDK 8.2.0 `sdk+0xd688c0` return-site guard) both passed. It stopped only at the expected stale payload SHA check; the manifest is refreshed to the authoritative `tools/make_manifest.py` digest `09858cc1c38a730fdeceb89a6dae0d5a9dc89d915a89bbc7b1156b311e66b5eb`. Native build is pending in the next run.


## 2026-11-26 — Metro SDK 8.2.0 targeted yield throttle: build verified
- Additional thread-state evidence from the 19:37 gameplay run: at ~63 s PhysX (0x1010) waited on mutex 0x712677d5dc owned by audio-I1 (0x1009); at ~64.8 s audio-I1 waited on the same mutex owned by PhysX. Later samples show the owner/wait state changing again, so this is lock hand-off contention/ping-pong, not enough evidence to call it a permanent deadlock. It supports the conclusion that the hot YieldThread loops starve or repeatedly contend with the audio worker.
- At ~80 s, PhysX had accumulated 25.88 s CPU and Secondary 18.64 s CPU; watchdog rates reached 776,085/s and 817,728/s respectively. Main reached 672,695/s. At on-screen frame 900, p99 frame time was 5,680.33 ms, dropped frames 197/298, footprint 736 MiB; thermal telemetry was unavailable (-1).
- The latest uploaded gameplay log predates the exact-site patch. The APK containing the narrowed SDK 8.2.0 site guard has now built successfully.
- CI run: https://github.com/Snap888/nx2android-android-port/actions/runs/45866775641 — all checks, NGR patch verification, payload manifest, signing, and Release APK build passed.
- Artifact: `nx2android-apk`, artifact ID `15140607937`, SHA-256 `84717a2cc5676312b99150ccdf0c04016de9ba3d898822faf6d2791efaeeb6c4`.
- Install this APK, then recompile/update the Metro 2033 Redux data pack. The new log must contain `Metro SDK 8.2.0 YieldThread sdk+0xd688c0 hard throttle`; the target yield rate should be capped near 4k/s per affected thread (actual Android nanosleep scheduling may vary). Compare frame p99/max, process CPU, audio queue/underruns, and system responsiveness.
- The save transaction still reports EACCES in the pre-patch log; the same APK also includes patch 38 stage-by-stage clonefile diagnostics so the next run can identify the exact failing save-clone operation. This remains separate from the CPU/yield hang.

## 2026-11-26 — User-visible NGR save directory

### Implementation branch
- Created `feature/metro-save-manager` from `feature/ngr-universal-library`.
- Branch base: `8f3e75958e51c5d4ab7762270faf7ccfda14e215`.

### Changes
- Added asynchronous legacy-save migration in `MainActivity.java`. The copy runs on a dedicated background-priority thread before launching NativeActivity; it does not block the launcher UI thread.
- Default public save location: `Download/NX2A/Saves/<game-id>/`.
- Existing private saves at `files/games/<game-id>/save/` are copied only when a destination file does not already exist. The private source is retained. Each file is copied to a temporary sibling, fsynced, then renamed into place. Migration marker is stored beside the per-game directory, not inside the game's save tree.
- Launcher passes `ngr_public_save_path` to NativeActivity. `ngrhost.c` validates the expected `/Download/NX2A/Saves/<game-id>` suffix and creates the directory before loading the game runtime. If unavailable, it unsets the public override and retains private-save fallback.
- Updated the NGR patcher so `front_android.c` mounts the validated public directory as `DM_SAVE`; `DM_TEMP` remains under private per-game storage.
- Added `docs/USER_VISIBLE_SAVES.md` with migration behavior and device validation steps.
- Updated payload manifest to version 205; `apply_patches.py` SHA-256: `abbec1a608301d91ecfab13072bae7e2aa62eb42435f1244e38808a5d212016b`.
- Added this branch to the APK workflow push triggers.

### Validation status
- GitHub source edits committed successfully.
- Local Gradle/NDK build was not run in this environment.
- CI must validate Python syntax, patch application/idempotence against pinned porter, native compilation, manifest hash and APK artifact.
- Device test must update/recompile the Metro data pack so its `libdmhost.so` includes the revised `DM_SAVE` mount patch. The APK alone does not replace the already-installed game's native data pack.
- This change does not claim to fix the Metro CPU hang. The latest project evidence identified pathological SDK 8.2.0 YieldThread polling at `sdk+0xd688c0`; the targeted hard-throttle build exists in the previous feature branch and must be verified on-device separately.

### Next actions
1. Inspect CI for `feature/metro-save-manager`; fix patch-anchor, Python, Java or NDK failures.
2. Install the APK and update Metro's data pack.
3. Verify runtime marker `[NGR save] using user-visible save directory`, save mount path, checkpoint write, exit and reload.
4. Compare private fallback when storage permission is denied.
5. Continue SDK 8.2.0 yield-throttle validation using fresh logs from the APK/data pack containing the hard-throttle patch.

### CI result — 2026-11-26
- GitHub Actions run: 45873462593 — SUCCESS.
- Checks passed: Python syntax/unit tests, NGR patch application and idempotence against pinned porter, WebView JavaScript syntax, payload manifest consistency.
- Release APK build and artifact upload both succeeded.
- Artifact: `nx2android-apk`, artifact ID `15142809840`, run URL: https://github.com/Snap888/nx2android-android-port/actions/runs/45873462593
- Artifact ZIP SHA-256: `e07588be1f787325f8478aba1775c8b46cd697ce784fecde239ae3fd1e892248`.
- Build commit: `a5f63a67ad81fbd861fc8cb8033129e60f9a438c`. The branch head subsequently received only a comment-only change in `ngrhost.c` (`bee018b91843fcbd9c2bf6fe7a1031279b07658c`); functional source is identical.
- Draft PR: https://github.com/Snap888/nx2android-android-port/pull/1

### Device validation still required
1. Install the new APK.
2. Recompile/update Metro 2033 Redux's data pack so its `libdmhost.so` contains the new `DM_SAVE` root patch.
3. Verify runtime log says `[NGR save] using user-visible save directory`.
4. Create checkpoint, exit, confirm files in Download, relaunch and load.
5. Upload fresh runtime/gameplay logs to verify SDK 8.2.0 YieldThread hard-throttle behavior and remaining stalls. CI does not establish device-level hang resolution.


## 2026-11-26 — Metro: restore private transactional saves, add slow-I/O tracing

### Changes
- Reverted the live `DM_SAVE` mount to `<app-private-files>/games/<game-id>/save`. Android shared Download/FUSE is no longer used for the live transaction tree; the game keeps its rename/exchange semantics on app-private storage.
- Kept `Download/NX2A/Saves/<game-id>/` as a user-visible mirror. Before launch, a public file is imported only when its mtime is clearly newer than the private copy. After NativeActivity returns, committed private saves are copied to Download on a background thread.
- Save mirror copies are staged in sibling temporary files, flushed and synced, then moved into place. No partial copy is published as a completed save.
- Cleared stale `NGR_PUBLIC_SAVE_DIR` from the native host before starting a new game, preventing a previous activity's environment override from leaking into the next session.
- Added NGR patch 40: when physical and guest filenames already match, unsupported xattr removal (`ENOTSUP/EOPNOTSUPP`) is treated as optional metadata rather than a failed file creation. This addresses the observed `errno=95` path.
- Added NGR patch 41: event-driven slow `pread` diagnostics for host reads taking at least 25 ms. The log includes fd, offset, requested/returned bytes, elapsed time and errno; normal reads do not emit per-read logs.
- Payload manifest bumped to version 206; `apply_patches.py` SHA-256: `a9e22481289ce602c13c02a031e2292dc9741161c29f553a3aad409bfd886a0e`.
- Updated workflow so pushes to `feature/metro-save-manager` force a test APK build.

### Important scope
- This corrects the confirmed external-storage save incompatibilities: the previous log showed `errno=95` during optional xattr handling and `EINVAL` during directory exchange. The updated native Data Pack must be rebuilt/recompiled for the game; APK-only installation does not replace its `libdmhost.so`.
- Audio mutex contention and Vulkan present/alias stalls are not yet claimed fixed. The current evidence shows transient lock contention and long frame gaps, but does not identify a safe lock-order change. Do not change guest mutex semantics or globally delay audio/worker threads without further evidence.
- Slow-read diagnostics will establish whether location-streaming pauses are host I/O stalls. If no slow preads align with a freeze, investigate decompression/worker hand-off and Vulkan present separately.

### Validation / next steps
1. CI run for head `c04f920e309af0714fab79794a34dec31ea38a0e`: https://github.com/Snap888/nx2android-android-port/actions/runs/45880168188 (status was in progress when recorded).
2. Confirm patch 39–41 apply cleanly and idempotently to pinned Porter, and that the native host and APK compile.
3. Install APK; recompile/update Metro 2033 Redux data pack.
4. Verify `DM_SAVE` resolves to app-private storage, save commits succeed, and no `errno=95` / `atomic swap failed errno=22` remain.
5. Exit to launcher; verify Download mirror refreshes; relaunch and load the save.
6. Capture a new gameplay log with slowframe/watchdog enabled. Correlate `[io] slow pread` events with frame stalls, audio underruns, mutex owner snapshots, and Vulkan present waits.


### CI result — 2026-11-26 save/IO fix
- GitHub Actions run: 45880168188 — SUCCESS (head used by CI: `c04f920e309af0714fab79794a34dec31ea38a0e`).
- Passed: Python syntax and tests, NGR patch application twice (idempotence), WebView JS syntax, payload manifest consistency, Release APK build and artifact upload.
- APK artifact: `nx2android-apk`, artifact ID `15146718921`, SHA-256 `296b092cf21429b6041a12587f3d0f2bb2b83ee1058b6eb4060d11f054716315`.
- Run: https://github.com/Snap888/nx2android-android-port/actions/runs/45880168188
- The subsequent `PROJECT_LOG.md`-only commit does not change APK/native code.
- CI validates that patches apply and the Android app builds. It does not compile a Metro data pack on the user's device or prove runtime save/audio/hang fixes. Recompile/update Metro's data pack before gameplay testing.



## 2026-11-26 — Metro 2033 Redux: новый разбор зависаний и QoS для видеодекодера

### Что подтверждено свежими логами
- Сессия 2026-11-26 22:26:29, game ID `9383b4fd4e8540ed5d6e`, SDK 35, ARM64, Turnip выбран из `Download/GAME/Turnip_Gen8_V37/libvulkan_freedreno.so`.
- Игра действительно использует AudioOut через AAudio: 240 кадров на callback при 48 кГц (5 мс), стартовая очередь — 4 блока.
- AudioOut queue резко истощается: callback 4000 — 1,424 underrun/2,000; 6000 — 729; 8000 — 913; 10000 — 700; 12000 — 2,000; 14000 — 1,966; 16000 — 2,000; 22000–30000 — 2,000 underrun в каждом окне. Это подтверждает, что producer не успевает подавать блоки, а не неисправность самого AAudio callback.
- Thread snapshots показывают, что `video-decoder` — заметный CPU-конкурент: 4.87 CPU-секунды примерно за первые 17 секунд и 7.05 CPU-секунды примерно за 34 секунды. В это же время AudioOut queue теряет большую часть буферов.
- SDK 8.2.0 горячий YieldThread site остаётся `sdk+0xd688c0`; PhysX/Secondary/main уже ограничиваются предыдущим hard-throttle patch. Снимки также фиксируют main/video mutex wait contention, но они не доказывают устойчивый deadlock или конкретный порядок блокировок.
- NVN frame work: p50 около 33.4 ms; p95 до 130.6 ms, max 9.27 s в окне первых 600 кадров и max 29.17 s в следующем окне. GPU p50 около 0.36–0.65 ms на ранних окнах, затем около 17.23 ms при frame 1200. NVN submit+present достигает max 1.58 s. Это согласуется с длинными CPU-side stalls и последующей GPU-нагрузкой.
- В slow-I/O diagnostics найден один `pread` длительностью 71.3 ms; в этой сессии нет признаков, что постоянное чтение с Download является основной причиной многосекундных зависаний.
- Android Logcat: Slow delivery 18.975 s для `MainActivity$1`, Slow dispatch 5.329 s для ActivityThread. Эти события подтверждают задержки обработки Android main looper, но не доказывают, что источник именно Java UI.
- `AdrenoVK-0 Shader compilation failed` после завершения NativeActivity относится к новому PID 2272 и контекстам Android framework/Chromium, а не к игровому PID 11605. Не использовать эти сообщения как основание для патча игрового Vulkan shader pipeline.

### Изменение
- Patch 42 `NX2A_METRO_VIDEO_DECODER_QOS`: добавлен `video-decoder` в Metro-only `DM_QOS_UTILITY_NAMES`. Это понижает конкуренцию фонового декодирования за CPU относительно main/audio threads; существующий механизм priority inheritance должен временно поднять QoS владельца блокировки, если игровой поток ждёт его mutex.
- Изменение ограничено Metro game ID и именем `video-decoder`; другие игры и аудиопотоки не затрагиваются.
- Payload manifest bumped to version 207; новый SHA-256 `apply_patches.py`: `5a1551849a8cd181649076af99b20a8848419732ec03f9ddf9192555c1dc53dd`.

### Ограничения / что не заявляем
- QoS-патч — направленная оптимизация по измеренному CPU-конкуренту, а не доказанное устранение lock cycle. Не менял семантику гостевых mutex/condition variables, Vulkan aliasing и AudioOut buffer count.
- Старый лог содержит многосекундные frame stalls; для проверки нужен новый Metro Data Pack, потому что patch script применяется при пересборке Data Pack, а APK сам по себе не заменяет `libdmhost.so`.
- Нужно сравнить с тем же сценарием: underrun на 2k callback-окнах, CPU time `video-decoder`, frame work p95/max, main/video mutex snapshots и медленные pread.

### Следующие шаги
1. Проверить CI: patch 42 должен применяться к pinned Porter и проходить повторное применение без изменений.
2. Установить новый APK и обновить/пересобрать Metro Data Pack.
3. Повторить проблемный участок не менее 2–3 минут; не менять одновременно Vulkan-драйвер, разрешение и игровые настройки.
4. Сравнить новые callback underrun, CPU time декодера, frame timing и mutex snapshots. Если зависания сохраняются, следующий шаг — точечная трассировка владельца mutex и producer wakeups AudioOut, а не увеличение буфера вслепую.


### CI follow-up — 2026-11-26
- Первый workflow после изменения прошёл Python syntax/tests и NGR patch apply/idempotence, но остановился на manifest freshness: локально рассчитанный SHA-256 не совпал с `tools/make_manifest.py`.
- Взял authoritative hash из CI diff и обновил `payload.json`: `5a1551849a8cd181649076af99b20a8848419732ec03f9ddf9192555c1dc53dd`.
- Новый workflow запущен на обновлённом manifest commit; APK пока не объявлять готовым до успешного завершения.

## 2026-11-26 — Metro save transaction EACCES + low-overhead diagnostics

### New evidence
- Updated gameplay log shows the save transaction itself is failing:
  - save:/user.cfg opens for write, then clonefile save.new fails errno=13.
  - Same EACCES repeats for 2033_auto_save and checkpoint player files.
  - The committed save remains unchanged; this explains why the Download mirror is empty even though the Java mirror task reports completion.
- Existing Android reflink patch only treated EOPNOTSUPP/ENOTTY/EXDEV/EINVAL/ENOSYS/EPERM as unsupported. EACCES from FICLONE therefore aborted the transaction instead of taking the normal byte-copy fallback.
- New user A/B test: no hangs with logging disabled; hangs return when logging is enabled. Treat intrusive diagnostics as a likely timing perturbation, not as proof of a game-only hang.

### Changes
- Payload patch 43: treat FICLONE EACCES as an unsupported reflink result and use the existing byte-copy fallback. This preserves private transactional storage and atomic save commit; it does not weaken permissions or bypass the transaction.
- Metro diagnostic profile in ngrhost.c: disable watchdog full thread dumps and their 10/15-second sampling for this title. Keep low-overhead runtime and selected slow-frame summaries. Verbose NVN, filesystem and per-lock tracing were already suppressed.
- Payload manifest bumped to version 208 and apply_patches.py SHA-256 updated.

### Validation / next
- GitHub CI must validate patch application/idempotence, payload manifest and Release APK.
- Device test: save user.cfg + reach checkpoint, exit normally, verify files in Download/NX2A/Saves/9383b4fd4e8540ed5d6e, relaunch and load.
- Confirm gameplay log reports [fs] Android save clone: FICLONE unavailable (errno=13); byte-copy fallback active and subsequent save commits succeed with nonzero writes.
- Compare stability with diagnostics off vs only runtime + slow-frame summaries. Do not enable watchdog dumps, NVN or filesystem tracing for normal play.


## 2026-11-27 — Metro save EACCES and missing-render-feature audit

### Save failure confirmed from the latest runtime log
- Repeated `clonefile .../save.new failed errno=13` occurs after the game opens `save:/user.cfg`, `save:/2033_auto_save`, and checkpoint `.player` files. The save transaction therefore aborts before replacing the committed tree; this is not a Download mirror-only issue.
- Patch 43, `NX2A_FICLONE_EACCES_FALLBACK`, now treats `EACCES` from Android `FICLONE` as an unavailable reflink and falls back to the existing byte-copy path. Transactional clone/commit/swap remains enabled; no permissions are broadened.
- Payload manifest bumped to version 208; `apply_patches.py` SHA-256: `8e8e2420a6461603fbc0f5211cf426f6b15f9a10be3bbe7994e72b9ae78b53c1`.

### Missing textures / shadows / reticle audit
- Latest log identifies Turnip Adreno 740 / Vulkan 1.4.363 and 854 shader bundle entries; no shader compilation failures or explicit texture upload errors were found in the inspected startup/gameplay window.
- Three NVN entry points report as unimplemented: `nvnTextureBuilderGetRawStorageClass` once, `nvnProgramSetSampleShading` four times, and `nvnCommandBufferSetStencilCullCriteria` 26 times.
- The stencil-cull entry point is documented as a ZCull hint, not the actual depth/stencil test state; its absence alone is not evidence for missing shadows. The texture-builder getter is a concrete compatibility gap and should be implemented from the matching pinned porter source before making a safe patch. Sample-shading arguments and the shader/depth path need validation before changing behavior.
- Do not claim missing fire/reticle/shadows are fixed yet. Next diagnostics should correlate the missing visual object with the draw's texture descriptor, texture format/swizzle, shader key, depth target, and pipeline state, using opt-in low-volume event logging (not per-frame/per-draw logging).

### Performance/logging
- User confirms gameplay is smooth with logging disabled and hangs when logging is enabled. Keep verbose NVN/filesystem/lock tracing disabled by default; only explicit diagnostic sessions may enable it. Avoid high-frequency log writes in hot paths.

### Validation still required
- Rebuild/recompile Metro Data Pack so the new porter patch is actually applied to `libdmhost.so`; APK build alone does not compile the pinned native porter.
- Verify save commit no longer reports `errno=13`, save files appear in the private committed tree and then Download mirror, and reload works.
- Retest the same scene with logging disabled for performance and with minimal diagnostics for visual regressions. Compare screenshots for fire, reticle and shadow scenes.


## 2026-11-26 — Save transaction permission recovery (patches 44–45)

- Compared `feature/metro-save-manager` against `main`: the feature branch adds per-game `DM_SAVE` under `<files>/games/<game-id>/save`, plus a transactional private-save store and a Download mirror. The legacy `main` branch does not contain this per-game save manager, so reverting the whole feature to `main` would also discard the launcher/runtime work rather than isolate the save defect.
- Confirmed the pinned porter implements `clonefile()` as a recursive tree clone; NGR patch 32 adds Linux `FICLONE` and byte-copy fallback, patch 34 adjusts destination permissions, and patch 43 adds EACCES to the reflink fallback list.
- The earlier `errno=13` report is not enough to prove the failure is the FICLONE ioctl. Recursive `clonefile()` can also return EACCES while creating `save.new`, enumerating a source directory, or opening a source file. The previous patch 43 addressed only the ioctl case.
- Patch 44 restores owner rwx on the private per-game root and `DM_SAVE` root before the game runtime uses them, and logs an explicit red error if the save root is still not accessible.
- Patch 45 retries source-file open / source-directory enumeration after restoring only the app owner's required read (and directory execute) permission when the original operation fails with EACCES. Destination files/directories continue to receive owner write permissions from patch 34.
- Payload version bumped to 211. `apply_patches.py` SHA-256 (verified by CI manifest generation): `822092694a1b1d8bf1da1191d761695899500fc4f1f5e80583b9b9bf2395659a`.
- Commits: save patcher `45d8bbb8a1b72691569a647094f92ad0575cab37`; payload manifest `df27166f0cbe1179b29a12ed1165d883248c7f49`; project log `a6d306949076a85e6da9adb2b282b7409d3fadca`.
- Validation status: Android runtime save/load has not yet been re-tested. CI must confirm patch application against the pinned porter and produce the APK before device testing. Required device test: create a new save, exit cleanly, relaunch, load it, then verify the Download mirror contains the committed save.

- CI validation caught two patch-set issues before any APK was published: the source-directory permission edit had to compose with the earlier clonefile diagnostics patch, and the new save-root patch had to preserve the original idempotence marker. Both were corrected. The full patch application now passes twice against the pinned porter (run 45890392757, patch-verification step); its later manifest check failed only because the manifest still carried the previous patcher hash, which has now been corrected to the hash reported by CI.

- CI result: **success** — run `45890510369`, built from `a6d306949076a85e6da9adb2b282b7409d3fadca`. Python/unit checks, double application of the complete patch set against the pinned porter, WebView syntax, payload manifest check, and release APK build all passed.
- APK artifact: `nx2android-apk`, artifact ID `15151721124`, 35,872,190 bytes; archive SHA-256 `1dafdc46a0b67c8d12934403790d4a47b01c2a27822c2977908ab1905bdbaced`. Device-level save/load verification is still outstanding.


## 2026-11-27 — Vulkan masked-clear MRT/FLOAT/UINT/SINT implementation

### Implementation
- Added patch 46, `NX2A_MASKED_CLEAR_ALL_ATTACHMENTS`, to the payload patcher.
- Masked-clear pipeline cache key now includes render-pass attachment formats, sample count, clear mask, selected color attachment index, and numeric output class.
- Pipeline color write mask is applied to the requested attachment index instead of hard-coded attachment 0.
- Added three fragment shader variants: FLOAT/UNORM/SNORM (`vec4`), UINT (`uvec4`), and SINT (`ivec4`). Each declares output locations 0–7; the pipeline write mask enables only the requested target. This permits mixed-type MRTs without mismatched fragment output types.
- `clear_masked()` no longer rejects attachment indices >0 or integer attachments; it selects the shader variant from the porter format metadata.
- The payload patcher generates the GLSL sources under `nxnative/dm/android/shaders/`; existing `build.py` compiles all shader files to SPIR-V headers during native build.
- Payload version advanced to 212. `apply_patches.py` SHA-256: `220850506fe68424b75c25195ab408457dfc014eef98c80aa11541b7f4bf911f`.

### Validation status
- Source patch and manifest are committed to `feature/metro-save-manager`.
- CI patch-application, shader compilation, native build and APK artifact validation are pending.
- Runtime validation on Turnip Adreno 740 is pending. This change fixes masked-clear semantics only; it does not yet prove the missing fire/reticle/distant textures/shadow defects are resolved.
- Texture descriptor, sampler-version, mip/LOD, swizzle and depth/stencil investigations remain next steps.
- Keep detailed/high-frequency logging disabled by default.


## 2026-11-27 — Masked-clear implementation refined for mixed MRT formats

### Final implementation details
- Patch 46 adds the all-attachment masked-clear path and selects FLOAT/UINT/SINT output class from the target attachment format.
- Patch 47 refines the shader design: one fragment shader per (attachment location, numeric class), 24 variants total. This avoids declaring outputs at unrelated locations whose numeric classes may differ in a mixed-format MRT.
- The patcher generates `maskclear_f0.frag` … `maskclear_f23.frag` in the pinned Porter source tree. The existing Android `build.py` shader glob compiles them into 24 SPIR-V headers.
- Pipeline selection uses `kind * 8 + attachmentIndex`; only the selected attachment has a nonzero `colorWriteMask`.
- Patch 48 increases the masked-clear pipeline cache from 32/64 entries to 512, enough for the practical combinations of 8 attachment locations, 3 numeric classes and 15 nonzero channel masks.
- Pipeline cache key includes attachment index and numeric class in addition to the existing render-target formats, depth format, sample count and channel mask.
- Payload version advanced to 214. `apply_patches.py` SHA-256: `a5d5cf58bd54dd5c4be95549217a92e6c102bf6d065a2f358edb1d7229112b6d`.

### Validation status
- GitHub branch commits:
  - patch 46 + first manifest/log: `3f0bdbbebb523d13a9a61e7266bbbf11f6450a8c` / `f6247b2cfdd943278a9033edc4dfd38b0931d970` / `a9791124e9909e6464728f7f7928655042fcd656`
  - per-location/type shader refinement: `f088070711ab22e6e800aca0d9f8ba1803d32de0`
  - shader generator and source patch corrected: `38561d684b99798fb546215f374b84e1aaa0474d`
  - cache capacity: `7e60ad3174ee0cc746167c9f714a36ae2e502b31`
  - manifest update: `034bd1431045784b334f13381fc18b209027da61`
- CI run `45898531356` was created for the first version; it predates the final 24-shader refinement and is not a valid final-build result. A new run for the final manifest/log commits must be inspected.
- No APK is declared ready until final CI patch application, double-application idempotence, manifest check, shader compilation and APK build pass.
- Device test still required on Turnip Adreno 740. Masked clear is a targeted renderer correctness fix; it is not proof that fire, reticle, distant textures or shadows are all restored.


### Follow-up correctness refinement
- Replaced the three broad MRT shader variants with 24 variants, one output location and one numeric class per shader. This is necessary because unrelated MRT slots can use different float/integer formats; even masked-off outputs should not rely on mismatched shader output types.
- UINT clear conversion now clamps negative input components to zero before conversion, matching the existing full-clear path's unsigned conversion rule.
- Pipeline cache capacity is 512 entries (up to 8 attachment locations × 3 numeric classes × 15 nonzero channel masks, with room for multiple pass layouts).
- Latest manifest commit: `2c301cce1947b73f9ea1cd5e5b3d64ff73ce96dc`; current branch head must be checked before final CI validation.


### CI result for the 24-shader implementation (pre-final UINT clamp)
- Run `45898729198` completed successfully from commit `0bb67836f9da41ee8bdceb91d67b6342759d2d11`.
- Passed: Python syntax/unit checks, patch application twice against pinned Porter, WebView syntax, payload manifest verification, release APK build.
- Artifact: `nx2android-apk`, ID `15154972411`, 35,873,460 bytes. This artifact contains payload version 213 and predates the final unsigned-value clamp/hash update; do not use it as the final test APK.
- Final source now has payload version 214 and the unsigned clear conversion clamp. A new CI run is required for the final artifact.


## 2026-11-27 — Final APK for masked-clear patch (payload 214)

### CI
- Final payload source (version 214, including the per-location/type shader variants and UINT clamp) passed workflow run `45898925959`, commit `a5c3903a4c543c09d4377fe8a96d3527a2cfac87`.
- Passed: Python syntax/unit checks, patcher applied twice against pinned Porter, WebView syntax, manifest hash check, signed release APK build and artifact upload.
- Artifact: `nx2android-apk`, ID `15155250643`, 35,873,495 bytes. Link: `https://github.com/Snap888/nx2android-android-port/actions/runs/45898925959/artifacts/15155250643`.
- CI does not compile the native Porter Data Pack. The device-side native rebuild and visual regression test remain mandatory.

### Additional findings from Metro gameplay log 9383b4fd4e8540ed5d6e
- The log contains exactly 200 repeated `[alias] stale read` events for one overlapping storage range `+73793536..+77725696`: sampled image 1280x720, NVN format `0x38`, while a 640x360 image of the same format and exact same pool range was rendered later. The current `alias_check()` only reports this condition; it does not synchronize the two independent VkImages. This is a strong, separate candidate for textures that disappear or become stale when the game reuses texture-pool storage with another description. Do not blindly copy/scale until the sample counts and texture usage are confirmed.
- No buffer-texture alignment warnings, `vkCreateImageView` failures, unsupported texture formats, or deswizzle errors were present in this gameplay log.
- NVN counters: 1,718 texture builder calls, 1,719 texture initializations, 1,687 mip-level settings, 197 texture views, 30 sampler registrations, 197 buffer-to-texture copies.
- `nvnTextureBuilderGetRawStorageClass` was called 3 times but is missing. Pinned `hle_nvn.c` has `nvnTextureBuilderGetStorageClass` returning 0 and a separate `nvnTextureGetRawStorageClass` returning 1; the builder raw variant needs its own ABI-safe stub, with return semantics verified before merging.
- `nvnProgramSetSampleShading` was called 898 times; the observed unimplemented calls had enable argument 0, so it is not currently the leading cause. `nvnCommandBufferSetStencilCullCriteria` is a ZCull hint, not actual depth/stencil state.
- Next graphics work: add opt-in low-volume alias metadata (include sample count/target/flags) and implement the builder raw-storage getter; then determine whether the 640x360/1280x720 alias is MSAA/resolve reuse or another pool-layout reinterpretation before changing image storage semantics.

### Current status
- Masked-clear fix is implemented and packaged in APK; not yet device-verified.
- Missing fire/reticle/distant textures/shadows are not declared fixed. Alias stale-read behavior is now the strongest remaining evidence-backed lead.
- Preserve the current save implementation and keep high-frequency diagnostics disabled by default.


## 2026-11-27 — NVN raw storage class + bounded texture-alias diagnostics (payload 215)

- Patch 50 adds the missing `nvnTextureBuilderGetRawStorageClass` entry point as an ABI-safe no-prototype NVN export taking `const NVNtextureBuilder *` and returning 1. This follows the pinned porter's existing `nvnTextureGetRawStorageClass` behavior; it is separate from `nvnTextureBuilderGetStorageClass`, which remains 0.
- Patch 51 makes stale texture-alias logging opt-in via `DM_VK_ALIAS_TRACE=1`, caps it at 16 events, and reports both images' sample counts, targets, flags, dimensions, format and pool range. The stale-read watermark still updates when tracing is disabled.
- This diagnostic does not yet synchronize aliased images or fix the 1280x720 / 640x360 content mismatch. It is intended to determine whether the pair is MSAA/resolve reuse or a different layout reinterpretation without per-draw logging.
- Payload version advanced to 215. `apply_patches.py` SHA-256: `0ef02b50bb796c8c9bcd50b3ba580136337db597fa3e0639ac4180cf855f0f31`.
- CI and APK build for version 215 are pending. Version 214 artifact remains available but does not include these two follow-up patches.


### Version 215 validation queue
- The previous version-214 run `45899160982` completed successfully; it validates the APK pipeline before patches 50–51.
- Patches 50–51 and manifest version 215 are now the branch head. Their own patch-application and APK build must be validated in a run whose head includes the version-215 manifest; earlier artifacts must not be substituted.


### Manifest hash correction
- CI run `45899368099` correctly rejected the hand-computed hash for patcher version 215. The source patch and Python syntax checks passed; failure was isolated to `payload.json` SHA-256.
- Recomputed SHA-256 against the exact branch file and confirmed it matches CI's `tools/make_manifest.py`: `ddebc883fba3fcd0ef79d7eb9523b29aa836ff73203b378c5653ed27096794c6`.
- Corrected `payload.json` at commit `c4a5da43f66cde7aa28f9453c3e651601d101553`. Version remains 215. Final CI must be rerun; do not use the rejected run's result.


## 2026-11-27 — Payload 215 final native build passed

### CI / native validation
- Final run: `45899795144`, source commit `9b269aa11497a77e96f5eaa4d44fef57b14be892`, conclusion SUCCESS.
- Passed: Python syntax and tests; patch set applied twice to pinned Porter; WebView syntax; payload manifest hash; signed APK build; native Vulkan backend compile and SPIR-V shader compile.
- New CI native compile step runs:
  `python3 nxnative/dm/android/build.py --game 0100CD701434C000 --ndk "$ANDROID_SDK_ROOT/ndk/27.2.12479018" --lib --release --jobs 4`
  against the patched pinned Porter. It successfully produced `libdmhost.so`; all 24 generated masked-clear GLSL variants compiled to SPIR-V.
- Artifact: `nx2android-apk`, ID `15154829303`, 35,874,265 bytes. Link: `https://github.com/Snap888/nx2android-android-port/actions/runs/45899795144/artifacts/15154829303`.
- Payload version: 215. Patcher SHA-256: `ddebc883fba3fcd0ef79d7eb9523b29aa836ff73203b378c5653ed27096794c6`.

### Runtime test still required
- Install APK, rebuild Metro 2033 Redux Data Pack so the updated patched `libdmhost.so` is used, then test fire, reticle, distant textures and shadows on Turnip Adreno 740.
- If the 1280x720 / 640x360 alias needs further classification, add `DM_VK_ALIAS_TRACE=1` to the game's `env.txt` for one test run. It emits at most 16 alias records and is disabled by default.
- Saves remain untouched by the graphics patches. User's last verified state: saves work and gameplay does not hang with verbose logging disabled.


## 2026-11-27 — Metro gameplay log 9383b4fd4e8540ed5d6e: index-buffer chunk crossing

### Новые данные игрового прогона
- Файлы: `Logs/ngr-gameplay-9383b4fd4e8540ed5d6e.log.txt` (blob `8c76459ccf97bdf0c7c9305ff904e307874fa14f`) и `Logs/ngr-runtime-9383b4fd4e8540ed5d6e.log.txt` (blob `6e5696d97484fb338b1c4041dfe379927d3d0910`).
- Сессия 2026-11-27 01:05:58–01:07:15; Turnip Adreno 740, Vulkan 1.4.362, driver 26.2.99.
- Shader bundle: 854/854 shaders загружены. NVN init: 1,718 texture builder calls, 1,719 texture initializations, 1,687 mip-level calls, 197 texture views, 30 sampler registrations, 197 CopyBufferToTexture calls.
- Packaged textures: 0 missed, 0 first uploads / reuploads during tracked intervals, 0 write-protection faults. This rules against a broad texture-upload failure but does not prove sampled image contents/LOD are correct.
- At present 3000: 1,520,460 draws replayed, skipped due to no program/target = 0, pipeline skips = 5; 1,667 live images, 427 MB, 61 evicted images. 61 evictions are not by themselves proof of a bug.
- **New strongest direct lead:** repeated `[vk] [RED] index ranges across a memory pool chunk's end` for the same range `0x718fa89afc + 0x63c`, chunk end `0x718fa8a000`. The range crosses the VkBuffer boundary by `0x138` bytes. Counter reaches 4096 (power-of-two rate-limited reports). In pinned `gfx_vk_exec.c`, `draw_idx()` only resolves the first VkBuffer with `vk_buf_at(d->ibuf, 1, ...)`, then issues `vkCmdDrawIndexed` against it; the crossing is counted but not repaired. The source comment explicitly notes that the GPU can read past the VkBuffer and, with robustBufferAccess off, see zeros. This can drop/corrupt indexed geometry and is a plausible contributor to missing particle meshes, distant geometry and shadow casters. Need capture the affected draw's count/index type/base vertex before choosing a safe fix.
- No `partial channel clear` / `clear_masked` warning appears in this current gameplay log. Do not attribute this run's missing effects to masked clear without a new reproduction.
- `nvnProgramSetSampleShading` has 898 registrations; the four unimplemented runtime calls show enable argument 0. `nvnCommandBufferSetStencilCullCriteria` remains a ZCull hint, not depth/stencil state.
- 27 texture swizzle builder calls; one logged non-identity swizzle `(2,3,4,0)`. Pinned `swz_comp()` maps NVN 0=ZERO, 1=ONE, 2=R, 3=G, 4=B, 5=A; therefore this exact swizzle is RGB identity with alpha forced to ZERO. If the affected fire/reticle uses this texture, it can become fully transparent under alpha blending. This is a high-priority candidate, but the current log does not identify the texture's pool offset/ID, so trace the texture descriptor and its draw before changing semantics globally.
- The current run has no active alias trace because `DM_VK_ALIAS_TRACE` defaults off. Prior run documented 200 stale-read alias warnings for overlapping 1280x720 and 640x360 views over the same pool range. Keep that as a separate candidate and use the bounded 16-event trace only in a controlled follow-up.

### Отдельный старый build log
- `Logs/1` (blob `6358b361837c37915b14e40064b1ec4441380fad`) is from 2026-11-24 17:39 UTC, not the 2026-11-27 gameplay session.
- Its shader translation completed (854/854), but data-pack stage failed with Python `NameError: name 'ui_font_assets' is not defined` in `porter/pipeline.py:858`, called by `Port.data()` at line 870. This is a Python packaging/name-resolution failure, not an NDK/C++ or Vulkan shader compile failure. Later payload 215 CI run `45899795144` passed native Vulkan backend and SPIR-V compilation, so do not conflate the stale log with current graphics runtime.

### Next actions
1. Add opt-in, capped metadata for crossing indexed draws (address, count, index type, base vertex, indirect flag); default off.
2. Implement a correct cross-chunk index read path. Prefer a GPU-side two-buffer-to-contiguous scratch copy with required barriers if source data can be GPU-written; use CPU shadow copy only after proving the index buffer is CPU-owned for this workload.
3. Correlate affected draw/shader/pipeline with fire, reticle, distant meshes and shadow casters. Do not assume all symptoms share one cause.
4. In a separate controlled run enable `DM_VK_ALIAS_TRACE=1` (max 16 events) and inspect the known 1280x720 / 640x360 overlapping image pair.
5. Keep saves unchanged and heavy per-frame logging disabled.



## 2026-11-27 — Payload 217: GPU repair for direct indexed draws crossing pool chunks

### Implemented
- apply_patches.py patch 52 adds vk_index_range_scratch() to the pinned NVN Vulkan backend.
- For a direct, non-quad indexed draw whose index range crosses a zero-copy memory-pool chunk, the backend now:
  1. validates the complete range belongs to the same guest pool and stays inside its bounds;
  2. rounds the copy range to Vulkan's 4-byte buffer-copy alignment;
  3. ends the current render pass and lands deferred uniform updates;
  4. copies each source chunk GPU-to-GPU into the submission scratch buffer, with global memory barriers before and after;
  5. binds the scratch index buffer for the draw. The copy is recorded before prepare_draw() so pipeline, descriptors, vertex buffers and render-pass state are set up normally afterward.
- Copy size is capped at 64 MiB; an invalid/unresolvable crossing is skipped with one bounded error instead of issuing an out-of-bounds indexed draw.
- No CPU shadow copy is used: index data may have been written by GPU work earlier in the submission.
- NVN quad conversion (prim == 7) and indexed-indirect draws are deliberately not changed; their source ranges are handled differently and need separate work.
- Patch 53 adds DM_VK_SWIZZLE_TRACE=1 (maximum 64 records) with texture pool/offset, serial, dimensions, format, levels, texture/view selectors and final Vulkan component mapping. It does not override game-requested swizzles.
- Patch 51's DM_VK_ALIAS_TRACE=1 remains opt-in and capped at 16 events. New DM_VK_INDEX_TRACE=1 is capped at 16 crossing draws. All are off by default.

### Validation
- Payload version: 217.
- apply_patches.py SHA-256: c7ac0571c4107d2e615ed79746c9d0d1ea7ed4a348d958ec2fdf2a250a7f7c9b.
- Workflow run 45904299239 passed: Python syntax/tests, patch application twice against the workflow's pinned Porter, payload manifest check, signed APK build, patched Vulkan backend compilation and SPIR-V shader compilation.
- Successful run artifact (same code patcher; manifest was version 216, before the version-only 217 bump): 15157655920, 35,876,705 bytes. Exact version-217 workflow run 45904370735 was queued/in progress when this entry was written.
- Native compilation proves the patched backend builds; it does not prove the visual defects are fixed on the Adreno 740 device.

### Device test / remaining work
1. Install the test APK and rebuild Metro 2033 Redux's Data Pack so the game uses the newly patched libdmhost.so.
2. First test with diagnostic variables unset: fire textures, reticle, distant textures, shadows, FPS and stability.
3. If symptoms remain, enable only one bounded trace per short run: DM_VK_INDEX_TRACE=1, DM_VK_SWIZZLE_TRACE=1, or DM_VK_ALIAS_TRACE=1. Do not enable verbose per-frame logging.
4. The (2,3,4,0) texture swizzle explicitly requests RGB with alpha ZERO; no global semantic change is justified until the affected texture and its draw are identified.
5. Distant-texture sampler LOD and the earlier 1280x720 / 640x360 overlapping-image alias remain unresolved. No global maxLod change or image-storage rewrite was made.
6. Shadows may share the indexed-geometry defect, but must be checked against shadow-caster draws and depth attachments separately.

## 2026-11-27 — Texture / particle regression: reject ineffective BC override, add bounded trace

### Device evidence reviewed
- The stored gameplay log is session 9383b4fd4e8540ed5d6e, launched at 2026-11-27 01:05:58. Its game manifest says Data Pack made: 2026-11-26 22:00:32; it is not a new capture after the later payload-219 build.
- Runtime reports Turnip Adreno 740 with BC and ASTC support; 854-shader bundle loaded; 1,667 live Vulkan images / 427 MB.
- The same log reports 0 first uploads and 0 re-uploads in the packaged-texture counters, 27 texture swizzle builder calls with one non-identity (2,3,4,0), and no texture-format mapping, image-allocation, or vkCreateImageView failure messages.
- This does not prove all 1,667 images contain valid pixels or are sampled by the intended shaders. The saved log has no texture first-use / descriptor trace.
- Android AdrenoGLES shader compile errors are from the separate Chromium/WebView path; the game Vulkan device in this log is Turnip. Do not use those GLES errors as proof of Metro's Vulkan shaders failing.

### Correction to payload 219 BC hypothesis
- Pinned upstream gfx_vk_tex.c already contains cpu_content_tex() and explicitly documents the BC7 particle-sprite zero-image case.
- On this device, f->compressed covers hardware-supported BC formats; f->dec identifies software-decoded formats. Extending the predicate to f->dec did not address the reported Turnip BC path and bypassed IMAGE/COMPRESSIBLE guards for compressed formats.
- Removed the speculative NX2A_CPU_DECODED_BC_FIRST_USE override and its test. Do not reintroduce it without a trace proving the actual texture format takes that path.

### Implemented: opt-in texture trace
- DM_VK_TEX_TRACE=1 enables bounded diagnostics; default remains off.
- [tex-first]: max 96 first-use records; logs upload source (linear, packaged, ft-written, cpu-content, no-upload), serial, pool/offset, memory pointer/size, NVN/Vulkan format, target, dimensions, flags, pool flags, layout, compressed/decoder state.
- [tex-bind]: max 96 sampled/storage descriptor records for textures at least 16x16; logs shader key, binding, handle/ID, serial, pool/offset, format, dimensions, levels, flags, texture/view swizzles, Vulkan image/view and GPU-write state.
- [tex-bind-miss]: max 32 unresolved texture-ID records.
- Instrumentation preserves upload and descriptor behavior. No per-frame trace and no change to swizzle, LOD, aliasing, render targets, or save handling.
- Payload version: 225. Patcher marker IDs: NX2A_TEX_FIRST_TRACE, NX2A_TEX_BIND_TRACE.
- CI run 45912643379 for HEAD 44eb34ed0b65fb0e203155a53d159f8ac28338e0 passed: Python tests, patch application twice against pinned Porter, WebView syntax, payload manifest, signed APK, and patched NVN Vulkan backend / SPIR-V compilation. APK artifact 15160672401 (35,878,129 bytes).

### Next actions
1. Wait for CI 45912386380; fix any patch/test/compiler failures before device testing.
2. Install its APK and verify the runtime library in the selected game's data pack is refreshed by the app. Capture a new gameplay log after this build; confirm the tex-first and tex-bind records appear.
3. If source=no-upload, use first-use metadata to isolate the gating reason; if IDs are missing, audit texture-pool registration/handle decode; if bindings exist, correlate format/swizzle/image bytes with shader key and sampler.
4. Keep the next trace run short. All tracing is opt-in and bounded; do not enable verbose/per-frame logging.
5. After texture path is identified, investigate the known (2,3,4,0) swizzle only for the correlated texture. Keep alias and shadow-depth issues separate.

## 2026-11-27 — Metro texture alias coherence (payload 229)

### Fresh device log reviewed
- Current gameplay capture: session 9383b4fd4e8540ed5d6e, 2026-11-27 09:12; Turnip Adreno 740, Vulkan 1.4, BC and ASTC supported.
- Shader bundle: 854/854 shaders loaded; prewarm: 359/359 graphics pipelines. At present 600, replay reports 600 draws and zero skips for no program / no target / no pipeline. This does not prove every later draw succeeds, but it does not support a global shader-compilation failure.
- Confirmed overlapping NVN storage: the same pool byte range is sampled as 1280x720, NVN format 0x38 (VK_FORMAT_R8G8B8A8_SRGB), single-sample target 1, after being rendered as 640x360, same format, 4x MSAA target 5. The Vulkan backend keeps separate device-local VkImages for different NVN descriptions; upstream gfx_vk_tex.c explicitly notes that one image cannot see another image's writes over the same NVN memory. The existing alias trace was reporting this stale-read condition.
- The repeated indexed range at 0x718fa89afc (798 uint16 indices, base vertex 50734) is handled by the GPU scratch-copy path (path gpu-copy). Do not rework this path based on the current log.
- No shader/pipeline failure was correlated with the absent fire or textures. The far-only-visible laser sight remains uncorrelated and is not yet proven to be the same defect.

### Implemented
- New patch NX2A_ALIAS_MSAA_RESOLVE: for the exact observed 4x MSAA 640x360 -> single-sample 1280x720 RGBA8_SRGB alias, resolve into a cached single-sample temporary image and nearest-blit into the stale sampled alias before use.
- The fallback is deliberately narrow: NVN format 0x38, same Vulkan sRGB format, 4 samples -> 1, 2x width and height, one mip/layer, color aspect. Other alias configurations remain logged, not silently modified.
- Temporary image memory is deferred-freed with the existing Vulkan lifetime machinery; the temporary is cached per destination image.
- When DM_VK_ALIAS_TRACE=1 is set, bounded DM_VK_TEX_TRACE first-use and descriptor traces are now automatically enabled (existing caps remain 96 first-use, 96 binds, 32 misses).
- Added patcher tests for MSAA alias patch application/idempotence and alias-triggered texture trace.
- Payload manifest version: 229. Patcher SHA-256: 5f2eb7a3e8077cce4ea75ceae7ddd305fd23d837a39211362f638068acfad9de.
- Commits: b8c3fdaa (alias sync implementation), 6d7d6894 (preserve prior alias trace marker for idempotence), 22cc210e (test idempotence), 345902fc (payload checksum/version).
- CI run 45951526428 is building the APK and compiling the patched Vulkan backend; device correctness is not yet verified.

### Important limitation / next test
- MSAA resolve + nearest 2x blit is a visual reconstruction of the observed alias, not a bit-exact recreation of the Switch's raw per-sample memory reinterpretation. It should make the newer target's colour data visible to the older alias, but the Adreno device test must confirm whether the mapping is sufficient.
- Install the payload-229 APK, rebuild the Metro Data Pack, and verify a new log contains [alias-sync] records and no repeated stale-read records for this exact pair.
- Because alias trace now enables texture tracing automatically, inspect [tex-first], [tex-bind] and [tex-bind-miss] on the same short run. This will show whether missing fire/particles are actually bound to valid images and whether their first-use source was no-upload.
- For the laser sight, next isolate the correlated shader/texture descriptor and sampler LOD. Do not change global maxLod, mip bias, culling, or depth state without that correlation.
