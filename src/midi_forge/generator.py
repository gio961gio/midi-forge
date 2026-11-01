"""Algorithmic MIDI generators for chord progressions and arpeggios."""
import math
from typing import List, Optional
from .midi_io import MidiFile, MidiTrack, MidiEvent
from .theory import parse_progression


def generate_progression_midi(
    root: str = "C",
    scale: str = "major",
    progression: str = "I-V-vi-IV",
    bpm: float = 120.0,
    ticks_per_chord: int = 1920,  # 1 bar in 4/4 at 480 ticks/beat
    octave: int = 4,
    velocity: int = 85,
) -> MidiFile:
    """
    Generate a Standard MIDI File from a musical chord progression.

    Validates musical and timing parameters strictly before generation.
    """
    if not isinstance(bpm, (int, float)) or not math.isfinite(bpm) or bpm <= 0:
        raise ValueError(f"BPM must be a finite positive number, got: {bpm}")

    uspq = int(round(60000000.0 / bpm))
    if not (1 <= uspq <= 0xFFFFFF):
        raise ValueError(f"Tempo value {uspq} us/beat derived from BPM {bpm} exceeds 24-bit MIDI limit (1..16777215)")

    if not isinstance(ticks_per_chord, int) or ticks_per_chord <= 0:
        raise ValueError(f"ticks_per_chord must be a positive integer, got: {ticks_per_chord}")

    if not (1 <= velocity <= 127):
        raise ValueError(f"velocity must be in range 1..127, got: {velocity}")

    mf = MidiFile(ticks_per_beat=480)
    track = MidiTrack(name=f"{root} {scale.capitalize()} - {progression}")

    # Set tempo event at tick 0
    track.events.append(MidiEvent(tick=0, type="set_tempo", tempo=uspq))

    chords = parse_progression(progression, root_name=root, scale_type=scale, octave=octave)

    current_tick = 0
    note_duration = max(1, int(ticks_per_chord * 0.95))

    for chord_notes in chords:
        for pitch in chord_notes:
            track.add_note(
                start_tick=current_tick,
                duration_ticks=note_duration,
                note=pitch,
                velocity=velocity,
            )
        current_tick += ticks_per_chord

    track.events.append(MidiEvent(tick=current_tick, type="end_of_track"))
    mf.tracks.append(track)
    return mf
