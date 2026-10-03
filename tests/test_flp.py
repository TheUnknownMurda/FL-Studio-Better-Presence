import pathlib
import struct

import pytest

from flbp import fl_watcher, flp

FL_DEMOS = pathlib.Path(r"C:\Program Files\Image-Line\FL Studio 2025")


def project(*events, header_length=6):
    """A small .flp: the header, then the events."""
    body = b"".join(events)
    header = struct.pack("<hHH", 0, 4, 96).ljust(header_length, b"\0")
    return b"FLhd" + struct.pack("<I", header_length) + header + b"FLdt" + struct.pack("<I", len(body)) + body


def byte(event, value):
    return bytes([event, value])


def word(event, value):
    return bytes([event]) + struct.pack("<H", value)


def dword(event, value):
    return bytes([event]) + struct.pack("<I", value)


def text(event, value):
    data = value.encode("utf-16-le") + b"\0\0" if event != 199 else value.encode("ascii") + b"\0"
    assert len(data) < 128
    return bytes([event, len(data)]) + data


def start(version="24.2.99.4844"):
    """The events every project starts with: version, build, licensed..."""
    return [text(199, version), dword(159, 4844), dword(169, 7), byte(28, 1), byte(37, 1),
            text(200, "[@9;]3>6uyy@AA=;:")]


def test_tempo():
    assert flp.bpm_from_bytes(project(*start(), dword(156, 140000), word(67, 10))) == 140.0


def test_tempo_with_decimals():
    assert flp.bpm_from_bytes(project(*start(), dword(156, 87500))) == 87.5


def test_fl_25_2_3_and_later():
    # FL 25.2.3 added an event with a 3-byte value before the tempo
    events = [text(199, "25.2.5.5319"), dword(159, 5319), dword(169, 7), byte(28, 1),
              b"\xac\x01\x01\x00", text(192, "FL Studio 25.2.5.5319"), byte(37, 1), dword(156, 175000)]
    assert flp.bpm_from_bytes(project(*events)) == 175.0


def test_title_from_project_info():
    info = flp.info_from_bytes(project(*start(), dword(156, 143000), text(194, "Mic Check Ready")))
    assert info.bpm == 143.0
    assert info.title == "Mic Check Ready"
    assert flp.info_from_bytes(project(*start(), dword(156, 143000), text(194, ""))).title == ""


def test_reading_stops_at_the_first_channel():
    # The project's own information comes first: what follows the first channel isn't read
    info = flp.info_from_bytes(project(*start(), word(64, 0), dword(156, 143000), text(194, "Late")))
    assert info.bpm is None and info.title is None


def test_tempo_before_fl_3_4():
    assert flp.bpm_from_bytes(project(text(199, "3.0"), word(66, 120))) == 120.0


def test_long_text_event():
    # From 128 bytes on, the length takes several 7-bit groups: 44 + (1 << 7) = 172
    name = bytes([201, 0x80 | 44, 1]) + b"z" * 172
    assert flp.bpm_from_bytes(project(*start(), name, dword(156, 128000))) == 128.0


def test_unreadable_files():
    assert flp.bpm_from_bytes(b"") is None
    assert flp.bpm_from_bytes(b"RIFF" + b"\0" * 40) is None
    assert flp.bpm_from_bytes(project(*start(), dword(156, 140000))[:60]) is None  # cut before the tempo
    assert flp.bpm_from_bytes(project(*start())) is None  # no tempo


def test_impossible_tempo():
    assert flp.bpm_from_bytes(project(*start(), dword(156, 900000))) is None


def test_read_bpm(tmp_path):
    path = tmp_path / "song.flp"
    path.write_bytes(project(*start(), dword(156, 95000)))
    assert flp.read_bpm(path) == 95.0
    assert flp.read_bpm(tmp_path / "missing.flp") is None


def test_format_bpm():
    assert flp.format_bpm(140.0) == "140"
    assert flp.format_bpm(87.5) == "87.5"
    assert flp.format_bpm(123.456) == "123.456"


@pytest.mark.skipif(not FL_DEMOS.exists(), reason="FL Studio 2025 isn't installed")
def test_fl_demo_projects():
    paths = sorted(FL_DEMOS.rglob("*.flp"))
    assert paths
    infos = {path.name: flp.read_project(path) for path in paths}
    assert not [name for name, info in infos.items() if info.bpm is None]
    # The demos have a title in Project info, which FL shows instead of the file's name
    assert infos["Jay Cactus x Confz - Mic Check Ready.flp"].title == "Mic Check Ready"
    assert not [name for name, info in infos.items() if info.title is None]


def test_recent_projects():
    """The projects in FL's recent list, saved by the installed FL, when there are some."""
    paths = [pathlib.Path(path) for path in fl_watcher.recent_projects() if pathlib.Path(path).is_file()]
    unreadable = [path.name for path in paths if flp.read_bpm(path) is None]
    assert not unreadable
