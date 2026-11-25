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
- APK готов для тестирования; исправление пока не подтверждено на устройстве. Важно: CI проверил patch application/idempotency и собрал APK, но не компилировал сам patched Porter runtime C-код на устройстве. Нужен A/B запуск Metro: сравнить yield rate двух worker threads, AudioOut underruns/queue depth, Android UI responsiveness и p95/p99 frame time.
- Не менялись AAudio callback period, AudioOut QMAX/queue semantics и Vulkan texture aliasing. Presentation stalls и stale texture alias warnings остаются отдельными задачами, если сохранятся после снижения CPU starvation.

### Следующие шаги
1. Дождаться CI на commit 197ad30311dc5a8e992c2880cb824d0800036a8e и проверить APK artifact.
2. Установить APK, запустить Metro в той же сцене и проверить, что лог содержит DM_YIELD_PROGRESS_LIMIT, DM_QOS_UTILITY_NAMES / Metro scheduler marker, а per-call DeviceGetInteger не спамит при DM_NVN_LOG=0.
3. Сравнить аудио underruns, queue depth, watchdog CPU time двух worker threads и отклик Android UI.
4. Если submit+present остаётся >100 ms при GPU <5 ms, отдельно исследовать Vulkan queue present / Android BufferQueue; если stale alias reads сохраняются — записать A/B кадры и проверить alias lifetime.
