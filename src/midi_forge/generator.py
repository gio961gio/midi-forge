"""Algorithmic MIDI generators for chord progressions and arpeggios."""
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
    """Generate a Standard MIDI File from a musical chord progression."""
    mf = MidiFile(ticks_per_beat=480)
    track = MidiTrack(name=f"{root} {scale.capitalize()} - {progression}")

    # Set tempo (microseconds per beat)
    uspq = int(60000000.0 / bpm)
    track.events.append(MidiEvent(delta_time=0, type="set_tempo", tempo=uspq))

    chords = parse_progression(progression, root_name=root, scale_type=scale, octave=octave)

    current_tick = 0
    note_duration = int(ticks_per_chord * 0.95)  # slight gap between chords

    for chord_notes in chords:
        for pitch in chord_notes:
            track.add_note(
                start_tick=current_tick,
                duration_ticks=note_duration,
                note=pitch,
                velocity=velocity,
            )
        current_tick += ticks_per_chord

    track.events.append(MidiEvent(delta_time=current_tick, type="end_of_track"))
    mf.tracks.append(track)
    return mf