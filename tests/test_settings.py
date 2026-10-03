import json
import os

from flbp.settings import DEFAULTS, Settings


def test_defaults_on_first_run():
    settings = Settings()
    assert settings.first_run
    assert settings.values == DEFAULTS
    assert settings.path.startswith(os.environ["FLBP_CONFIG_DIR"])


def test_saved_and_read_again():
    Settings().update(secret_mode="always", custom_details="{task} 🎹", idle_minutes=25)
    settings = Settings()
    assert not settings.first_run
    assert settings["secret_mode"] == "always"
    assert settings["custom_details"] == "{task} 🎹"
    assert settings["idle_minutes"] == 25


def test_damaged_values_keep_their_default():
    settings = Settings()
    os.makedirs(os.path.dirname(settings.path))
    with open(settings.path, "w", encoding="utf-8") as file:
        json.dump({"secret": "yes", "small_icon": "huge", "idle_minutes": 9999, "show_bpm": False}, file)
    settings = Settings()
    assert settings["secret_mode"] == "off"
    assert settings["small_icon"] == "task"
    assert settings["idle_minutes"] == 240
    assert settings["show_bpm"] is False


def test_unreadable_file():
    settings = Settings()
    os.makedirs(os.path.dirname(settings.path))
    with open(settings.path, "w", encoding="utf-8") as file:
        file.write("{not json")
    assert Settings().values == DEFAULTS


def test_half_an_emoji_pasted_in_a_text():
    Settings().update(custom_details="Melody\ud834 ♪ 🎹")
    assert Settings()["custom_details"] == "Melody\ud834 ♪ 🎹"


def test_file_with_byte_order_mark():
    settings = Settings()
    os.makedirs(os.path.dirname(settings.path))
    with open(settings.path, "w", encoding="utf-8-sig") as file:  # as old Notepad saves
        json.dump({"secret_mode": "always"}, file)
    assert Settings()["secret_mode"] == "always"


def test_disk_refusing_doesnt_stop_the_app(tmp_path):
    settings = Settings(path=str(tmp_path))  # a folder: the file can't be written there
    settings.update(secret_mode="always")  # logged, not raised
    assert settings["secret_mode"] == "always"  # still applies until the app quits


def test_reset():
    settings = Settings()
    settings.update(secret_mode="always")
    settings.reset()
    assert Settings().values == DEFAULTS


def test_settings_of_version_1_0():
    settings = Settings()
    os.makedirs(os.path.dirname(settings.path))
    with open(settings.path, "w", encoding="utf-8") as file:
        json.dump({"secret": True, "reset_timer_per_project": False, "button_url": "https://soundcloud.com/me"}, file)
    settings = Settings()
    assert settings["secret_mode"] == "always"
    assert settings["timer_mode"] == "fl"
    assert settings["button_link"] == "mine"
    assert settings["button_url"] == "https://soundcloud.com/me"
