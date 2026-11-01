"""Music theory engine: scales, chords, and Roman numeral analysis."""
import re
from typing import List, Dict

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SEMITONE_MAP = {
    "C": 0, "B#": 0,
    "C#": 1, "DB": 1,
    "D": 2,
    "D#": 3, "EB": 3,
    "E": 4, "FB": 4,
    "F": 5, "E#": 5,
    "F#": 6, "GB": 6,
    "G": 7,
    "G#": 8, "AB": 8,
    "A": 9,
    "A#": 10, "BB": 10,
    "B": 11, "CB": 11,
}

SCALE_INTERVALS = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "ionian": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "aeolian": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10],
}

ROMAN_NUMERAL_DEGREE = {
    "I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5, "VII": 6,
    "i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6,
}


def note_to_midi(name: str, octave: int = 4) -> int:
    """
    Convert note name with optional sharp/flat and octave to MIDI pitch (C4 = 60).

    Supports enharmonic spellings (e.g. C#/Db, D#/Eb, F#/Gb, G#/Ab, A#/Bb).
    Raises ValueError for invalid note names or out-of-bounds MIDI pitches (0..127).
    """
    clean_name = name.strip().upper()
    if clean_name not in SEMITONE_MAP:
        raise ValueError(
            f"Invalid note name: '{name}'. Supported notes include: C, C#/Db, D, D#/Eb, E, F, F#/Gb, G, G#/Ab, A, A#/Bb, B"
        )

    semitone = SEMITONE_MAP[clean_name]
    pitch = 12 * (octave + 1) + semitone

    if not (0 <= pitch <= 127):
        raise ValueError(f"Computed MIDI pitch {pitch} for note '{name}{octave}' is out of bounds (0-127)")

    return pitch


def midi_to_note(midi_pitch: int) -> str:
    """Convert MIDI number to human-readable string like 'C4'."""
    if not (0 <= midi_pitch <= 127):
        raise ValueError(f"MIDI pitch {midi_pitch} is out of bounds (0-127)")
    octave = (midi_pitch // 12) - 1
    name = NOTE_NAMES[midi_pitch % 12]
    return f"{name}{octave}"


def get_scale_notes(root_name: str, scale_type: str = "major", octave: int = 4) -> List[int]:
    """Return MIDI note numbers for a given root note and scale."""
    root_pitch = note_to_midi(root_name, octave)
    norm_scale = scale_type.lower().replace("-", "_").strip()
    if norm_scale not in SCALE_INTERVALS:
        raise ValueError(f"Unsupported scale type: '{scale_type}'. Supported: {list(SCALE_INTERVALS.keys())}")

    scale_pitches = [root_pitch + interval for interval in SCALE_INTERVALS[norm_scale]]
    for p in scale_pitches:
        if not (0 <= p <= 127):
            raise ValueError(f"Scale pitch {p} for {root_name} {scale_type} at octave {octave} is out of bounds (0-127)")
    return scale_pitches


def parse_progression(
    prog_str: str,
    root_name: str = "C",
    scale_type: str = "major",
    octave: int = 4,
) -> List[List[int]]:
    """
    Convert Roman numeral chord progression (e.g. 'I-V-vi-IV' or 'ii-V-I') into diatonic MIDI chords.

    Diatonic triads are derived from the specified scale/mode by stacking scale thirds.
    Rejects invalid tokens and unsupported scales (such as pentatonic/blues) with informative errors.
    """
    if not prog_str or not prog_str.strip():
        raise ValueError("Progression string cannot be empty")

    norm_scale = scale_type.lower().replace("-", "_").strip()
    if norm_scale in ("pentatonic_major", "pentatonic_minor", "blues"):
        raise ValueError(
            f"Scale '{scale_type}' does not support Roman numeral diatonic progressions. "
            "Supported scales: major, minor, dorian, phrygian, lydian, mixolydian, harmonic_minor"
        )

    if norm_scale not in SCALE_INTERVALS:
        raise ValueError(f"Unsupported scale type: '{scale_type}'")

    scale_notes = get_scale_notes(root_name, scale_type, octave)
    num_scale_notes = len(scale_notes)

    # Split tokens by hyphen, en-dash, em-dash, comma or whitespace
    raw_tokens = [t.strip() for t in re.split(r"[-–—,\s]+", prog_str) if t.strip()]
    if not raw_tokens:
        raise ValueError(f"No valid chord tokens found in progression string: '{prog_str}'")

    chords = []
    for token in raw_tokens:
        # Normalize symbol: strip trailing degree decorators (° for diminished, + for augmented, 7 for 7th)
        base_roman = token.rstrip("°+7")
        if base_roman not in ROMAN_NUMERAL_DEGREE:
            raise ValueError(
                f"Unsupported Roman numeral token: '{token}'. "
                "Supported Roman numerals: I, ii, iii, IV, V, vi, vii° (and minor/modal equivalents like i, ii°, III, iv, v, VI, VII)"
            )

        degree = ROMAN_NUMERAL_DEGREE[base_roman]
        if degree >= num_scale_notes:
            raise ValueError(f"Degree {degree + 1} exceeds scale note count ({num_scale_notes})")

        # Build diatonic triad by stacking scale degrees (root, 3rd, 5th)
        root_pitch = scale_notes[degree]
        third_pitch = scale_notes[(degree + 2) % num_scale_notes] + (12 if degree + 2 >= num_scale_notes else 0)
        fifth_pitch = scale_notes[(degree + 4) % num_scale_notes] + (12 if degree + 4 >= num_scale_notes else 0)

        chord = [root_pitch, third_pitch, fifth_pitch]
        for p in chord:
            if not (0 <= p <= 127):
                raise ValueError(f"Chord pitch {p} in chord '{token}' is out of MIDI bounds (0-127)")

        chords.append(chord)

    return chords
