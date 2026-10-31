"""Unit tests for Midi Forge."""
import os
import tempfile
import pytest
from midi_forge.midi_io import MidiFile, MidiTrack, MidiEvent
from midi_forge.theory import note_to_midi, midi_to_note, get_scale_notes, parse_progression
from midi_forge.generator import generate_progression_midi
from midi_forge.processors import humanize, quantize


def test_note_conversion():
    assert note_to_midi("C", 4) == 60
    assert note_to_midi("A", 4) == 69
    assert midi_to_note(60) == "C4"
    assert midi_to_note(69) == "A4"


def test_scale_notes():
    c_maj = get_scale_notes("C", "major", 4)
    assert c_maj == [60, 62, 64, 65, 67, 69, 71]

    a_min = get_scale_notes("A", "minor", 4)
    assert a_min[0] == 69  # A4


def test_parse_progression():
    chords = parse_progression("I-V-vi-IV", root_name="C", scale_type="major")
    assert len(chords) == 4
    # I = C major triad [60, 64, 67]
    assert chords[0] == [60, 64, 67]


def test_midi_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_mid = os.path.join(tmpdir, "test.mid")
        mf = generate_progression_midi(root="G", scale="major", progression="I-IV-V", bpm=130.0)
        mf.save(out_mid)
        assert os.path.exists(out_mid)

        loaded = MidiFile.load(out_mid)
        assert len(loaded.tracks) >= 1
        note_events = [e for e in loaded.tracks[0].events if e.type == "note_on"]
        assert len(note_events) > 0


def test_humanize_processor():
    mf = generate_progression_midi(root="C", scale="major", progression="I-V")
    original_vels = [e.velocity for e in mf.tracks[0].events if e.type == "note_on"]

    humanized = humanize(mf, timing_jitter_ticks=10, velocity_variance=15, seed=42)
    new_vels = [e.velocity for e in humanized.tracks[0].events if e.type == "note_on"]

    assert original_vels != new_vels


def test_quantize_processor():
    mf = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    # Add an off-grid note at tick 115 (close to 120, which is 1/16 at 480 tpb)
    track.events.append(MidiEvent(delta_time=115, type="note_on", note=60, velocity=80))
    mf.tracks.append(track)

    quantized = quantize(mf, grid="1/16", strength=1.0)
    # 1/16 grid at 480 tpb is 120 ticks
    assert quantized.tracks[0].events[0].delta_time == 120