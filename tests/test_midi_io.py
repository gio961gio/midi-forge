"""Comprehensive tests for MIDI I/O, VLQ encoding, SMF parser/writer, and absolute tick timing."""
import struct
import tempfile
import os
import pytest
from midi_forge.midi_io import (
    MidiFile,
    MidiTrack,
    MidiEvent,
    read_vlq,
    write_vlq,
    EVENT_PRIORITY,
)


# =========================================================================
# 1. Variable Length Quantity (VLQ) Tests
# =========================================================================

@pytest.mark.parametrize("val, expected_bytes", [
    (0, b"\x00"),
    (0x40, b"\x40"),
    (0x7F, b"\x7F"),
    (0x80, b"\x81\x00"),
    (0x2000, b"\xC0\x00"),
    (0x3FFF, b"\xFF\x7F"),
    (0x4000, b"\x81\x80\x00"),
    (0x100000, b"\xC0\x80\x00"),
    (0x1FFFFF, b"\xFF\xFF\x7F"),
    (0x200000, b"\x81\x80\x80\x00"),
    (0x0FFFFFFF, b"\xFF\xFF\xFF\x7F"),
])
def test_vlq_roundtrip_boundaries(val, expected_bytes):
    encoded = write_vlq(val)
    assert encoded == expected_bytes
    decoded, offset = read_vlq(encoded, 0)
    assert decoded == val
    assert offset == len(encoded)


def test_vlq_negative_and_overflow_rejections():
    with pytest.raises(ValueError, match="must be a non-negative integer"):
        write_vlq(-1)

    with pytest.raises(ValueError, match="exceeds SMF maximum"):
        write_vlq(0x10000000)

    # 5-byte VLQ must be rejected
    five_byte_vlq = b"\x81\x80\x80\x80\x00"
    with pytest.raises(ValueError, match="exceeds 4 bytes"):
        read_vlq(five_byte_vlq, 0)

    # Truncated VLQ where high bit indicates continuation but buffer ends
    truncated_vlq = b"\x81\x80"
    with pytest.raises(ValueError, match="unexpected end of track chunk"):
        read_vlq(truncated_vlq, 0)


# =========================================================================
# 2. Header and Chunk Validation Tests
# =========================================================================

def test_header_validation_errors():
    with tempfile.TemporaryDirectory() as tmp:
        # 1. File too short
        f_short = os.path.join(tmp, "short.mid")
        with open(f_short, "wb") as f:
            f.write(b"MThd\x00\x00")
        with pytest.raises(ValueError, match="File too short"):
            MidiFile.load(f_short)

        # 2. Invalid magic
        f_bad_magic = os.path.join(tmp, "bad_magic.mid")
        with open(f_bad_magic, "wb") as f:
            f.write(b"RIFF" + b"\x00" * 10)
        with pytest.raises(ValueError, match="Invalid MIDI file header"):
            MidiFile.load(f_bad_magic)

        # 3. Header length < 6
        f_bad_len = os.path.join(tmp, "bad_len.mid")
        with open(f_bad_len, "wb") as f:
            f.write(b"MThd\x00\x00\x00\x04" + b"\x00" * 10)
        with pytest.raises(ValueError, match="Invalid MThd header length"):
            MidiFile.load(f_bad_len)

        # 4. Unsupported format 2
        f_fmt2 = os.path.join(tmp, "fmt2.mid")
        with open(f_fmt2, "wb") as f:
            f.write(b"MThd" + struct.pack(">IHHH", 6, 2, 1, 480))
        with pytest.raises(ValueError, match="Unsupported MIDI format 2"):
            MidiFile.load(f_fmt2)

        # 5. Format 0 with ntrks != 1
        f_fmt0_multi = os.path.join(tmp, "fmt0_multi.mid")
        with open(f_fmt0_multi, "wb") as f:
            f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 2, 480))
        with pytest.raises(ValueError, match="Format 0 MIDI file must contain exactly 1 track"):
            MidiFile.load(f_fmt0_multi)

        # 6. SMPTE division high bit
        f_smpte = os.path.join(tmp, "smpte.mid")
        with open(f_smpte, "wb") as f:
            f.write(b"MThd" + struct.pack(">IHHH", 6, 1, 1, 0x80E8))
        with pytest.raises(NotImplementedError, match="SMPTE timecode division is not supported"):
            MidiFile.load(f_smpte)

        # 7. Division <= 0
        f_div0 = os.path.join(tmp, "div0.mid")
        with open(f_div0, "wb") as f:
            f.write(b"MThd" + struct.pack(">IHHH", 6, 1, 1, 0))
        with pytest.raises(ValueError, match="Invalid ticks_per_beat division"):
            MidiFile.load(f_div0)


