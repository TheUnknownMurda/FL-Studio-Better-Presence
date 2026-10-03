"""Stand-ins for FL Studio and for the connection to Discord, for the tests of the engine and the interface."""
import uuid

from flbp.discord_ipc import Status
from flbp.fl_watcher import FLState, Panel

SONG = FLState(running=True, project="Summer Vibes", version="2025", panel=Panel("piano_roll"),
               foreground=True)


def song(**changes):
    return FLState(**{**SONG.__dict__, **changes})


class FakeWatcher:
    """FL Studio as a test sets it: the state to report, and whether the user used FL since the last look."""

    def __init__(self, state=None):
        self.state = state or FLState()
        self.input = False

    def poll(self):
        return self.state

    def user_input_in_fl(self, state):
        used, self.input = self.input, False
        return used


class FakeDiscord:
    """The connection to Discord as a test sets it, keeping the activity it was given."""

    def __init__(self, status=Status.CONNECTED, user="Tester"):
        self.status = status
        self.user = user
        self.error = ""
        self.pipe_prefix = rf"\\.\pipe\flbp-test-{uuid.uuid4().hex}-"  # no Discord there
        self.shown = None
        self.stopped = False

    def show(self, activity):
        self.shown = activity

    def stop(self):
        self.stopped = True
