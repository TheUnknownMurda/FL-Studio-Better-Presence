"""
Watches FL Studio from the outside: which project is open, and which of FL's
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

from . import flp

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

# Window handles are pointer-sized: declared so ctypes never truncates them
user32.GetForegroundWindow.restype = wt.HWND
user32.GetParent.restype = wt.HWND
user32.GetParent.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.FindWindowExW.restype = wt.HWND
user32.FindWindowExW.argtypes = [wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
ntdll.NtQueryInformationProcess.argtypes = [wt.HANDLE, wt.ULONG, ctypes.c_void_p, wt.ULONG, ctypes.POINTER(wt.ULONG)]

MAIN_WINDOW_CLASS = "TFruityLoopsMainForm"
# The window FL shows for the whole export of a song, titled "Rendering to song.wav" (or .mp3, .ogg, .flac)
EXPORT_WINDOW_CLASS = "TWAVRenderForm"

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

# "my song.flp - FL Studio 2025", or "Title - FL Studio 2025" for a project with a title in Project info, or
# "FL Studio 2025" without a project. A * marks unsaved changes in some versions, not in FL Studio 2025.
_TITLE = re.compile(r"^(?:(?P<name>.+?)\s*[–—-]\s*)?FL Studio\s*(?P<version>[\d.]*)\s*$")
# While it renders an export, FL shows its progress there instead, in bars: "Rendering: 23/129"
_RENDERING = re.compile(r"^Rendering:\s*(?P<done>\d+)\s*/\s*(?P<total>\d+)")
# FL puts symbols of its icon font in some titles, like "808 Kick (Insert 1)" for a plugin: characters
# of Unicode's private use areas, which show as boxes anywhere else
_ICONS = re.compile("[-\U000f0000-\U0010ffff]")


def without_icons(text):
    return _ICONS.sub("", text or "")

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
    export_file: str = ""  # the file FL is exporting the song to, like "song.wav", while it does
    export_progress: int = None  # how much of it is done, in percent, once the rendering started


def parse_title(title):
    """Returns (project, unsaved, version) from the title of FL's main window."""
    match = _TITLE.match(without_icons(title).strip())
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
    title = " ".join(without_icons(title).split())
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


def _is_main_window(hwnd):
    return bool(hwnd) and bool(user32.IsWindow(hwnd)) and _class_name(hwnd) == MAIN_WINDOW_CLASS


def _window_info(hwnd):
    pid = wt.DWORD()
    thread = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return hwnd, pid.value, thread


def find_main_window(known=None):
    """
    (window, process id, thread id) of FL Studio's main window, or None when FL isn't running. The window found
    last time is given back as known, which saves going through every window of the computer.
    """
    # With several FL Studios open, the one in front wins
    foreground = user32.GetForegroundWindow()
    if _is_main_window(foreground):
        return _window_info(foreground)
    if _is_main_window(known):
        return _window_info(known)
    found = []

    @ENUM_WINDOWS_PROC
    def callback(hwnd, _):
        if _class_name(hwnd) == MAIN_WINDOW_CLASS:
            found.append(hwnd)
        return True

    user32.EnumWindows(callback, 0)
    return _window_info(found[0]) if found else None


_plugin_kinds = {}  # each plugin window's kind, "plugin" for an instrument or "effect", worked out once


def plugin_kind(hwnd):
    """
    "plugin" for an instrument's window, "effect" for an effect's: FL titles both alike, like "Serum (Insert 2)"
    and "Fruity Parametric EQ 2 (Insert 2)", but only an instrument's window holds its channel's envelopes.
    """
    if hwnd not in _plugin_kinds:
        if len(_plugin_kinds) > 200:
            _plugin_kinds.clear()  # FL makes a new window each time a plugin is opened
        found = []

        @ENUM_WINDOWS_PROC
        def look(child, _):
            if _class_name(child) == "TMEnvEditor":
                found.append(child)
                return False
            return True

        user32.EnumChildWindows(hwnd, look, 0)
        _plugin_kinds[hwnd] = "plugin" if found else "effect"
    return _plugin_kinds[hwnd]


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
                if panel.kind == "plugin":
                    panel.kind = plugin_kind(hwnd)
                return panel
            hwnd = user32.GetParent(hwnd)
    return None


def export_file(pid):
    """The name of the file FL is exporting to, like "song.wav", or "" when it isn't exporting."""
    hwnd = None
    while True:
        hwnd = user32.FindWindowExW(None, hwnd, EXPORT_WINDOW_CLASS, None)
        if not hwnd:
            return ""
        window_pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == pid and user32.IsWindowVisible(hwnd):
            return export_name(_text(hwnd))