def test_truncated_track_chunk():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "truncated_track.mid")
        # Header declares 1 track; track chunk claims 100 bytes but only 10 bytes provided
        header = b"MThd" + struct.pack(">IHHH", 6, 1, 1, 480)
        track_header = b"MTrk" + struct.pack(">I", 100) + b"\x00" * 10
        with open(path, "wb") as f:
            f.write(header + track_header)

        with pytest.raises(ValueError, match="Truncated track data"):
            MidiFile.load(path)


# =========================================================================
# 3. Absolute Tick Invariant & Delta Conversion
# =========================================================================

def test_absolute_tick_roundtrip_preservation():
    """Verify that a note from absolute tick 100 to 200 roundtrips with exact ticks and duration."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "timing_test.mid")
        mf = MidiFile(format_type=1, ticks_per_beat=480)
        track = MidiTrack(name="Piano")
        track.add_note(start_tick=100, duration_ticks=100, note=64, velocity=90)
        mf.tracks.append(track)
        mf.save(path)

        loaded = MidiFile.load(path)
        assert len(loaded.tracks) == 1
        evs = loaded.tracks[0].events

        note_ons = [e for e in evs if e.type == "note_on" and e.velocity > 0]
        note_offs = [e for e in evs if e.type == "note_off" or (e.type == "note_on" and e.velocity == 0)]

        assert len(note_ons) == 1
        assert len(note_offs) == 1

        assert note_ons[0].tick == 100
        assert note_offs[0].tick == 200
        assert (note_offs[0].tick - note_ons[0].tick) == 100


def test_simultaneous_and_overlapping_same_pitch_notes():
    """Verify multiple notes of the same pitch on the same channel retain distinct start/end ticks."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "overlap.mid")
        mf = MidiFile(format_type=1, ticks_per_beat=480)
        track = MidiTrack()

        # Note 1: tick 100 to 300
        track.add_note(start_tick=100, duration_ticks=200, note=60, velocity=80)
        # Note 2: tick 200 to 400 (overlaps Note 1 on same pitch 60)
        track.add_note(start_tick=200, duration_ticks=200, note=60, velocity=85)
        mf.tracks.append(track)
        mf.save(path)

        loaded = MidiFile.load(path)
        evs = loaded.tracks[0].events
        on_ticks = [e.tick for e in evs if e.type == "note_on" and e.velocity > 0]
        off_ticks = [e.tick for e in evs if e.type in ("note_off", "note_on") and e.velocity == 0]

        assert on_ticks == [100, 200]
        assert off_ticks == [300, 400]


