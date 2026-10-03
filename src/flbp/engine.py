"""
The heart of the app: every second it reads FL Studio's state, builds the status and hands it to Discord.
"""
import os
import time

from . import flp, presence
from .discord_ipc import DiscordClient
from .fl_watcher import FLState, FLWatcher, Panel
from .stats import Stats

DISCORD_APP_ID = "1555738506310066286"  # the "FL Studio" application on Discord's developer portal

# Shown in the settings window while FL Studio is closed, to see what the status will look like
SAMPLE_STATE = FLState(running=True, project="Summer Vibes", version="2025",
                       panel=Panel("piano_roll"), foreground=True)
SAMPLE_PROJECT = flp.ProjectInfo(bpm=140.0, title="", genre="Hip hop", artists="You")
SAMPLE_ELAPSED = 47 * 60 + 12

TICK_INTERVAL = 1  # seconds between two ticks
CLOCK_JUMP = 30  # seconds: a tick this late or early means the computer slept or its clock changed
MAX_COUNTED_TICK = 5  # seconds: a tick never counts more in the statistics, even when the app was held up


class ProjectReader:
    """What FL saved in the open project's file, read again each time it is saved."""

    RETRY_INTERVAL = 5  # seconds, when the file couldn't be read: FL may have been writing it

    def __init__(self):
        self._key = None
        self._retry_at = 0.0
        self.info = None  # the file's flp.ProjectInfo, None without a file
        self.modified = None  # when the file was last saved, as read with the information

    def read(self, path):
        """The project file's information, or None without a file."""
        if not path:
            self._key = self.info = self.modified = None
            return None
        try:
            stat = os.stat(path)
        except OSError:
            self._key = self.info = self.modified = None
            return None
        key = (path, stat.st_mtime_ns, stat.st_size)
        if key != self._key or (self.info.bpm is None and time.monotonic() >= self._retry_at):
            self._key = key
            self.info = flp.read_project(path)
            self.modified = stat.st_mtime
            self._retry_at = time.monotonic() + self.RETRY_INTERVAL
        return self.info


def new_project(previous, current):
    """True when another project was opened. Saving a new project for the first time keeps the same one."""
    return previous.running and current.project != previous.project and bool(previous.project)


class Engine:

    def __init__(self, settings, discord=None, watcher=None, clock=time.time, stats=None):
        self.settings = settings
        self.discord = discord or DiscordClient(DISCORD_APP_ID)
        self.watcher = watcher or FLWatcher()
        self.clock = clock
        self.stats = stats or Stats()
        self.state = FLState()
        self.project = None  # what FL saved in the open project's file (flp.ProjectInfo), when it has one
        self.idle = False
        self.activity = None  # the status for Discord, also while hidden. None while FL Studio is closed.
        self.hidden = "closed"  # why Discord shows nothing: "closed" (FL Studio), "off", "away", or ""
        # Timers, moved on by the time away and the time the computer sleeps, which don't count
        self._fl_start = None  # since FL Studio was opened
        self._project_start = None  # since the open project was opened
        self._project_opened = None  # the same, never moved: to compare with when its file was saved
        self._spent_before = None  # the time FL counted on the project before it was opened this time
        self._read_info = None
        self._last_input = clock()
        self._last_tick = None
        self._reader = ProjectReader()

    @property
    def bpm(self):
        return self.project.bpm if self.project else None

    def tick(self):
        """Reads FL Studio's state and updates the status. Called every second."""
        now = self.clock()
        counted = 0.0
        if self._last_tick is not None:
            jump = now - self._last_tick - TICK_INTERVAL
            if abs(jump) > CLOCK_JUMP:
                # The computer slept, or its clock was changed: that time isn't counted as work, nor as time away
                self._move_timers(jump, now)
                self._last_input += jump
            else:
                counted = min(max(now - self._last_tick, 0.0), MAX_COUNTED_TICK)
        self._last_tick = now
        previous, state = self.state, self.watcher.poll()
        self.state = state
        if not state.running:
            self._fl_start = self._project_start = self._project_opened = self._spent_before = None
            self.idle = False
            self._last_input = now
        else:
            if self._fl_start is None:
                self._fl_start = now
            if self._project_start is None or new_project(previous, state):
                self._project_start = self._project_opened = now
                self._spent_before = self._read_info = None
            if state.export_file or self.watcher.user_input_in_fl(state):
                self._user_active(now)  # an export keeps the user busy, without touching anything
            self._check_idle(now)
            if not self.idle and previous.running:
                self.stats.add(counted, state.project, now)
        self.project = self._reader.read(state.project_file)
        self._learn_time_spent()
        self.refresh()

    def refresh(self):
        """Builds the status again, after a tick or a change of settings, and hands it to Discord."""
        self.activity = presence.build(self.state, self.project, self.settings, self.idle, self.timer_start(),
                                       self.project_time())
        if not self.state.running:
            self.hidden = "closed"
        elif not self.settings["enabled"]:
            self.hidden = "off"
        elif self.idle and self.settings["idle_action"] == "hide":
            self.hidden = "away"
        else:
            self.hidden = ""
        self.discord.show(None if self.hidden else self.activity)

    def timer_start(self):
        """When the status' timer started, as the setting wants it."""
        mode = self.settings["timer_mode"]
        if mode == "fl":
            return self._fl_start
        if mode == "project" and self._project_start is not None and self._spent_before:
            return self._project_start - self._spent_before
        return self._project_start

    def project_time(self):
        """The seconds spent on the project so far: what FL counted before, and this time."""
        if self._project_start is None:
            return None
        until = self._last_input if self.idle else self.clock()  # paused while away
        return max(0.0, until - self._project_start) + (self._spent_before or 0.0)

    def preview(self):
        """The status the settings window shows: the real one, or an example while FL Studio is closed."""
        if self.state.running:
            return self.activity
        return presence.build(SAMPLE_STATE, SAMPLE_PROJECT, self.settings,
                              timer_start=self.clock() - SAMPLE_ELAPSED, project_time=11 * 3600 + 54 * 60)

    def stop(self):
        self.stats.save()
        self.discord.stop()

    def _learn_time_spent(self):
        """
        What FL counted on the project before this time, from its file: all of it when the file was saved before
        the project was opened, nothing when the project was first saved during this time.
        """
        info = self.project
        if info is self._read_info or self._project_opened is None:
            return
        self._read_info = info
        if info is None or info.spent is None:
            return
        if self._reader.modified < self._project_opened:
            self._spent_before = info.spent
        elif self._spent_before is None:
            self._spent_before = 0.0

    def _move_timers(self, seconds, now):
        if self._fl_start is not None:
            self._fl_start = min(self._fl_start + seconds, now)
        if self._project_start is not None:
            self._project_start = min(self._project_start + seconds, now)

    def _user_active(self, now):
        if self.idle:
            # The time away doesn't count: the timer resumes where it paused
            self._move_timers(now - self._last_input, now)
            self.idle = False
        self._last_input = now

    def _check_idle(self, now):
        away = now - self._last_input >= self.settings["idle_minutes"] * 60
        should_be_idle = away and self.settings["idle_action"] != "off"
        if should_be_idle and not self.idle:
            self.idle = True
        elif self.idle and not should_be_idle:
            self._user_active(now)  # the idle option was turned off or its delay increased
