import json
import os
import re
import sys
import tempfile
import threading
import time
import tkinter as tk
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

from playwright.sync_api import sync_playwright

BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_FILE = BASE_DIR / "meetings.json"
TIME_FMT = "%H:%M"
HEADLESS = os.environ.get("AUTOJOIN_HEADLESS") == "1"
TEAMS = "Teams"
PLATFORMS = ["Webex", TEAMS]
PROFILE_DIR = BASE_DIR / "chrome_profile"
DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

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


def parse_time(value):
    return datetime.strptime(value.strip(), TIME_FMT).time()


def days_text(days):
    if len(days) == 7:
        return "Каждый день"
    return ", ".join(DAYS[d] for d in sorted(days))


def migrate_meeting(m):
    if str(m.get("platform", "")).startswith("Teams"):
        m["platform"] = TEAMS
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
            return "сейчас" if start <= now else f"сегодня {m['start']}"
        if offset == 1:
            return f"завтра {m['start']}"
        return f"{DAYS[day.weekday()]} {m['start']}"
    return "—"


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
    return ", ".join(names[:15]) or "кнопок не найдено"


def snap(page, tag, log):
    try:
        path = BASE_DIR / f"debug_{tag}.png"
        page.screenshot(path=str(path))
        log(f"Скриншот сохранён: {path.name}")
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
        log("Webex: поле имени не найдено")
        return False
    log("Webex: имя введено")
    page.wait_for_timeout(500)
    if not click_join(page, WEBEX_JOIN_PATTERNS, NAME_PATTERNS):
        log("Webex: кнопка входа не найдена")
        log("Кнопки на странице: " + describe_buttons(page))
        snap(page, "webex_join", log)
        return False
    log("Webex: нажал «Присоединиться»")
    end = time.time() + 15
    while time.time() < end:
        dismiss_media_prompt(page)
        page.wait_for_timeout(1000)
    log("Webex: вход выполнен")
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
    raise RuntimeError("Не найден браузер Chrome, Edge или Chromium")


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
        titles = [title or "(без названия)" for _, title in teams_windows()]
        return "; ".join(titles) or "окон Teams нет"
    except Exception as exc:
        return f"не удалось получить список ({exc})"


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
    raise RuntimeError("Не найден браузер Chrome, Edge или Chromium")


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
                    log(
                        "Если в Chrome появилось окно «Открыть приложение Microsoft Teams?», "
                        "отметьте «Всегда разрешать» и нажмите «Открыть приложение». Это нужно только один раз"
                    )
                if not started_app and elapsed > 50:
                    started_app = True
                    target = teams_protocol_url(url)
                    if target and hasattr(os, "startfile"):
                        try:
                            os.startfile(target)
                            log("Teams: запускаю приложение напрямую")
                        except Exception:
                            pass
                page.wait_for_timeout(1500)
            snap(page, "teams_app", log)
            log("Окна Teams: " + describe_teams_windows())
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
            log("Teams: нажал «Присоединиться сейчас»")
            return True
        time.sleep(1)
    log("Teams: кнопка «Присоединиться сейчас» не найдена")
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
            log("Teams: нажал «Выйти»")
            return True
    if handles:
        try:
            win = win_spec(handles[0])
            win.set_focus()
            win.type_keys("^+h")
            log("Teams: выход через Ctrl+Shift+H")
            return True
        except Exception:
            pass
    return False


def run_teams_app(m, profile, log, stop_event):
    end_dt = datetime.combine(date.today(), parse_time(m["end"]))
    title = m["title"] or m["platform"]
    with ComSession():
        log(f"Вхожу: {title}")
        handle = open_teams_app(m["url"], log, stop_event)
        if not handle:
            log("Teams: окно приложения не появилось")
            return
        log("Teams: приложение открыто")
        teams_app_join(handle, log)
        while datetime.now() < end_dt and not stop_event.is_set():
            time.sleep(1)
        log(f"Выхожу: {title}")
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
            log(f"Вхожу: {title}")
            join_webex(page, m["url"], profile["name"], log)
            while datetime.now() < end_dt and not stop_event.is_set() and not page.is_closed():
                page.wait_for_timeout(1000)
            if not page.is_closed():
                log(f"Выхожу: {title}")
                leave_meeting(page)
        finally:
            try:
                browser.close()
            except Exception:
                pass


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

