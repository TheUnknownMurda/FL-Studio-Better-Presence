"""The settings window, drawn off screen: nothing appears while the tests run."""
import time
import types

import pytest

from fakes import SONG, FakeDiscord, FakeWatcher
from flbp.app import describe
from flbp.discord_ipc import Status
from flbp.engine import Engine
from flbp.settings import DEFAULTS, Settings


@pytest.fixture
def window(application):
    from flbp.ui.settings_window import SettingsWindow
    settings = Settings()
    engine = Engine(settings, FakeDiscord(), FakeWatcher(SONG))
    engine.tick()
    window = SettingsWindow(settings, engine)
    window.show()
    yield window
    window.close()


def wait(milliseconds):
    from PySide6 import QtWidgets
    end = time.monotonic() + milliseconds / 1000
    while time.monotonic() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)


def test_shows_the_saved_settings(application):
    from flbp.ui.settings_window import SettingsWindow
    Settings().update(secret=True, custom_state="{bpm} · album", idle_minutes=25, idle_action="hide",
                      small_icon="custom", small_icon_url="https://example.com/logo.png", button_label="Listen",
                      button_url="https://soundcloud.com/me", reset_timer_per_project=False)
    settings = Settings()
    window = SettingsWindow(settings, Engine(settings, FakeDiscord(), FakeWatcher(SONG)))
    try:
        assert window.secret_card.switch.isChecked()
        assert window.second_line.mode.value() == "custom"
        assert window.second_line.field.text() == "{bpm} · album"
        assert window.first_line.mode.value() == "auto"
        assert window.away_card.minutes.value() == 25
        assert window.away_card.action.value() == "hide"
        assert window.small_icon.choice() == "custom"
        assert window.small_icon.link_text() == "https://example.com/logo.png"
        assert window.button_card.label() == "Listen"
        assert not window.timer_card.restart.is_on()
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


def test_own_text_suggested(window):
    window.second_line.mode._pick("custom")
    assert window.second_line.field.text() == "{bpm}"
    window.second_line.mode._pick("auto")
    wait(400)
    assert Settings()["custom_state"] == ""


def test_placeholder_buttons(window):
    from PySide6 import QtWidgets
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


def test_own_image(window):
    window.small_icon.mode._pick("custom")
    assert window.small_icon.link_error.isVisible()  # asks for the link
    window.small_icon.link.setText("example.com/logo.png")
    assert "https://" in window.small_icon.link_error.text()
    window.small_icon.link.setText("https://example.com/logo.png")
    window.small_icon.hover.setText("My label")
    wait(400)
    assert not window.small_icon.link_error.isVisible()
    assets = window.engine.discord.shown["assets"]
    assert assets["small_image"] == "https://example.com/logo.png"
    assert assets["small_text"] == "My label"
    assert window.preview.badge_text.text() == "My label"


def test_button(window):
    window.button_card.label_field.setText("My SoundCloud")
    assert window.button_card.error.isVisible()  # the link is missing
    window.button_card.link.setText("https://soundcloud.com/me")
    wait(400)
    assert not window.button_card.error.isVisible()
    assert window.engine.discord.shown["buttons"] == [{"label": "My SoundCloud", "url": "https://soundcloud.com/me"}]
    assert window.preview.button.text() == "My SoundCloud"


def test_away_settings(window):
    window.away_card.minutes.setValue(3)
    window.away_card.action._pick("hide")
    wait(400)
    assert Settings()["idle_minutes"] == 3
    assert Settings()["idle_action"] == "hide"
    # "Keep my own text" only shows with an own text while "Idle" is shown
    assert not window.away_card.keep.isVisible()
    window.away_card.action._pick("show")
    window.first_line.mode._pick("custom")
    wait(400)
    assert window.away_card.keep.isVisible()


def test_status_hidden(window):
    window._enabled.setChecked(False)
    wait(400)
    assert window.engine.discord.shown is None
    assert window.preview.notes["hiddenNote"].isVisible()
    assert window.preview.card.graphicsEffect() is not None


def test_discord_problems_in_the_preview(window):
    discord = window.engine.discord
    discord.error = "child \"activity\" fails"
    window.refresh_preview()
    assert window.preview.banner.text() == "Discord refused your status: child \"activity\" fails"
    discord.status, discord.error = Status.NO_DISCORD, ""
    window.refresh_preview()
    assert window.preview.banner.text().startswith("Discord isn't open")
    discord.status = Status.CONNECTED
    window.refresh_preview()
    assert not window.preview.banner.isVisible()
    assert window.preview.connection.text() == "● Connected to Discord as Tester"


def test_example_while_fl_studio_is_closed(application):
    from flbp.ui.settings_window import SettingsWindow
    settings = Settings()
    engine = Engine(settings, FakeDiscord(Status.OFF, ""), FakeWatcher())
    engine.tick()
    window = SettingsWindow(settings, engine)
    window.show()
    try:
        assert window.preview.notes["info"].isVisible()
        assert window.preview.details.text() == "Composing · Summer Vibes"
    finally:
        window.close()


def test_reset_to_defaults(window):
    from PySide6 import QtWidgets
    window.secret_card.switch.setChecked(True)
    window._reset.click()
    assert window._confirm.isVisible()
    window._confirm.findChild(QtWidgets.QPushButton, "danger").click()
    assert Settings().values == DEFAULTS
    assert not window.secret_card.switch.isChecked()
    assert not window._confirm.isVisible()


def test_startup_switch_off_outside_the_exe(window):
    assert not window.startup_card.switch.isEnabled()


def describe_with(hidden="", status=Status.CONNECTED, error="", details="Composing · Summer Vibes"):
    engine = types.SimpleNamespace(hidden=hidden, activity={"details": details},
                                   discord=types.SimpleNamespace(status=status, error=error))
    return describe(engine)


def test_status_line_of_the_menu():
    assert describe_with() == ("shown", "Showing: Composing · Summer Vibes")
    assert describe_with(hidden="closed") == ("not_shown", "Waiting for FL Studio")
    assert describe_with(hidden="off") == ("not_shown", "Status hidden")
    assert describe_with(hidden="away") == ("not_shown", "Hidden while you're away")
    assert describe_with(status=Status.NO_DISCORD) == ("problem", "Discord isn't open")
    assert describe_with(status=Status.REFUSED) == ("problem", "Discord refused the app")
    assert describe_with(error="child \"activity\" fails") == ("problem", "Discord refused the status")
    assert describe_with(status=Status.OFF) == ("shown", "Connecting to Discord…")
