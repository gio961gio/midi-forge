# Midi Forge

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

> **Algorithmic MIDI Generation, Musical Scale Quantization & Groove Humanization Engine**

Midi Forge is a lightweight, zero-dependency Python library and CLI tool for procedural MIDI creation and manipulation. It provides a pure-Python binary parser and writer for Standard MIDI Files (SMF 0 and 1), a music theory engine for scales and harmonic progressions, groove humanization, and musical grid quantization.

---

## Key Features

- **Zero-Dependency SMF Engine**: Native binary parser and writer for Standard MIDI Files (Format 0 and 1) handling Variable-Length Quantities (VLQ), delta times, note on/off, tempo meta events, and track naming without external binary dependencies.
- **Harmonic Music Theory**: Generates chord progressions from Roman numeral notation (`I-V-vi-IV`, `ii-V-I`, `i-VI-III-VII`) across musical scales (Major, Minor, Dorian, Phrygian, Lydian, Mixolydian, Harmonic Minor, Pentatonic, Blues).
- **Groove Humanization**: Simulates natural human performance feel by adding micro-timing jitter and velocity variances using Gaussian probability distributions.
- **Swing & Quantization**: Snaps MIDI notes to configurable musical grids (1/4, 1/8, 1/16, 1/32, triplets) with customizable snap strength and MPC-style swing offsets.
- **JSON Serialization**: Inspects and serializes MIDI event streams into structured JSON format for web integration, analysis, or machine learning pipelines.

---

## Project Structure

```
midi-forge/
├── src/
│   └── midi_forge/
│       ├── __init__.py        # Package metadata & exports
│       ├── midi_io.py         # Pure-Python SMF binary parser & writer
│       ├── theory.py          # Scales, chord formulas, Roman numeral parser
│       ├── generator.py       # Algorithmic chord progression generator
│       ├── processors.py      # Humanizer, swing quantizer, transposer
│       └── cli.py             # Rich CLI subcommands
├── tests/
│   └── test_midi_forge.py     # Unit test suite
├── pyproject.toml             # Build configuration
├── requirements.txt           # Test requirements
├── ROADMAP.md                 # 30+ hours of planned development
└── LICENSE                    # MIT License
```

---

## Installation

```bash
git clone https://github.com/gio961gio/midi-forge.git
cd midi-forge
pip install -e .
```

---

## CLI Usage

### 1. Generate a chord progression
```bash
midi-forge generate --root C --scale major --progression I-V-vi-IV --bpm 124 --out progression.mid
```

### 2. Humanize a rigid MIDI file
```bash
midi-forge humanize input.mid --timing 12 --velocity 10 --out humanized.mid
```

### 3. Quantize with swing
```bash
midi-forge quantize input.mid --grid 1/16 --strength 0.85 --swing 0.25 --out swinging.mid
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

```bash
pytest tests/ -v
```

---

## License

This project is licensed under the [MIT License](LICENSE).