from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

import app

MOCK = Path(__file__).parent / "mock"


@pytest.fixture
def page():
    with sync_playwright() as p:
        try:
            browser = app.launch_browser(p, [])
        except RuntimeError:
            pytest.skip("browser is not available")
        yield browser.new_context(locale="ru-RU").new_page()
        browser.close()


def test_webex_join_skips_media_and_leaves(page):
    logs = []
    assert app.join_webex(page, (MOCK / "landing.html").as_uri(), "Test User", logs.append)
    state = page.evaluate("({joined: window.joined, skipped: window.skipped, usedMedia: window.usedMedia})")
    assert state["joined"] == "Test User"
    assert state["skipped"] is True
    assert state["usedMedia"] is None
    app.leave_meeting(page)
    assert page.evaluate("window.left") is True
