# Midi Forge - Development Roadmap

This roadmap outlines completed milestones and planned future work for **Midi Forge**. Over **30 hours** of software engineering development are scheduled across four phases.

---

## Phase 1: Core Engine & SMF Binary I/O (Completed - v0.1.0)
- [x] Pure-Python binary parser and writer for Standard MIDI Files (SMF 0 & 1).
- [x] Music theory module: note conversions, modal scales, chord formulas.
- [x] Roman numeral progression generator.
- [x] Gaussian timing and velocity humanizer.
- [x] Grid quantizer with swing support.
- [x] CLI subcommands (`generate`, `humanize`, `quantize`, `inspect`, `to-json`).
- [x] Unit test suite.

---

## Phase 1.1: MIDI Engine Stabilization (Completed - v0.1.1)
- [x] **Unambiguous Absolute-Tick Time Model**: Canonical `tick` field for all events; delta conversion only during SMF serialization/parsing.
- [x] **Hardened Parser & Chunk Bounds**: Header validation, MTrk chunk bounds checking, VLQ bounds (<= 4 bytes, <= 0x0FFFFFFF), and running status state machine.
- [x] **Channel Voice & Meta Event Coverage**: Full payload support for CC, Program Change, Channel Pressure, Poly Aftertouch, Pitch Bend, Time/Key Signature, arbitrary meta events, and SysEx.
- [x] **Deterministic FIFO Note Pairing**: Reusable `pair_notes` engine matching note-ons with note-offs, including velocity-zero note-off handling and overlapping same-pitch notes.
- [x] **Duration-Preserving Humanization & Isolated RNG**: Note duration invariant preserved across timing jitter; local `random.Random` instance avoiding global state mutation.
- [x] **Absolute Tick Quantization & Swing**: Grid quantization and swing operating on paired note onsets, enforcing positive note durations and leaving non-note events intact.
- [x] **Diatonic Modal Triads & Validation**: 7-mode diatonic triad chord generator; strict rejection of malformed tokens and unsupported Roman numeral scales (no silent fallbacks).
- [x] **Non-Destructive File Safety**: CLI `--force` guard, deterministic default filenames (`<input>_humanized.mid`, `<input>_quantized.mid`), and atomic temporary file writes.
- [x] **CI & Multi-Platform Matrix**: GitHub Actions workflow testing Ubuntu and Windows across Python 3.9, 3.10, 3.11, and 3.12.

---

## Phase 1.2: MIDI Data Integrity & Edge Cases (Completed - v0.1.2)
- [x] **Preserve SysEx Status Byte (0xF0 vs 0xF7)**: Preserve original SysEx status byte and raw payload across SMF serialization/deserialization without forcing all SysEx events to 0xF0.
- [x] **Authoritative Track Name & Meta Preservation**: `MidiTrack.name` is authoritative and automatically serialized as Track Name (`0xFF 0x03`) without duplicates; all other meta events (`0x01` text, `0x02` copyright, `0x05` lyric, etc.) retain their distinct `meta_type` and raw payload.
- [x] **Strict Pre-Serialization Validation**: Elimination of silent `& 0x7F` masking and clamping; validation of all channel, meta, file, and track parameters prior to SMF serialization.
- [x] **Race-Safe CLI No-Overwrite**: Atomic no-replace publication via hard-links (`os.link`) when `force=False`, protecting against concurrent file creation races; guaranteed temp file cleanup.
- [x] **Correct Enharmonic Octave Crossing**: Absolute pitch offset calculation handling B#4 (C5 = 72) and Cb4 (B3 = 59) across octave boundaries under `C4 = MIDI 60`.
- [x] **Strict Roman Numeral Suffixes**: Explicit grammar supporting `°` (diminished triad), `+` (augmented triad), and `7` (modal scale-stacked 4-note seventh chords); rejection of malformed suffixes (`I++`, `V77`).

---

## Phase 2: Advanced Arpeggiator & Voice Leading (~8 Hours)
- [ ] **Voice Leading Optimizer**: Implement parsimonious voice leading algorithm to minimize harmonic voice movement between chords.
- [ ] **Euclidean Rhythm Generator**: Generate Bjorklund euclidean rhythms for polyrhythmic hi-hats and percussion MIDI.
- [ ] **Pattern Arpeggiator**: Configurable arpeggiator modes (Up, Down, UpDown, Converge, Diverge, Random, Chord-Strum).
- [ ] **Scale Snapping**: Transpose any out-of-scale notes to the nearest harmonic degree.

---

## Phase 3: DAW Integration & Microtonality (~10 Hours)
- [ ] **Real-Time MIDI Routing**: Virtual MIDI port input/output loopback via `python-rtmidi`.
- [ ] **Microtonal Tuning (MTS)**: Support for MIDI Tuning Standard (SysEx) and Scala (`.scl`) tuning files for non-12-EDO scales.
- [ ] **Ableton Live Clip (.alc) Exporter**: Package MIDI tracks directly into Ableton Live clip XML formats.
- [ ] **Controller Modulation**: Algorithmic automation curves for Modulation Wheel (CC 1), Breath (CC 2), and Expression (CC 11).

---

## Phase 4: Desktop GUI & Piano Roll (~12 Hours)
- [ ] **PyQt6 / Tkinter Desktop UI**: Interactive visual piano roll interface.
- [ ] **Note Canvas**: Click-to-add, resize, and drag note events on a dynamic musical grid.
- [ ] **Real-Time Audio Preview**: Built-in simple polyphonic additive synthesizer to audition generated MIDI without launching an external DAW.
- [ ] **Drag & Drop Out**: Drag generated MIDI files directly into digital audio workstations.