def test_same_tick_deterministic_ordering():
    """Verify that a note-off at tick 480 is serialized before a note-on at tick 480."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "same_tick.mid")
        mf = MidiFile(format_type=0, ticks_per_beat=480)
        track = MidiTrack()

        # Add Note-On at tick 480 first, then Note-Off at tick 480
        # The writer's deterministic ordering must place Note-Off before Note-On
        track.events.append(MidiEvent(tick=480, type="note_on", note=60, velocity=80))
        track.events.append(MidiEvent(tick=480, type="note_off", note=60, velocity=0))
        mf.tracks.append(track)
        mf.save(path)

        loaded = MidiFile.load(path)
        events_at_480 = [e for e in loaded.tracks[0].events if e.tick == 480]
        types_at_480 = [e.type for e in events_at_480]

        assert types_at_480[0] == "note_off"
        assert types_at_480[1] == "note_on"


# =========================================================================
# 4. Channel Voice Messages and Running Status Tests
# =========================================================================

def test_all_channel_voice_message_families():
    """Verify CC, Program Change, Channel Pressure, Poly Aftertouch, and Pitch Bend round-trip."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "channel_messages.mid")
        mf = MidiFile(format_type=1, ticks_per_beat=480)
        track = MidiTrack(name="All Controllers")

        track.events.extend([
            MidiEvent(tick=0, type="program_change", channel=0, program=42),
            MidiEvent(tick=10, type="control_change", channel=0, control=7, value=100),  # Volume
            MidiEvent(tick=20, type="control_change", channel=0, control=10, value=64),  # Pan
            MidiEvent(tick=30, type="poly_pressure", channel=0, note=60, pressure=85),
            MidiEvent(tick=40, type="channel_pressure", channel=0, pressure=95),
            MidiEvent(tick=50, type="pitch_bend", channel=0, pitch_bend=10000),
            MidiEvent(tick=100, type="note_on", channel=0, note=60, velocity=90),
            MidiEvent(tick=200, type="note_off", channel=0, note=60, velocity=0),
        ])
        mf.tracks.append(track)
        mf.save(path)

        loaded = MidiFile.load(path)
        levs = loaded.tracks[0].events

        prog = [e for e in levs if e.type == "program_change"][0]
        assert prog.tick == 0 and prog.program == 42

        cc7 = [e for e in levs if e.type == "control_change" and e.control == 7][0]
        assert cc7.tick == 10 and cc7.value == 100

        cc10 = [e for e in levs if e.type == "control_change" and e.control == 10][0]
        assert cc10.tick == 20 and cc10.value == 64

        poly = [e for e in levs if e.type == "poly_pressure"][0]
        assert poly.tick == 30 and poly.note == 60 and poly.pressure == 85

        chan_p = [e for e in levs if e.type == "channel_pressure"][0]
        assert chan_p.tick == 40 and chan_p.pressure == 95

        pb = [e for e in levs if e.type == "pitch_bend"][0]
        assert pb.tick == 50 and pb.pitch_bend == 10000


def test_running_status_parsing():
    """Verify that running status is correctly maintained and cleared on meta events."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "running_status.mid")
        # Hand-craft a track chunk with running status:
        # Event 1: delta=0, status 0x90 (Note On ch 0), note 60, vel 64
        # Event 2: delta=10, NO STATUS BYTE (running status 0x90!), note 62, vel 70
        # Event 3: delta=0, Meta event Set Tempo (clears running status!)
        # Event 4: delta=10, explicit status 0x80 (Note Off ch 0), note 60, vel 0
        track_payload = (
            b"\x00\x90\x3C\x40" +          # Note On 60 vel 64
            b"\x0A\x3E\x46" +              # Running Note On 62 vel 70
            b"\x00\xFF\x51\x03\x07\xA1\x20" + # Set Tempo (500000 us)
            b"\x0A\x80\x3C\x00" +          # Note Off 60
            b"\x00\x80\x3E\x00" +          # Note Off 62 (running status 0x80)
            b"\x00\xFF\x2F\x00"            # End of Track
        )

        header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480)
        track_chunk = b"MTrk" + struct.pack(">I", len(track_payload)) + track_payload

        with open(path, "wb") as f:
            f.write(header + track_chunk)

        loaded = MidiFile.load(path)
        events = loaded.tracks[0].events

        note_ons = [e for e in events if e.type == "note_on"]
        assert len(note_ons) == 2
        assert note_ons[0].note == 60 and note_ons[0].tick == 0
        assert note_ons[1].note == 62 and note_ons[1].tick == 10

        note_offs = [e for e in events if e.type == "note_off"]
        assert len(note_offs) == 2
        assert note_offs[0].note == 60 and note_offs[0].tick == 20
        assert note_offs[1].note == 62 and note_offs[1].tick == 20


# =========================================================================
# 5. Meta Events and SysEx Preservation Tests
# =========================================================================

def test_meta_and_sysex_preservation():
    """Verify track name, tempo, time signature, key signature, SysEx, and unknown meta events."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "meta_sysex.mid")
        mf = MidiFile(format_type=1, ticks_per_beat=480)
        track = MidiTrack(name="Master Track")

        track.events.extend([
            MidiEvent(tick=0, type="text", text="Master Track"),
            MidiEvent(tick=0, type="set_tempo", tempo=461538),  # ~130 BPM
            MidiEvent(tick=0, type="time_signature", raw_data=bytes([3, 2, 24, 8])),  # 3/4 time
            MidiEvent(tick=0, type="key_signature", raw_data=bytes([2, 0])),  # D Major (2 sharps)
            MidiEvent(tick=0, type="sysex", raw_data=b"\x7E\x7F\x09\x01\xF7"),
            MidiEvent(tick=0, type="meta", meta_type=0x7F, raw_data=b"CustomSequencerData"),
            MidiEvent(tick=480, type="end_of_track"),
        ])
        mf.tracks.append(track)
        mf.save(path)

        loaded = MidiFile.load(path)
        levs = loaded.tracks[0].events

        tempo_ev = [e for e in levs if e.type == "set_tempo"][0]
        assert tempo_ev.tempo == 461538
        assert tempo_ev.bpm == pytest.approx(130.0, abs=0.1)

        ts_ev = [e for e in levs if e.type == "time_signature"][0]
        assert ts_ev.raw_data == bytes([3, 2, 24, 8])

        ks_ev = [e for e in levs if e.type == "key_signature"][0]
        assert ks_ev.raw_data == bytes([2, 0])

        sysex_ev = [e for e in levs if e.type == "sysex"][0]
        assert sysex_ev.raw_data == b"\x7E\x7F\x09\x01\xF7"

        meta_custom = [e for e in levs if e.type == "meta" and e.meta_type == 0x7F][0]
        assert meta_custom.raw_data == b"CustomSequencerData"

        # End of Track must be singular and at tick 480
        eot_evs = [e for e in levs if e.type == "end_of_track"]
        assert len(eot_evs) == 1
        assert eot_evs[0].tick == 480


