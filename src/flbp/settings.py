"""
The user's settings, saved as JSON in %APPDATA%\\FL Studio Better Presence.
"""
import json
import os

from . import APP_NAME

DEFAULTS = {
    "enabled": True,  # show my status
    "secret": False,  # hide the project's name, for client work
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
    "idle_minutes": 10,
    "idle_action": "show",
    "custom_text_while_idle": False,
    "reset_timer_per_project": True,
}
CHOICES = {
    "small_icon": ("task", "custom", "none"),
    "idle_action": ("show", "hide", "off"),  # show "Idle", hide the status, or do nothing
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
            with open(self.path, encoding="utf-8") as file:
                saved = json.load(file)
        except (OSError, ValueError):
            return
        if not isinstance(saved, dict):
            return
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
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        # Written beside it then swapped, so a crash never leaves half a file
        temporary = self.path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(self.values, file, indent=2, ensure_ascii=False)
        os.replace(temporary, self.path)
        self.first_run = False
