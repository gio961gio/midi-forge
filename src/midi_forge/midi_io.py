"""Pure Python Standard MIDI File (SMF) parser and writer with absolute tick timing."""
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

EVENT_PRIORITY = {
    "set_tempo": 0,
    "time_signature": 1,
    "key_signature": 2,
    "text": 3,
    "meta": 4,
    "note_off": 10,
    "control_change": 20,
    "program_change": 21,
    "channel_pressure": 22,
    "poly_pressure": 23,
    "pitch_bend": 24,
    "sysex": 30,
    "note_on": 40,
    "end_of_track": 100,
}


def read_vlq(data: bytes, offset: int, max_offset: Optional[int] = None) -> Tuple[int, int]:
    """
    Read Variable Length Quantity (VLQ).

    Returns (value, new_offset).
    Raises ValueError on truncated data, values exceeding 4 bytes, or overflow (> 0x0FFFFFFF).
    """
    if max_offset is None:
        max_offset = len(data)

    if offset >= max_offset:
        raise ValueError(f"Truncated VLQ: offset {offset} reaches or exceeds buffer boundary {max_offset}")

    val = 0
    bytes_read = 0
    while True:
        if offset >= max_offset:
            raise ValueError("Truncated VLQ: unexpected end of track chunk before terminating byte")
        b = data[offset]
        offset += 1
        bytes_read += 1
        val = (val << 7) | (b & 0x7F)

        if bytes_read > 4:
            raise ValueError("Malformed VLQ: variable-length quantity exceeds 4 bytes")

        if not (b & 0x80):
            break

    if val > 0x0FFFFFFF:
        raise ValueError(f"VLQ value {val} exceeds SMF limit of 0x0FFFFFFF")

    return val, offset


def write_vlq(value: int) -> bytes:
    """
    Encode a non-negative integer into Variable Length Quantity bytes (up to 4 bytes).

    Raises ValueError on negative values, non-integers, or values exceeding 0x0FFFFFFF.
    """
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"VLQ value must be a non-negative integer, got: {value!r}")
    if value > 0x0FFFFFFF:
        raise ValueError(f"VLQ value {value} exceeds SMF maximum 0x0FFFFFFF")

    buf = [value & 0x7F]
    value >>= 7
    while value > 0:
        buf.append(0x80 | (value & 0x7F))
        value >>= 7
    buf.reverse()
    return bytes(buf)


@dataclass
class MidiEvent:
    """
    In-memory representation of a MIDI event using canonical absolute tick timing.

    Attributes
    ----------
    tick : int
        Non-negative absolute tick position from track start.
    type : str
        Event type ('note_on', 'note_off', 'control_change', 'program_change',
        'channel_pressure', 'poly_pressure', 'pitch_bend', 'set_tempo',
        'time_signature', 'key_signature', 'text', 'meta', 'sysex', 'end_of_track').
    channel : int, default 0
        MIDI channel (0-15).
    note : int, default 60
        MIDI note number (0-127).
    velocity : int, default 64
        Velocity (0-127).
    control : int, default 0
        Controller number for CC (0-127).
    value : int, default 0
        Controller value (0-127).
    program : int, default 0
        Program change number (0-127).
    pressure : int, default 0
        Aftertouch / channel pressure value (0-127).
    pitch_bend : int, default 8192
        14-bit pitch bend value (0-16383, 8192 = center).
    tempo : int, default 500000
        Microseconds per beat for set_tempo (default 120 BPM).
    meta_type : int, default 0
        Meta event type byte for generic meta events.
    text : str, default ""
        Decoded text for text/track_name events.
    raw_data : bytes, default b""
        Preserved raw byte payload for meta/sysex events.
    sysex_status : int, default 0xF0
        Preserved SysEx status byte (0xF0 or 0xF7).
    """
    tick: int = 0
    type: str = "note_on"
    channel: int = 0
    note: int = 60
    velocity: int = 64
    control: int = 0
    value: int = 0
    program: int = 0
    pressure: int = 0
    pitch_bend: int = 8192
    tempo: int = 500000
    meta_type: int = 0
    text: str = ""
    raw_data: bytes = b""
    sysex_status: int = 0xF0

    def __post_init__(self):
        if not isinstance(self.tick, int) or isinstance(self.tick, bool) or self.tick < 0:
            raise ValueError(f"Event tick must be a non-negative integer, got: {self.tick!r}")

    @property
    def delta_time(self) -> int:
        """Deprecated legacy alias for canonical absolute tick."""
        return self.tick

    @delta_time.setter
    def delta_time(self, val: int):
        if not isinstance(val, int) or isinstance(val, bool) or val < 0:
            raise ValueError(f"Event tick must be a non-negative integer, got: {val!r}")
        self.tick = val

    @property
    def bpm(self) -> float:
        if self.type == "set_tempo" and self.tempo > 0:
            return round(60000000.0 / self.tempo, 2)
        return 120.0