STATUS_TAGS = {
    "ожидает": "waiting",
    "идёт": "running",
    "выполнено": "done",
    "ошибка": "error",
}


class App:
    def __init__(self, root):
        self.root = root
        root.title("Автовход на собрания")
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w = min(1020, sw - 40)
        h = min(780, sh - 120)
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+16")
        root.minsize(860, 500)
        root.configure(bg=BG)
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
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        today = datetime.now().weekday()
        self.day_vars = [tk.BooleanVar(value=(i == today)) for i in range(7)]

        self.load()
        self.setup_style()
        self.build()
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

    def build(self):
        main = ttk.Frame(self.root, padding=(24, 16, 24, 14))
        main.pack(fill="both", expand=True)

        head = ttk.Frame(main)
        head.pack(fill="x", pady=(0, 10))
        titles = ttk.Frame(head)
        titles.pack(side="left")
        ttk.Label(titles, text="Автовход на собрания", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text="Webex и Teams: заходит и выходит сам по дням недели", style="Sub.TLabel").pack(anchor="w")
        self.pill = ttk.Label(head, text="●  Очередь остановлена", style="Pill.TLabel")
        self.pill.pack(side="right")

        bar = ttk.Frame(main)
        bar.pack(fill="x", pady=(0, 10))
        self.start_btn = ttk.Button(bar, text="▶  Запустить очередь", style="Accent.TButton", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar, text="■  Остановить", style="Ghost.TButton", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="Удалить выбранное", style="Danger.TButton", command=self.remove_selected).pack(side="right")

        outer, prof = self.card(main, "Мои данные")
        outer.pack(fill="x", pady=(0, 10))
        self.field(prof, "Имя, которое увидят на собрании", self.name_var, 1, 0, width=40)
        prof.columnconfigure(0, weight=1)

        outer, form = self.card(main, "Новое собрание")
        outer.pack(fill="x", pady=(0, 10))
        self.field(form, "Название", self.title_var, 1, 0, width=26)
        ttk.Label(form, text="Платформа").grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(0, 3))
        ttk.Combobox(form, textvariable=self.platform_var, values=PLATFORMS, state="readonly", width=14).grid(
            row=2, column=1, sticky="we", padx=(0, 10), pady=(0, 8)
        )
        self.field(form, "Ссылка на собрание", self.url_var, 1, 2, width=30, colspan=3)
        ttk.Label(form, text="Дни недели").grid(row=3, column=0, columnspan=2, sticky="w", padx=(0, 10), pady=(0, 3))
        days_row = ttk.Frame(form, style="Card.TFrame")
        days_row.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))
        for i, label in enumerate(DAYS):
            ttk.Checkbutton(days_row, text=label, variable=self.day_vars[i], style="Day.Toolbutton").pack(
                side="left", padx=(0, 4)
            )
        self.field(form, "Зайти в (ЧЧ:ММ)", self.start_var, 3, 2, width=12)
        self.field(form, "Выйти в (ЧЧ:ММ)", self.end_var, 3, 3, width=12)
        ttk.Button(form, text="＋  Добавить", style="Accent.TButton", command=self.add_meeting).grid(
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

        outer, queue = self.card(main, "Расписание")
        outer.pack(fill="both", expand=True, pady=(0, 10))
        queue.rowconfigure(1, weight=1)
        queue.columnconfigure(0, weight=1)
        columns = ("title", "platform", "days", "time", "next", "status")
        self.tree = ttk.Treeview(queue, columns=columns, show="headings", height=4, selectmode="extended")
        for col, text, width in (
            ("title", "Название", 220),
            ("platform", "Платформа", 100),
            ("days", "Дни", 150),
            ("time", "Время", 110),
            ("next", "Ближайшее", 130),
            ("status", "Статус", 110),
        ):
            self.tree.heading(col, text=text, anchor="w")
            self.tree.column(col, width=width, anchor="w")
        self.tree.tag_configure("waiting", foreground=ACCENT)
        self.tree.tag_configure("running", foreground=OK)
        self.tree.tag_configure("done", foreground=MUTED)
        self.tree.tag_configure("error", foreground=ERR)
        scroll = ttk.Scrollbar(queue, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")
        self.tree.bind("<Delete>", lambda e: self.remove_selected())

    def set_pill(self, on):
        if on:
            self.pill.configure(text="●  Очередь работает", style="PillOn.TLabel")
        else:
            self.pill.configure(text="●  Очередь остановлена", style="Pill.TLabel")

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")

        def write():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"{stamp}  {message}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.root.after(0, write)

    def load(self):
        if not DATA_FILE.exists():
            return
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        self.name_var.set(data.get("name", ""))
        for m in data.get("meetings", []):
            migrated = migrate_meeting(m)
            if migrated:
                self.meetings.append(migrated)
                self.status[migrated["id"]] = "ожидает"

    def save(self):
        data = {
            "name": self.name_var.get().strip(),
            "meetings": self.meetings,
        }
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_meeting(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Ошибка", "Вставьте ссылку на собрание")
            return
        days = [i for i, v in enumerate(self.day_vars) if v.get()]
        if not days:
            messagebox.showerror("Ошибка", "Выберите хотя бы один день недели")
            return
        try:
            start = parse_time(self.start_var.get())
            end = parse_time(self.end_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный формат времени. Пример: 12:30")
            return
        if end <= start:
            messagebox.showerror("Ошибка", "Время выхода должно быть позже времени входа")
            return
        meeting = {
            "id": uuid.uuid4().hex[:8],
            "title": self.title_var.get().strip() or f"Собрание {self.platform_var.get()}",
            "platform": self.platform_var.get(),
            "url": url,
            "days": days,
            "start": start.strftime(TIME_FMT),
            "end": end.strftime(TIME_FMT),
        }
        self.meetings.append(meeting)
        self.status[meeting["id"]] = "ожидает"
        self.title_var.set("")
        self.url_var.set("")
        self.start_var.set("")
        self.end_var.set("")
        self.save()
        self.last_signature = None
        if not self.running:
            self.log("Собрание добавлено. Нажмите «Запустить очередь», чтобы оно сработало")

    def remove_selected(self):
        for iid in self.tree.selection():
            if self.status.get(iid) == "идёт":
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
            status = self.status.get(m["id"], "")
            nxt = next_run_text(m, now, self.ran.get(m["id"]) == today)
            rows.append((m, status, nxt))
        signature = tuple((m["id"], status, nxt) for m, status, nxt in rows)
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
                        m["title"],
                        m["platform"],
                        days_text(m["days"]),
                        f"{m['start']}–{m['end']}",
                        nxt,
                        status,
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
            messagebox.showerror("Ошибка", "Впишите своё имя")
            return
        self.save()
        for m in self.meetings:
            if self.status.get(m["id"]) != "идёт":
                self.status[m["id"]] = "ожидает"
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.set_pill(True)
        self.last_signature = None
        threading.Thread(target=self.scheduler, daemon=True).start()
        self.log("Очередь запущена")

    def stop(self):
        self.running = False
        for event in self.stops.values():
            event.set()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.set_pill(False)
        self.log("Очередь остановлена")

    def scheduler(self):
        while self.running:
            now = datetime.now()
            today = now.date()
            for m in list(self.meetings):
                mid = m["id"]
                status = self.status.get(mid)
                if status in ("выполнено", "ошибка") and self.ran.get(mid) != today:
                    self.status[mid] = "ожидает"
                    status = "ожидает"
                if status != "ожидает" or self.ran.get(mid) == today:
                    continue
                if now.weekday() not in m["days"]:
                    continue
                start, end = window_for(m, today)
                if start <= now < end:
                    self.ran[mid] = today
                    self.status[mid] = "идёт"
                    event = threading.Event()
                    self.stops[mid] = event
                    threading.Thread(target=self.worker, args=(dict(m), event), daemon=True).start()
            time.sleep(1)

    def worker(self, meeting, event):
        mid = meeting["id"]
        profile = {"name": self.name_var.get().strip()}
        try:
            run_meeting(meeting, profile, self.log, event)
            result = "выполнено"
        except Exception as exc:
            result = "ошибка"
            self.log(f"Ошибка: {exc}")
        if mid not in self.status:
            return
        if event.is_set():
            self.ran.pop(mid, None)
            self.status[mid] = "ожидает"
        else:
            self.status[mid] = result

    def on_close(self):
        self.running = False
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
    App(root)
    root.mainloop()
