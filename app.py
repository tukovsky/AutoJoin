import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
import tkinter as tk
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from playwright.sync_api import sync_playwright

BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_FILE = BASE_DIR / "meetings.json"
TIME_FMT = "%H:%M"
HEADLESS = os.environ.get("AUTOJOIN_HEADLESS") == "1"
TEAMS = "Teams"
PLATFORMS = ["Webex", TEAMS]
PROFILE_DIR = BASE_DIR / "chrome_profile"

COOKIE_PATTERNS = [
    r"^(accept all|accept|agree|got it)$",
    r"^(принять все|принять|согласен|понятно)$",
]
MEDIA_SKIP_PATTERNS = [
    r"продолжить без использования",
    r"продолжить без (аудио|звука|микрофона|камеры)",
    r"continue without (using )?(my )?(microphone|mic|audio|camera)",
]
WEBEX_BROWSER_PATTERNS = [
    r"join from (your|this) browser",
    r"join from web ?app",
    r"use web ?app",
    r"join from the web",
    r"этого браузера",
    r"из браузера",
    r"с помощью браузера",
    r"через браузер",
    r"браузер",
]
WEBEX_JOIN_PATTERNS = [
    r"присоединиться к совещанию",
    r"^присоединиться$",
    r"join meeting",
    r"^join( now)?$",
]
NAME_PATTERNS = [r"имя", r"name"]
LEAVE_PATTERNS = [
    r"^leave",
    r"^hang up",
    r"^end call",
    r"^покинуть",
    r"^выйти",
]
TEAMS_PROCESSES = ("ms-teams.exe", "teams.exe")
TEAMS_PREJOIN_TITLE = re.compile(r"присоедин|joining|join", re.I)
TEAMS_LAUNCH_PATTERNS = [
    r"присоединиться в приложении",
    r"открыть (ваше )?приложение teams",
    r"join in the (teams )?app",
    r"open your teams app",
    r"launch the app",
]
TEAMS_CHROME_OPEN_RE = r"(?i).*(открыть приложение|open (microsoft )?teams).*"
TEAMS_CHROME_ALWAYS_RE = r"(?i).*(всегда разрешать|always allow).*"
TEAMS_APP_JOIN_RE = r"(?i).*(присоединиться сейчас|join now).*"
TEAMS_LEAVE_RE = r"(?i)^(выйти|покинуть|leave|hang up).*"

