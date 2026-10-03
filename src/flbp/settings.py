"""
The user's settings, saved as JSON in %APPDATA%\\FL Studio Better Presence.
"""
import json
import logging
import os
import time

from . import APP_NAME

log = logging.getLogger("flbp")

DEFAULTS = {
    "enabled": True,  # show my status
    # Hide the project's name, for client work: never, always, or for the projects whose name holds a word
    "secret_mode": "off",
    "secret_words": "client",  # separated by commas
    "secret_mode_before": "off",  # where unchecking Secret mode in the icon's menu goes back to
    "show_task": True,  # first line: what the user is doing
    "show_project": True,  # first line: the project's name
    "show_bpm": True,  # second line: the tempo
    "custom_details": "",  # the user's own first line, empty for the automatic one
    "custom_state": "",  # the user's own second line
    "small_icon": "task",
    "small_icon_url": "",
    "small_icon_text": "",
    "button_label": "",
    "button_url": "",
    "button_link": "mine",  # button_url, or the link typed in the open project's Project info
    "idle_minutes": 10,
    "idle_action": "show",
    "custom_text_while_idle": False,
    # The timer restarts for each project, counts since FL Studio was opened, or shows the whole project's time
    "timer_mode": "session",
}
CHOICES = {
    "secret_mode": ("off", "always", "some"),
    "secret_mode_before": ("off", "some"),
    "small_icon": ("task", "custom", "none"),
    "button_link": ("mine", "project"),
    "idle_action": ("show", "hide", "off"),  # show "Idle", hide the status, or do nothing
    "timer_mode": ("session", "fl", "project"),
}
IDLE_MINUTES_RANGE = (1, 240)


def config_dir():
    """Where the settings are saved. Tests use their own folder with FLBP_CONFIG_DIR."""
    return os.environ.get("FLBP_CONFIG_DIR") or os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                                                            APP_NAME)


class Settings:

    def __init__(self, path=None):
        self.path = path or os.path.join(config_dir(), "settings.json")
        self.values = dict(DEFAULTS)
        self.first_run = not os.path.exists(self.path)
        self.load()

    def __getitem__(self, key):
        return self.values[key]

    def load(self):
        """Reads the saved settings. A missing or damaged value keeps its default."""
        try:
            # utf-8-sig also reads a file saved by an editor that adds a byte order mark, like old Notepad
            with open(self.path, encoding="utf-8-sig") as file:
                saved = json.load(file)
        except (OSError, ValueError):
            return
        if not isinstance(saved, dict):
            return
        # Settings of version 1.0, replaced by choices of three
        if "secret_mode" not in saved and isinstance(saved.get("secret"), bool):
            saved["secret_mode"] = "always" if saved["secret"] else "off"
        if "timer_mode" not in saved and isinstance(saved.get("reset_timer_per_project"), bool):
            saved["timer_mode"] = "session" if saved["reset_timer_per_project"] else "fl"
        for key, default in DEFAULTS.items():
            value = saved.get(key)
            if type(value) is type(default) and value in CHOICES.get(key, (value,)):
                self.values[key] = value
        low, high = IDLE_MINUTES_RANGE
        self.values["idle_minutes"] = min(max(self.values["idle_minutes"], low), high)

    def update(self, **changes):
        """Changes some settings and saves them all."""
        for key, value in changes.items():
            if key not in DEFAULTS or type(value) is not type(DEFAULTS[key]):
                raise ValueError(f"{key}={value!r}")
        self.values.update(changes)
        self.save()

    def reset(self):
        self.values = dict(DEFAULTS)
        self.save()

    def save(self):
        """Writes the settings. When the disk refuses, they still apply until the app quits, and the problem is logged."""
        temporary = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            # Written beside it then swapped, so a crash never leaves half a file. In ASCII, so any text gets
            # written, even half an emoji pasted from a file name.
            with open(temporary, "w", encoding="utf-8") as file:
                json.dump(self.values, file, indent=2)
            for attempt in range(5):
                try:
                    os.replace(temporary, self.path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05)  # an antivirus or the search indexer reading the file for a moment
        except OSError as error:
            log.warning("Couldn't save the settings: %s", error)
            return
        self.first_run = False
