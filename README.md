# AutoJoin

The Russian version of this README is below: [Русская версия ↓](#русская-версия)

A Windows program that joins Webex and Teams meetings by itself on a weekly schedule and leaves them at the set time.

## Features

- Weekly schedule: for each meeting you pick the days of the week, the join time and the leave time. The meeting repeats every week.
- Webex: opens the link in Chrome, enters your name, dismisses the microphone and camera prompts with "Continue without using microphone and camera" and joins.
- Teams: opens the Teams desktop app from the link and presses "Join now". The microphone and camera are never turned on by the program.
- Leaves the meeting at the scheduled time.
- Import from an iCal (`.ics`) file: a university timetable exported from MAIS (button "Export do iCal") or any calendar with weekly events turns into a list of meetings. You only add the links.
- Each meeting can be switched on or off with the green check / red cross in the first column of the schedule (click it).
- Interface in Russian and English: the RU / EN switch is in the top right corner. The choice is remembered.
- Protection against failures: up to 5 join attempts with growing pauses, waiting for the internet and continuing when it returns, automatic rejoin if the connection to the meeting is lost, leaving the previous meeting when the next one starts, the computer does not fall asleep while the queue runs, only one copy of the program can run, a damaged `meetings.json` is saved as `meetings.broken.json` instead of being lost.
- If you leave a meeting by hand, the program will join it again. To keep it away, click the red cross for that meeting or press "Stop".

## Requirements

- Windows 10 or 11
- Google Chrome
- Microsoft Teams desktop app (only for Teams meetings)
- Python 3.10+ (only if you run from source)

## Run from source

```
pip install -r requirements.txt
python -m playwright install chromium
python app.py
```

## Build the exe

Locally: run `build.bat`. The result is `dist\AutoJoin.exe`.

On GitHub: create a tag like `v1.0.0` (for example via Releases → Draft a new release). The `Release` workflow builds `AutoJoin.exe` and attaches it to the release.

## How to use

1. Enter your name.
2. Add meetings: platform, link, days of the week, join time and leave time.
3. Press "Запустить очередь" (Start queue) and keep the program open.

The meeting list and your name are stored in `meetings.json` next to the program. The file is excluded from the repository because it contains meeting links.

## First Teams run

Teams is opened through Chrome. Once, Chrome may ask "Open Microsoft Teams?". Tick "Always allow" and press "Open Microsoft Teams". The choice is saved in the `chrome_profile` folder next to the program.

## Troubleshooting

A screenshot `debug_*.png` is saved next to the program, and the log at the bottom of the window shows the step where the program stopped.

## Tests and CI

```
pip install pytest
python -m pytest
```

The tests cover the schedule logic and the Webex join flow on mock pages from `tests/mock`. The same tests and a code check run on GitHub Actions on every push (workflow `CI`). Joining the Teams desktop app is not tested automatically: it needs Windows with Teams installed.

## Project structure

| Path | Purpose |
| --- | --- |
| `app.py` | the whole program |
| `requirements.txt` | Python dependencies |
| `build.bat` | local exe build |
| `tests/` | tests and mock pages |
| `.github/workflows/` | CI and release workflows |

---------------------------------

# Русская версия

Программа для Windows, которая сама заходит на собрания Webex и Teams по дням недели и выходит из них в заданное время.

## Возможности

- Расписание по дням недели: для каждого собрания выбираются дни, время входа и время выхода. Собрание повторяется каждую неделю.
- Webex: открывает ссылку в Chrome, вводит имя, закрывает окна про микрофон и камеру кнопкой «Продолжить без использования микрофона и камеры» и заходит.
- Teams: открывает приложение Teams по ссылке и нажимает «Присоединиться сейчас». Микрофон и камеру программа не включает.
- Выход из собрания в назначенное время.
- Импорт из файла iCal (`.ics`): расписание, выгруженное из МАИС (кнопка «Export do iCal»), или любой календарь с еженедельными событиями превращается в список собраний. Остаётся только вставить ссылки.
- Каждое собрание можно включить или выключить зелёной галочкой / красным крестиком в первом столбце расписания (нажмите на него).
- Интерфейс на русском и английском: переключатель RU / EN в правом верхнем углу. Выбор запоминается.
- Защита от сбоев: до 5 попыток входа с растущими паузами, ожидание интернета и продолжение, когда он вернётся, автоматический повторный вход при потере связи с собранием, выход из предыдущего собрания, когда начинается следующее, компьютер не засыпает, пока работает очередь, нельзя запустить две копии программы, повреждённый `meetings.json` сохраняется как `meetings.broken.json`, а не теряется.
- Если выйти из собрания вручную, программа зайдёт в него снова. Чтобы этого не было, нажмите красный крестик у этого собрания или «Остановить».

## Требования

- Windows 10 или 11
- Google Chrome
- Приложение Microsoft Teams (только для собраний в Teams)
- Python 3.10+ (только если запускаете из исходников)

## Запуск из исходников

```
pip install -r requirements.txt
python -m playwright install chromium
python app.py
```

## Сборка exe

Локально: запустить `build.bat`, готовый файл появится в `dist\AutoJoin.exe`.

Через GitHub: создать тег вида `v1.0.0` (например, через Releases → Draft a new release). Workflow `Release` соберёт `AutoJoin.exe` и прикрепит его к релизу.

## Как пользоваться

1. Вписать своё имя.
2. Добавить собрания: платформа, ссылка, дни недели, время входа и выхода.
3. Нажать «Запустить очередь» и оставить программу открытой.

Список собраний и имя хранятся в `meetings.json` рядом с программой. Файл исключён из репозитория, потому что в нём лежат ссылки на собрания.

## Первый запуск Teams

Teams открывается через Chrome. Один раз Chrome может спросить «Открыть приложение Microsoft Teams?». Нужно отметить «Всегда разрешать» и нажать «Открыть приложение». Выбор сохраняется в папке `chrome_profile` рядом с программой.

## Если что-то не сработало

Рядом с программой сохраняется скриншот `debug_*.png`, а в журнале внизу окна пишется, на каком шаге остановилась программа.

## Тесты и CI

```
pip install pytest
python -m pytest
```

Тесты проверяют логику расписания и вход в Webex на тестовых страницах из `tests/mock`. Те же тесты и проверка кода запускаются на GitHub Actions при каждом push (workflow `CI`). Вход в приложение Teams автоматически не проверяется: для этого нужен Windows с установленным Teams.

## Структура проекта

| Путь | Назначение |
| --- | --- |
| `app.py` | вся программа |
| `requirements.txt` | зависимости Python |
| `build.bat` | локальная сборка exe |
| `tests/` | тесты и тестовые страницы |
| `.github/workflows/` | CI и выпуск релиза |
