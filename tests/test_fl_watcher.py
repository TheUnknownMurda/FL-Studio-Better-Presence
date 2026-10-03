import os

import pytest

from flbp.fl_watcher import Panel, classify, parse_title


def test_title_with_project():
    assert parse_title("my song - FL Studio 2025") == ("my song", False, "2025")


def test_title_with_unsaved_changes():
    assert parse_title("*my song - FL Studio 2025") == ("my song", True, "2025")


def test_title_of_older_versions():
    assert parse_title("song.flp - FL Studio 21.2") == ("song", False, "21.2")
    assert parse_title("song.flp* - FL Studio 20") == ("song", True, "20")


def test_title_without_project():
    assert parse_title("FL Studio 2025") == ("", False, "2025")
    assert parse_title("FL Studio") == ("", False, "")


def test_title_with_dashes_and_fl_studio_in_the_name():
    assert parse_title("Lo-fi - beat 2 - FL Studio 2025") == ("Lo-fi - beat 2", False, "2025")
    assert parse_title("FL Studio 20 remix - FL Studio 2025") == ("FL Studio 20 remix", False, "2025")


def test_title_with_emoji():
    assert parse_title("📄 [Drums 🥁] {808} - FL Studio 2025") == ("📄 [Drums 🥁] {808}", False, "2025")


def test_other_titles():
    assert parse_title("") == ("", False, "")
    assert parse_title("Untitled - Notepad") == ("", False, "")


def test_panels_as_fl_studio_2025_titles_them():
    # FL draws "Piano roll - 808 Kick" and "Playlist - Arrangement", but titles their windows without the name
    assert classify("TEventEditForm", "Piano roll -") == Panel("piano_roll", "")
    assert classify("TEventEditForm", "Playlist -") == Panel("playlist", "")
    # and puts symbols of its icon font in the title of plugin windows
    assert classify("TPluginForm", "808 Kick (Insert 1)") == Panel("plugin", "808 Kick (Insert 1)")


def test_panels():
    assert classify("TEventEditForm", "Piano roll - Lead Synth") == Panel("piano_roll", "Lead Synth")
    assert classify("TEventEditForm", "Playlist - Arrangement") == Panel("playlist", "Arrangement")
    assert classify("TStepSeqForm", "Channel rack") == Panel("channel_rack", "")
    assert classify("TFXForm", "Mixer - Insert 3") == Panel("mixer", "Insert 3")
    assert classify("TPluginForm", "808 Kick (Insert 1)") == Panel("plugin", "808 Kick (Insert 1)")
    assert classify("TSampleListForm", "Browser") == Panel("browser", "")


def test_project_file_found_by_its_title(tmp_path):
    # FL's title bar says "Mic Check Ready", the title from Project info, for this file
    import struct
    from flbp.fl_watcher import find_project_file
    title = "Mic Check Ready".encode("utf-16-le") + b"\0\0"
    body = bytes([156]) + struct.pack("<I", 143000) + bytes([194, len(title)]) + title
    path = tmp_path / "Jay Cactus x Confz - Mic Check Ready.flp"
    path.write_bytes(b"FLhd" + struct.pack("<I", 6) + b"\0" * 6 + b"FLdt" + struct.pack("<I", len(body)) + body)
    command_line = f'"C:\\Program Files\\Image-Line\\FL Studio 2025\\FL64.exe" "{path}"'
    assert find_project_file("Mic Check Ready", command_line) == str(path)
    assert find_project_file("Jay Cactus x Confz - Mic Check Ready", command_line) == str(path)
    assert find_project_file("Another song", command_line) == ""


def test_project_file_with_half_an_emoji_in_its_name(tmp_path):
    # FL leaves the broken character out of its title bar
    import struct
    from flbp.fl_watcher import find_project_file
    body = bytes([156]) + struct.pack("<I", 175000)
    path = tmp_path / "x.flp"
    path.write_bytes(b"FLhd" + struct.pack("<I", 6) + b"\0" * 6 + b"FLdt" + struct.pack("<I", len(body)) + body)
    command_line = f'"FL64.exe" "{tmp_path}\\(Melody\ud834 ♪) {{808}}.flp"'
    renamed = tmp_path / "(Melody\ud834 ♪) {808}.flp"
    try:
        path.rename(renamed)
    except OSError:
        pytest.skip("this file system refuses half an emoji in a name")
    found = find_project_file("(Melody ♪) {808}", command_line)
    assert found and os.path.samefile(found, renamed)


def test_programs_of_fl_studios_folder():
    # How plugins FL runs apart, in ilbridge.exe, count as FL. This Python stands for FL Studio here.
    import os
    from flbp.fl_watcher import FLWatcher, process_path
    this = process_path(os.getpid())
    assert os.path.basename(this).lower() == "python.exe"
    assert process_path(0) == ""
    watcher = FLWatcher()
    assert watcher._part_of_fl(os.getpid(), os.getpid())
    parent = process_path(os.getppid())
    in_folder = parent.lower().startswith(os.path.dirname(this).lower() + os.sep)
    assert watcher._part_of_fl(os.getppid(), os.getpid()) == in_folder
    assert not watcher._part_of_fl(0, os.getpid())


def test_other_windows():
    assert classify("TEventEditForm", "Event editor - Pitch") is None
    assert classify("TFruityLoopsMainForm", "FL Studio 2025") is None
    assert classify("Button", "OK") is None


def test_export_window_title():
    from flbp.fl_watcher import export_name
    assert export_name("Rendering to export test.wav") == "export test.wav"
    assert export_name("Rendering to Mic Check Ready.mp3") == "Mic Check Ready.mp3"
    assert export_name("Rendering to ") == "the song"


def test_rendering_progress():
    # While exporting, FL's title shows the bars rendered instead of the project
    from flbp.fl_watcher import rendering_progress
    assert rendering_progress("Rendering: 23/129") == 17
    assert rendering_progress("Rendering: 129/129") == 100
    assert rendering_progress("Mic Check Ready - FL Studio 2025") is None
    assert rendering_progress("") is None
