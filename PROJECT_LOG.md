# PROJECT_LOG — NGR Universal Game Launcher

**Дата обновления:** 2026-11-24  
**Текущий этап:** Универсальная библиотека игр, встроенный runtime и диагностика.  
**Главная цель сейчас:** Надёжный запуск игр непосредственно из NGR без отдельного APK на каждую игру и без копирования игровых данных в Android/data.

## Сделано

- Основа проекта развивается в ветке `feature/ngr-universal-library`.
- Интегрированы рекомпилятор, встроенный runtime и библиотека игр.
- Реализованы импорт игровых данных и запуск через собственную NativeActivity.
- Добавлены настройки отдельных игр и диагностические чекбоксы:
  - основной runtime + stdout/stderr;
  - slow-frame;
  - NVN/Vulkan;
  - watchdog/thread snapshots;
  - filesystem/RomFS trace.
- Подробное логирование выключено по умолчанию, чтобы не создавать лишнюю нагрузку во время игры.
- GitHub Actions run `45479066455` (commit `902f8fdf5faa8f2b8f96e0ad1d71f2b9304b53db`) успешно прошёл проверки Python, JavaScript, payload manifest и Release APK.
- Исправлена изоляция диагностических сессий: при включении любой категории логирования Java очищает старые per-game файлы; NativeActivity записывает собственный PID даже если включены только slow-frame/NVN/watchdog. Это позволяет экспорту отфильтровать Logcat по PID игры.
- Коммиты исправления:
  - `b5e1aa6f853013989f351d063ebf1c66cb22934b` — PID tracking для всех диагностических режимов.
  - `898072245529b89e7d3cf3c5de52e6e1e9bf0966` — очистка лог-сессии при включении любой категории.

## Следующие шаги (приоритет)

1. Проверить CI для последних двух коммитов и получить свежий APK.
2. Проверить на устройстве отдельно каждый режим логирования, включая экспорт runtime/gameplay логов.
3. Проверить, что при выключенных чекбоксах не создаются большие диагностические файлы и не включается stdout/stderr redirect.
4. После подтверждения логирования вернуться к зависанию игры Twelve Minutes на 22% и сравнить рабочий/нерабочий запуск по свежим логам.

## Ключевые решения и данные

- Репозиторий: https://github.com/Snap888/nx2android-android-port
- Ветка: `feature/ngr-universal-library`
- Пакет: `unknown.none.nx2android`
- Сборка: GitHub Actions workflow `build-apk`, JDK 17; CI использует NDK 27.2.12479018.
- Основные файлы:
  - `app/src/main/cpp/ngrhost.c`
  - `app/src/main/java/unknown/none/nx2android/MainActivity.java`
  - `app/src/main/assets/nx2a/payload/webgui/index.html`
  - `app/src/main/assets/nx2a/payload/webgui/server.py`
  - `app/src/main/assets/nx2a/payload/payload.json`
- Предыдущий успешный APK: Actions run https://github.com/Snap888/nx2android-android-port/actions/runs/45479066455
- Артефакт предыдущего запуска: `nx2android-apk`, 35,845,447 bytes; SHA-256 zip `46323e3caaca10f623b836d5698a989f3935b89d1aa4338ca2435d99d8b1ea07`.

## Проблемы / Блокеры

- Последние два исправления ещё не прошли CI на момент записи этого лога.
- Проверка реального поведения на Android-устройстве не выполнена; сборка сама по себе не подтверждает, что драйверные переменные логирования поддерживаются конкретной ревизией porter.
- Нужно проверить соответствие `DM_FS`, `DM_FSLOG`, `DM_NVN_LOG`, `DM_SLOWFRAME` и `DM_WATCH_*` текущему коду/патчам porter.

## Открытые вопросы

- После установки нового APK: создаются ли отдельные диагностические файлы при включении каждого чекбокса?
- Достаточно ли логов для анализа зависания Twelve Minutes на 22%, или понадобится отдельный профиль захвата загрузки?
