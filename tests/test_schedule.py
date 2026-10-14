from datetime import datetime

import app

MEETING = {"days": [0, 2], "start": "12:30", "end": "13:00"}


def test_parse_time_accepts_short_hours():
    parsed = app.parse_time("9:05")
    assert (parsed.hour, parsed.minute) == (9, 5)


def test_days_text():
    assert app.days_text([2, 0]) == "Пн, Ср"
    assert app.days_text(list(range(7))) == "Каждый день"


def test_next_run_before_meeting_today():
    assert app.next_run_text(MEETING, datetime(2026, 10, 12, 12, 0), False) == "сегодня 12:30"


def test_next_run_during_meeting():
    assert app.next_run_text(MEETING, datetime(2026, 10, 12, 12, 40), False) == "сейчас"


def test_next_run_after_already_joined_today():
    assert app.next_run_text(MEETING, datetime(2026, 10, 12, 12, 40), True) == "Ср 12:30"


def test_next_run_after_meeting_ended():
    assert app.next_run_text(MEETING, datetime(2026, 10, 12, 13, 5), False) == "Ср 12:30"


def test_next_run_tomorrow():
    assert app.next_run_text(MEETING, datetime(2026, 10, 13, 9, 0), False) == "завтра 12:30"


def test_window_for_uses_given_day():
    start, end = app.window_for(MEETING, datetime(2026, 10, 12).date())
    assert start == datetime(2026, 10, 12, 12, 30)
    assert end == datetime(2026, 10, 12, 13, 0)


def test_migrate_old_dated_meeting():
    old = {"id": "x", "platform": "Webex", "start": "2026-10-12 12:30", "end": "2026-10-12 13:00"}
    migrated = app.migrate_meeting(old)
    assert migrated["days"] == [0]
    assert migrated["start"] == "12:30"
    assert migrated["end"] == "13:00"


def test_migrate_old_teams_platform_names():
    for name in ("Teams", "Teams (браузер)", "Teams (приложение)"):
        meeting = {"id": "x", "platform": name, "days": [1], "start": "9:00", "end": "10:00"}
        assert app.migrate_meeting(meeting)["platform"] == "Teams"


def test_migrate_broken_entry_is_dropped():
    assert app.migrate_meeting({"id": "x", "platform": "Webex"}) is None


def test_teams_protocol_url():
    assert app.teams_protocol_url("https://teams.microsoft.com/meet/123?p=abc") == "msteams:/meet/123?p=abc"
    assert app.teams_protocol_url("https://example.com/x") is None


def test_parse_ics_weekly_events():
    from pathlib import Path

    text = Path(__file__).parent.joinpath("mock", "timetable.ics").read_text(encoding="utf-8")
    items, skipped = app.parse_ics(text, datetime(2026, 10, 14, 17, 0))
    assert skipped == 0
    assert len(items) == 14
    assert sum(1 for it in items if it["online"]) == 9
    first = items[0]
    assert first["days"] == [0]
    assert (first["start"], first["end"]) == ("10:50", "12:20")
    assert first["title"] == "Manažment softvérových projektov · Cvičenie laboratórne"


def test_parse_ics_skips_finished_series():
    from pathlib import Path

    text = Path(__file__).parent.joinpath("mock", "timetable.ics").read_text(encoding="utf-8")
    items, skipped = app.parse_ics(text, datetime(2027, 6, 1, 9, 0))
    assert items == []
    assert skipped == 14


def test_language_switch_changes_texts():
    try:
        app.LANG = "en"
        assert app.days_text([0, 2]) == "Mon, Wed"
        assert app.next_run_text(MEETING, datetime(2026, 10, 13, 9, 0), False) == "tomorrow 12:30"
    finally:
        app.LANG = "ru"


def test_all_languages_have_same_keys():
    assert set(app.STRINGS["ru"]) == set(app.STRINGS["en"])


def make_retry_env(monkeypatch):
    import threading
    from datetime import timedelta

    monkeypatch.setattr(app, "internet_ok", lambda: True)
    monkeypatch.setattr(app, "RETRY_DELAY", 0)
    meeting = {"title": "T", "platform": "Webex", "end": "23:59"}
    end_dt = datetime.now() + timedelta(hours=1)
    return meeting, end_dt, threading.Event()


def test_retries_until_success(monkeypatch):
    meeting, end_dt, stop = make_retry_env(monkeypatch)
    calls = []

    def runner(m, profile, log, event):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("boom")
        event.set()

    states = []
    result = app.run_with_retries(meeting, {}, lambda msg: None, stop, runner=runner, end_dt=end_dt, on_state=states.append)
    assert result == "done"
    assert len(calls) == 3
    assert "retry" in states


def test_gives_up_after_max_attempts(monkeypatch):
    meeting, end_dt, stop = make_retry_env(monkeypatch)
    calls = []

    def runner(m, profile, log, event):
        calls.append(1)
        raise RuntimeError("boom")

    result = app.run_with_retries(meeting, {}, lambda msg: None, stop, runner=runner, end_dt=end_dt)
    assert result == "error"
    assert len(calls) == app.MAX_ATTEMPTS


def test_rejoins_when_meeting_drops(monkeypatch):
    meeting, end_dt, stop = make_retry_env(monkeypatch)
    monkeypatch.setattr(app, "DROP_DELAY", 0)
    calls = []

    def runner(m, profile, log, event):
        calls.append(1)
        if len(calls) == 2:
            event.set()

    logs = []
    result = app.run_with_retries(meeting, {}, logs.append, stop, runner=runner, end_dt=end_dt)
    assert result == "done"
    assert len(calls) == 2
    assert any("lost" in x or "потеряна" in x for x in logs)


def test_waits_for_internet(monkeypatch):
    import threading
    from datetime import timedelta

    answers = iter([False, False, True])
    monkeypatch.setattr(app, "internet_ok", lambda: next(answers))
    stop = threading.Event()
    stop.wait = lambda timeout=None: None
    logs = []
    assert app.wait_for_internet(datetime.now() + timedelta(hours=1), stop, logs.append)
    assert len(logs) == 2


def make_root():
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        return root
    except Exception:
        import pytest

        pytest.skip("no display for Tk")


def test_app_restores_saved_data_on_second_launch(monkeypatch, tmp_path):
    import json

    data_file = tmp_path / "meetings.json"
    saved = {
        "name": "Illia",
        "lang": "en",
        "meetings": [
            {"id": "a1", "title": "T", "platform": "Webex", "url": "https://x", "days": [0], "start": "09:00", "end": "10:00"}
        ],
    }
    data_file.write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(app, "DATA_FILE", data_file)
    root = make_root()
    try:
        window = app.App(root)
        assert window.name_var.get() == "Illia"
        assert [m["id"] for m in window.meetings] == ["a1"]
        assert window.meetings[0]["enabled"] is True
        assert app.LANG == "en"
    finally:
        app.LANG = "ru"
        root.destroy()


def test_app_survives_broken_data_file(monkeypatch, tmp_path):
    data_file = tmp_path / "meetings.json"
    data_file.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(app, "DATA_FILE", data_file)
    root = make_root()
    try:
        window = app.App(root)
        assert window.meetings == []
        assert (tmp_path / "meetings.broken.json").exists()
    finally:
        root.destroy()
