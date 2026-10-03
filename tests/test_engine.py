import os
import struct

import pytest

from fakes import SONG, FakeDiscord, FakeWatcher, song
from flbp.engine import Engine
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
    assert run.engine.preview()["details"] == "Composing · Summer Vibes*"


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
    run.settings["reset_timer_per_project"] = False
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
