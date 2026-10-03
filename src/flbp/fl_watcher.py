"""
Watches FL Studio from the outside: which project is open, whether it has unsaved changes, and which of FL's
windows the user is working in. FL's panels (Piano roll, Playlist, Mixer...) are real Windows windows with
their own class, so nothing needs to be installed in FL, and no MIDI device is needed.
"""
import ctypes
import ctypes.wintypes as wt
import os
import re
import time
import winreg
from dataclasses import dataclass

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

# Window handles are pointer-sized: declared so ctypes never truncates them
user32.GetForegroundWindow.restype = wt.HWND
user32.GetParent.restype = wt.HWND
user32.GetParent.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
ntdll.NtQueryInformationProcess.argtypes = [wt.HANDLE, wt.ULONG, ctypes.c_void_p, wt.ULONG, ctypes.POINTER(wt.ULONG)]

MAIN_WINDOW_CLASS = "TFruityLoopsMainForm"

# FL's panels, by the class of their window
PANEL_CLASSES = {
    "TStepSeqForm": "channel_rack",
    "TFXForm": "mixer",
    "TPluginForm": "plugin",
    "TSampleListForm": "browser",
}
# The Playlist and the Piano roll share a class, and are told apart by their title
EVENT_EDITOR_CLASS = "TEventEditForm"
EVENT_EDITORS = {"Piano roll": "piano_roll", "Playlist": "playlist"}

# "my song - FL Studio 2025", "*my song - FL Studio 2025" with unsaved changes, "song.flp - FL Studio 21.2",
# or "FL Studio 2025" without a project
_TITLE = re.compile(r"^(?:(?P<name>.+?)\s*[–—-]\s*)?FL Studio\s*(?P<version>[\d.]*)\s*$")

ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hwndActive", wt.HWND), ("hwndFocus", wt.HWND),
                ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND), ("hwndMoveSize", wt.HWND),
                ("hwndCaret", wt.HWND), ("rcCaret", wt.RECT)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]


@dataclass
class Panel:
    """One of FL's windows: its kind, like "piano_roll", and the text of its title after the window's name."""
    kind: str
    detail: str = ""


@dataclass
class FLState:
    running: bool = False
    project: str = ""  # empty for a new project that was never saved
    unsaved: bool = False
    version: str = ""  # "2025", "21.2"...
    panel: Panel = None  # the window the user works in, or None when it can't be told
    foreground: bool = False  # FL is the application the user is using
    project_file: str = ""
    pid: int = 0


def parse_title(title):
    """Returns (project, unsaved, version) from the title of FL's main window."""
    match = _TITLE.match((title or "").strip())
    if not match:
        return "", False, ""
    version = match.group("version").rstrip(".")
    name = (match.group("name") or "").strip()
    unsaved = name.startswith("*") or name.endswith("*")
    name = name.strip("*").strip()
    if name.lower().endswith(".flp"):
        name = name[:-4]
    return name, unsaved, version


def classify(window_class, title):
    """The Panel for one of FL's windows, or None when it isn't one of the panels the app knows."""
    title = title or ""
    detail = title.split(" - ", 1)[1].strip() if " - " in title else ""
    if window_class == EVENT_EDITOR_CLASS:
        for name, kind in EVENT_EDITORS.items():
            if title.startswith(name):
                return Panel(kind, detail)
        return None
    kind = PANEL_CLASSES.get(window_class)
    if kind == "plugin":
        return Panel(kind, title.strip())  # "Serum (Insert 2)": the plugin's window says it all
    if kind:
        return Panel(kind, detail)
    return None


def _text(hwnd):
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, 512)
    return buffer.value


