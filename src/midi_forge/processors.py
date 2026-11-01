"""MIDI processors: humanization, note pairing, and swing quantization."""
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from .midi_io import MidiFile, MidiTrack, MidiEvent, EVENT_PRIORITY


@dataclass
class NotePair:
    """Paired Note-On and Note-Off events representing a single musical note."""
    note_on: MidiEvent
    note_off: MidiEvent

    @property
    def duration(self) -> int:
        return self.note_off.tick - self.note_on.tick


def pair_notes(track: MidiTrack) -> Tuple[List[NotePair], List[MidiEvent]]:
    """
    Pair Note On and matching Note Off events deterministically using FIFO order.

    - Matches on (channel, pitch).
    - Treats Note On with velocity 0 as Note Off.
    - Preserves overlapping notes of identical pitch on the same channel.
    - Leaves unpaired notes and non-note events intact in the unpaired list.

    Returns
    -------
    (paired_notes, unpaired_events) : Tuple[List[NotePair], List[MidiEvent]]
    """
    pairs: List[NotePair] = []
    active_notes: Dict[Tuple[int, int], List[MidiEvent]] = {}
    unpaired: List[MidiEvent] = []

    for ev in track.events:
        if ev.type == "note_on" and ev.velocity > 0:
            key = (ev.channel, ev.note)
            active_notes.setdefault(key, []).append(ev)
        elif ev.type == "note_off" or (ev.type == "note_on" and ev.velocity == 0):
            key = (ev.channel, ev.note)
            queue = active_notes.get(key, [])
            if queue:
                matching_on = queue.pop(0)
                pairs.append(NotePair(note_on=matching_on, note_off=ev))
            else:
                unpaired.append(ev)
        else:
            unpaired.append(ev)

    # Any remaining unclosed Note Ons are preserved in unpaired
    for queue in active_notes.values():
        unpaired.extend(queue)

    return pairs, unpaired


def humanize(
    midi_file: MidiFile,
    timing_jitter_ticks: int = 15,
    velocity_variance: int = 10,
    seed: Optional[int] = None,
) -> MidiFile:
    """
    Add subtle human variations to note timing and velocity while strictly preserving note durations.

    Uses a local random instance to prevent mutating global random state.
    """
    if timing_jitter_ticks < 0:
        raise ValueError(f"timing_jitter_ticks must be non-negative, got: {timing_jitter_ticks}")
    if velocity_variance < 0:
        raise ValueError(f"velocity_variance must be non-negative, got: {velocity_variance}")

    rng = random.Random(seed)

    for track in midi_file.tracks:
        pairs, unpaired = pair_notes(track)

        for pair in pairs:
            orig_duration = max(1, pair.duration)

            # Apply timing jitter to the entire note, preserving its exact duration
            if timing_jitter_ticks > 0:
                jitter = int(rng.gauss(0, timing_jitter_ticks / 2.0))
                new_start = max(0, pair.note_on.tick + jitter)
                pair.note_on.tick = new_start
                pair.note_off.tick = new_start + orig_duration

            # Apply velocity variance only to Note On (clamped to 1..127)
            if velocity_variance > 0 and pair.note_on.velocity > 0:
                vel_delta = int(rng.gauss(0, velocity_variance / 2.0))
                pair.note_on.velocity = max(1, min(127, pair.note_on.velocity + vel_delta))

        # Rebuild and sort track events deterministically
        all_events = []
        for pair in pairs:
            all_events.append(pair.note_on)
            all_events.append(pair.note_off)
        all_events.extend(unpaired)

        all_events.sort(key=lambda e: (e.tick, EVENT_PRIORITY.get(e.type, 50)))
        track.events = all_events

    return midi_file


def quantize(
    midi_file: MidiFile,
    grid: str = "1/16",
    strength: float = 1.0,
    swing: float = 0.0,
) -> MidiFile:
    """
    Snap note onsets to a musical beat grid with optional swing in absolute ticks.

    Preserves note duration and leaves non-note events intact.
    """
    grid_division_map = {
        "1/4": 1.0,
        "1/8": 0.5,
        "1/16": 0.25,
        "1/32": 0.125,
        "1/8T": 1.0 / 3.0,
        "1/16T": 1.0 / 6.0,
    }

    if grid not in grid_division_map:
        raise ValueError(
            f"Unsupported grid '{grid}'. Supported grids: {list(grid_division_map.keys())}"
        )

    if not (0.0 <= strength <= 1.0):
        raise ValueError(f"strength must be between 0.0 and 1.0, got: {strength}")

    if not (-1.0 <= swing <= 1.0):
        raise ValueError(f"swing must be between -1.0 and 1.0, got: {swing}")

    ticks_per_beat = midi_file.ticks_per_beat
    division = grid_division_map[grid]
    grid_ticks = int(ticks_per_beat * division)

    if grid_ticks <= 0:
        return midi_file

    for track in midi_file.tracks:
        pairs, unpaired = pair_notes(track)

        for pair in pairs:
            t = pair.note_on.tick
            orig_duration = max(1, pair.duration)

            grid_idx = round(t / grid_ticks)
            target_tick = grid_idx * grid_ticks

            # Apply swing to offbeat subdivisions (odd grid index)
            if swing != 0.0 and (grid_idx % 2 == 1):
                target_tick += int(grid_ticks * 0.33 * swing)

            # Interpolate based on strength
            new_start = max(0, int(t + (target_tick - t) * strength))
            pair.note_on.tick = new_start
            pair.note_off.tick = max(new_start + 1, new_start + orig_duration)

        all_events = []
        for pair in pairs:
            all_events.append(pair.note_on)
            all_events.append(pair.note_off)
        all_events.extend(unpaired)

        all_events.sort(key=lambda e: (e.tick, EVENT_PRIORITY.get(e.type, 50)))
        track.events = all_events

    return midi_file