def test_exactly_one_eot_no_duplicates():
    """Verify that multiple redundant EOT events in memory produce exactly one EOT in output."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "eot_dedup.mid")
        mf = MidiFile(format_type=1, ticks_per_beat=480)
        track = MidiTrack()
        track.events.append(MidiEvent(tick=100, type="note_on", note=60, velocity=80))
        track.events.append(MidiEvent(tick=200, type="end_of_track"))
        track.events.append(MidiEvent(tick=200, type="end_of_track"))
        mf.tracks.append(track)
        mf.save(path)

        loaded = MidiFile.load(path)
        eots = [e for e in loaded.tracks[0].events if e.type == "end_of_track"]
        assert len(eots) == 1
        assert eots[0].tick == 200


# =========================================================================
# 6. SysEx 0xF0 vs 0xF7 Status Preservation and Validation
# =========================================================================

def test_sysex_f0_vs_f7_roundtrip_and_validation():
    """Verify 0xF0 and 0xF7 SysEx events survive load/save round trips without mutation."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "sysex_status.mid")
        mf = MidiFile(format_type=1, ticks_per_beat=480)
        track = MidiTrack(name="SysEx Track")

        f0_payload = b"\x7E\x7F\x09\x01\xF7"
        f7_payload = b"\x00\x41\x10\x42\x12\x40"

        track.events.extend([
            MidiEvent(tick=0, type="sysex", sysex_status=0xF0, raw_data=f0_payload),
            MidiEvent(tick=240, type="sysex", sysex_status=0xF7, raw_data=f7_payload),
            MidiEvent(tick=480, type="end_of_track"),
        ])
        mf.tracks.append(track)
        mf.save(path)

        loaded = MidiFile.load(path)
        levs = loaded.tracks[0].events

        sysex_events = [e for e in levs if e.type == "sysex"]
        assert len(sysex_events) == 2

        # Verify 0xF0 event
        assert sysex_events[0].tick == 0
        assert sysex_events[0].sysex_status == 0xF0
        assert sysex_events[0].raw_data == f0_payload

        # Verify 0xF7 event (status preserved!)
        assert sysex_events[1].tick == 240
        assert sysex_events[1].sysex_status == 0xF7
        assert sysex_events[1].raw_data == f7_payload

        # Writer validation: invalid sysex_status must raise ValueError
        bad_track = MidiTrack(name="Bad SysEx")
        bad_track.events.append(MidiEvent(tick=0, type="sysex", sysex_status=0x00, raw_data=b"\x01"))
        bad_mf = MidiFile(tracks=[bad_track])
        with pytest.raises(ValueError, match="sysex_status must be 0xF0 or 0xF7"):
            bad_mf.save(os.path.join(tmp, "bad_sysex.mid"))

        bad_track.events[0].sysex_status = 0x80
        with pytest.raises(ValueError, match="sysex_status must be 0xF0 or 0xF7"):
            bad_mf.save(os.path.join(tmp, "bad_sysex2.mid"))


