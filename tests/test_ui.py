"""The settings window and the app's status line, drawn off screen: nothing appears while the tests run."""
import os
import time
import types
import uuid

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtWidgets  # noqa: E402

from flbp.app import describe  # noqa: E402
from flbp.discord_ipc import Status  # noqa: E402
from flbp.engine import Engine  # noqa: E402
from flbp.fl_watcher import FLState, Panel  # noqa: E402
from flbp.settings import DEFAULTS, Settings  # noqa: E402
from flbp.ui.settings_window import SettingsWindow  # noqa: E402

SONG = FLState(running=True, project="Summer Vibes", version="2025", panel=Panel("piano_roll", "Lead synth"),
               foreground=True)


class FakeWatcher:
    def __init__(self, state):
        self.state = state

    def poll(self):
        return self.state

    def user_input_in_fl(self, state):
        return True


class FakeDiscord:
    def __init__(self):
        self.status = Status.CONNECTED
        self.user = "Tester"
        self.error = ""
        self.pipe_prefix = rf"\\.\pipe\flbp-test-{uuid.uuid4().hex}-"
        self.shown = None

    def show(self, activity):
        self.shown = activity

    def stop(self):
        pass


@pytest.fixture(scope="module")
def application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def window(application):
    settings = Settings()
    engine = Engine(settings, FakeDiscord(), FakeWatcher(SONG))
    engine.tick()
    window = SettingsWindow(settings, engine)
    window.show()
    yield window
    window.close()


def wait(milliseconds):
    end = time.monotonic() + milliseconds / 1000
    while time.monotonic() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)


def test_shows_the_saved_settings(application):
    Settings().update(secret=True, custom_state="{bpm} · album", idle_minutes=25, idle_action="hide")
    settings = Settings()
    window = SettingsWindow(settings, Engine(settings, FakeDiscord(), FakeWatcher(SONG)))
    try:
        assert window.secret_card.switch.isChecked()
        assert window.second_line.mode.value() == "custom"
        assert window.second_line.field.text() == "{bpm} · album"
        assert window.first_line.mode.value() == "auto"
        assert window.away_card.minutes.value() == 25
        assert window.away_card.action.value() == "hide"
    finally:
        window.close()


def test_a_switch_is_saved_and_shown_in_discord(window):
    window.secret_card.switch.setChecked(True)
    wait(400)
    assert Settings()["secret"] is True
    assert window.engine.discord.shown["details"] == "Composing"
    assert window.preview.details.text() == "Composing"


def test_typing_is_applied_once_it_pauses(window):
    window.first_line.mode._pick("custom")
    window.first_line.field.setText("Cooking {task}")
    assert Settings()["custom_details"] != "Cooking {task}"
    wait(400)
    assert Settings()["custom_details"] == "Cooking {task}"
    assert window.engine.discord.shown["details"] == "Cooking Composing"


def test_closing_applies_what_was_typed(window):
    window.first_line.mode._pick("custom")
    window.first_line.field.setText("Late night session")
    window.close()
    assert Settings()["custom_details"] == "Late night session"


def test_placeholder_buttons(window):
    window.second_line.mode._pick("custom")
    window.second_line.field.setText("")
    bar = window.second_line.field.parent().findChildren(QtWidgets.QPushButton, "chip")
    next(button for button in bar if button.text() == "BPM").click()
    assert window.second_line.field.text() == "{bpm}"


def test_unknown_placeholder_warning(window):
    window.first_line.mode._pick("custom")
    window.first_line.field.setText("{task] on {project}")
    assert window.first_line.note.isVisible()
    assert "{task]" in window.first_line.note.text()


def test_status_hidden(window):
    window._enabled.setChecked(False)
    wait(400)
    assert window.engine.discord.shown is None
    assert window.preview.notes["hiddenNote"].isVisible()
    assert window.preview.card.graphicsEffect() is not None


def test_reset_to_defaults(window):
    window.secret_card.switch.setChecked(True)
    window._reset.click()
    assert window._confirm.isVisible()
    window._confirm.findChild(QtWidgets.QPushButton, "danger").click()
    assert Settings().values == DEFAULTS
    assert not window.secret_card.switch.isChecked()
    assert not window._confirm.isVisible()


def test_startup_switch_off_outside_the_exe(window):
    assert not window.startup_card.switch.isEnabled()


def describe_with(hidden="", status=Status.CONNECTED, details="Composing · Summer Vibes"):
    engine = types.SimpleNamespace(hidden=hidden, activity={"details": details},
                                   discord=types.SimpleNamespace(status=status))
    return describe(engine)


def test_status_line_of_the_menu():
    assert describe_with() == ("shown", "Showing: Composing · Summer Vibes")
    assert describe_with(hidden="closed") == ("not_shown", "Waiting for FL Studio")
    assert describe_with(hidden="off") == ("not_shown", "Status hidden")
    assert describe_with(hidden="away") == ("not_shown", "Hidden while you're away")
    assert describe_with(status=Status.NO_DISCORD) == ("problem", "Discord isn't open")
    assert describe_with(status=Status.REFUSED) == ("problem", "Discord refused the app")
    assert describe_with(status=Status.OFF) == ("shown", "Connecting to Discord…")
