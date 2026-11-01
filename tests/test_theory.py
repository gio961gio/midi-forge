"""Comprehensive tests for Music Theory engine and Progression Generator."""
import pytest
from midi_forge.theory import (
    note_to_midi,
    midi_to_note,
    get_scale_notes,
    parse_progression,
)
from midi_forge.generator import generate_progression_midi


# =========================================================================
# 1. Note Conversion and Enharmonics
# =========================================================================

def test_note_enharmonics_and_casing():
    """Verify standard notes and enharmonic flat/sharp pairs across different casing."""
    assert note_to_midi("C", 4) == 60
    assert note_to_midi("A", 4) == 69

    # Enharmonic equivalents (case-insensitive)
    assert note_to_midi("C#", 4) == note_to_midi("Db", 4) == 61
    assert note_to_midi("c#", 4) == note_to_midi("db", 4) == 61
    assert note_to_midi("D#", 4) == note_to_midi("Eb", 4) == 63
    assert note_to_midi("F#", 4) == note_to_midi("Gb", 4) == 66
    assert note_to_midi("G#", 4) == note_to_midi("Ab", 4) == 68
    assert note_to_midi("A#", 4) == note_to_midi("Bb", 4) == 70
    assert note_to_midi("bb", 4) == 70


def test_note_and_midi_pitch_bounds():
    """Verify invalid notes and out-of-bounds MIDI octaves raise ValueError."""
    with pytest.raises(ValueError, match="Invalid note name"):
        note_to_midi("H", 4)
    with pytest.raises(ValueError, match="Invalid note name"):
        note_to_midi("Z#", 4)

    # Octave bounds: pitch < 0 or > 127
    with pytest.raises(ValueError, match="out of bounds"):
        note_to_midi("C", -2)  # 12 * (-1) = -12
    with pytest.raises(ValueError, match="out of bounds"):
        note_to_midi("G#", 9)  # 12 * 10 + 8 = 128
    with pytest.raises(ValueError, match="out of bounds"):
        note_to_midi("C", 10)  # 12 * 11 = 132

    # midi_to_note bounds
    assert midi_to_note(60) == "C4"
    with pytest.raises(ValueError, match="out of bounds"):
        midi_to_note(-1)
    with pytest.raises(ValueError, match="out of bounds"):
        midi_to_note(128)


# =========================================================================
# 2. Scale Degrees and Diatonic Modes
# =========================================================================

