"""
The heart of the app: every second it reads FL Studio's state, builds the status and hands it to Discord.
"""
import os
import time

from . import flp, presence
from .discord_ipc import DiscordClient
from .fl_watcher import FLState, FLWatcher, Panel

DISCORD_APP_ID = "1555738506310066286"  # the "FL Studio" application on Discord's developer portal

# Shown in the settings window while FL Studio is closed, to see what the status will look like
SAMPLE_STATE = FLState(running=True, project="Summer Vibes", unsaved=True, version="2025",
                       panel=Panel("piano_roll", "Lead synth"), foreground=True)
SAMPLE_BPM = 140.0
SAMPLE_ELAPSED = 47 * 60 + 12


class BpmReader:
    """The tempo of the open project, read again from its .flp each time it is saved."""

    RETRY_INTERVAL = 5  # seconds, when the file couldn't be read: FL may have been writing it

    def __init__(self):
        self._key = None
        self._bpm = None
        self._retry_at = 0.0

    def read(self, path):
        if not path:
            return None
        try:
            info = os.stat(path)
        except OSError:
            return None
        key = (path, info.st_mtime_ns, info.st_size)
        if key != self._key or (self._bpm is None and time.monotonic() >= self._retry_at):
            self._key = key
            self._bpm = flp.read_bpm(path)
            self._retry_at = time.monotonic() + self.RETRY_INTERVAL
        return self._bpm


def new_project(previous, current):
    """True when another project was opened. Saving a new project for the first time keeps the same one."""
    return previous.running and current.project != previous.project and bool(previous.project)


class Engine:

    def __init__(self, settings, discord=None, watcher=None, clock=time.time):
        self.settings = settings
        self.discord = discord or DiscordClient(DISCORD_APP_ID)
        self.watcher = watcher or FLWatcher()
        self.clock = clock
        self.state = FLState()
        self.bpm = None
        self.idle = False
        self.activity = None  # the status for Discord, also while hidden. None while FL Studio is closed.
        self.hidden = "closed"  # why Discord shows nothing: "closed" (FL Studio), "off", "away", or ""
        self._timer_start = None
        self._last_input = clock()
        self._bpm_reader = BpmReader()

    def tick(self):
        """Reads FL Studio's state and updates the status. Called every second."""
        now = self.clock()
        previous, state = self.state, self.watcher.poll()
        self.state = state
        if not state.running:
            self._timer_start = None
            self.idle = False
            self._last_input = now
        else:
            if self._timer_start is None or (self.settings["reset_timer_per_project"] and new_project(previous, state)):
                self._timer_start = now
            if self.watcher.user_input_in_fl(state):
                self._user_active(now)
            self._check_idle(now)
        self.bpm = self._bpm_reader.read(state.project_file)
        self.refresh()

    def refresh(self):
        """Builds the status again, after a tick or a change of settings, and hands it to Discord."""
        self.activity = presence.build(self.state, self.bpm, self.settings, self.idle, self._timer_start)
        if not self.state.running:
            self.hidden = "closed"
        elif not self.settings["enabled"]:
            self.hidden = "off"
        elif self.idle and self.settings["idle_action"] == "hide":
            self.hidden = "away"
        else:
            self.hidden = ""
        self.discord.show(None if self.hidden else self.activity)

    def preview(self):
        """The status the settings window shows: the real one, or an example while FL Studio is closed."""
        if self.state.running:
            return self.activity
        return presence.build(SAMPLE_STATE, SAMPLE_BPM, self.settings, timer_start=self.clock() - SAMPLE_ELAPSED)

    def stop(self):
        self.discord.stop()

    def _user_active(self, now):
        if self.idle:
            # The time away doesn't count: the timer resumes where it paused
            self._timer_start = min(self._timer_start + (now - self._last_input), now)
            self.idle = False
        self._last_input = now

    def _check_idle(self, now):
        away = now - self._last_input >= self.settings["idle_minutes"] * 60
        should_be_idle = away and self.settings["idle_action"] != "off"
        if should_be_idle and not self.idle:
            self.idle = True
        elif self.idle and not should_be_idle:
            self._user_active(now)  # the idle option was turned off or its delay increased