def rendering_progress(title):
    """The progress of a rendering, in percent, from FL's title "Rendering: 23/129", or None."""
    match = _RENDERING.match(title or "")
    if not match:
        return None
    return min(100, int(match.group("done")) * 100 // max(1, int(match.group("total"))))


def export_name(title):
    """The file of an export window's title: "Rendering to song.wav" gives "song.wav"."""
    title = " ".join(without_icons(title).split())
    return re.sub(r"^Rendering to\s*", "", title) or "the song"


def process_path(pid):
    """The program a process runs, like C:\\...\\FL64.exe, or "" when it can't be told."""
    if not pid:
        return ""
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


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


_titles = {}  # the title saved in each project file looked at: {path: (modification time, title)}


def project_title(path):
    """The title typed in a project's Project info, "" when it has none, read once per version of the file."""
    try:
        modified = os.stat(path).st_mtime_ns
    except OSError:
        return ""
    if _titles.get(path, (None,))[0] != modified:
        if len(_titles) > 100:
            _titles.clear()
        _titles[path] = (modified, flp.read_project(path).title or "")
    return _titles[path][1]


def _comparable(name):
    """A name as FL's title bar shows it: without icons, nor halves of emoji, which FL leaves out."""
    name = without_icons(name).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "ignore")
    return " ".join(name.split()).lower()


def find_project_file(project, fl_command_line=""):
    """The full path of the open project, found from FL's command line or recent projects, or ""."""
    if not project:
        return ""
    wanted = _comparable(project)
    candidates = [part.strip() for part in fl_command_line.split('"') if part.strip().lower().endswith(".flp")]
    candidates += recent_projects()
    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        stem = os.path.splitext(os.path.basename(candidate))[0]
        # FL shows the title typed in Project info rather than the file's name, when the project has one
        if wanted in (_comparable(stem), _comparable(project_title(candidate))):
            return candidate
    return ""


class FLWatcher:
    """Reads FL Studio's state each time poll() is called."""

    LOOKUP_INTERVAL = 5  # seconds between two searches for the file of a project that wasn't found
    SEARCH_INTERVAL = 2  # seconds between two searches for FL Studio while it is closed

    def __init__(self):
        self._hwnd = None
        self._next_search = 0.0
        self._folder = ""  # FL Studio's installation folder
        self._folder_pid = None
        self._last_panel = None
        self._project = None
        self._title = ("", False, "")  # what FL's title says: (project, unsaved, version)
        self._project_file = ""
        self._next_lookup = 0.0
        self._last_input_tick = None

    def poll(self):
        window = None
        if self._hwnd or time.monotonic() >= self._next_search:
            window = find_main_window(self._hwnd)
        if not window:
            # Looking through every window of the computer is the costliest part, so it is done less often
            if self._hwnd or time.monotonic() >= self._next_search:
                self._next_search = time.monotonic() + self.SEARCH_INTERVAL
            self._hwnd = None
            self._last_panel = None
            self._project = None
            return FLState()
        hwnd, pid, thread = window
        self._hwnd = hwnd
        title = _text(hwnd)
        progress = rendering_progress(title)
        if progress is None:
            self._title = parse_title(title)
        # While rendering, FL's title shows the progress instead of the project, which stays the same
        project, unsaved, version = self._title
        foreground_pid = wt.DWORD()
        user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(foreground_pid))
        foreground = foreground_pid.value == pid or self._part_of_fl(foreground_pid.value, pid)

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
        exporting = export_file(pid)
        return FLState(running=True, project=project, unsaved=unsaved, version=version, panel=self._last_panel,
                       foreground=foreground, project_file=self._project_file, pid=pid, export_file=exporting,
                       export_progress=progress if exporting else None)

    def _part_of_fl(self, other_pid, fl_pid):
        """
        True for a program of FL Studio's own folder, like ilbridge.exe, where FL runs some plugins apart: working
        in them is working in FL. A web browser FL opened a link in doesn't count.
        """
        if fl_pid != self._folder_pid:
            path = process_path(fl_pid)
            self._folder = os.path.dirname(path).lower() + os.sep if path else ""
            self._folder_pid = fl_pid
        return bool(self._folder) and process_path(other_pid).lower().startswith(self._folder)

    def user_input_in_fl(self, state):
        """True when the keyboard or mouse was used since the last call while FL was the active application."""
        info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return True  # without this information the user is never considered idle
        new_input = self._last_input_tick is not None and info.dwTime != self._last_input_tick
        self._last_input_tick = info.dwTime
        return new_input and state.foreground