def test_seven_diatonic_modes_triads():
    """
    Verify diatonic triad chord qualities across the seven advertised 7-note scales:
    Major, Natural Minor, Dorian, Phrygian, Lydian, Mixolydian, and Harmonic Minor.
    """
    # 1. C Major (I=Cmaj, ii=Dmin, V=Gmaj, vi=Amin, vii°=Bdim)
    c_maj_prog = parse_progression("I-ii-V-vi-vii°", root_name="C", scale_type="major", octave=4)
    assert c_maj_prog[0] == [60, 64, 67]  # C Major [C, E, G]
    assert c_maj_prog[1] == [62, 65, 69]  # D Minor [D, F, A]
    assert c_maj_prog[2] == [67, 71, 74]  # G Major [G, B, D]
    assert c_maj_prog[3] == [69, 72, 76]  # A Minor [A, C, E]
    assert c_maj_prog[4] == [71, 74, 77]  # B Diminished [B, D, F]

    # 2. A Natural Minor (i=Amin, ii°=Bdim, III=Cmaj, iv=Dmin, v=Emin, VI=Fmaj, VII=Gmaj)
    a_min_prog = parse_progression("i-ii°-III-iv-v-VI-VII", root_name="A", scale_type="minor", octave=4)
    assert a_min_prog[0] == [69, 72, 76]  # A Minor [A, C, E]
    assert a_min_prog[1] == [71, 74, 77]  # B Diminished [B, D, F]
    assert a_min_prog[2] == [72, 76, 79]  # C Major [C, E, G]
    assert a_min_prog[3] == [74, 77, 81]  # D Minor [D, F, A]
    assert a_min_prog[4] == [76, 79, 83]  # E Minor [E, G, B]
    assert a_min_prog[5] == [77, 81, 84]  # F Major [F, A, C]
    assert a_min_prog[6] == [79, 83, 86]  # G Major [G, B, D]

    # 3. D Dorian (i=Dmin, IV=Gmaj) - characteristic major IV in Dorian
    d_dorian = parse_progression("i-IV", root_name="D", scale_type="dorian", octave=4)
    assert d_dorian[0] == [62, 65, 69]  # D Minor
    assert d_dorian[1] == [67, 71, 74]  # G Major (Dorian raised 6th B creates G-B-D!)

    # 4. G Mixolydian (I=Gmaj, VII=Fmaj) - characteristic flat VII in Mixolydian
    g_mixo = parse_progression("I-VII", root_name="G", scale_type="mixolydian", octave=4)
    assert g_mixo[0] == [67, 71, 74]  # G Major [G4, B4, D5]
    assert g_mixo[1] == [77, 81, 84]  # F Major [F5, A5, C6]

    # 5. A Harmonic Minor (V=Emaj, vii°=G#dim) - raised 7th (G#) creates major V
    a_harm = parse_progression("i-V-vii°", root_name="A", scale_type="harmonic_minor", octave=4)
    assert a_harm[0] == [69, 72, 76]  # A Minor
    assert a_harm[1] == [76, 80, 83]  # E Major [E, G#, B]
    assert a_harm[2] == [80, 83, 86]  # G# Diminished [G#, B, D]


def test_rejection_of_invalid_tokens_and_unsupported_scales():
    """Verify that invalid Roman numerals or non-diatonic scales raise ValueError."""
    # Invalid token must not silently fall back to tonic!
    with pytest.raises(ValueError, match="Unsupported Roman numeral token"):
        parse_progression("I-V-INVALID-IV", root_name="C", scale_type="major")

    with pytest.raises(ValueError, match="Progression string cannot be empty"):
        parse_progression("", root_name="C")

    # Pentatonic and blues scales do not support diatonic Roman numeral progressions
    with pytest.raises(ValueError, match="does not support Roman numeral diatonic progressions"):
        parse_progression("I-IV-V", root_name="C", scale_type="pentatonic_major")

    with pytest.raises(ValueError, match="does not support Roman numeral diatonic progressions"):
        parse_progression("I-IV-V", root_name="A", scale_type="blues")


# =========================================================================
# 3. Generator Validation Tests
# =========================================================================

def test_generator_parameter_validation():
    """Verify generator validates BPM, ticks_per_chord, and velocity."""
    with pytest.raises(ValueError, match="BPM must be a finite positive number"):
        generate_progression_midi(bpm=-120.0)

    with pytest.raises(ValueError, match="BPM must be a finite positive number"):
        generate_progression_midi(bpm=float("inf"))

    with pytest.raises(ValueError, match="ticks_per_chord must be a positive integer"):
        generate_progression_midi(ticks_per_chord=0)

    with pytest.raises(ValueError, match="velocity must be in range 1..127"):
        generate_progression_midi(velocity=0)

    with pytest.raises(ValueError, match="velocity must be in range 1..127"):
        generate_progression_midi(velocity=128)


# =========================================================================
# 4. Enharmonic Octave Handling (B#, Cb, E#, Fb)
# =========================================================================