# =========================================================================
# 7. Track Name Preservation, Authority, and Deduplication
# =========================================================================

def test_track_name_preservation_and_deduplication():
    """Verify track.name survives save/load, deduplicates 0x03 events, and preserves other text meta."""
    with tempfile.TemporaryDirectory() as tmp:
        # 1. MidiTrack(name="Piano") without explicit text event
        piano_path = os.path.join(tmp, "piano.mid")
        mf_piano = MidiFile(format_type=1, ticks_per_beat=480)
        track_piano = MidiTrack(name="Piano")
        track_piano.events.append(MidiEvent(tick=0, type="note_on", note=60, velocity=80))
        track_piano.events.append(MidiEvent(tick=480, type="note_off", note=60, velocity=0))
        mf_piano.tracks.append(track_piano)
        mf_piano.save(piano_path)

        loaded_piano = MidiFile.load(piano_path)
        assert loaded_piano.tracks[0].name == "Piano"
        track_name_events = [e for e in loaded_piano.tracks[0].events if e.type == "text"]
        assert len(track_name_events) == 1
        assert track_name_events[0].text == "Piano"

        # 2. Existing explicit track name event is not duplicated
        dedup_path = os.path.join(tmp, "dedup.mid")
        mf_dedup = MidiFile(format_type=1, ticks_per_beat=480)
        track_dedup = MidiTrack(name="Guitar")
        track_dedup.events.extend([
            MidiEvent(tick=0, type="text", meta_type=0x03, text="Guitar", raw_data=b"Guitar"),
            MidiEvent(tick=0, type="text", meta_type=0x03, text="Duplicate", raw_data=b"Duplicate"),
            MidiEvent(tick=240, type="end_of_track"),
        ])
        mf_dedup.tracks.append(track_dedup)
        mf_dedup.save(dedup_path)

        loaded_dedup = MidiFile.load(dedup_path)
        assert loaded_dedup.tracks[0].name == "Guitar"
        assert len([e for e in loaded_dedup.tracks[0].events if e.type == "text"]) == 1

        # 3. Disagreement: track.name is authoritative
        auth_path = os.path.join(tmp, "authoritative.mid")
        mf_auth = MidiFile(format_type=1, ticks_per_beat=480)
        track_auth = MidiTrack(name="AuthoritativeName")
        track_auth.events.append(MidiEvent(tick=0, type="text", meta_type=0x03, text="OldName"))
        mf_auth.tracks.append(track_auth)
        mf_auth.save(auth_path)

        loaded_auth = MidiFile.load(auth_path)
        assert loaded_auth.tracks[0].name == "AuthoritativeName"

        # 4. Other meta text events (e.g. 0x01 text, 0x02 copyright, 0x05 lyric) are preserved
        meta_path = os.path.join(tmp, "other_text.mid")
        mf_meta = MidiFile(format_type=1, ticks_per_beat=480)
        track_meta = MidiTrack(name="Vocals")
        track_meta.events.extend([
            MidiEvent(tick=0, type="meta", meta_type=0x01, raw_data=b"General text"),
            MidiEvent(tick=0, type="meta", meta_type=0x02, raw_data=b"(C) 2026 Author"),
            MidiEvent(tick=100, type="meta", meta_type=0x05, raw_data=b"La la la"),
            MidiEvent(tick=200, type="end_of_track"),
        ])
        mf_meta.tracks.append(track_meta)
        mf_meta.save(meta_path)

        loaded_meta = MidiFile.load(meta_path)
        assert loaded_meta.tracks[0].name == "Vocals"
        l_events = loaded_meta.tracks[0].events
        meta_01 = [e for e in l_events if e.type == "meta" and e.meta_type == 0x01]
        assert len(meta_01) == 1 and meta_01[0].raw_data == b"General text"
        meta_02 = [e for e in l_events if e.type == "meta" and e.meta_type == 0x02]
        assert len(meta_02) == 1 and meta_02[0].raw_data == b"(C) 2026 Author"
        meta_05 = [e for e in l_events if e.type == "meta" and e.meta_type == 0x05]
        assert len(meta_05) == 1 and meta_05[0].raw_data == b"La la la"


