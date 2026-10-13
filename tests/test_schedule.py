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