STRINGS = {
    "ru": {
        "app_title": "Автовход на собрания",
        "subtitle": "Webex и Teams: заходит и выходит сам по дням недели",
        "pill_off": "●  Очередь остановлена",
        "pill_on": "●  Очередь работает",
        "btn_start": "▶  Запустить очередь",
        "btn_stop": "■  Остановить",
        "btn_delete": "Удалить выбранное",
        "btn_import": "Импорт из iCal",
        "card_me": "Мои данные",
        "lbl_name": "Имя, которое увидят на собрании",
        "card_new": "Новое собрание",
        "lbl_title": "Название",
        "lbl_platform": "Платформа",
        "lbl_url": "Ссылка на собрание",
        "lbl_days": "Дни недели",
        "lbl_join_at": "Зайти в",
        "lbl_leave_at": "Выйти в",
        "btn_add": "＋  Добавить",
        "card_schedule": "Расписание",
        "col_on": "Вкл",
        "col_title": "Название",
        "col_platform": "Платформа",
        "col_days": "Дни",
        "col_time": "Время",
        "col_next": "Ближайшее",
        "col_status": "Статус",
        "st_waiting": "waiting",
        "st_running": "running",
        "st_retry": "повтор",
        "st_done": "done",
        "st_error": "error",
        "st_nolink": "nolink",
        "st_off": "выключено",
        "every_day": "Каждый день",
        "now": "сейчас",
        "today": "сегодня {t}",
        "tomorrow": "завтра {t}",
        "menu_cut": "Вырезать",
        "menu_copy": "Копировать",
        "menu_paste": "Вставить",
        "err_title": "Ошибка",
        "err_url": "Вставьте ссылку на собрание",
        "err_days": "Выберите хотя бы один день недели",
        "err_time": "Неверное время. Часы от 0 до 23, минуты от 0 до 59",
        "err_order": "Время выхода должно быть позже времени входа",
        "err_name": "Впишите своё имя",
        "err_minutes": "Минуты должны быть числом",
        "err_read": "Не удалось прочитать файл: {exc}",
        "default_title": "Собрание {platform}",
        "added_hint": "Собрание добавлено. Нажмите «Запустить очередь», чтобы оно сработало",
        "link_dialog": "Ссылка на собрание",
        "file_title": "Файл расписания",
        "filetype_ical": "Календарь iCal",
        "filetype_all": "Все файлы",
        "import_title": "Импорт расписания",
        "import_none": "В файле нет повторяющихся еженедельных занятий",
        "import_note": "Отмечены онлайн-занятия: зелёная галочка включает занятие, красный крестик пропускает. Вставьте ссылки: для одного предмета достаточно одной, остальные подставятся сами. Ссылку можно добавить и позже, двойным щелчком по строке в расписании.",
        "import_skipped": " Пропущено записей, которые не повторяются каждую неделю: {n}.",
        "import_before": "Заходить за",
        "import_min": "мин до начала",
        "btn_import_do": "Импортировать",
        "btn_cancel": "Отмена",
        "imported": "Импортировано занятий: {n}",
        "imported_nolink": ". Без ссылки: {n} (двойной щелчок по строке, чтобы добавить)",
        "queue_started": "Очередь запущена",
        "queue_stopped": "Очередь остановлена",
        "awake": "Компьютер не будет засыпать, пока очередь работает",
        "joining": "Вхожу: {title}",
        "leaving": "Выхожу: {title}",
        "screenshot": "Скриншот сохранён: {name}",
        "buttons_on_page": "Кнопки на странице: {names}",
        "no_buttons": "кнопок не найдено",
        "no_browser": "Не найден браузер Chrome, Edge или Chromium",
        "webex_no_name": "Webex: поле имени не найдено",
        "webex_name_ok": "Webex: имя введено",
        "webex_no_join": "Webex: кнопка входа не найдена",
        "webex_pressed": "Webex: нажал «Присоединиться»",
        "webex_joined": "Webex: вход выполнен",
        "untitled": "(без названия)",
        "no_teams_windows": "окон Teams нет",
        "teams_list_fail": "не удалось получить список ({exc})",
        "teams_hint": "Если в Chrome появилось окно «Открыть приложение Microsoft Teams?», отметьте «Всегда разрешать» и нажмите «Открыть приложение». Это нужно только один раз",
        "teams_direct": "Teams: запускаю приложение напрямую",
        "teams_windows": "Окна Teams: {x}",
        "teams_pressed_join": "Teams: нажал «Присоединиться сейчас»",
        "teams_join_missing": "Teams: кнопка «Присоединиться сейчас» не найдена",
        "teams_pressed_leave": "Teams: нажал «Выйти»",
        "teams_leave_keys": "Teams: выход через Ctrl+Shift+H",
        "teams_no_window": "Teams: окно приложения не появилось",
        "teams_opened": "Teams: приложение открыто",
        "teams_window_lost": "Teams: окно приложения пропало",
        "join_failed": "не удалось нажать кнопку входа",
        "offline": "Нет интернета. Жду подключения",
        "online_back": "Интернет вернулся",
        "attempt": "Попытка {n} из {total}: {title}",
        "attempt_failed": "Не удалось зайти: {exc}. Повтор через {sec} с",
        "dropped": "Связь с собранием потеряна, захожу снова",
        "gave_up": "Не удалось зайти на «{title}», попытки закончились",
        "preempted": "Начинается следующее собрание, выхожу из «{title}»",
        "error_log": "Ошибка: {exc}",
        "backup_made": "Файл настроек был повреждён, его копия сохранена как {name}",
        "already_running": "Программа уже запущена. Закройте второе окно",
    },
    "en": {
        "app_title": "Meeting AutoJoin",
        "subtitle": "Webex and Teams: joins and leaves by itself on a weekly schedule",
        "pill_off": "●  Queue stopped",
        "pill_on": "●  Queue running",
        "btn_start": "▶  Start queue",
        "btn_stop": "■  Stop",
        "btn_delete": "Delete selected",
        "btn_import": "Import iCal",
        "card_me": "My details",
        "lbl_name": "Name shown in the meeting",
        "card_new": "New meeting",
        "lbl_title": "Title",
        "lbl_platform": "Platform",
        "lbl_url": "Meeting link",
        "lbl_days": "Days of the week",
        "lbl_join_at": "Join at",
        "lbl_leave_at": "Leave at",
        "btn_add": "＋  Add",
        "card_schedule": "Schedule",
        "col_on": "On",
        "col_title": "Title",
        "col_platform": "Platform",
        "col_days": "Days",
        "col_time": "Time",
        "col_next": "Next",
        "col_status": "Status",
        "st_waiting": "waiting",
        "st_running": "in meeting",
        "st_retry": "retrying",
        "st_done": "done",
        "st_error": "error",
        "st_nolink": "no link",
        "st_off": "disabled",
        "every_day": "Every day",
        "now": "now",
        "today": "today {t}",
        "tomorrow": "tomorrow {t}",
        "menu_cut": "Cut",
        "menu_copy": "Copy",
        "menu_paste": "Paste",
        "err_title": "Error",
        "err_url": "Paste the meeting link",
        "err_days": "Select at least one day of the week",
        "err_time": "Invalid time. Hours 0 to 23, minutes 0 to 59",
        "err_order": "Leave time must be later than join time",
        "err_name": "Enter your name",
        "err_minutes": "Minutes must be a number",
        "err_read": "Could not read the file: {exc}",
        "default_title": "{platform} meeting",
        "added_hint": "Meeting added. Press “Start queue” to activate it",
        "link_dialog": "Meeting link",
        "file_title": "Timetable file",
        "filetype_ical": "iCal calendar",
        "filetype_all": "All files",
        "import_title": "Import schedule",
        "import_none": "The file has no weekly recurring events",
        "import_note": "Online classes are selected: a green check includes a class, a red cross skips it. Paste the links: one link per subject is enough, the rest are filled in automatically. You can add a link later by double-clicking a row in the schedule.",
        "import_skipped": " Skipped entries that do not repeat weekly: {n}.",
        "import_before": "Join",
        "import_min": "min before start",
        "btn_import_do": "Import",
        "btn_cancel": "Cancel",
        "imported": "Classes imported: {n}",
        "imported_nolink": ". Without a link: {n} (double-click a row to add one)",
        "queue_started": "Queue started",
        "queue_stopped": "Queue stopped",
        "awake": "The computer will not go to sleep while the queue is running",
        "joining": "Joining: {title}",
        "leaving": "Leaving: {title}",
        "screenshot": "Screenshot saved: {name}",
        "buttons_on_page": "Buttons on the page: {names}",
        "no_buttons": "no buttons found",
        "no_browser": "Chrome, Edge or Chromium not found",
        "webex_no_name": "Webex: name field not found",
        "webex_name_ok": "Webex: name entered",
        "webex_no_join": "Webex: join button not found",
        "webex_pressed": "Webex: pressed “Join”",
        "webex_joined": "Webex: joined",
        "untitled": "(untitled)",
        "no_teams_windows": "no Teams windows",
        "teams_list_fail": "could not get the list ({exc})",
        "teams_hint": "If Chrome shows “Open Microsoft Teams?”, tick “Always allow” and press “Open”. This is needed only once",
        "teams_direct": "Teams: launching the app directly",
        "teams_windows": "Teams windows: {x}",
        "teams_pressed_join": "Teams: pressed “Join now”",
        "teams_join_missing": "Teams: “Join now” button not found",
        "teams_pressed_leave": "Teams: pressed “Leave”",
        "teams_leave_keys": "Teams: left with Ctrl+Shift+H",
        "teams_no_window": "Teams: the app window did not appear",
        "teams_opened": "Teams: app opened",
        "teams_window_lost": "Teams: the app window disappeared",
        "join_failed": "could not press the join button",
        "offline": "No internet. Waiting for the connection",
        "online_back": "Internet is back",
        "attempt": "Attempt {n} of {total}: {title}",
        "attempt_failed": "Could not join: {exc}. Retrying in {sec} s",
        "dropped": "Connection to the meeting lost, rejoining",
        "gave_up": "Could not join “{title}”, out of attempts",
        "preempted": "The next meeting is starting, leaving “{title}”",
        "error_log": "Error: {exc}",
        "backup_made": "The settings file was damaged, a copy was saved as {name}",
        "already_running": "The program is already running. Close the other window",
    },
}
DAY_NAMES = {
    "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
LANG = "ru"
MAX_ATTEMPTS = 5
RETRY_DELAY = 20
DROP_DELAY = 5
INTERNET_HOSTS = (("1.1.1.1", 443), ("8.8.8.8", 53), ("9.9.9.9", 443))
INSTANCE_PORT = 47631


def tr(key, **kw):
    text = STRINGS[LANG].get(key) or STRINGS["ru"][key]
    return text.format(**kw) if kw else text


def day_names():
    return DAY_NAMES[LANG]


def detect_language():
    try:
        import ctypes

        if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFF == 0x19:
            return "ru"
        return "en"
    except Exception:
        return "ru"


def internet_ok():
    for host, port in INTERNET_HOSTS:
        try:
            socket.create_connection((host, port), 3).close()
            return True
        except OSError:
            continue
    return False


def wait_for_internet(end_dt, stop_event, log):
    if internet_ok():
        return True
    log(tr("offline"))
    while datetime.now() < end_dt and not stop_event.is_set():
        if internet_ok():
            log(tr("online_back"))
            return True
        stop_event.wait(5)
    return False


def keep_awake(on):
    if sys.platform != "win32":
        return
    try:
        import ctypes

        flags = 0x80000000 | (0x00000001 | 0x00000002 if on else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


def acquire_instance_lock():
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", INSTANCE_PORT))
    except OSError:
        lock.close()
        return None
    return lock


def beep():
    try:
        import winsound

        winsound.MessageBeep()
    except Exception:
        pass


def parse_time(value):
    return datetime.strptime(value.strip(), TIME_FMT).time()


def days_text(days):
    if len(days) == 7:
        return tr("every_day")
    return ", ".join(day_names()[d] for d in sorted(days))


def migrate_meeting(m):
    if str(m.get("platform", "")).startswith("Teams"):
        m["platform"] = TEAMS
    m.setdefault("enabled", True)
    if "days" in m:
        return m
    try:
        start = datetime.strptime(m["start"], "%Y-%m-%d %H:%M")
        end = datetime.strptime(m["end"], "%Y-%m-%d %H:%M")
    except Exception:
        return None
    m["days"] = [start.weekday()]
    m["start"] = start.strftime(TIME_FMT)
    m["end"] = end.strftime(TIME_FMT)
    return m


def window_for(m, day):
    start = datetime.combine(day, parse_time(m["start"]))
    end = datetime.combine(day, parse_time(m["end"]))
    return start, end


def next_run_text(m, now, ran_today):
    for offset in range(8):
        day = now.date() + timedelta(days=offset)
        if day.weekday() not in m["days"]:
            continue
        start, end = window_for(m, day)
        if end <= now:
            continue
        if offset == 0 and ran_today:
            continue
        if offset == 0:
            return tr("now") if start <= now else tr("today", t=m["start"])
        if offset == 1:
            return tr("tomorrow", t=m["start"])
        return f"{day_names()[day.weekday()]} {m['start']}"
    return "—"


ICS_DAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
ICS_ONLINE_WORDS = ("online", "virtual", "webex", "teams")


def ics_unescape(value):
    return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def ics_datetime(value):
    value = value.strip()
    parsed = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        parsed = parsed.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    return parsed


def ics_events(text):
    lines = []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    event = None
    for line in lines:
        if line.strip() == "BEGIN:VEVENT":
            event = {}
        elif line.strip() == "END:VEVENT":
            if event is not None:
                yield event
            event = None
        elif event is not None and ":" in line:
            key, _, value = line.partition(":")
            event[key.split(";")[0].upper()] = value


def parse_ics(text, now):
    items = []
    skipped = 0
    for ev in ics_events(text):
        try:
            start = ics_datetime(ev["DTSTART"])
            end = ics_datetime(ev["DTEND"])
        except (KeyError, ValueError):
            skipped += 1
            continue
        rule = dict(part.split("=", 1) for part in ev.get("RRULE", "").split(";") if "=" in part)
        if (
            rule.get("FREQ") != "WEEKLY"
            or rule.get("INTERVAL", "1") != "1"
            or end.date() != start.date()
            or end <= start
        ):
            skipped += 1
            continue
        if "UNTIL" in rule:
            try:
                if ics_datetime(rule["UNTIL"]) < now:
                    skipped += 1
                    continue
            except ValueError:
                pass
        days = sorted({ICS_DAYS[d[-2:]] for d in rule.get("BYDAY", "").split(",") if d[-2:] in ICS_DAYS})
        if not days:
            days = [start.weekday()]
        summary = ics_unescape(ev.get("SUMMARY", "")).strip()
        info = ics_unescape(ev.get("LOCATION", "") + " " + ev.get("DESCRIPTION", "")).lower()
        name, _, kind = summary.rpartition(" - ")
        if not name:
            name, kind = summary, ""
        subject = re.sub(r"\s*\(\d+\)", "", name).strip() or "Занятие"
        items.append(
            {
                "title": f"{subject} · {kind.strip()}" if kind.strip() else subject,
                "subject": subject,
                "days": days,
                "start": start.strftime(TIME_FMT),
                "end": end.strftime(TIME_FMT),
                "online": any(word in info for word in ICS_ONLINE_WORDS),
                "platform": TEAMS if "teams" in info and "webex" not in info else PLATFORMS[0],
            }
        )
    items.sort(key=lambda it: (it["days"][0], it["start"], it["title"]))
    return items, skipped


def click_first(page, patterns, roles=("button", "link"), text_fallback=False):
    for frame in page.frames:
        for pattern in patterns:
            rx = re.compile(pattern, re.I)
            for role in roles:
                try:
                    loc = frame.get_by_role(role, name=rx)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.click(timeout=2000)
                        return True
                except Exception:
                    pass
            if text_fallback:
                try:
                    loc = frame.get_by_text(rx)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.click(timeout=2000)
                        return True
                except Exception:
                    pass
    return False


def fill_field(page, patterns, value, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        for frame in page.frames:
            for pattern in patterns:
                rx = re.compile(pattern, re.I)
                for getter in (frame.get_by_placeholder, frame.get_by_label):
                    try:
                        loc = getter(rx)
                        if loc.count() > 0 and loc.first.is_visible():
                            loc.first.fill(value)
                            return True
                    except Exception:
                        pass
        page.wait_for_timeout(500)
    return False


def fill_first_input(page, value):
    for frame in page.frames:
        try:
            inputs = frame.locator(
                "input[type=text]:visible, input[type=email]:visible, input:not([type]):visible"
            )
            if inputs.count() >= 1:
                inputs.first.fill(value)
                return True
        except Exception:
            pass
    return False


def press_enter_in_field(page, patterns):
    for frame in page.frames:
        for pattern in patterns:
            rx = re.compile(pattern, re.I)
            for getter in (frame.get_by_placeholder, frame.get_by_label):
                try:
                    loc = getter(rx)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.press("Enter")
                        return True
                except Exception:
                    pass
    return False


def dismiss_media_prompt(page):
    return click_first(page, MEDIA_SKIP_PATTERNS, text_fallback=True)


def click_join(page, join_patterns, name_patterns, timeout=40):
    started = time.time()
    pressed = False
    while time.time() - started < timeout:
        dismiss_media_prompt(page)
        if click_first(page, join_patterns, text_fallback=True):
            return True
        if not pressed and time.time() - started > 10:
            pressed = True
            if press_enter_in_field(page, name_patterns):
                return True
        page.wait_for_timeout(500)
    return False


def describe_buttons(page):
    names = []
    for frame in page.frames:
        try:
            for el in frame.get_by_role("button").all():
                try:
                    if not el.is_visible():
                        continue
                    text = (el.inner_text(timeout=300) or el.get_attribute("aria-label") or "").strip()
                    names.append(text.replace("\n", " ")[:40])
                except Exception:
                    pass
        except Exception:
            pass
    return ", ".join(names[:15]) or tr("no_buttons")


def snap(page, tag, log):
    try:
        path = BASE_DIR / f"debug_{tag}.png"
        page.screenshot(path=str(path))
        log(tr("screenshot", name=path.name))
    except Exception:
        pass


def open_name_page(page, name_patterns, browser_patterns, name, log, tag):
    started = time.time()
    while time.time() - started < 75:
        dismiss_media_prompt(page)
        if fill_field(page, name_patterns, name, 2):
            return True
        if time.time() - started > 30 and fill_first_input(page, name):
            return True
        click_first(page, browser_patterns, text_fallback=True)
        page.wait_for_timeout(1000)
    snap(page, tag, log)
    return False


def join_webex(page, url, name, log):
    page.goto(url, wait_until="domcontentloaded")
    click_first(page, COOKIE_PATTERNS)
    if not open_name_page(page, NAME_PATTERNS, WEBEX_BROWSER_PATTERNS, name, log, "webex_name"):
        log(tr("webex_no_name"))
        return False
    log(tr("webex_name_ok"))
    page.wait_for_timeout(500)
    if not click_join(page, WEBEX_JOIN_PATTERNS, NAME_PATTERNS):
        log(tr("webex_no_join"))
        log(tr("buttons_on_page", names=describe_buttons(page)))
        snap(page, "webex_join", log)
        return False
    log(tr("webex_pressed"))
    end = time.time() + 15
    while time.time() < end:
        dismiss_media_prompt(page)
        page.wait_for_timeout(1000)
    log(tr("webex_joined"))
    return True


def leave_meeting(page):
    try:
        if click_first(page, LEAVE_PATTERNS):
            page.wait_for_timeout(1000)
            click_first(page, LEAVE_PATTERNS)
            page.wait_for_timeout(1000)
    except Exception:
        pass


def launch_browser(p, args):
    for channel in ("chrome", "msedge", None):
        try:
            if channel:
                return p.chromium.launch(channel=channel, headless=HEADLESS, args=args)
            return p.chromium.launch(headless=HEADLESS, args=args)
        except Exception:
            continue
    raise RuntimeError(tr("no_browser"))


class ComSession:
    def __enter__(self):
        self.ok = False
        try:
            import comtypes

            comtypes.CoInitialize()
            self.ok = True
        except Exception:
            pass
        return self

    def __exit__(self, *exc):
        if self.ok:
            try:
                import comtypes

                comtypes.CoUninitialize()
            except Exception:
                pass


def win_spec(handle):
    from pywinauto import Desktop

    return Desktop(backend="uia").window(handle=handle)


def uia_find(spec, pattern, types):
    for control_type in types:
        try:
            found = spec.child_window(title_re=pattern, control_type=control_type, found_index=0)
            if found.exists(timeout=1):
                return found.wrapper_object()
        except Exception:
            pass
    return None


def uia_press(element, radio=False):
    actions = ("select", "invoke") if radio else ("invoke", "select")
    for action in actions:
        try:
            getattr(element, action)()
            return True
        except Exception:
            pass
    try:
        element.click_input()
        return True
    except Exception:
        return False


def teams_windows():
    import psutil
    from pywinauto import Desktop

    result = []
    for w in Desktop(backend="uia").windows():
        try:
            if psutil.Process(w.process_id()).name().lower() in TEAMS_PROCESSES:
                result.append((w.handle, w.window_text()))
        except Exception:
            continue
    return result


def describe_teams_windows():
    try:
        titles = [title or tr("untitled") for _, title in teams_windows()]
        return "; ".join(titles) or tr("no_teams_windows")
    except Exception as exc:
        return tr("teams_list_fail", exc=exc)


def find_prejoin_window():
    for handle, title in teams_windows():
        if TEAMS_PREJOIN_TITLE.search(title or ""):
            return handle
    return None


def accept_chrome_dialog():
    from pywinauto import Desktop

    desktop = Desktop(backend="uia")
    for w in desktop.windows(class_name="Chrome_WidgetWin_1"):
        try:
            spec = desktop.window(handle=w.handle)
            button = uia_find(spec, TEAMS_CHROME_OPEN_RE, ["Button"])
            if not button:
                continue
            box = uia_find(spec, TEAMS_CHROME_ALWAYS_RE, ["CheckBox"])
            if box:
                try:
                    if box.get_toggle_state() == 0:
                        box.toggle()
                except Exception:
                    pass
            return uia_press(button)
        except Exception:
            continue
    return False


def teams_protocol_url(url):
    m = re.match(r"https?://teams\.(?:microsoft|live)\.com(/.*)$", url.strip())
    return "msteams:" + m.group(1) if m else None


def launch_persistent(p, args):
    PROFILE_DIR.mkdir(exist_ok=True)
    for profile in (PROFILE_DIR, Path(tempfile.mkdtemp(prefix="autojoin_"))):
        for channel in ("chrome", "msedge", None):
            try:
                kwargs = dict(headless=HEADLESS, args=args, locale="ru-RU", viewport={"width": 1100, "height": 760})
                if channel:
                    kwargs["channel"] = channel
                return p.chromium.launch_persistent_context(str(profile), **kwargs)
            except Exception:
                continue
    raise RuntimeError(tr("no_browser"))


def open_teams_app(url, log, stop_event):
    with sync_playwright() as p:
        context = launch_persistent(p, ["--disable-blink-features=AutomationControlled"])
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            started = time.time()
            clicked = False
            hinted = False
            started_app = False
            while time.time() - started < 120 and not stop_event.is_set():
                handle = find_prejoin_window()
                if handle:
                    return handle
                accept_chrome_dialog()
                elapsed = time.time() - started
                if not clicked and elapsed > 6:
                    clicked = True
                    click_first(page, TEAMS_LAUNCH_PATTERNS, text_fallback=True)
                if not hinted and elapsed > 25:
                    hinted = True
                    log(tr("teams_hint"))
                if not started_app and elapsed > 50:
                    started_app = True
                    target = teams_protocol_url(url)
                    if target and hasattr(os, "startfile"):
                        try:
                            os.startfile(target)
                            log(tr("teams_direct"))
                        except Exception:
                            pass
                page.wait_for_timeout(1500)
            snap(page, "teams_app", log)
            log(tr("teams_windows", x=describe_teams_windows()))
            return None
        finally:
            try:
                context.close()
            except Exception:
                pass


def teams_app_join(handle, log, timeout=60):
    win = win_spec(handle)
    started = time.time()
    while time.time() - started < timeout:
        join = uia_find(win, TEAMS_APP_JOIN_RE, ["Button"])
        if join:
            time.sleep(1)
            uia_press(join)
            log(tr("teams_pressed_join"))
            return True
        time.sleep(1)
    log(tr("teams_join_missing"))
    return False


def teams_app_leave(handle, log):
    handles = [handle] if handle else []
    handles += [h for h, _ in teams_windows() if h != handle]
    for h in handles:
        try:
            button = uia_find(win_spec(h), TEAMS_LEAVE_RE, ["Button"])
        except Exception:
            button = None
        if button and uia_press(button):
            log(tr("teams_pressed_leave"))
            return True
    if handles:
        try:
            win = win_spec(handles[0])
            win.set_focus()
            win.type_keys("^+h")
            log(tr("teams_leave_keys"))
            return True
        except Exception:
            pass
    return False


def run_teams_app(m, profile, log, stop_event):
    end_dt = datetime.combine(date.today(), parse_time(m["end"]))
    title = m["title"] or m["platform"]
    with ComSession():
        log(tr("joining", title=title))
        handle = open_teams_app(m["url"], log, stop_event)
        if not handle:
            if stop_event.is_set():
                return
            raise RuntimeError(tr("teams_no_window"))
        log(tr("teams_opened"))
        if not teams_app_join(handle, log):
            raise RuntimeError(tr("teams_join_missing"))
        missing = 0
        tick = 0
        while datetime.now() < end_dt and not stop_event.is_set():
            time.sleep(1)
            tick += 1
            if tick % 5:
                continue
            try:
                missing = 0 if teams_windows() else missing + 1
            except Exception:
                missing = 0
            if missing >= 3:
                log(tr("teams_window_lost"))
                return
        log(tr("leaving", title=title))
        teams_app_leave(handle, log)


def run_meeting(m, profile, log, stop_event):
    if m["platform"] == TEAMS:
        run_teams_app(m, profile, log, stop_event)
        return
    end_dt = datetime.combine(date.today(), parse_time(m["end"]))
    title = m["title"] or m["platform"]
    with sync_playwright() as p:
        browser = launch_browser(p, ["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(locale="ru-RU", viewport={"width": 1280, "height": 800})
        page = context.new_page()
        try:
            log(tr("joining", title=title))
            if not join_webex(page, m["url"], profile["name"], log):
                raise RuntimeError(tr("join_failed"))
            tick = 0
            alive = True
            while datetime.now() < end_dt and not stop_event.is_set() and not page.is_closed():
                page.wait_for_timeout(1000)
                tick += 1
                if tick % 10 == 0:
                    try:
                        page.evaluate("1")
                    except Exception:
                        alive = False
                        break
            if alive and not page.is_closed():
                log(tr("leaving", title=title))
                leave_meeting(page)
        finally:
            try:
                browser.close()
            except Exception:
                pass


def run_with_retries(meeting, profile, log, stop_event, runner=None, end_dt=None, on_state=None):
    runner = runner or run_meeting
    end_dt = end_dt or datetime.combine(date.today(), parse_time(meeting["end"]))
    title = meeting["title"] or meeting["platform"]
    failures = 0
    while not stop_event.is_set() and datetime.now() < end_dt - timedelta(seconds=15):
        if not wait_for_internet(end_dt, stop_event, log):
            break
        if on_state:
            on_state("running")
        if failures:
            log(tr("attempt", n=failures + 1, total=MAX_ATTEMPTS, title=title))
        try:
            runner(meeting, profile, log, stop_event)
            if stop_event.is_set() or datetime.now() >= end_dt - timedelta(seconds=15):
                break
            log(tr("dropped"))
            delay = DROP_DELAY
        except Exception as exc:
            delay = RETRY_DELAY * (failures + 1)
            log(tr("attempt_failed", exc=exc, sec=delay))
        failures += 1
        if failures >= MAX_ATTEMPTS:
            log(tr("gave_up", title=title))
            return "error"
        if on_state:
            on_state("retry")
        stop_event.wait(delay)
    return "done"


BG = "#12141a"
CARD = "#1b1e27"
FIELD = "#252936"
BORDER = "#2c3140"
TEXT = "#e8eaf0"
MUTED = "#8a90a2"
ACCENT = "#5b8def"
ACCENT_HOVER = "#7aa3f5"
OK = "#3ecf8e"
ERR = "#ef5b5b"
FONT = "Segoe UI"

KEYCODE_EVENTS = {86: "<<Paste>>", 67: "<<Copy>>", 88: "<<Cut>>", 65: "<<SelectAll>>"}

STATUS_TAGS = {
    "waiting": "waiting",
    "running": "running",
    "retry": "running",
    "done": "done",
    "error": "error",
    "nolink": "error",
    "off": "done",
}


class App:
    def __init__(self, root):
        self.root = root
        self.startup_notes = []
        self.log_lines = []
        self.preempted = set()
        self.meetings = []
        self.status = {}
        self.stops = {}
        self.ran = {}
        self.running = False
        self.last_signature = None

        self.name_var = tk.StringVar()
        self.title_var = tk.StringVar()
        self.platform_var = tk.StringVar(value=PLATFORMS[0])
        self.url_var = tk.StringVar()
        self.start_h = tk.StringVar(value="08")
        self.start_m = tk.StringVar(value="00")
        self.end_h = tk.StringVar(value="09")
        self.end_m = tk.StringVar(value="30")
        today = datetime.now().weekday()
        self.day_vars = [tk.BooleanVar(value=(i == today)) for i in range(7)]

        self.load()
        self.lang_var = tk.StringVar(value=LANG)
        root.title(tr("app_title"))
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w = min(1020, sw - 40)
        h = min(780, sh - 120)
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+16")
        root.minsize(860, 500)
        root.configure(bg=BG)

        self.setup_style()
        self.bind_clipboard_keys()
        self.bind_context_menu()
        self.build()
        for key, kw in self.startup_notes:
            self.log(tr(key, **kw))
        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEXT, font=(FONT, 10), borderwidth=0)
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD)
        s.configure("TLabel", background=CARD, foreground=MUTED, font=(FONT, 9))
        s.configure("Title.TLabel", background=BG, foreground=TEXT, font=(FONT, 18, "bold"))
        s.configure("Plain.TLabel", background=BG, foreground=TEXT, font=(FONT, 10))
        s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=(FONT, 10))
        s.configure("Section.TLabel", background=CARD, foreground=TEXT, font=(FONT, 11, "bold"))
        s.configure("Pill.TLabel", background=FIELD, foreground=MUTED, font=(FONT, 9, "bold"), padding=(12, 5))
        s.configure("PillOn.TLabel", background="#183a2d", foreground=OK, font=(FONT, 9, "bold"), padding=(12, 5))
        s.configure(
            "TEntry",
            fieldbackground=FIELD,
            foreground=TEXT,
            insertcolor=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=6,
        )
        s.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)], darkcolor=[("focus", ACCENT)])
        s.configure(
            "TSpinbox",
            fieldbackground=FIELD,
            background=FIELD,
            foreground=TEXT,
            arrowcolor=MUTED,
            insertcolor=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=6,
            arrowsize=14,
        )
        s.map("TSpinbox", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)], darkcolor=[("focus", ACCENT)])
        s.configure(
            "TCombobox",
            fieldbackground=FIELD,
            background=FIELD,
            foreground=TEXT,
            arrowcolor=MUTED,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=6,
        )
        s.map(
            "TCombobox",
            fieldbackground=[("readonly", FIELD)],
            foreground=[("readonly", TEXT)],
            selectbackground=[("readonly", FIELD)],
            selectforeground=[("readonly", TEXT)],
            bordercolor=[("focus", ACCENT)],
        )
        self.root.option_add("*TCombobox*Listbox.background", FIELD)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", font=(FONT, 10, "bold"), padding=(18, 8))
        s.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", FIELD)], foreground=[("disabled", MUTED)])
        s.configure("Ghost.TButton", background=FIELD, foreground=TEXT, font=(FONT, 10), padding=(16, 8))
        s.map("Ghost.TButton", background=[("active", BORDER), ("disabled", CARD)], foreground=[("disabled", MUTED)])
        s.configure("Danger.TButton", background="#3a2227", foreground=ERR, font=(FONT, 10), padding=(16, 8))
        s.map("Danger.TButton", background=[("active", "#4a2a31"), ("disabled", CARD)], foreground=[("disabled", MUTED)])
        s.configure(
            "Day.Toolbutton",
            background=FIELD,
            foreground=MUTED,
            font=(FONT, 9, "bold"),
            padding=(9, 6),
            borderwidth=0,
            anchor="center",
        )
        s.map(
            "Day.Toolbutton",
            background=[("selected", ACCENT), ("active", BORDER)],
            foreground=[("selected", "#ffffff"), ("active", TEXT)],
        )
        s.configure(
            "Treeview",
            background=CARD,
            fieldbackground=CARD,
            foreground=TEXT,
            rowheight=34,
            borderwidth=0,
            font=(FONT, 10),
        )
        s.map("Treeview", background=[("selected", "#27304a")], foreground=[("selected", TEXT)])
        s.configure(
            "Treeview.Heading",
            background=CARD,
            foreground=MUTED,
            font=(FONT, 9, "bold"),
            padding=(10, 6),
            borderwidth=0,
        )
        s.map("Treeview.Heading", background=[("active", CARD)])
        s.configure("Vertical.TScrollbar", background=FIELD, troughcolor=CARD, bordercolor=CARD, arrowcolor=MUTED)

    def card(self, parent, title=None):
        outer = tk.Frame(parent, bg=BORDER)
        inner = ttk.Frame(outer, style="Card.TFrame", padding=14)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        if title:
            ttk.Label(inner, text=title, style="Section.TLabel").grid(row=0, column=0, columnspan=8, sticky="w", pady=(0, 8))
        return outer, inner

    def field(self, parent, label, var, row, col, width=18, colspan=1, **kw):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0, 10), pady=(0, 3))
        entry = ttk.Entry(parent, textvariable=var, width=width, **kw)
        entry.grid(row=row + 1, column=col, columnspan=colspan, sticky="we", padx=(0, 10), pady=(0, 8))
        return entry

    def bind_clipboard_keys(self):
        def handler(event):
            virtual = KEYCODE_EVENTS.get(event.keycode)
            if not virtual or event.keysym.lower() in ("v", "c", "x", "a"):
                return None
            event.widget.event_generate(virtual)
            return "break"

        self.root.bind_all("<Control-KeyPress>", handler)

    def bind_context_menu(self):
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=FIELD,
            fg=TEXT,
            activebackground=ACCENT,
            activeforeground="#ffffff",
            bd=0,
        )
        target = {"widget": None}
        items = (("menu_cut", "<<Cut>>"), ("menu_copy", "<<Copy>>"), ("menu_paste", "<<Paste>>"))
        for key, virtual in items:
            menu.add_command(label=tr(key), command=lambda v=virtual: target["widget"].event_generate(v))

        def show(event):
            for index, (key, _) in enumerate(items):
                menu.entryconfigure(index, label=tr(key))
            target["widget"] = event.widget
            event.widget.focus_set()
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        for widget_class in ("TEntry", "TSpinbox"):
            self.root.bind_class(widget_class, "<Button-3>", show)

    def time_picker(self, parent, label, hour_var, minute_var, col):
        ttk.Label(parent, text=label).grid(row=3, column=col, sticky="w", padx=(0, 10), pady=(0, 3))
        box = ttk.Frame(parent, style="Card.TFrame")
        box.grid(row=4, column=col, sticky="w", padx=(0, 10), pady=(0, 8))
        ttk.Spinbox(
            box, textvariable=hour_var, from_=0, to=23, increment=1, format="%02.0f", width=3, wrap=True, justify="center"
        ).pack(side="left")
        ttk.Label(box, text=" : ", style="Section.TLabel").pack(side="left")
        ttk.Spinbox(
            box, textvariable=minute_var, from_=0, to=59, increment=5, format="%02.0f", width=3, wrap=True, justify="center"
        ).pack(side="left")

    def build(self):
        main = ttk.Frame(self.root, padding=(24, 16, 24, 14))
        main.pack(fill="both", expand=True)

        head = ttk.Frame(main)
        head.pack(fill="x", pady=(0, 10))
        titles = ttk.Frame(head)
        titles.pack(side="left")
        ttk.Label(titles, text=tr("app_title"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text=tr("subtitle"), style="Sub.TLabel").pack(anchor="w")
        langs = ttk.Frame(head)
        langs.pack(side="right", padx=(10, 0))
        for code in STRINGS:
            ttk.Radiobutton(
                langs, text=code.upper(), value=code, variable=self.lang_var, style="Day.Toolbutton", command=self.set_language
            ).pack(side="left", padx=2)
        self.pill = ttk.Label(head, text=tr("pill_off"), style="Pill.TLabel")
        self.pill.pack(side="right")

        bar = ttk.Frame(main)
        bar.pack(fill="x", pady=(0, 10))
        self.start_btn = ttk.Button(bar, text=tr("btn_start"), style="Accent.TButton", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar, text=tr("btn_stop"), style="Ghost.TButton", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(10, 0))
        ttk.Button(bar, text=tr("btn_delete"), style="Danger.TButton", command=self.remove_selected).pack(side="right")
        ttk.Button(bar, text=tr("btn_import"), style="Ghost.TButton", command=self.import_ics).pack(
            side="right", padx=(0, 10)
        )

        outer, prof = self.card(main, tr("card_me"))
        outer.pack(fill="x", pady=(0, 10))
        self.field(prof, tr("lbl_name"), self.name_var, 1, 0, width=40)
        prof.columnconfigure(0, weight=1)

        outer, form = self.card(main, tr("card_new"))
        outer.pack(fill="x", pady=(0, 10))
        self.field(form, tr("lbl_title"), self.title_var, 1, 0, width=26)
        ttk.Label(form, text=tr("lbl_platform")).grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(0, 3))
        ttk.Combobox(form, textvariable=self.platform_var, values=PLATFORMS, state="readonly", width=14).grid(
            row=2, column=1, sticky="we", padx=(0, 10), pady=(0, 8)
        )
        self.field(form, tr("lbl_url"), self.url_var, 1, 2, width=30, colspan=3)
        ttk.Label(form, text=tr("lbl_days")).grid(row=3, column=0, columnspan=2, sticky="w", padx=(0, 10), pady=(0, 3))
        days_row = ttk.Frame(form, style="Card.TFrame")
        days_row.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))
        for i, label in enumerate(day_names()):
            ttk.Checkbutton(days_row, text=label, variable=self.day_vars[i], style="Day.Toolbutton").pack(
                side="left", padx=(0, 4)
            )
        self.time_picker(form, tr("lbl_join_at"), self.start_h, self.start_m, 2)
        self.time_picker(form, tr("lbl_leave_at"), self.end_h, self.end_m, 3)
        ttk.Button(form, text=tr("btn_add"), style="Accent.TButton", command=self.add_meeting).grid(
            row=4, column=4, sticky="we", pady=(0, 8)
        )
        form.columnconfigure(0, weight=2)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(2, weight=1)
        form.columnconfigure(3, weight=1)
        form.columnconfigure(4, weight=1)

        log_wrap = tk.Frame(main, bg=BORDER)
        log_wrap.pack(side="bottom", fill="x")
        self.log_box = tk.Text(
            log_wrap,
            height=5,
            state="disabled",
            bg=CARD,
            fg=MUTED,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            font=("Consolas", 9),
            wrap="word",
        )
        self.log_box.pack(fill="x", padx=1, pady=1)

        outer, queue = self.card(main, tr("card_schedule"))
        outer.pack(fill="both", expand=True, pady=(0, 10))
        queue.rowconfigure(1, weight=1)
        queue.columnconfigure(0, weight=1)
        columns = ("on", "title", "platform", "days", "time", "next", "status")
        self.tree = ttk.Treeview(queue, columns=columns, show="headings", height=4, selectmode="extended")
        for col, key, width in (
            ("on", "col_on", 50),
            ("title", "col_title", 220),
            ("platform", "col_platform", 100),
            ("days", "col_days", 150),
            ("time", "col_time", 110),
            ("next", "col_next", 130),
            ("status", "col_status", 110),
        ):
            self.tree.heading(col, text=tr(key), anchor="center" if col == "on" else "w")
            self.tree.column(col, width=width, anchor="center" if col == "on" else "w", stretch=col != "on")
        self.tree.tag_configure("waiting", foreground=ACCENT)
        self.tree.tag_configure("running", foreground=OK)
        self.tree.tag_configure("done", foreground=MUTED)
        self.tree.tag_configure("error", foreground=ERR)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.tree.bind("<Double-1>", self.edit_link)
        self.tree.bind("<Button-1>", self.tree_click)
        self.restore_log()

    def set_pill(self, on):
        if on:
            self.pill.configure(text=tr("pill_on"), style="PillOn.TLabel")
        else:
            self.pill.configure(text=tr("pill_off"), style="Pill.TLabel")

    def restore_log(self):
        self.log_box.configure(state="normal")
        for line in self.log_lines[-200:]:
            self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_language(self):
        global LANG
        LANG = self.lang_var.get()
        self.save()
        for child in self.root.winfo_children():
            child.destroy()
        self.root.title(tr("app_title"))
        self.build()
        self.set_pill(self.running)
        self.start_btn.configure(state="disabled" if self.running else "normal")
        self.stop_btn.configure(state="normal" if self.running else "disabled")
        self.last_signature = None

    def tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell" or self.tree.identify_column(event.x) != "#1":
            return None
        iid = self.tree.identify_row(event.y)
        meeting = next((m for m in self.meetings if m["id"] == iid), None)
        if not meeting:
            return None
        meeting["enabled"] = not meeting.get("enabled", True)
        if not meeting["enabled"] and self.status.get(iid) in ("running", "retry") and iid in self.stops:
            self.stops[iid].set()
        self.save()
        self.last_signature = None
        return "break"

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")

        line = f"{stamp}  {message}\n"
        self.log_lines.append(line)

        def write():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.root.after(0, write)

    def load(self):
        global LANG
        LANG = detect_language()
        if not DATA_FILE.exists():
            return
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            broken = DATA_FILE.with_name("meetings.broken.json")
            try:
                os.replace(DATA_FILE, broken)
                self.startup_notes.append(("backup_made", {"name": broken.name}))
            except OSError:
                pass
            return
        if data.get("lang") in STRINGS:
            LANG = data["lang"]
        self.name_var.set(data.get("name", ""))
        for m in data.get("meetings", []):
            migrated = migrate_meeting(m)
            if migrated:
                self.meetings.append(migrated)
                self.status[migrated["id"]] = "waiting"

    def save(self):
        data = {
            "name": self.name_var.get().strip(),
            "lang": LANG,
            "meetings": self.meetings,
        }
        temp = DATA_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, DATA_FILE)

    def add_meeting(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror(tr("err_title"), tr("err_url"))
            return
        days = [i for i, v in enumerate(self.day_vars) if v.get()]
        if not days:
            messagebox.showerror(tr("err_title"), tr("err_days"))
            return
        try:
            start = parse_time(f"{self.start_h.get()}:{self.start_m.get()}")
            end = parse_time(f"{self.end_h.get()}:{self.end_m.get()}")
        except ValueError:
            messagebox.showerror(tr("err_title"), tr("err_time"))
            return
        if end <= start:
            messagebox.showerror(tr("err_title"), tr("err_order"))
            return
        meeting = {
            "id": uuid.uuid4().hex[:8],
            "title": self.title_var.get().strip() or tr("default_title", platform=self.platform_var.get()),
            "enabled": True,
            "platform": self.platform_var.get(),
            "url": url,
            "days": days,
            "start": start.strftime(TIME_FMT),
            "end": end.strftime(TIME_FMT),
        }
        self.meetings.append(meeting)
        self.status[meeting["id"]] = "waiting"
        self.title_var.set("")
        self.url_var.set("")
        self.save()
        self.last_signature = None
        if not self.running:
            self.log(tr("added_hint"))

    def edit_link(self, event):
        if self.tree.identify_column(event.x) == "#1":
            return
        iid = self.tree.identify_row(event.y)
        meeting = next((m for m in self.meetings if m["id"] == iid), None)
        if not meeting:
            return
        value = simpledialog.askstring(
            tr("link_dialog"), meeting["title"], initialvalue=meeting.get("url", ""), parent=self.root
        )
        if value is None:
            return
        meeting["url"] = value.strip()
        self.save()
        self.last_signature = None

    def import_ics(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title=tr("file_title"),
            filetypes=[(tr("filetype_ical"), "*.ics *.ICS"), (tr("filetype_all"), "*.*")],
        )
        if not path:
            return
        try:
            raw = Path(path).read_bytes()
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp1250")
            items, skipped = parse_ics(text, datetime.now())
        except Exception as exc:
            messagebox.showerror(tr("err_title"), tr("err_read", exc=exc))
            return
        if not items:
            messagebox.showinfo(tr("import_title"), tr("import_none"))
            return
        self.import_dialog(items, skipped)

    def make_toggle(self, parent, var):
        label = tk.Label(parent, width=3, font=("Segoe UI Symbol", 12, "bold"), cursor="hand2")

        def paint(*_):
            if var.get():
                label.configure(text="✓", bg="#1f7a4d", fg="#d6ffe8")
            else:
                label.configure(text="✕", bg="#7a2a2a", fg="#ffc9c9")

        label.bind("<Button-1>", lambda e: var.set(not var.get()))
        var.trace_add("write", paint)
        paint()
        return label

    def import_dialog(self, items, skipped):
        win = tk.Toplevel(self.root)
        win.title(tr("import_title"))
        win.configure(bg=BG)
        win.transient(self.root)
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w = min(1060, sw - 40)
        h = min(640, sh - 120)
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(10, (sh - h) // 3)}")
        win.minsize(760, 360)

        body = ttk.Frame(win, padding=(20, 16, 20, 14))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=tr("import_title"), style="Title.TLabel").pack(anchor="w")
        note = tr("import_note")
        if skipped:
            note += tr("import_skipped", n=skipped)
        ttk.Label(body, text=note, style="Sub.TLabel", wraplength=w - 60, justify="left").pack(anchor="w", pady=(2, 10))

        bottom = ttk.Frame(body)
        bottom.pack(side="bottom", fill="x", pady=(10, 0))

        area = ttk.Frame(body)
        area.pack(fill="both", expand=True)
        canvas = tk.Canvas(area, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        inner.columnconfigure(1, weight=2)
        inner.columnconfigure(4, weight=3)

        rows = []
        for i, item in enumerate(items):
            row = {
                "item": item,
                "use": tk.BooleanVar(value=item["online"]),
                "platform": tk.StringVar(value=item["platform"]),
                "link": tk.StringVar(),
            }
            self.make_toggle(inner, row["use"]).grid(row=i, column=0, padx=(0, 8), pady=3)
            name_label = ttk.Label(inner, text=item["title"], style="Plain.TLabel")
            name_label.grid(row=i, column=1, sticky="w", padx=(0, 12))
            row["use"].trace_add(
                "write", lambda *_, v=row["use"], w=name_label: w.configure(foreground=TEXT if v.get() else MUTED)
            )
            if not item["online"]:
                name_label.configure(foreground=MUTED)
            ttk.Label(inner, text=f"{days_text(item['days'])}  {item['start']}–{item['end']}", style="Sub.TLabel").grid(
                row=i, column=2, sticky="w", padx=(0, 12)
            )
            ttk.Combobox(inner, textvariable=row["platform"], values=PLATFORMS, state="readonly", width=8).grid(
                row=i, column=3, padx=(0, 10)
            )
            entry = ttk.Entry(inner, textvariable=row["link"], width=34)
            entry.grid(row=i, column=4, sticky="we", padx=(0, 6))
            entry.bind("<FocusOut>", lambda e, r=row: share(r))
            rows.append(row)

        def share(source):
            value = source["link"].get().strip()
            if not value:
                return
            for other in rows:
                if other["item"]["subject"] == source["item"]["subject"] and not other["link"].get().strip():
                    other["link"].set(value)

        before_var = tk.StringVar(value="2")
        ttk.Label(bottom, text=tr("import_before"), style="Sub.TLabel").pack(side="left")
        ttk.Spinbox(bottom, textvariable=before_var, from_=0, to=30, increment=1, width=3, justify="center").pack(
            side="left", padx=6
        )
        ttk.Label(bottom, text=tr("import_min"), style="Sub.TLabel").pack(side="left")

        def confirm():
            try:
                before = max(0, min(int(before_var.get()), 60))
            except ValueError:
                messagebox.showerror(tr("err_title"), tr("err_minutes"), parent=win)
                return
            added = 0
            without_link = 0
            for row in rows:
                if not row["use"].get():
                    continue
                item = row["item"]
                begin = datetime.combine(date.today(), parse_time(item["start"])) - timedelta(minutes=before)
                if begin.date() != date.today():
                    begin = datetime.combine(date.today(), datetime.min.time())
                start_text = begin.strftime(TIME_FMT)
                duplicate = any(
                    m["title"] == item["title"] and m["days"] == item["days"] and m["start"] == start_text
                    for m in self.meetings
                )
                if duplicate:
                    continue
                url = row["link"].get().strip()
                meeting = {
                    "id": uuid.uuid4().hex[:8],
                    "title": item["title"],
                    "platform": row["platform"].get(),
                    "url": url,
                    "days": item["days"],
                    "start": start_text,
                    "end": item["end"],
                    "enabled": True,
                }
                self.meetings.append(meeting)
                self.status[meeting["id"]] = "waiting"
                added += 1
                if not url:
                    without_link += 1
            self.save()
            self.last_signature = None
            win.destroy()
            message = tr("imported", n=added)
            if without_link:
                message += tr("imported_nolink", n=without_link)
            self.log(message)

        ttk.Button(bottom, text=tr("btn_cancel"), style="Ghost.TButton", command=win.destroy).pack(side="right")
        ttk.Button(bottom, text=tr("btn_import_do"), style="Accent.TButton", command=confirm).pack(side="right", padx=(0, 10))
        win.grab_set()
        win.focus_set()

    def remove_selected(self):
        for iid in self.tree.selection():
            if self.status.get(iid) == "running":
                if iid in self.stops:
                    self.stops[iid].set()
            self.meetings = [m for m in self.meetings if m["id"] != iid]
            self.status.pop(iid, None)
            self.ran.pop(iid, None)
        self.save()
        self.last_signature = None

    def refresh(self):
        now = datetime.now()
        today = now.date()
        ordered = sorted(self.meetings, key=lambda m: (m["start"], m["title"]))
        rows = []
        for m in ordered:
            enabled = m.get("enabled", True)
            if not enabled:
                status = "off"
            elif not m.get("url"):
                status = "nolink"
            else:
                status = self.status.get(m["id"], "")
            nxt = next_run_text(m, now, self.ran.get(m["id"]) == today) if enabled else "—"
            rows.append((m, status, nxt))
        signature = (LANG,) + tuple((m["id"], status, nxt) for m, status, nxt in rows)
        if signature != self.last_signature:
            self.last_signature = signature
            selected = set(self.tree.selection())
            for item in self.tree.get_children():
                self.tree.delete(item)
            for m, status, nxt in rows:
                self.tree.insert(
                    "",
                    "end",
                    iid=m["id"],
                    values=(
                        "✓" if m.get("enabled", True) else "✕",
                        m["title"],
                        m["platform"],
                        days_text(m["days"]),
                        f"{m['start']}–{m['end']}",
                        nxt,
                        tr("st_" + status) if status else "",
                    ),
                    tags=(STATUS_TAGS.get(status, "waiting"),),
                )
            keep = [i for i in selected if self.tree.exists(i)]
            if keep:
                self.tree.selection_set(keep)
        self.root.after(1000, self.refresh)

    def start(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror(tr("err_title"), tr("err_name"))
            return
        self.save()
        for m in self.meetings:
            if self.status.get(m["id"]) not in ("running", "retry"):
                self.status[m["id"]] = "waiting"
        self.running = True
        keep_awake(True)
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.set_pill(True)
        self.last_signature = None
        threading.Thread(target=self.scheduler, daemon=True).start()
        self.log(tr("queue_started"))
        self.log(tr("awake"))

    def stop(self):
        self.running = False
        keep_awake(False)
        for event in self.stops.values():
            event.set()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.set_pill(False)
        self.log(tr("queue_stopped"))

    def scheduler(self):
        while self.running:
            now = datetime.now()
            today = now.date()
            for m in list(self.meetings):
                mid = m["id"]
                status = self.status.get(mid)
                if status in ("done", "error") and self.ran.get(mid) != today:
                    self.status[mid] = "waiting"
                    status = "waiting"
                if status != "waiting" or self.ran.get(mid) == today:
                    continue
                if not m.get("url") or not m.get("enabled", True) or now.weekday() not in m["days"]:
                    continue
                start, end = window_for(m, today)
                if start <= now < end:
                    self.preempt_running(mid)
                    self.ran[mid] = today
                    self.status[mid] = "running"
                    event = threading.Event()
                    self.stops[mid] = event
                    threading.Thread(target=self.worker, args=(dict(m), event), daemon=True).start()
            time.sleep(1)

    def preempt_running(self, new_id):
        for other, state in list(self.status.items()):
            if other == new_id or state not in ("running", "retry") or other not in self.stops:
                continue
            self.preempted.add(other)
            self.stops[other].set()
            meeting = next((m for m in self.meetings if m["id"] == other), None)
            if meeting:
                self.log(tr("preempted", title=meeting["title"]))

    def worker(self, meeting, event):
        mid = meeting["id"]
        profile = {"name": self.name_var.get().strip()}

        def on_state(state):
            if mid in self.status:
                self.status[mid] = state

        try:
            result = run_with_retries(meeting, profile, self.log, event, on_state=on_state)
        except Exception as exc:
            result = "error"
            self.log(tr("error_log", exc=exc))
        if result == "error":
            beep()
        if mid not in self.status:
            return
        if mid in self.preempted:
            self.preempted.discard(mid)
            self.status[mid] = "done"
        elif event.is_set():
            self.ran.pop(mid, None)
            self.status[mid] = "waiting"
        else:
            self.status[mid] = result

    def on_close(self):
        self.running = False
        keep_awake(False)
        for event in self.stops.values():
            event.set()
        self.save()
        self.root.destroy()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    lock = None if HEADLESS else acquire_instance_lock()
    if lock is None and not HEADLESS:
        LANG = detect_language()
        messagebox.showerror(tr("app_title"), tr("already_running"))
        raise SystemExit(1)
    App(root)
    root.mainloop()