def _class_name(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def find_main_window():
    """(window, process id, thread id) of FL Studio's main window, or None when FL isn't running."""
    found = []

    @ENUM_WINDOWS_PROC
    def callback(hwnd, _):
        if _class_name(hwnd) == MAIN_WINDOW_CLASS:
            pid = wt.DWORD()
            thread = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.append((hwnd, pid.value, thread))
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return None
    # With several FL windows open, the one in front wins
    foreground = user32.GetForegroundWindow()
    for window in found:
        if window[0] == foreground:
            return window
    return found[0]


def focused_panel(thread):
    """The panel holding the keyboard focus in FL's interface thread, or None."""
    info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    if not user32.GetGUIThreadInfo(thread, ctypes.byref(info)):
        return None
    for start in (info.hwndFocus, info.hwndActive):
        hwnd = start
        for _ in range(16):
            if not hwnd:
                break
            panel = classify(_class_name(hwnd), _text(hwnd))
            if panel:
                return panel
            hwnd = user32.GetParent(hwnd)
    return None


def command_line(pid):
    """The command line FL was started with, which names the .flp when FL was opened from one."""
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buffer = ctypes.create_string_buffer(65536)
        returned = wt.ULONG()
        # ProcessCommandLineInformation (60), Windows 8.1 and later: a UNICODE_STRING followed by its text
        if ntdll.NtQueryInformationProcess(handle, 60, buffer, len(buffer), ctypes.byref(returned)) != 0:
            return ""
        length = int.from_bytes(buffer.raw[0:2], "little")
        offset = 16 if ctypes.sizeof(ctypes.c_void_p) == 8 else 8
        return buffer.raw[offset:offset + length].decode("utf-16-le", errors="ignore")
    finally:
        kernel32.CloseHandle(handle)


def recent_projects():
    """FL's own list of recent projects, most recent first, for every installed version of FL."""
    paths = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Image-Line") as image_line:
            index = 0
            while True:
                try:
                    product = winreg.EnumKey(image_line, index)
                except OSError:
                    break
                index += 1
                try:
                    with winreg.OpenKey(image_line, product + r"\MRU") as mru:
                        values = []
                        value_index = 0
                        while True:
                            try:
                                name, value, _ = winreg.EnumValue(mru, value_index)
                            except OSError:
                                break
                            value_index += 1
                            if isinstance(value, str) and name.isdigit():
                                values.append((int(name), value))
                        paths.extend(value for _, value in sorted(values))
                except OSError:
                    continue
    except OSError:
        pass
    return paths


def find_project_file(project, fl_command_line=""):
    """The full path of the open project, found from FL's command line or recent projects, or ""."""
    if not project:
        return ""
    candidates = [part.strip() for part in fl_command_line.split('"') if part.strip().lower().endswith(".flp")]
    candidates += recent_projects()
    for candidate in candidates:
        stem = os.path.splitext(os.path.basename(candidate))[0]
        if stem.lower() == project.lower() and os.path.isfile(candidate):
            return candidate
    return ""


class FLWatcher:
    """Reads FL Studio's state each time poll() is called."""

    LOOKUP_INTERVAL = 5  # seconds between two searches for the file of a project that wasn't found

    def __init__(self):
        self._last_panel = None
        self._project = None
        self._project_file = ""
        self._next_lookup = 0.0
        self._last_input_tick = None

    def poll(self):
        window = find_main_window()
        if not window:
            self._last_panel = None
            self._project = None
            return FLState()
        hwnd, pid, thread = window
        project, unsaved, version = parse_title(_text(hwnd))
        foreground_pid = wt.DWORD()
        user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(foreground_pid))
        foreground = foreground_pid.value == pid

        # While another application is in front, FL has no focused window: the last one found is kept,
        # so checking Discord doesn't change the status
        if foreground:
            panel = focused_panel(thread)
            if panel:
                self._last_panel = panel
        # Searched again for a while when not found: FL may add a project saved for the first time to its
        # recent projects a moment after its title changed
        lookup_due = project and not self._project_file and time.monotonic() >= self._next_lookup
        if project != self._project or lookup_due:
            self._project = project
            self._project_file = find_project_file(project, command_line(pid))
            self._next_lookup = time.monotonic() + self.LOOKUP_INTERVAL
        return FLState(running=True, project=project, unsaved=unsaved, version=version, panel=self._last_panel,
                       foreground=foreground, project_file=self._project_file, pid=pid)

    def user_input_in_fl(self, state):
        """True when the keyboard or mouse was used since the last call while FL was the active application."""
        info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return True  # without this information the user is never considered idle
        new_input = self._last_input_tick is not None and info.dwTime != self._last_input_tick
        self._last_input_tick = info.dwTime
        return new_input and state.foreground