def test_enharmonic_octave_crossing():
    """Verify B# and Cb correctly cross octave boundaries under C4=60 convention."""
    # B#4 must be C5 (72), Cb4 must be B3 (59)
    assert note_to_midi("B#", 4) == 72
    assert note_to_midi("b#", 4) == 72
    assert note_to_midi("Cb", 4) == 59
    assert note_to_midi("cb", 4) == 59
    assert note_to_midi("CB", 4) == 59

    # E#4 and Fb4 within same octave
    assert note_to_midi("E#", 4) == note_to_midi("F", 4) == 65
    assert note_to_midi("e#", 4) == note_to_midi("f", 4) == 65
    assert note_to_midi("Fb", 4) == note_to_midi("E", 4) == 64
    assert note_to_midi("fb", 4) == note_to_midi("e", 4) == 64

    # Boundary tests: pitch calculation before bounds check
    assert note_to_midi("C", -1) == 0
    assert note_to_midi("B#", -1) == 12  # C0
    assert note_to_midi("Cb", 0) == 11   # B-1
    assert note_to_midi("G", 9) == 127

    # Reject only when final computed pitch is outside 0..127
    with pytest.raises(ValueError, match="out of bounds"):
        note_to_midi("Cb", -1)  # pitch = -1

    with pytest.raises(ValueError, match="out of bounds"):
        note_to_midi("G#", 9)  # pitch = 128

    with pytest.raises(ValueError, match="out of bounds"):
        note_to_midi("B#", 9)  # pitch = 132


# =========================================================================
# 5. Roman Numeral Chord Quality and Suffix Tests
# =========================================================================

def test_roman_numeral_suffixes_augmented_diminished_and_seventh():
    """Verify °, +, and 7 suffixes produce exact musical voicings without character stripping."""
    # 1. Augmented triad (root, root + 4, root + 8)
    c_aug = parse_progression("I+", root_name="C", scale_type="major", octave=4)
    assert len(c_aug) == 1
    assert c_aug[0] == [60, 64, 68]  # C, E, G#

    # 2. Dominant 7th in C Major (V7 = G-B-D-F: 4-note voicing)
    c_v7 = parse_progression("V7", root_name="C", scale_type="major", octave=4)
    assert len(c_v7) == 1
    assert c_v7[0] == [67, 71, 74, 77]  # G4, B4, D5, F5

    # 3. Diminished triad (vii° in C Major = B-D-F)
    c_vii_dim = parse_progression("vii°", root_name="C", scale_type="major", octave=4)
    assert len(c_vii_dim) == 1
    assert c_vii_dim[0] == [71, 74, 77]  # B4, D5, F5

    # 4. Modal 7th chord (stacked from scale degrees, not hard-coded major/minor)
    # In D Dorian: i7 is Dm7 [D4, F4, A4, C5]
    d_dorian_i7 = parse_progression("i7", root_name="D", scale_type="dorian", octave=4)
    assert d_dorian_i7[0] == [62, 65, 69, 72]

    # In D Dorian: IV7 is G7 [G4, B4, D5, F5] (characteristic major IV with minor 7th)
    d_dorian_iv7 = parse_progression("IV7", root_name="D", scale_type="dorian", octave=4)
    assert d_dorian_iv7[0] == [67, 71, 74, 77]

    # 5. Ordinary progressions retain their exact triads
    prog_ord = parse_progression("I-V-vi-IV", root_name="C", scale_type="major", octave=4)
    assert prog_ord == [
        [60, 64, 67],  # C
        [67, 71, 74],  # G
        [69, 72, 76],  # Am
        [65, 69, 72],  # F
    ]


def test_roman_numeral_malformed_suffixes_rejected():
    """Verify that malformed suffixes and unsupported token syntax raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported Roman numeral token"):
        parse_progression("I++", root_name="C")

    with pytest.raises(ValueError, match="Unsupported Roman numeral token"):
        parse_progression("V77", root_name="C")

    with pytest.raises(ValueError, match="Unsupported Roman numeral token"):
        parse_progression("vii°°", root_name="C")

    with pytest.raises(ValueError, match="Unsupported Roman numeral token"):
        parse_progression("Imaj7", root_name="C")

    with pytest.raises(ValueError, match="Unsupported Roman numeral token"):
        parse_progression("I+7", root_name="C")

    with pytest.raises(ValueError, match="Unsupported Roman numeral token"):
        parse_progression("I_foo", root_name="C")
