"""Music theory engine: scales, chords, and Roman numeral analysis."""
from typing import List, Dict

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALE_INTERVALS = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10],
}

CHORD_FORMULAS = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "dom7": [0, 4, 7, 10],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
}


def note_to_midi(name: str, octave: int = 4) -> int:
    """Convert note name like 'C' or 'F#' and octave to MIDI pitch (60 = C4)."""
    name = name.strip().capitalize()
    if name not in NOTE_NAMES:
        raise ValueError(f"Unknown note name: {name}")
    return 12 * (octave + 1) + NOTE_NAMES.index(name)


def midi_to_note(midi_pitch: int) -> str:
    """Convert MIDI number to human-readable string like 'C4'."""
    octave = (midi_pitch // 12) - 1
    name = NOTE_NAMES[midi_pitch % 12]
    return f"{name}{octave}"


def get_scale_notes(root_name: str, scale_type: str = "major", octave: int = 4) -> List[int]:
    """Return MIDI note numbers for a given root note and scale."""
    root_pitch = note_to_midi(root_name, octave)
    scale_type = scale_type.lower().replace("-", "_")
    if scale_type not in SCALE_INTERVALS:
        raise ValueError(f"Unsupported scale type: {scale_type}")
    return [root_pitch + interval for interval in SCALE_INTERVALS[scale_type]]


ROMAN_NUMERALS_MAJOR = {
    "I": ("maj", 0),
    "ii": ("min", 1),
    "iii": ("min", 2),
    "IV": ("maj", 3),
    "V": ("maj", 4),
    "vi": ("min", 5),
    "vii°": ("dim", 6),
}

ROMAN_NUMERALS_MINOR = {
    "i": ("min", 0),
    "ii°": ("dim", 1),
    "III": ("maj", 2),
    "iv": ("min", 3),
    "v": ("min", 4),
    "VI": ("maj", 5),
    "VII": ("maj", 6),
}


def parse_progression(prog_str: str, root_name: str = "C", scale_type: str = "major", octave: int = 4) -> List[List[int]]:
    """Convert Roman numeral chord progression like 'I-V-vi-IV' into MIDI chords."""
    numerals = [n.strip() for n in prog_str.replace("–", "-").split("-")]
    scale_notes = get_scale_notes(root_name, scale_type, octave)
    is_minor = "minor" in scale_type.lower()
    table = ROMAN_NUMERALS_MINOR if is_minor else ROMAN_NUMERALS_MAJOR

    chords = []
    for num in numerals:
        if num in table:
            chord_type, degree = table[num]
            root_midi = scale_notes[degree % len(scale_notes)]
            chord_intervals = CHORD_FORMULAS[chord_type]
            chords.append([root_midi + interval for interval in chord_intervals])
        else:
            # Fallback: simple triad on scale degree
            degree = 0
            chords.append([scale_notes[0], scale_notes[2 % len(scale_notes)], scale_notes[4 % len(scale_notes)]])

    return chords