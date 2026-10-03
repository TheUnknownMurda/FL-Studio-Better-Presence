"""
Starts the app with Windows, from the current user's Run key: no administrator rights needed.
"""
import os
import sys
import winreg

from . import APP_NAME

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# Where Windows' Settings and Task Manager remember the apps the user turned off at startup
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"


def available():
    """Only the app as an .exe can be started with Windows, not the Python sources. Tests turn it off."""
    return getattr(sys, "frozen", False) and not os.environ.get("FLBP_NO_STARTUP")


def command():
    """What Windows runs at sign-in: the app, straight to the notification area."""
    return f'"{sys.executable}" --background'


def _read(key_path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def is_enabled():
    if not _read(RUN_KEY, APP_NAME):
        return False
    approved = _read(APPROVED_KEY, APP_NAME)
    # The first byte is 2 or 6 while allowed, 3 or 7 once turned off in Windows' Settings
    return not (isinstance(approved, bytes) and approved and approved[0] & 1)


def set_enabled(enabled):
    if not available():
        return
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    # Turning it on here overrides turning it off in Windows' Settings
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass


def refresh():
    """Points the Run key to this .exe again, in case the user moved it."""
    if available() and _read(RUN_KEY, APP_NAME) not in (None, command()):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command())
