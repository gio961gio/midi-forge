"""Pure Python Standard MIDI File (SMF) parser and writer."""
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


def read_vlq(data: bytes, offset: int) -> Tuple[int, int]:
    """Read Variable Length Quantity (VLQ). Returns (value, new_offset)."""
    val = 0
    while True:
        b = data[offset]
        offset += 1
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return val, offset


def write_vlq(value: int) -> bytes:
    """Encode an integer into Variable Length Quantity bytes."""
    buf = [value & 0x7F]
    value >>= 7
    while value > 0:
        buf.append(0x80 | (value & 0x7F))
        value >>= 7
    buf.reverse()
    return bytes(buf)


@dataclass
class MidiEvent:
    delta_time: int
    type: str  # "note_on", "note_off", "set_tempo", "end_of_track", "text"
    channel: int = 0
    note: int = 60
    velocity: int = 64
    tempo: int = 500000  # microseconds per beat (default 120 BPM)
    text: str = ""
    raw_data: bytes = b""

    @property
    def bpm(self) -> float:
        if self.type == "set_tempo" and self.tempo > 0:
            return round(60000000.0 / self.tempo, 2)
        return 120.0


@dataclass
class MidiTrack:
    name: str = "Track"
    events: List[MidiEvent] = field(default_factory=list)

    def add_note(self, start_tick: int, duration_ticks: int, note: int, velocity: int = 80, channel: int = 0):
        """Add note_on and note_off with absolute tick scheduling."""
        self.events.append(MidiEvent(delta_time=start_tick, type="note_on", channel=channel, note=note, velocity=velocity))
        self.events.append(MidiEvent(delta_time=start_tick + duration_ticks, type="note_off", channel=channel, note=note, velocity=0))


@dataclass
class MidiFile:
    format_type: int = 1
    ticks_per_beat: int = 480
    tracks: List[MidiTrack] = field(default_factory=list)

    @classmethod
    def load(cls, file_path: str) -> "MidiFile":
        """Parse a .mid/.midi binary file."""
        with open(file_path, "rb") as f:
            data = f.read()

        if data[:4] != b"MThd":
            raise ValueError("Invalid MIDI file header: expected MThd")

        _, fmt, ntrks, division = struct.unpack(">4sHHH", data[4:14])
        mf = cls(format_type=fmt, ticks_per_beat=division)

        offset = 14
        for _ in range(ntrks):
            if offset >= len(data) or data[offset : offset + 4] != b"MTrk":
                break
            track_len = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
            track_bytes = data[offset + 8 : offset + 8 + track_len]
            offset += 8 + track_len

            track = MidiTrack()
            t_offset = 0
            running_status = 0

            while t_offset < len(track_bytes):
                delta, t_offset = read_vlq(track_bytes, t_offset)
                if t_offset >= len(track_bytes):
                    break

                status = track_bytes[t_offset]
                if status >= 0x80:
                    running_status = status
                    t_offset += 1
                else:
                    status = running_status

                event_type_nibble = status & 0xF0
                channel = status & 0x0F

                if event_type_nibble == 0x90:  # Note On
                    note = track_bytes[t_offset]
                    vel = track_bytes[t_offset + 1]
                    t_offset += 2
                    ev_type = "note_off" if vel == 0 else "note_on"
                    track.events.append(MidiEvent(delta_time=delta, type=ev_type, channel=channel, note=note, velocity=vel))
                elif event_type_nibble == 0x80:  # Note Off
                    note = track_bytes[t_offset]
                    vel = track_bytes[t_offset + 1]
                    t_offset += 2
                    track.events.append(MidiEvent(delta_time=delta, type="note_off", channel=channel, note=note, velocity=vel))
                elif status == 0xFF:  # Meta Event
                    meta_type = track_bytes[t_offset]
                    t_offset += 1
                    meta_len, t_offset = read_vlq(track_bytes, t_offset)
                    meta_data = track_bytes[t_offset : t_offset + meta_len]
                    t_offset += meta_len

                    if meta_type == 0x51 and meta_len == 3:  # Set Tempo
                        tempo_val = (meta_data[0] << 16) | (meta_data[1] << 8) | meta_data[2]
                        track.events.append(MidiEvent(delta_time=delta, type="set_tempo", tempo=tempo_val))
                    elif meta_type == 0x03:  # Track Name
                        track.name = meta_data.decode("latin1", errors="ignore")
                        track.events.append(MidiEvent(delta_time=delta, type="text", text=track.name))
                    elif meta_type == 0x2F:  # End of Track
                        track.events.append(MidiEvent(delta_time=delta, type="end_of_track"))
                else:
                    # Skip other channel/sysex messages
                    t_offset += 1

            mf.tracks.append(track)
        return mf

    def save(self, file_path: str):
        """Save to a .mid binary file."""
        out = bytearray()
        # MThd header chunk
        out.extend(b"MThd")
        out.extend(struct.pack(">IHHH", 6, self.format_type, len(self.tracks), self.ticks_per_beat))

        for track in self.tracks:
            track_bytes = bytearray()
            # If events are in absolute ticks, sort and convert to delta
            sorted_events = sorted(track.events, key=lambda e: e.delta_time)
            last_tick = 0

            for ev in sorted_events:
                delta = max(0, ev.delta_time - last_tick)
                last_tick = ev.delta_time
                track_bytes.extend(write_vlq(delta))

                if ev.type == "note_on":
                    track_bytes.extend(bytes([0x90 | (ev.channel & 0x0F), ev.note & 0x7F, ev.velocity & 0x7F]))
                elif ev.type == "note_off":
                    track_bytes.extend(bytes([0x80 | (ev.channel & 0x0F), ev.note & 0x7F, ev.velocity & 0x7F]))
                elif ev.type == "set_tempo":
                    tempo_bytes = bytes([(ev.tempo >> 16) & 0xFF, (ev.tempo >> 8) & 0xFF, ev.tempo & 0xFF])
                    track_bytes.extend(bytes([0xFF, 0x51, 0x03]) + tempo_bytes)
                elif ev.type == "end_of_track":
                    track_bytes.extend(bytes([0xFF, 0x2F, 0x00]))

            # Always ensure end of track
            if not sorted_events or sorted_events[-1].type != "end_of_track":
                track_bytes.extend(write_vlq(0) + bytes([0xFF, 0x2F, 0x00]))

            out.extend(b"MTrk")
            out.extend(struct.pack(">I", len(track_bytes)))
            out.extend(track_bytes)

        with open(file_path, "wb") as f:
            f.write(out)

    def to_dict(self) -> Dict[str, Any]:
        """Convert MIDI representation to dictionary for JSON serialization."""
        return {
            "format": self.format_type,
            "ticks_per_beat": self.ticks_per_beat,
            "num_tracks": len(self.tracks),
            "tracks": [
                {
                    "name": t.name,
                    "event_count": len(t.events),
                    "events": [
                        {
                            "delta_time": e.delta_time,
                            "type": e.type,
                            "note": e.note,
                            "velocity": e.velocity,
                            "bpm": e.bpm if e.type == "set_tempo" else None,
                        }
                        for e in t.events
                    ],
                }
                for t in self.tracks
            ],
        }