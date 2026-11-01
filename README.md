# Midi Forge

[![CI](https://github.com/gio961gio/midi-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/gio961gio/midi-forge/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-64%20passed-brightgreen.svg)](tests/)

> **Algorithmic MIDI Generation, Musical Scale Quantization & Groove Humanization Engine**

Midi Forge is a lightweight, zero-dependency pure Python library and command-line tool for procedural MIDI creation, harmonic generation, and MIDI manipulation. It features a hardened Standard MIDI File (SMF 0 and 1) parser and writer using an unambiguous absolute-tick time model, full preservation of channel and meta events, race-safe non-destructive file safety, and a modal music theory engine.

---

## Key Features

- **Robust Pure-Python SMF Engine**:
  - **Unambiguous Absolute-Tick Time Model**: All events in memory use non-negative absolute tick positions (`MidiEvent.tick`). Automatic delta-to-absolute accumulation on load and sorted delta serialization on save.
  - **Full Channel Voice Support**: Consumes exact data byte payloads for Note On (including velocity-0), Note Off, Polyphonic Aftertouch, Control Change (CC), Program Change, Channel Pressure, and 14-bit Pitch Bend.
  - **SysEx Status Byte Preservation**: Preserves original SysEx status (`0xF0` vs `0xF7`) and exact byte payloads across load/save cycles, correctly supporting continuation and escape packets.
  - **Authoritative Track Name & Meta Preservation**: `MidiTrack.name` is authoritative for track name events (`0x03`). Missing track name events are synthesized at tick 0 upon save, and redundant duplicate track names are omitted. Arbitrary text/meta events (`0x01` text, `0x02` copyright, `0x05` lyric, etc.) retain their distinct `meta_type` and payloads.
  - **Strict Pre-Serialization Validation**: No silent bitmasking (`& 0x7F`) or clamping. Pre-validates channel (0-15), note/velocity/CC/program/pressure (0-127), pitch bend (0-16383), tempo (1-0xFFFFFF), PPQ (1-32767), format (0/1), and track counts, raising an informative `ValueError` on invalid in-memory data.
  - **Running Status & Boundary Validation**: Handles standard running status correctly, clearing it upon encountering meta or SysEx events. Bounds checks every chunk (`MThd`, `MTrk`), rejecting truncated files, unsupported formats (Format 2), or malformed Variable-Length Quantities (VLQs > 4 bytes or > `0x0FFFFFFF`).
  - **PPQ Timing**: Supports standard pulses-per-quarter-note (PPQ) divisions. (SMPTE timecode divisions are explicitly rejected).
  - **Deterministic Same-Tick Ordering**: Safe ordering for simultaneous events (meta first, note-offs before retriggered note-ons, end-of-track last).
- **Deterministic Note Pairing & Processors**:
  - **FIFO Note Pairing**: Reusable note-pairing engine matching Note On and Note Off by `(channel, pitch)`, correctly handling overlapping notes and velocity-zero note-offs.
  - **Duration-Preserving Humanization**: Applies timing jitter to note onsets and offsets simultaneously so that original note duration is never altered. Jitter and velocity variances are parameterized and use isolated random state (`random.Random(seed)`), avoiding global state mutation.
  - **Swing & Quantization**: Snaps note onsets in absolute ticks to standard musical grids (`1/4`, `1/8`, `1/16`, `1/32`, `1/8T`, `1/16T`) with strength interpolation and MPC-style swing applied to offbeat subdivisions. Enforces positive minimum note durations.
- **Harmonic Music Theory & Generator**:
  - **Enharmonic Spelling & Octave Crossing**: Case-insensitive note parsing with natural note offsets before boundary checking. Correctly handles octave crossings (`B#4 == C5 == 72`, `Cb4 == B3 == 59`, `E#4 == F4 == 65`, `Fb4 == E4 == 64`) under the documented `C4 = MIDI 60` convention.
  - **Strict Roman Numeral Suffix Parsing**: Explicit grammar supporting `°` (diminished triad: root, +3, +6), `+` (augmented triad: root, +4, +8), and `7` (diatonic 4-note seventh chord stacked from scale thirds) without character stripping. Rejects malformed tokens (`I++`, `V77`) with clear errors.
  - **Diatonic Modal Triads**: Generates chord progressions from Roman numeral notation (`I-V-vi-IV`, `ii-V-I`, `i-VI-III-VII`) by stacking scale degrees across the 7 diatonic modes (Major, Natural Minor, Dorian, Phrygian, Lydian, Mixolydian, Harmonic Minor). Rejects invalid tokens without silent fallbacks.
- **Race-Safe Non-Destructive File Safety**:
  - CLI operations never overwrite existing destination files by default.
  - Default humanize and quantize outputs write to `<input>_humanized.mid` and `<input>_quantized.mid`.
  - Destination publication uses atomic exclusive operations (`os.link` without replace on no-force path) to protect against concurrent file creation races.
  - Explicit `--force` flag is required to replace existing destinations (using atomic `os.replace`).
  - Temporary files are guaranteed to be cleaned up on all error paths.

---

## Project Structure

```
midi-forge/
├── src/
│   └── midi_forge/
│       ├── __init__.py        # Package metadata & exports
│       ├── midi_io.py         # Pure-Python SMF parser & writer (absolute tick model, validation)
│       ├── theory.py          # Scales, chord formulas, strict Roman numeral parser
│       ├── generator.py       # Algorithmic chord progression generator
│       ├── processors.py      # FIFO note pairing, humanizer, swing quantizer
│       └── cli.py             # CLI with race-safe non-destructive file safety
├── tests/
│   ├── test_midi_io.py        # VLQ, header bounds, running status, SysEx, validation, SMF roundtrip
│   ├── test_processors.py     # Note pairing, humanization, swing quantization
│   ├── test_theory.py         # Enharmonics, octave crossing, chord suffixes, diatonic modes
│   ├── test_cli.py            # Non-destructive CLI safety, race conditions & default outputs
│   └── test_midi_forge.py     # High-level integration tests
├── .github/
│   └── workflows/ci.yml       # GitHub Actions CI (Ubuntu & Windows, Python 3.9-3.12)
├── pyproject.toml             # Build configuration & optional test dependencies
├── requirements.txt           # Test dependencies
├── ROADMAP.md                 # Development roadmap
└── LICENSE                    # MIT License
```

---

## Installation

```bash
git clone https://github.com/gio961gio/midi-forge.git
cd midi-forge
pip install -e .
```

To install test dependencies:
```bash
pip install -e .[test]
```

---

## CLI Usage

### 1. Generate a chord progression
```bash
midi-forge generate --root C --scale major --progression I-V-vi-IV --bpm 124 --out progression.mid
```
To overwrite an existing destination file, supply `--force`:
```bash
midi-forge generate --root D --scale dorian --progression i-IV --out progression.mid --force
```

### 2. Humanize a MIDI file safely
```bash
# Writes to input_humanized.mid by default
midi-forge humanize input.mid --timing 12 --velocity 10

# Or specify a custom output path:
midi-forge humanize input.mid --out output.mid --timing 12 --velocity 10
```

### 3. Quantize with swing
```bash
# Writes to input_quantized.mid by default
midi-forge quantize input.mid --grid 1/16 --strength 0.85 --swing 0.25
```

### 4. Inspect MIDI file metadata
```bash
midi-forge inspect progression.mid
```

### 5. Export to JSON
```bash
midi-forge to-json progression.mid --out events.json
```

---

## Running Tests

Run the full automated test suite with pytest (64 collected test items):
```bash
pytest -v
```

---

## License

This project is licensed under the [MIT License](LICENSE).