@dataclass
class MidiTrack:
    name: str = "Track"
    events: List[MidiEvent] = field(default_factory=list)

    def add_note(
        self,
        start_tick: int,
        duration_ticks: int,
        note: int,
        velocity: int = 80,
        channel: int = 0,
    ):
        """
        Add a note_on and corresponding note_off at absolute tick positions.

        Parameters
        ----------
        start_tick : int
            Absolute start tick (>= 0).
        duration_ticks : int
            Note duration in ticks (> 0).
        note : int
            MIDI pitch (0-127).
        velocity : int, default 80
            Note velocity (0-127).
        channel : int, default 0
            MIDI channel (0-15).
        """
        if not isinstance(start_tick, int) or isinstance(start_tick, bool) or start_tick < 0:
            raise ValueError(f"start_tick must be a non-negative integer, got: {start_tick!r}")
        if not isinstance(duration_ticks, int) or isinstance(duration_ticks, bool) or duration_ticks <= 0:
            raise ValueError(f"duration_ticks must be a positive integer, got: {duration_ticks!r}")
        if not isinstance(note, int) or isinstance(note, bool) or not (0 <= note <= 127):
            raise ValueError(f"note pitch must be an integer in 0..127, got: {note!r}")
        if not isinstance(velocity, int) or isinstance(velocity, bool) or not (0 <= velocity <= 127):
            raise ValueError(f"velocity must be an integer in 0..127, got: {velocity!r}")
        if not isinstance(channel, int) or isinstance(channel, bool) or not (0 <= channel <= 15):
            raise ValueError(f"channel must be an integer in 0..15, got: {channel!r}")

        self.events.append(
            MidiEvent(tick=start_tick, type="note_on", channel=channel, note=note, velocity=velocity)
        )
        self.events.append(
            MidiEvent(tick=start_tick + duration_ticks, type="note_off", channel=channel, note=note, velocity=0)
        )


