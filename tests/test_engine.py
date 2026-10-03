import os
import struct

import pytest

from fakes import SONG, FakeDiscord, FakeWatcher, song
from flbp.engine import Engine
from flbp.fl_watcher import FLState
from flbp.settings import DEFAULTS


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture
def run():
    """An engine with a fake FL Studio, Discord and clock, and a function to let time pass."""
    watcher, discord, clock = FakeWatcher(), FakeDiscord(), Clock()
    settings = dict(DEFAULTS)
    engine = Engine(settings, discord, watcher, clock)

    def tick(seconds=1, state=None, used=False):
        if state is not None:
            watcher.state = state
        for _ in range(int(seconds)):
            clock.now += 1
            watcher.input = used
            engine.tick()
        return discord.shown

    tick.engine, tick.settings, tick.clock, tick.discord = engine, settings, clock, discord
    return tick


def test_nothing_shown_while_fl_studio_is_closed(run):
    assert run() is None
    assert run.engine.hidden == "closed"
    # The settings window shows an example meanwhile
    assert run.engine.preview()["details"] == "Composing · Summer Vibes"


def test_status_when_fl_studio_opens(run):
    shown = run(state=SONG)
    assert shown["details"] == "Composing · Summer Vibes"
    assert shown["timestamps"]["start"] == run.clock.now
    assert run.engine.preview() == shown


def test_timer_restarts_for_each_project(run):
    start = run(state=SONG)["timestamps"]["start"]
    assert run(60)["timestamps"]["start"] == start
    assert run(state=song(project="Other song"))["timestamps"]["start"] == run.clock.now


def test_timer_kept_when_saving_a_new_project(run):
    start = run(state=song(project=""))["timestamps"]["start"]
    assert run(60, state=song(project="First save"))["timestamps"]["start"] == start


def test_timer_counts_from_fl_studio_opening(run):
    run.settings["timer_mode"] = "fl"
    start = run(state=SONG)["timestamps"]["start"]
    assert run(state=song(project="Other song"))["timestamps"]["start"] == start


def test_idle_and_back(run):
    start = run(state=SONG, used=True)["timestamps"]["start"]
    shown = run(10 * 60)
    assert run.engine.idle
    assert shown["details"] == "Idle · Summer Vibes"
    assert "timestamps" not in shown
    run(20 * 60)
    shown = run(used=True)
    assert not run.engine.idle
    # The 30 minutes away don't count
    assert shown["timestamps"]["start"] == start + 30 * 60 + 1


def test_computer_asleep_isnt_counted(run):
    start = run(state=SONG, used=True)["timestamps"]["start"]
    run(60, used=True)
    run.clock.now += 8 * 3600  # the lid closed for the night, then a key pressed to wake the computer up
    shown = run(used=True)
    assert shown["timestamps"]["start"] == start + 8 * 3600
    assert not run.engine.idle


def test_computer_asleep_while_idle(run):
    start = run(state=SONG, used=True)["timestamps"]["start"]
    run(10 * 60)  # idle: the timer pauses
    assert run.engine.idle
    run.clock.now += 8 * 3600
    shown = run(used=True)
    # Neither the night nor the 10 minutes before it count
    assert shown["timestamps"]["start"] == start + 8 * 3600 + 10 * 60 + 1


def test_clock_set_back(run):
    start = run(state=SONG, used=True)["timestamps"]["start"]
    run(60, used=True)
    run.clock.now -= 3600
    shown = run(used=True)
    assert shown["timestamps"]["start"] == start - 3600  # still 61 seconds of work
    assert not run.engine.idle


def test_hidden_while_away(run):
    run.settings["idle_action"] = "hide"
    run(state=SONG, used=True)
    assert run(10 * 60) is None
    assert run.engine.hidden == "away"
    assert run(used=True) is not None


def test_never_idle(run):
    run.settings["idle_action"] = "off"
    run(state=SONG, used=True)
    assert run(60 * 60)["details"] == "Composing · Summer Vibes"