# =========================================================================
# 8. Strict Serialization Validation (No Silent Masking or Clamping)
# =========================================================================

def test_strict_serialization_validation_post_construction_mutations():
    """Verify that save() rejects invalid mutated fields with clear ValueError instead of masking/clamping."""
    with tempfile.TemporaryDirectory() as tmp:
        dummy_path = os.path.join(tmp, "test_val.mid")

        def make_valid_mf():
            mf = MidiFile(format_type=1, ticks_per_beat=480)
            track = MidiTrack(name="Test")
            track.events.append(MidiEvent(tick=0, type="note_on", channel=0, note=60, velocity=64))
            track.events.append(MidiEvent(tick=480, type="note_off", channel=0, note=60, velocity=0))
            mf.tracks.append(track)
            return mf

        # 1. Note bounds (must be 0..127)
        mf = make_valid_mf()
        mf.tracks[0].events[0].note = 128
        with pytest.raises(ValueError, match="note"):
            mf.save(dummy_path)
        mf.tracks[0].events[0].note = -1
        with pytest.raises(ValueError, match="note"):
            mf.save(dummy_path)
        mf.tracks[0].events[0].note = 200
        with pytest.raises(ValueError, match="note"):
            mf.save(dummy_path)

        # 2. Velocity bounds (must be 0..127)
        mf = make_valid_mf()
        mf.tracks[0].events[0].velocity = 128
        with pytest.raises(ValueError, match="velocity"):
            mf.save(dummy_path)
        mf.tracks[0].events[0].velocity = 130
        with pytest.raises(ValueError, match="velocity"):
            mf.save(dummy_path)
        mf.tracks[0].events[0].velocity = -5
        with pytest.raises(ValueError, match="velocity"):
            mf.save(dummy_path)

        # 3. Channel bounds (must be 0..15)
        mf = make_valid_mf()
        mf.tracks[0].events[0].channel = 16
        with pytest.raises(ValueError, match="channel"):
            mf.save(dummy_path)
        mf.tracks[0].events[0].channel = -1
        with pytest.raises(ValueError, match="channel"):
            mf.save(dummy_path)

        # 4. Control Change bounds (0..127)
        mf = make_valid_mf()
        mf.tracks[0].events.append(MidiEvent(tick=10, type="control_change", control=128, value=64))
        with pytest.raises(ValueError, match="control"):
            mf.save(dummy_path)
        mf.tracks[0].events[-1].control = 7
        mf.tracks[0].events[-1].value = 250
        with pytest.raises(ValueError, match="value"):
            mf.save(dummy_path)

        # 5. Program Change bounds (0..127)
        mf = make_valid_mf()
        mf.tracks[0].events.append(MidiEvent(tick=10, type="program_change", program=128))
        with pytest.raises(ValueError, match="program"):
            mf.save(dummy_path)

        # 6. Pressure bounds (0..127)
        mf = make_valid_mf()
        mf.tracks[0].events.append(MidiEvent(tick=10, type="channel_pressure", pressure=128))
        with pytest.raises(ValueError, match="pressure"):
            mf.save(dummy_path)
        mf.tracks[0].events[-1] = MidiEvent(tick=10, type="poly_pressure", note=60, pressure=128)
        with pytest.raises(ValueError, match="pressure"):
            mf.save(dummy_path)

        # 7. Pitch Bend bounds (0..16383, no silent clipping!)
        mf = make_valid_mf()
        mf.tracks[0].events.append(MidiEvent(tick=10, type="pitch_bend", pitch_bend=16384))
        with pytest.raises(ValueError, match="pitch_bend"):
            mf.save(dummy_path)
        mf.tracks[0].events[-1].pitch_bend = -1
        with pytest.raises(ValueError, match="pitch_bend"):
            mf.save(dummy_path)
        mf.tracks[0].events[-1].pitch_bend = 20000
        with pytest.raises(ValueError, match="pitch_bend"):
            mf.save(dummy_path)

        # 8. Tempo bounds (1..0xFFFFFF, no silent clipping!)
        mf = make_valid_mf()
        mf.tracks[0].events.append(MidiEvent(tick=0, type="set_tempo", tempo=0))
        with pytest.raises(ValueError, match="tempo"):
            mf.save(dummy_path)
        mf.tracks[0].events[-1].tempo = -10
        with pytest.raises(ValueError, match="tempo"):
            mf.save(dummy_path)
        mf.tracks[0].events[-1].tempo = 0x1000000
        with pytest.raises(ValueError, match="tempo"):
            mf.save(dummy_path)

        # 9. Event tick (must be non-negative integer <= 0x0FFFFFFF)
        mf = make_valid_mf()
        mf.tracks[0].events[0].tick = 0x10000000
        with pytest.raises(ValueError, match="exceeds SMF"):
            mf.save(dummy_path)

        # 10. Unsupported event type
        mf = make_valid_mf()
        mf.tracks[0].events.append(MidiEvent(tick=10, type="unsupported_custom_type"))
        with pytest.raises(ValueError, match="Unrecognized or unsupported event type"):
            mf.save(dummy_path)

        # 11. Format type and track counts
        mf = make_valid_mf()
        mf.format_type = 2
        with pytest.raises(ValueError, match="format_type"):
            mf.save(dummy_path)
        mf.format_type = 0
        mf.tracks.append(MidiTrack(name="Extra"))
        with pytest.raises(ValueError, match="Format 0 MIDI file must contain exactly 1 track"):
            mf.save(dummy_path)

        # 12. Ticks per beat PPQ (1..32767)
        mf = make_valid_mf()
        mf.ticks_per_beat = 0
        with pytest.raises(ValueError, match="ticks_per_beat"):
            mf.save(dummy_path)
        mf.ticks_per_beat = -1
        with pytest.raises(ValueError, match="ticks_per_beat"):
            mf.save(dummy_path)
        mf.ticks_per_beat = 32768
        with pytest.raises(ValueError, match="ticks_per_beat"):
            mf.save(dummy_path)