def _validate_int_field(ev_type: str, field_name: str, value: Any, min_val: int, max_val: int):
    """Validate an integer field is within inclusive range [min_val, max_val]."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            f"Event '{ev_type}': field '{field_name}' must be an integer, got {type(value).__name__} ({value!r})"
        )
    if not (min_val <= value <= max_val):
        raise ValueError(
            f"Event '{ev_type}': field '{field_name}' value {value} out of range ({min_val}..{max_val})"
        )


SUPPORTED_EVENT_TYPES = {
    "note_on",
    "note_off",
    "poly_pressure",
    "control_change",
    "program_change",
    "channel_pressure",
    "pitch_bend",
    "set_tempo",
    "time_signature",
    "key_signature",
    "text",
    "meta",
    "sysex",
    "end_of_track",
}


@dataclass
class MidiFile:
    format_type: int = 1
    ticks_per_beat: int = 480
    tracks: List[MidiTrack] = field(default_factory=list)

    @classmethod
    def load(cls, file_path: str) -> "MidiFile":
        """Parse a .mid/.midi binary file into an in-memory MidiFile structure."""
        with open(file_path, "rb") as f:
            data = f.read()

        if len(data) < 8:
            raise ValueError(f"File too short to contain a valid MIDI header: {len(data)} bytes")

        if data[:4] != b"MThd":
            raise ValueError(f"Invalid MIDI file header: expected MThd, got {data[:4]!r}")

        header_len = struct.unpack(">I", data[4:8])[0]
        if header_len < 6:
            raise ValueError(f"Invalid MThd header length: expected at least 6, got {header_len}")

        if len(data) < 8 + header_len:
            raise ValueError(
                f"Truncated file: declared header length {header_len} exceeds file size {len(data)}"
            )

        fmt, ntrks, division = struct.unpack(">HHH", data[8:14])

        if fmt not in (0, 1):
            raise ValueError(f"Unsupported MIDI format {fmt}. Only format 0 and 1 are supported.")

        if fmt == 0 and ntrks != 1:
            raise ValueError(f"Format 0 MIDI file must contain exactly 1 track, declared {ntrks}")

        # SMPTE timecode timing validation
        if division & 0x8000:
            raise NotImplementedError(
                "SMPTE timecode division is not supported; only PPQ (ticks per beat) is supported."
            )
        if division <= 0:
            raise ValueError(f"Invalid ticks_per_beat division: {division}")

        mf = cls(format_type=fmt, ticks_per_beat=division)

        # Skip any header extension bytes beyond standard 6
        offset = 8 + header_len
        parsed_tracks = 0

        while offset < len(data) and parsed_tracks < ntrks:
            if offset + 8 > len(data):
                raise ValueError(
                    f"Truncated file: expected track header at offset {offset}, but only {len(data) - offset} bytes remain"
                )

            chunk_id = data[offset : offset + 4]
            if chunk_id != b"MTrk":
                raise ValueError(
                    f"Expected MTrk chunk at offset {offset}, found {chunk_id!r}"
                )

            track_len = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
            if offset + 8 + track_len > len(data):
                raise ValueError(
                    f"Truncated track data for track {parsed_tracks + 1}: declared length {track_len} "
                    f"exceeds remaining {len(data) - (offset + 8)} bytes"
                )

            track_bytes = data[offset + 8 : offset + 8 + track_len]
            offset += 8 + track_len

            track = MidiTrack()
            t_offset = 0
            current_tick = 0
            running_status = 0
            track_end_offset = len(track_bytes)

            while t_offset < track_end_offset:
                delta, t_offset = read_vlq(track_bytes, t_offset, max_offset=track_end_offset)
                current_tick += delta

                if t_offset >= track_end_offset:
                    raise ValueError(f"Unexpected end of track data at tick {current_tick}")

                first_byte = track_bytes[t_offset]

                if first_byte >= 0x80:
                    status = first_byte
                    t_offset += 1
                    if status < 0xF0:
                        running_status = status
                    else:
                        # Clear running status for SysEx / Realtime / Meta
                        running_status = 0
                else:
                    if running_status == 0:
                        raise ValueError(
                            f"Running status encountered byte {first_byte:#x} at tick {current_tick} "
                            "before any channel status was established"
                        )
                    status = running_status

                # Handle Meta Events (0xFF)
                if status == 0xFF:
                    if t_offset >= track_end_offset:
                        raise ValueError(f"Truncated meta event at tick {current_tick}")
                    meta_type = track_bytes[t_offset]
                    t_offset += 1
                    meta_len, t_offset = read_vlq(track_bytes, t_offset, max_offset=track_end_offset)
                    if t_offset + meta_len > track_end_offset:
                        raise ValueError(
                            f"Truncated meta event payload (type {meta_type:#x}, length {meta_len}) at tick {current_tick}"
                        )
                    meta_data = track_bytes[t_offset : t_offset + meta_len]
                    t_offset += meta_len

                    if meta_type == 0x51:  # Set Tempo (must be exactly 3 bytes)
                        if meta_len != 3:
                            raise ValueError(f"Set Tempo meta event must have length 3, got {meta_len}")
                        tempo_val = (meta_data[0] << 16) | (meta_data[1] << 8) | meta_data[2]
                        track.events.append(
                            MidiEvent(tick=current_tick, type="set_tempo", tempo=tempo_val, raw_data=meta_data)
                        )
                    elif meta_type == 0x03:  # Track Name / Sequence Name
                        try:
                            text_str = meta_data.decode("utf-8")
                        except UnicodeDecodeError:
                            text_str = meta_data.decode("latin1", errors="replace")
                        track.name = text_str
                        track.events.append(
                            MidiEvent(tick=current_tick, type="text", meta_type=0x03, text=text_str, raw_data=meta_data)
                        )
                    elif meta_type == 0x58:  # Time Signature
                        track.events.append(
                            MidiEvent(tick=current_tick, type="time_signature", raw_data=meta_data)
                        )
                    elif meta_type == 0x59:  # Key Signature
                        track.events.append(
                            MidiEvent(tick=current_tick, type="key_signature", raw_data=meta_data)
                        )
                    elif meta_type == 0x2F:  # End of Track
                        track.events.append(
                            MidiEvent(tick=current_tick, type="end_of_track", raw_data=meta_data)
                        )
                    else:  # Preserved arbitrary meta event (e.g. 0x01, 0x02, 0x04, 0x05, etc.)
                        track.events.append(
                            MidiEvent(tick=current_tick, type="meta", meta_type=meta_type, raw_data=meta_data)
                        )

                # Handle SysEx Events (0xF0, 0xF7)
                elif status in (0xF0, 0xF7):
                    sysex_len, t_offset = read_vlq(track_bytes, t_offset, max_offset=track_end_offset)
                    if t_offset + sysex_len > track_end_offset:
                        raise ValueError(f"Truncated SysEx message at tick {current_tick}")
                    sysex_data = track_bytes[t_offset : t_offset + sysex_len]
                    t_offset += sysex_len
                    track.events.append(
                        MidiEvent(tick=current_tick, type="sysex", sysex_status=status, raw_data=sysex_data)
                    )

                # Handle Channel Voice Messages (0x80..0xEF)
                else:
                    event_type_nibble = status & 0xF0
                    channel = status & 0x0F

                    if event_type_nibble in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                        # 2 data bytes required
                        if t_offset + 2 > track_end_offset:
                            raise ValueError(
                                f"Truncated 2-byte channel message ({status:#x}) at tick {current_tick}"
                            )
                        d1 = track_bytes[t_offset]
                        d2 = track_bytes[t_offset + 1]
                        t_offset += 2

                        if not (0 <= d1 <= 127 and 0 <= d2 <= 127):
                            raise ValueError(f"Invalid MIDI data bytes ({d1}, {d2}) at tick {current_tick}")

                        if event_type_nibble == 0x90:  # Note On
                            track.events.append(
                                MidiEvent(tick=current_tick, type="note_on", channel=channel, note=d1, velocity=d2)
                            )
                        elif event_type_nibble == 0x80:  # Note Off
                            track.events.append(
                                MidiEvent(tick=current_tick, type="note_off", channel=channel, note=d1, velocity=d2)
                            )
                        elif event_type_nibble == 0xA0:  # Polyphonic Aftertouch
                            track.events.append(
                                MidiEvent(tick=current_tick, type="poly_pressure", channel=channel, note=d1, pressure=d2)
                            )
                        elif event_type_nibble == 0xB0:  # Control Change
                            track.events.append(
                                MidiEvent(tick=current_tick, type="control_change", channel=channel, control=d1, value=d2)
                            )
                        elif event_type_nibble == 0xE0:  # Pitch Bend (14-bit: lsb, msb)
                            pb_val = (d2 << 7) | d1
                            track.events.append(
                                MidiEvent(tick=current_tick, type="pitch_bend", channel=channel, pitch_bend=pb_val)
                            )

                    elif event_type_nibble in (0xC0, 0xD0):
                        # 1 data byte required
                        if t_offset + 1 > track_end_offset:
                            raise ValueError(
                                f"Truncated 1-byte channel message ({status:#x}) at tick {current_tick}"
                            )
                        d1 = track_bytes[t_offset]
                        t_offset += 1

                        if not (0 <= d1 <= 127):
                            raise ValueError(f"Invalid MIDI data byte ({d1}) at tick {current_tick}")

                        if event_type_nibble == 0xC0:  # Program Change
                            track.events.append(
                                MidiEvent(tick=current_tick, type="program_change", channel=channel, program=d1)
                            )
                        elif event_type_nibble == 0xD0:  # Channel Pressure
                            track.events.append(
                                MidiEvent(tick=current_tick, type="channel_pressure", channel=channel, pressure=d1)
                            )
                    else:
                        raise ValueError(f"Unrecognized MIDI status {status:#x} at tick {current_tick}")

            mf.tracks.append(track)
            parsed_tracks += 1

        if parsed_tracks < ntrks:
            raise ValueError(f"Expected {ntrks} tracks but only parsed {parsed_tracks} tracks")

        return mf

    def validate_for_save(self):
        """
        Pre-serialization validation of all file, track, and event fields.

        Enforces SMF specifications without silently masking or clamping values.
        Raises ValueError with offending field, value, and valid range.
        """
        if not isinstance(self.format_type, int) or isinstance(self.format_type, bool) or self.format_type not in (0, 1):
            raise ValueError(f"Unsupported MIDI format_type: {self.format_type!r}. Supported formats: 0, 1")

        if not isinstance(self.ticks_per_beat, int) or isinstance(self.ticks_per_beat, bool) or not (1 <= self.ticks_per_beat <= 32767):
            raise ValueError(
                f"ticks_per_beat must be a positive integer in range 1..32767 (15-bit PPQ), got: {self.ticks_per_beat!r}"
            )

        if not isinstance(self.tracks, list) or not (0 <= len(self.tracks) <= 65535):
            raise ValueError(f"Track count must be in range 0..65535, got: {len(self.tracks)}")

        if self.format_type == 0 and len(self.tracks) != 1:
            raise ValueError(f"Format 0 MIDI file must contain exactly 1 track, got {len(self.tracks)}")

        for track_idx, track in enumerate(self.tracks):
            if not isinstance(track, MidiTrack):
                raise ValueError(f"Track at index {track_idx} is not an instance of MidiTrack")

            for ev in track.events:
                if not isinstance(ev.tick, int) or isinstance(ev.tick, bool) or ev.tick < 0:
                    raise ValueError(f"Event tick must be a non-negative integer, got: {ev.tick!r}")
                if ev.tick > 0x0FFFFFFF:
                    raise ValueError(f"Event tick {ev.tick} exceeds SMF maximum 0x0FFFFFFF")

                if ev.type not in SUPPORTED_EVENT_TYPES:
                    raise ValueError(f"Unrecognized or unsupported event type: '{ev.type}'")

                # Channel voice events
                if ev.type in (
                    "note_on", "note_off", "poly_pressure", "control_change",
                    "program_change", "channel_pressure", "pitch_bend"
                ):
                    _validate_int_field(ev.type, "channel", ev.channel, 0, 15)

                if ev.type in ("note_on", "note_off"):
                    _validate_int_field(ev.type, "note", ev.note, 0, 127)
                    _validate_int_field(ev.type, "velocity", ev.velocity, 0, 127)
                elif ev.type == "poly_pressure":
                    _validate_int_field(ev.type, "note", ev.note, 0, 127)
                    _validate_int_field(ev.type, "pressure", ev.pressure, 0, 127)
                elif ev.type == "control_change":
                    _validate_int_field(ev.type, "control", ev.control, 0, 127)
                    _validate_int_field(ev.type, "value", ev.value, 0, 127)
                elif ev.type == "program_change":
                    _validate_int_field(ev.type, "program", ev.program, 0, 127)
                elif ev.type == "channel_pressure":
                    _validate_int_field(ev.type, "pressure", ev.pressure, 0, 127)
                elif ev.type == "pitch_bend":
                    _validate_int_field(ev.type, "pitch_bend", ev.pitch_bend, 0, 16383)
                elif ev.type == "set_tempo":
                    _validate_int_field(ev.type, "tempo", ev.tempo, 1, 0xFFFFFF)
                    if ev.raw_data and len(ev.raw_data) != 3:
                        raise ValueError(f"Event 'set_tempo': raw_data length must be 3 bytes, got {len(ev.raw_data)}")
                elif ev.type == "time_signature":
                    if ev.raw_data and len(ev.raw_data) != 4:
                        raise ValueError(f"Event 'time_signature': raw_data length must be 4 bytes, got {len(ev.raw_data)}")
                elif ev.type == "key_signature":
                    if ev.raw_data and len(ev.raw_data) != 2:
                        raise ValueError(f"Event 'key_signature': raw_data length must be 2 bytes, got {len(ev.raw_data)}")
                elif ev.type == "text":
                    if ev.meta_type != 0:
                        _validate_int_field(ev.type, "meta_type", ev.meta_type, 0, 255)
                    payload_len = len(ev.raw_data) if ev.raw_data else len(ev.text.encode("utf-8"))
                    if payload_len > 0x0FFFFFFF:
                        raise ValueError(f"Event 'text': payload length {payload_len} exceeds SMF limit")
                elif ev.type == "meta":
                    _validate_int_field(ev.type, "meta_type", ev.meta_type, 0, 255)
                    if len(ev.raw_data) > 0x0FFFFFFF:
                        raise ValueError(f"Event 'meta': payload length {len(ev.raw_data)} exceeds SMF limit")
                elif ev.type == "sysex":
                    if not isinstance(ev.sysex_status, int) or isinstance(ev.sysex_status, bool) or ev.sysex_status not in (0xF0, 0xF7):
                        raise ValueError(f"Event 'sysex': sysex_status must be 0xF0 or 0xF7, got: {ev.sysex_status!r}")
                    if not isinstance(ev.raw_data, (bytes, bytearray)):
                        raise ValueError(f"Event 'sysex': raw_data must be bytes or bytearray, got {type(ev.raw_data).__name__}")
                    if len(ev.raw_data) > 0x0FFFFFFF:
                        raise ValueError(f"Event 'sysex': payload length {len(ev.raw_data)} exceeds SMF limit")

    def save(self, file_path: str):
        """
        Serialize in-memory MidiFile structure to a Standard MIDI File (.mid).

        Guarantees:
        - Pre-serialization validation of all file, track, and event fields without silent masking/clamping.
        - Deterministic sorting by absolute tick and event priority.
        - Non-negative delta times derived from sorted absolute tick positions.
        - Preserves exact SysEx status (0xF0 vs 0xF7) and payload bytes.
        - Authoritative track.name serialization with deduplication of Track Name meta events (0x03).
        - Preserves all other text and arbitrary meta events with their original meta_type and payload.
        - Exactly one final end_of_track event per track.
        """
        self.validate_for_save()

        out = bytearray()
        out.extend(b"MThd")
        out.extend(struct.pack(">IHHH", 6, self.format_type, len(self.tracks), self.ticks_per_beat))

        for track in self.tracks:
            track_bytes = bytearray()

            # Handle track name and meta events:
            # A track name event is identified by (type == "text" and meta_type in (0, 0x03)) or (type == "meta" and meta_type == 0x03).
            # track.name is authoritative:
            # If track.name is non-empty:
            # - The first track name event (or a newly synthesized one at tick 0 if none exist) is updated with track.name.
            # - Any subsequent track name events are omitted to prevent duplicates.
            # All other events (including other meta/text types like 0x01, 0x02, 0x05) are preserved.
            processed_events = []
            track_name_found = False
            target_name = track.name.strip() if track.name else ""

            for ev in track.events:
                is_track_name_event = (
                    (ev.type == "text" and ev.meta_type in (0, 0x03))
                    or (ev.type == "meta" and ev.meta_type == 0x03)
                )
                if is_track_name_event:
                    if not track_name_found:
                        track_name_found = True
                        if target_name:
                            processed_events.append(
                                MidiEvent(
                                    tick=ev.tick,
                                    type="text",
                                    meta_type=0x03,
                                    text=target_name,
                                    raw_data=target_name.encode("utf-8"),
                                )
                            )
                        else:
                            processed_events.append(ev)
                    else:
                        # Drop duplicate track name event
                        continue
                else:
                    processed_events.append(ev)

            # If track has a non-empty name but no track name event existed, synthesize one at tick 0
            if target_name and not track_name_found:
                processed_events.insert(
                    0,
                    MidiEvent(
                        tick=0,
                        type="text",
                        meta_type=0x03,
                        text=target_name,
                        raw_data=target_name.encode("utf-8"),
                    ),
                )

            # Separate non-EOT events from EOT events to avoid duplicate EOTs
            non_eot_events = [e for e in processed_events if e.type != "end_of_track"]
            eot_events = [e for e in processed_events if e.type == "end_of_track"]

            sorted_events = sorted(
                non_eot_events,
                key=lambda e: (e.tick, EVENT_PRIORITY.get(e.type, 50))
            )

            # Determine final tick for End of Track
            if eot_events:
                final_eot_tick = max(eot_events[-1].tick, (sorted_events[-1].tick if sorted_events else 0))
            else:
                final_eot_tick = sorted_events[-1].tick if sorted_events else 0

            last_tick = 0
            for ev in sorted_events:
                delta = ev.tick - last_tick
                if delta < 0:
                    raise ValueError(f"Event tick {ev.tick} precedes previous event tick {last_tick}")
                last_tick = ev.tick
                track_bytes.extend(write_vlq(delta))

                if ev.type == "note_on":
                    track_bytes.extend(bytes([0x90 | ev.channel, ev.note, ev.velocity]))
                elif ev.type == "note_off":
                    track_bytes.extend(bytes([0x80 | ev.channel, ev.note, ev.velocity]))
                elif ev.type == "poly_pressure":
                    track_bytes.extend(bytes([0xA0 | ev.channel, ev.note, ev.pressure]))
                elif ev.type == "control_change":
                    track_bytes.extend(bytes([0xB0 | ev.channel, ev.control, ev.value]))
                elif ev.type == "program_change":
                    track_bytes.extend(bytes([0xC0 | ev.channel, ev.program]))
                elif ev.type == "channel_pressure":
                    track_bytes.extend(bytes([0xD0 | ev.channel, ev.pressure]))
                elif ev.type == "pitch_bend":
                    track_bytes.extend(bytes([0xE0 | ev.channel, ev.pitch_bend & 0x7F, (ev.pitch_bend >> 7) & 0x7F]))
                elif ev.type == "set_tempo":
                    tempo_bytes = bytes([(ev.tempo >> 16) & 0xFF, (ev.tempo >> 8) & 0xFF, ev.tempo & 0xFF])
                    track_bytes.extend(bytes([0xFF, 0x51, 0x03]) + tempo_bytes)
                elif ev.type == "text":
                    meta_type = ev.meta_type if ev.meta_type != 0 else 0x03
                    payload = ev.raw_data if ev.raw_data else ev.text.encode("utf-8")
                    track_bytes.extend(bytes([0xFF, meta_type]) + write_vlq(len(payload)) + payload)
                elif ev.type == "time_signature":
                    payload = ev.raw_data if ev.raw_data else bytes([4, 2, 24, 8])
                    track_bytes.extend(bytes([0xFF, 0x58]) + write_vlq(len(payload)) + payload)
                elif ev.type == "key_signature":
                    payload = ev.raw_data if ev.raw_data else bytes([0, 0])
                    track_bytes.extend(bytes([0xFF, 0x59]) + write_vlq(len(payload)) + payload)
                elif ev.type == "sysex":
                    track_bytes.extend(bytes([ev.sysex_status]) + write_vlq(len(ev.raw_data)) + ev.raw_data)
                elif ev.type == "meta":
                    track_bytes.extend(bytes([0xFF, ev.meta_type]) + write_vlq(len(ev.raw_data)) + ev.raw_data)

            # Append the single final End-of-Track marker
            eot_delta = max(0, final_eot_tick - last_tick)
            track_bytes.extend(write_vlq(eot_delta) + bytes([0xFF, 0x2F, 0x00]))

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
                            "tick": e.tick,
                            "type": e.type,
                            "channel": e.channel,
                            "note": e.note if e.type in ("note_on", "note_off", "poly_pressure") else None,
                            "velocity": e.velocity if e.type in ("note_on", "note_off") else None,
                            "control": e.control if e.type == "control_change" else None,
                            "value": e.value if e.type == "control_change" else None,
                            "program": e.program if e.type == "program_change" else None,
                            "pressure": e.pressure if e.type in ("poly_pressure", "channel_pressure") else None,
                            "pitch_bend": e.pitch_bend if e.type == "pitch_bend" else None,
                            "tempo": e.tempo if e.type == "set_tempo" else None,
                            "bpm": e.bpm if e.type == "set_tempo" else None,
                            "meta_type": e.meta_type if e.type in ("meta", "text") else None,
                            "text": e.text if e.type == "text" else None,
                            "sysex_status": e.sysex_status if e.type == "sysex" else None,
                        }
                        for e in t.events
                    ],
                }
                for t in self.tracks
            ],
        }
