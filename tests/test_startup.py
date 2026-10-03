"""Starting with Windows, tried on a registry key of its own: Windows' real startup list isn't touched."""
import winreg

import pytest

from flbp import APP_NAME, startup

TEST_ROOT = r"Software\FL Studio Better Presence tests"
EXE = '"C:\\Apps\\FL-Studio-Better-Presence.exe" --background'


def delete_tree(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            names = []
            while True:
                try:
                    names.append(winreg.EnumKey(key, len(names)))
                except OSError:
                    break
        for name in names:
            delete_tree(path + "\\" + name)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except FileNotFoundError:
        pass


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setattr(startup, "RUN_KEY", TEST_ROOT + r"\Run")
    monkeypatch.setattr(startup, "APPROVED_KEY", TEST_ROOT + r"\StartupApproved\Run")
    monkeypatch.setattr(startup, "available", lambda: True)
    monkeypatch.setattr(startup, "command", lambda: EXE)
    delete_tree(TEST_ROOT)
    yield
    delete_tree(TEST_ROOT)


def turn_off_in_windows_settings():
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, startup.APPROVED_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_BINARY, b"\x03" + b"\0" * 11)


def test_turned_on_and_off(registry):
    assert not startup.is_enabled()
    startup.set_enabled(True)
    assert startup.is_enabled()
    assert startup._read(startup.RUN_KEY, APP_NAME) == EXE
    startup.set_enabled(False)
    assert not startup.is_enabled()
    assert startup._read(startup.RUN_KEY, APP_NAME) is None


def test_turned_off_in_windows_settings(registry):
    startup.set_enabled(True)
    turn_off_in_windows_settings()
    assert not startup.is_enabled()
    # Turning it on in the app wins
    startup.set_enabled(True)
    assert startup.is_enabled()


def test_follows_the_exe_when_moved(registry, monkeypatch):
    startup.set_enabled(True)
    moved = '"D:\\Music tools\\FL-Studio-Better-Presence.exe" --background'
    monkeypatch.setattr(startup, "command", lambda: moved)
    startup.refresh()
    assert startup._read(startup.RUN_KEY, APP_NAME) == moved


def test_refresh_keeps_the_users_choice(registry):
    startup.refresh()
    assert not startup.is_enabled()  # never turned on: stays off
    startup.set_enabled(True)
    turn_off_in_windows_settings()
    startup.refresh()
    assert not startup.is_enabled()  # turned off in Windows' Settings: stays off


def test_only_for_the_exe():
    # The tests run from the sources, with FLBP_NO_STARTUP set
    assert not startup.available()
    startup.set_enabled(True)  # does nothing
    assert startup.command().endswith('" --background')
