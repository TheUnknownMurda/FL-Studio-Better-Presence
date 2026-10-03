import json
import os

from flbp.settings import DEFAULTS, Settings


def test_defaults_on_first_run():
    settings = Settings()
    assert settings.first_run
    assert settings.values == DEFAULTS
    assert settings.path.startswith(os.environ["FLBP_CONFIG_DIR"])


def test_saved_and_read_again():
    Settings().update(secret=True, custom_details="{task} 🎹", idle_minutes=25)
    settings = Settings()
    assert not settings.first_run
    assert settings["secret"] is True
    assert settings["custom_details"] == "{task} 🎹"
    assert settings["idle_minutes"] == 25


def test_damaged_values_keep_their_default():
    settings = Settings()
    os.makedirs(os.path.dirname(settings.path))
    with open(settings.path, "w", encoding="utf-8") as file:
        json.dump({"secret": "yes", "small_icon": "huge", "idle_minutes": 9999, "show_bpm": False}, file)
    settings = Settings()
    assert settings["secret"] is False
    assert settings["small_icon"] == "task"
    assert settings["idle_minutes"] == 240
    assert settings["show_bpm"] is False


def test_unreadable_file():
    settings = Settings()
    os.makedirs(os.path.dirname(settings.path))
    with open(settings.path, "w", encoding="utf-8") as file:
        file.write("{not json")
    assert Settings().values == DEFAULTS


def test_reset():
    settings = Settings()
    settings.update(secret=True)
    settings.reset()
    assert Settings().values == DEFAULTS
