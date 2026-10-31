# Midi Forge - Development Roadmap

This roadmap outlines planned future work for **Midi Forge**. Over **30 hours** of software engineering development are scheduled across four phases.

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