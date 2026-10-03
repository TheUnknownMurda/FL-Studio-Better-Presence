"""
Reads the tempo saved in an FL Studio project (.flp), the only project data FL shares without a MIDI script.

A .flp is an "FLhd" header followed by an "FLdt" chunk of events. Each event starts with its id, which also
gives the size of its value: below 64 one byte, below 128 two, below 192 four, and above that a length
written in 7-bit groups followed by that many bytes.
"""
import struct

TEMPO = 156  # tempo x 1000, since FL 3.4
LEGACY_TEMPO = 66  # whole tempo, before FL 3.4
# Events that don't follow the size rule. FL 25.2.3 and later write event 172 near the start of every project
# with a 3-byte value: read as 4 bytes, the events after it are lost, the tempo among them.
SIZE_EXCEPTIONS = {172: 3}
MIN_BPM, MAX_BPM = 10, 522  # FL's tempo range: anything else means the file wasn't read right
# The tempo is among the first events: within 200 bytes in the 170 projects tried, which weigh up to 7 MB
HEAD_SIZE = 65536


def read_bpm(path):
    """The tempo of the saved project, like 140.0, or None when the file can't be read."""
    try:
        with open(path, "rb") as file:
            data = file.read(HEAD_SIZE)
    except OSError:
        return None
    return bpm_from_bytes(data)


def bpm_from_bytes(data):
    try:
        if data[0:4] != b"FLhd":
            return None
        position = 8 + struct.unpack_from("<I", data, 4)[0]
        if data[position:position + 4] != b"FLdt":
            return None
        position += 8
        bpm = None
        end = len(data)
        while position < end:
            event = data[position]
            position += 1
            if event < 64:
                position += 1
            elif event < 128:
                if event == LEGACY_TEMPO:
                    bpm = float(struct.unpack_from("<H", data, position)[0])
                position += 2
            elif event < 192:
                if event == TEMPO:
                    bpm = struct.unpack_from("<I", data, position)[0] / 1000
                    break
                position += SIZE_EXCEPTIONS.get(event, 4)
            else:
                length = 0
                shift = 0
                while True:
                    byte = data[position]
                    position += 1
                    length |= (byte & 0x7F) << shift
                    shift += 7
                    if not byte & 0x80:
                        break
                position += length
        return bpm if bpm is not None and MIN_BPM <= bpm <= MAX_BPM else None
    except (IndexError, struct.error):
        return None


def format_bpm(bpm):
    """140.0 -> "140", 87.5 -> "87.5"."""
    return f"{bpm:.3f}".rstrip("0").rstrip(".")
