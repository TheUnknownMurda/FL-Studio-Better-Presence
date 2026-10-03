"""
Reads what FL Studio saves at the start of a project (.flp): its tempo, and its title from Project info, which
FL shows in its title bar instead of the file's name. The tempo is the only project data FL shares without a
MIDI script.

A .flp is an "FLhd" header followed by an "FLdt" chunk of events. Each event starts with its id, which also
gives the size of its value: below 64 one byte, below 128 two, below 192 four, and above that a length
written in 7-bit groups followed by that many bytes.
"""
import struct
from dataclasses import dataclass

TEMPO = 156  # tempo x 1000, since FL 3.4
LEGACY_TEMPO = 66  # whole tempo, before FL 3.4
TITLE = 194  # the title typed in Project info, in UTF-16
# The project's own information comes before its first channel and pattern: no need to read further
FIRST_CHANNEL, FIRST_PATTERN = 64, 65
# Events that don't follow the size rule. FL 25.2.3 and later write event 172 near the start of every project
# with a 3-byte value: read as 4 bytes, the events after it are lost, the tempo among them.
SIZE_EXCEPTIONS = {172: 3}
MIN_BPM, MAX_BPM = 10, 522  # FL's tempo range: anything else means the file wasn't read right
# The tempo and the title are among the first events: within 200 bytes in the 170 projects tried, which weigh
# up to 7 MB
HEAD_SIZE = 65536


@dataclass
class ProjectInfo:
    bpm: float = None  # like 140.0, None when it couldn't be read
    title: str = None  # "" for a project without a title


def read_project(path):
    """The tempo and title of a saved project. Both are None when the file can't be read."""
    try:
        with open(path, "rb") as file:
            data = file.read(HEAD_SIZE)
    except OSError:
        return ProjectInfo()
    return info_from_bytes(data)


def read_bpm(path):
    """The tempo of the saved project, like 140.0, or None when the file can't be read."""
    return read_project(path).bpm


def bpm_from_bytes(data):
    return info_from_bytes(data).bpm


def info_from_bytes(data):
    info = _scan(data, SIZE_EXCEPTIONS)
    if info.bpm is None:
        # In case a later FL Studio writes event 172 with 4 bytes again
        plain = _scan(data, {})
        if plain.bpm is not None:
            return plain
    return info


def _scan(data, sizes):
    info = ProjectInfo()
    tempo = legacy = None
    try:
        if data[0:4] != b"FLhd":
            return info
        position = 8 + struct.unpack_from("<I", data, 4)[0]
        if data[position:position + 4] != b"FLdt":
            return info
        position += 8
        while position < len(data) and (tempo is None or info.title is None):
            event = data[position]
            position += 1
            if event in (FIRST_CHANNEL, FIRST_PATTERN):
                break
            if event < 64:
                size = 1
            elif event < 128:
                size = 2
                if event == LEGACY_TEMPO:
                    legacy = float(struct.unpack_from("<H", data, position)[0])
            elif event < 192:
                size = sizes.get(event, 4)
                if event == TEMPO:
                    tempo = struct.unpack_from("<I", data, position)[0] / 1000
            else:
                size = 0
                shift = 0
                while True:
                    byte = data[position]
                    position += 1
                    size |= (byte & 0x7F) << shift
                    shift += 7
                    if not byte & 0x80:
                        break
                if event == TITLE:
                    info.title = data[position:position + size].decode("utf-16-le", "ignore").rstrip("\0").strip()
            position += size
    except (IndexError, struct.error):
        pass  # a file cut short: what was read before still counts
    bpm = tempo if tempo is not None else legacy
    info.bpm = bpm if bpm is not None and MIN_BPM <= bpm <= MAX_BPM else None
    return info


def format_bpm(bpm):
    """140.0 -> "140", 87.5 -> "87.5"."""
    return f"{bpm:.3f}".rstrip("0").rstrip(".")
