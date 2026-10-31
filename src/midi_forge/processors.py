"""MIDI processors: humanization, scale snapping, and swing quantization."""
import random
from typing import List, Optional
from .midi_io import MidiFile, MidiEvent


def humanize(
    midi_file: MidiFile,
    timing_jitter_ticks: int = 15,
    velocity_variance: int = 10,
    seed: Optional[int] = None,
) -> MidiFile:
    """Add subtle random human variations to note velocity and timing."""
    if seed is not None:
        random.seed(seed)

    for track in midi_file.tracks:
        for ev in track.events:
            if ev.type in ("note_on", "note_off"):
                # Add micro-timing jitter
                if timing_jitter_ticks > 0:
                    jitter = int(random.gauss(0, timing_jitter_ticks / 2.0))
                    ev.delta_time = max(0, ev.delta_time + jitter)

                # Add velocity variation on note_on
                if ev.type == "note_on" and ev.velocity > 0 and velocity_variance > 0:
                    delta_vel = int(random.gauss(0, velocity_variance / 2.0))
                    ev.velocity = max(1, min(127, ev.velocity + delta_vel))

    return midi_file


def quantize(
    midi_file: MidiFile,
    grid: str = "1/16",
    strength: float = 1.0,
    swing: float = 0.0,
) -> MidiFile:
    """Snap note events to a musical beat grid with optional swing."""
    ticks_per_beat = midi_file.ticks_per_beat

    grid_division_map = {
        "1/4": 1.0,
        "1/8": 0.5,
        "1/16": 0.25,
        "1/32": 0.125,
        "1/8T": 1.0 / 3.0,
        "1/16T": 1.0 / 6.0,
    }
    division = grid_division_map.get(grid, 0.25)
    grid_ticks = int(ticks_per_beat * division)

    if grid_ticks <= 0:
        return midi_file

    strength = max(0.0, min(1.0, strength))

    for track in midi_file.tracks:
        for ev in track.events:
            if ev.type in ("note_on", "note_off"):
                t = ev.delta_time
                grid_idx = round(t / grid_ticks)
                target_tick = grid_idx * grid_ticks

                # Apply swing to off-beats
                if swing != 0.0 and (grid_idx % 2 == 1):
                    target_tick += int(grid_ticks * 0.33 * swing)

                # Interpolate based on strength
                new_t = int(t + (target_tick - t) * strength)
                ev.delta_time = max(0, new_t)

    return midi_file