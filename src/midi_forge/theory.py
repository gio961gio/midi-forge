"""Music theory engine: scales, chords, and Roman numeral analysis."""
import re
from typing import List, Dict

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

BASE_NOTE_SEMITONES: Dict[str, int] = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
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

CHORD_TOKEN_REGEX = re.compile(r"^([IVXivx]+)([°+7])?$")


def note_to_midi(name: str, octave: int = 4) -> int:
    """
    Convert note name with optional sharp/flat and octave to MIDI pitch (C4 = 60).

    Supports enharmonic spellings (e.g. B#4 = C5 = 72, Cb4 = B3 = 59, E#4 = F4 = 65, Fb4 = E4 = 64).
    Calculates absolute pitch with accidental offsets before bounds checking to correctly handle
    enharmonic octave crossings.
    Raises ValueError for invalid note names or out-of-bounds MIDI pitches (0..127).
    """
    if not isinstance(octave, int) or isinstance(octave, bool):
        raise ValueError(f"Octave must be an integer, got: {octave!r}")

    clean = name.strip()
    if not clean:
        raise ValueError("Note name cannot be empty")

    letter = clean[0].upper()
    if letter not in BASE_NOTE_SEMITONES:
        raise ValueError(
            f"Invalid note name: '{name}'. Supported base letters: A, B, C, D, E, F, G"
        )

    accidental_str = clean[1:].strip().lower()
    if accidental_str in ("",):
        acc_offset = 0
    elif accidental_str in ("#", "sharp"):
        acc_offset = 1
    elif accidental_str in ("b", "flat"):
        acc_offset = -1
    else:
        raise ValueError(
            f"Invalid accidental '{clean[1:]}' in note name '{name}'. Supported: '', '#', 'b'"
        )

    pitch = 12 * (octave + 1) + BASE_NOTE_SEMITONES[letter] + acc_offset

    if not (0 <= pitch <= 127):
        raise ValueError(f"Computed MIDI pitch {pitch} for note '{name}{octave}' is out of bounds (0-127)")

    return pitch


def midi_to_note(midi_pitch: int) -> str:
    """Convert MIDI number to human-readable string like 'C4'."""
    if not isinstance(midi_pitch, int) or isinstance(midi_pitch, bool) or not (0 <= midi_pitch <= 127):
        raise ValueError(f"MIDI pitch {midi_pitch!r} is out of bounds (0-127)")
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

    Supports documented quality and extension suffixes:
    - '°': diminished triad (root, minor third +3, diminished fifth +6)
    - '+': augmented triad (root, major third +4, augmented fifth +8)
    - '7': diatonic seventh chord stacked in scale thirds (root, 3rd, 5th, 7th) from the selected scale/mode
    - (no suffix): diatonic triad (root, 3rd, 5th) stacked from the selected scale/mode

    Rejects malformed suffixes (e.g. 'I++', 'V77') and unsupported scales with informative errors.
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
        match = CHORD_TOKEN_REGEX.fullmatch(token)
        if not match:
            raise ValueError(
                f"Unsupported Roman numeral token: '{token}'. "
                "Tokens must consist of a Roman numeral (I..VII, i..vii) optionally followed by '°', '+', or '7'."
            )

        base_roman, suffix = match.groups()
        if base_roman not in ROMAN_NUMERAL_DEGREE:
            raise ValueError(
                f"Unsupported Roman numeral token: '{token}'. "
                "Supported Roman numerals: I, ii, iii, IV, V, vi, vii° (and minor/modal equivalents like i, ii°, III, iv, v, VI, VII)"
            )

        degree = ROMAN_NUMERAL_DEGREE[base_roman]
        if degree >= num_scale_notes:
            raise ValueError(f"Degree {degree + 1} exceeds scale note count ({num_scale_notes})")

        root_pitch = scale_notes[degree]

        def _get_scale_degree_pitch(degree_idx: int, step_offset: int) -> int:
            idx = degree_idx + step_offset
            octave_shift = (idx // num_scale_notes) * 12
            note_idx = idx % num_scale_notes
            return scale_notes[note_idx] + octave_shift

        if suffix == "°":
            # Diminished triad: root, minor third (+3), diminished fifth (+6)
            chord = [root_pitch, root_pitch + 3, root_pitch + 6]
        elif suffix == "+":
            # Augmented triad: root, major third (+4), augmented fifth (+8)
            chord = [root_pitch, root_pitch + 4, root_pitch + 8]
        elif suffix == "7":
            # Diatonic 7th chord stacked in scale thirds
            chord = [
                _get_scale_degree_pitch(degree, 0),
                _get_scale_degree_pitch(degree, 2),
                _get_scale_degree_pitch(degree, 4),
                _get_scale_degree_pitch(degree, 6),
            ]
        else:
            # Diatonic triad stacked in scale thirds
            chord = [
                _get_scale_degree_pitch(degree, 0),
                _get_scale_degree_pitch(degree, 2),
                _get_scale_degree_pitch(degree, 4),
            ]

        for p in chord:
            if not (0 <= p <= 127):
                raise ValueError(f"Chord pitch {p} in chord '{token}' is out of MIDI bounds (0-127)")

        chords.append(chord)

    return chords
