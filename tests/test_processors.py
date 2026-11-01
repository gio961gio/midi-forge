"""Comprehensive tests for MIDI processors: note pairing, humanization, and swing quantization."""
import random
import pytest
from midi_forge.midi_io import MidiFile, MidiTrack, MidiEvent
from midi_forge.processors import pair_notes, humanize, quantize


# =========================================================================
# 1. Note Pairing Tests
# =========================================================================

def test_pair_notes_fifo_and_vel_zero():
    """Verify FIFO pairing for overlapping same-pitch notes and velocity-zero note-offs."""
    track = MidiTrack()
    # Note A: on at 100, off at 300
    track.events.append(MidiEvent(tick=100, type="note_on", note=60, velocity=80))
    # Note B: on at 200, off at 400 (overlaps Note A on pitch 60)
    track.events.append(MidiEvent(tick=200, type="note_on", note=60, velocity=90))
    # Note-on with vel=0 ending Note A at tick 300
    track.events.append(MidiEvent(tick=300, type="note_on", note=60, velocity=0))
    # Standard Note-off ending Note B at tick 400
    track.events.append(MidiEvent(tick=400, type="note_off", note=60, velocity=0))
    # Add a CC event
    track.events.append(MidiEvent(tick=150, type="control_change", control=1, value=64))

    pairs, unpaired = pair_notes(track)
    assert len(pairs) == 2
    assert len(unpaired) == 1
    assert unpaired[0].type == "control_change"

    # Pair 0: started at 100, ended at 300
    assert pairs[0].note_on.tick == 100 and pairs[0].note_off.tick == 300
    assert pairs[0].duration == 200

    # Pair 1: started at 200, ended at 400
    assert pairs[1].note_on.tick == 200 and pairs[1].note_off.tick == 400
    assert pairs[1].duration == 200


def test_unpaired_notes_preserved():
    """Verify that orphan Note Ons or orphan Note Offs are preserved in unpaired events."""
    track = MidiTrack()
    track.events.append(MidiEvent(tick=50, type="note_off", note=60, velocity=0))  # orphan off
    track.events.append(MidiEvent(tick=100, type="note_on", note=64, velocity=80))  # orphan on

    pairs, unpaired = pair_notes(track)
    assert len(pairs) == 0
    assert len(unpaired) == 2


# =========================================================================
# 2. Humanizer Tests
# =========================================================================

def test_humanize_preserves_exact_note_duration():
    """Verify humanization applies timing jitter while preserving exact note duration."""
    mf = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    track.add_note(start_tick=100, duration_ticks=150, note=60, velocity=80)
    track.add_note(start_tick=300, duration_ticks=240, note=64, velocity=85)
    mf.tracks.append(track)

    humanized = humanize(mf, timing_jitter_ticks=20, velocity_variance=10, seed=123)
    pairs, _ = pair_notes(humanized.tracks[0])

    assert len(pairs) == 2
    # Note 1 duration must remain exactly 150
    assert pairs[0].duration == 150
    assert pairs[0].note_off.tick > pairs[0].note_on.tick

    # Note 2 duration must remain exactly 240
    assert pairs[1].duration == 240
    assert pairs[1].note_off.tick > pairs[1].note_on.tick


def test_humanize_determinism_and_isolated_random_state():
    """Verify seeded humanizer produces identical results without mutating global random."""
    # Set global random state
    random.seed(999)
    global_val_before = random.random()

    mf1 = MidiFile(ticks_per_beat=480)
    t1 = MidiTrack()
    t1.add_note(100, 100, 60, 80)
    mf1.tracks.append(t1)

    mf2 = MidiFile(ticks_per_beat=480)
    t2 = MidiTrack()
    t2.add_note(100, 100, 60, 80)
    mf2.tracks.append(t2)

    h1 = humanize(mf1, timing_jitter_ticks=15, velocity_variance=10, seed=42)
    h2 = humanize(mf2, timing_jitter_ticks=15, velocity_variance=10, seed=42)

    # Identical seed produces identical ticks and velocities
    assert h1.tracks[0].events[0].tick == h2.tracks[0].events[0].tick
    assert h1.tracks[0].events[0].velocity == h2.tracks[0].events[0].velocity

    # Reset global seed to 999 and check that next call produces global_val_before
    random.seed(999)
    assert random.random() == global_val_before