def test_valid_boundary_values_roundtrip():
    """Verify valid boundary values for all MIDI parameters round-trip accurately."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "boundaries.mid")
        mf = MidiFile(format_type=1, ticks_per_beat=32767)
        track = MidiTrack(name="Boundaries")

        track.events.extend([
            MidiEvent(tick=0, type="set_tempo", tempo=1),
            MidiEvent(tick=0, type="set_tempo", tempo=0xFFFFFF),
            MidiEvent(tick=0, type="note_on", channel=0, note=0, velocity=0),
            MidiEvent(tick=0, type="note_on", channel=15, note=127, velocity=127),
            MidiEvent(tick=10, type="pitch_bend", channel=0, pitch_bend=0),
            MidiEvent(tick=10, type="pitch_bend", channel=15, pitch_bend=16383),
            MidiEvent(tick=20, type="control_change", channel=0, control=0, value=0),
            MidiEvent(tick=20, type="control_change", channel=15, control=127, value=127),
            MidiEvent(tick=30, type="program_change", channel=0, program=0),
            MidiEvent(tick=30, type="program_change", channel=15, program=127),
            MidiEvent(tick=40, type="channel_pressure", channel=0, pressure=0),
            MidiEvent(tick=40, type="channel_pressure", channel=15, pressure=127),
            MidiEvent(tick=50, type="poly_pressure", channel=0, note=0, pressure=0),
            MidiEvent(tick=50, type="poly_pressure", channel=15, note=127, pressure=127),
            MidiEvent(tick=60, type="end_of_track"),
        ])
        mf.tracks.append(track)
        mf.save(path)

        loaded = MidiFile.load(path)
        assert loaded.ticks_per_beat == 32767
        levs = loaded.tracks[0].events

        pbs = [e for e in levs if e.type == "pitch_bend"]
        assert len(pbs) == 2
        assert pbs[0].pitch_bend == 0 and pbs[0].channel == 0
        assert pbs[1].pitch_bend == 16383 and pbs[1].channel == 15

        ccs = [e for e in levs if e.type == "control_change"]
        assert len(ccs) == 2
        assert ccs[0].control == 0 and ccs[0].value == 0
        assert ccs[1].control == 127 and ccs[1].value == 127

        tempos = [e for e in levs if e.type == "set_tempo"]
        assert len(tempos) == 2
        assert tempos[0].tempo == 1
        assert tempos[1].tempo == 0xFFFFFF
