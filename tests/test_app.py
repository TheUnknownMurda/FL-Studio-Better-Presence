"""The icon next to the clock and its menu, off screen: no icon appears while the tests run."""
import time

import pytest

from fakes import SONG, FakeDiscord, FakeWatcher
from flbp.engine import Engine
from flbp.settings import Settings


def wait(milliseconds):
    from PySide6 import QtWidgets
    end = time.monotonic() + milliseconds / 1000
    while time.monotonic() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)


@pytest.fixture
def make_app(application, monkeypatch):
    from PySide6 import QtWidgets
    from flbp.app import App
    monkeypatch.setattr(QtWidgets.QApplication, "quit", lambda: None)  # the tests' Qt keeps running
    apps = []

    def make(welcome=False, state=SONG):
        settings = Settings()
        app = App(settings, Engine(settings, FakeDiscord(), FakeWatcher(state)), welcome=welcome)
        app.messages = []
        app.tray.showMessage = lambda *args: app.messages.append(args[1])
        apps.append(app)
        return app

    yield make
    for app in apps:
        if app.window is not None:
            app.window.close()
        app.timer.stop()


def test_status_line_and_icon(make_app):
    app = make_app()
    assert app.status_action.text() == "Showing: Composing · Summer Vibes"
    assert app.tray.toolTip() == "FL Studio Better Presence\nShowing: Composing · Summer Vibes"
    assert not app.tray.icon().isNull()


def test_menu_hides_the_status(make_app):
    app = make_app()
    app.enabled_action.trigger()
    assert Settings()["enabled"] is False
    assert app.engine.discord.shown is None
    assert app.status_action.text() == "Status hidden"
    app.enabled_action.trigger()
    assert app.engine.discord.shown["details"] == "Composing · Summer Vibes"


def test_menu_secret_mode(make_app):
    app = make_app()
    app.secret_action.trigger()
    assert Settings()["secret"] is True
    assert app.engine.discord.shown["details"] == "Composing"


def test_menu_and_window_agree(make_app):
    app = make_app()
    app.show_settings()
    app.enabled_action.trigger()
    assert not app.window._enabled.isChecked()
    app.window.secret_card.switch.setChecked(True)
    wait(400)
    assert app.secret_action.isChecked()


def test_one_settings_window(make_app):
    app = make_app()
    app.show_settings()
    first = app.window
    app.show_settings()
    assert app.window is first
    first.close()
    wait(50)
    assert app.window is None


def test_welcome_message_once(make_app):
    app = make_app(welcome=True)
    app.show_settings()
    app.window.close()
    wait(50)
    assert len(app.messages) == 1 and "next to the clock" in app.messages[0]
    app.show_settings()
    app.window.close()
    wait(50)
    assert len(app.messages) == 1


def test_waiting_for_fl_studio(make_app):
    from flbp.fl_watcher import FLState
    app = make_app(state=FLState())
    assert app.status_action.text() == "Waiting for FL Studio"
    assert app.engine.discord.shown is None


def test_messages_from_another_copy(make_app):
    app = make_app()
    app.handle_message("settings")
    assert app.window is not None
    app.handle_message("something else")  # ignored
    app.handle_message("quit")
    assert app.engine.discord.stopped


def test_quit(make_app):
    app = make_app()
    app.show_settings()
    app.quit()
    assert app.engine.discord.stopped
    assert not app.timer.isActive()