def test_humanize_velocity_clamping_and_non_note_preservation():
    """Verify velocity stays within 1..127 and non-note events (CC, tempo) are unchanged."""
    mf = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    track.events.append(MidiEvent(tick=0, type="set_tempo", tempo=500000))
    track.events.append(MidiEvent(tick=0, type="control_change", control=1, value=64))
    track.add_note(start_tick=100, duration_ticks=100, note=60, velocity=126)
    mf.tracks.append(track)

    humanized = humanize(mf, timing_jitter_ticks=10, velocity_variance=50, seed=42)
    evs = humanized.tracks[0].events

    tempo_ev = [e for e in evs if e.type == "set_tempo"][0]
    assert tempo_ev.tick == 0 and tempo_ev.tempo == 500000

    cc_ev = [e for e in evs if e.type == "control_change"][0]
    assert cc_ev.tick == 0 and cc_ev.value == 64

    note_on = [e for e in evs if e.type == "note_on" and e.velocity > 0][0]
    assert 1 <= note_on.velocity <= 127


def test_humanize_parameter_validation():
    mf = MidiFile()
    with pytest.raises(ValueError, match="timing_jitter_ticks must be non-negative"):
        humanize(mf, timing_jitter_ticks=-5)
    with pytest.raises(ValueError, match="velocity_variance must be non-negative"):
        humanize(mf, velocity_variance=-1)


# =========================================================================
# 3. Quantizer and Swing Tests
# =========================================================================

@pytest.mark.parametrize("grid_name, expected_step", [
    ("1/4", 480),
    ("1/8", 240),
    ("1/16", 120),
    ("1/32", 60),
    ("1/8T", 160),
    ("1/16T", 80),
])
def test_quantize_grids_at_full_strength(grid_name, expected_step):
    """Verify 100% strength snaps notes to the expected tick boundary for all grids."""
    mf = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    # Note slightly off-grid
    off_tick = expected_step + 15
    track.add_note(start_tick=off_tick, duration_ticks=50, note=60, velocity=80)
    mf.tracks.append(track)

    quantized = quantize(mf, grid=grid_name, strength=1.0)
    pairs, _ = pair_notes(quantized.tracks[0])

    assert pairs[0].note_on.tick == expected_step
    assert pairs[0].duration == 50


def test_quantize_strength_boundaries():
    """Verify strength=0 leaves timing intact while strength=1 snaps completely."""
    mf = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    track.add_note(start_tick=110, duration_ticks=100, note=60, velocity=80)
    mf.tracks.append(track)

    # Strength 0: no movement (tick remains 110)
    q0 = quantize(mf, grid="1/16", strength=0.0)
    assert q0.tracks[0].events[0].tick == 110

    # Strength 1: snaps to 120 (nearest 1/16 grid at 480 tpb)
    q1 = quantize(mf, grid="1/16", strength=1.0)
    assert q1.tracks[0].events[0].tick == 120


def test_quantize_swing_behavior():
    """Verify swing alters only offbeat subdivisions (odd grid index) and leaves downbeats intact."""
    mf = MidiFile(ticks_per_beat=480)
    track = MidiTrack()

    # Note 1 at downbeat tick 0 (grid index 0 - even)
    track.add_note(start_tick=0, duration_ticks=60, note=60, velocity=80)
    # Note 2 at offbeat tick 120 (grid index 1 - odd for 1/16)
    track.add_note(start_tick=120, duration_ticks=60, note=62, velocity=80)
    mf.tracks.append(track)

    # Apply 50% swing to 1/16
    q_swing = quantize(mf, grid="1/16", strength=1.0, swing=0.5)
    pairs, _ = pair_notes(q_swing.tracks[0])

    # Downbeat (even index) must not shift
    assert pairs[0].note_on.tick == 0

    # Offbeat (odd index 1) must be shifted later by swing
    expected_swing_tick = 120 + int(120 * 0.33 * 0.5)
    assert pairs[1].note_on.tick == expected_swing_tick


def test_quantize_non_note_events_remain_unchanged():
    """Verify tempo and CC events retain their original ticks and values after quantize."""
    mf = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    track.events.append(MidiEvent(tick=13, type="set_tempo", tempo=480000))
    track.events.append(MidiEvent(tick=27, type="control_change", control=64, value=127))
    track.add_note(start_tick=115, duration_ticks=100, note=60, velocity=80)
    mf.tracks.append(track)

    quantized = quantize(mf, grid="1/16", strength=1.0)
    evs = quantized.tracks[0].events

    tempo_ev = [e for e in evs if e.type == "set_tempo"][0]
    assert tempo_ev.tick == 13 and tempo_ev.tempo == 480000

    cc_ev = [e for e in evs if e.type == "control_change"][0]
    assert cc_ev.tick == 27 and cc_ev.value == 127


def test_quantize_parameter_validation():
    mf = MidiFile()
    with pytest.raises(ValueError, match="Unsupported grid"):
        quantize(mf, grid="1/64")
    with pytest.raises(ValueError, match="strength must be between 0.0 and 1.0"):
        quantize(mf, strength=1.5)
    with pytest.raises(ValueError, match="swing must be between -1.0 and 1.0"):
        quantize(mf, swing=2.0)