def test_status_turned_off(run):
    run.settings["enabled"] = False
    assert run(state=SONG) is None
    assert run.engine.hidden == "off"
    assert run.engine.preview()["details"] == "Composing · Summer Vibes"
    run.settings["enabled"] = True
    run.engine.refresh()
    assert run.discord.shown["details"] == "Composing · Summer Vibes"


def test_tempo_read_again_after_saving(run, tmp_path):
    path = tmp_path / "Summer Vibes.flp"

    def save(bpm, mtime):
        body = bytes([156]) + struct.pack("<I", int(bpm * 1000))
        path.write_bytes(b"FLhd" + struct.pack("<I", 6) + b"\0" * 6 + b"FLdt" + struct.pack("<I", len(body)) + body)
        os.utime(path, (mtime, mtime))

    save(140, 1000)
    assert run(state=song(project_file=str(path)))["state"] == "140 BPM"
    save(150, 2000)
    assert run()["state"] == "150 BPM"


def test_stop(run):
    run.engine.stop()
    assert run.discord.stopped


def write_project(path, bpm=140, spent=None, mtime=None):
    """A small .flp with its tempo, and the time FL counted on it when given."""
    body = bytes([156]) + struct.pack("<I", int(bpm * 1000))
    if spent is not None:
        body += bytes([237, 16]) + struct.pack("<dd", 46000.0, spent / 86400)
    path.write_bytes(b"FLhd" + struct.pack("<I", 6) + b"\0" * 6 + b"FLdt" + struct.pack("<I", len(body)) + body)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def test_whole_project_timer(run, tmp_path):
    path = tmp_path / "Summer Vibes.flp"
    write_project(path, spent=5 * 3600, mtime=run.clock.now - 3600)  # 5 hours counted by FL before today
    run.settings["timer_mode"] = "project"
    opened = run.clock.now + 1
    shown = run(state=song(project_file=str(path)))
    assert shown["timestamps"]["start"] == opened - 5 * 3600
    run(60, used=True)
    # Saved now: FL's count holds this session too, which mustn't count twice
    write_project(path, spent=5 * 3600 + 61, mtime=run.clock.now)
    assert run()["timestamps"]["start"] == opened - 5 * 3600


def test_whole_project_timer_of_a_new_project(run, tmp_path):
    run.settings["timer_mode"] = "project"
    start = run(state=song(project=""))["timestamps"]["start"]
    path = tmp_path / "First save.flp"
    write_project(path, spent=120, mtime=run.clock.now + 30)  # saved during this session, for the first time
    assert run(30, state=song(project="First save", project_file=str(path)))["timestamps"]["start"] == start


def test_time_placeholder(run, tmp_path):
    path = tmp_path / "Summer Vibes.flp"
    write_project(path, spent=11 * 3600 + 50 * 60, mtime=run.clock.now - 3600)
    run.settings["custom_state"] = "{time} on it"
    run(state=song(project_file=str(path)))
    assert run(4 * 60, used=True)["state"] == "11 h 54 on it"


def test_export_keeps_you_busy(run):
    run(state=song(export_file="Summer Vibes.wav"), used=True)
    shown = run(15 * 60)  # nobody touches anything during a long export
    assert not run.engine.idle
    assert shown["details"] == "Exporting · Summer Vibes"


def test_time_in_fl_studio_counted(run):
    run(state=SONG, used=True)
    run(30, used=True)
    assert run.engine.stats.today(run.clock.now) == 30
    run(10 * 60)  # away: idle after 10 minutes, which no longer count
    counted = run.engine.stats.today(run.clock.now)
    assert counted == 30 + 10 * 60 - 1
    run(60)
    assert run.engine.stats.today(run.clock.now) == counted
    run(60, state=FLState())  # FL Studio closed
    assert run.engine.stats.today(run.clock.now) == counted
    assert run.engine.stats.top_project(run.clock.now) == ("Summer Vibes", counted)
