"""Midi Forge: Algorithmic MIDI processing, groove humanization, and scale quantization."""
from .midi_io import MidiFile, MidiTrack, MidiEvent, read_vlq, write_vlq
from .processors import humanize, quantize, pair_notes
from .theory import note_to_midi, midi_to_note, get_scale_notes, parse_progression
from .generator import generate_progression_midi

__version__ = "0.1.1"

__all__ = [
    "MidiFile",
    "MidiTrack",
    "MidiEvent",
    "read_vlq",
    "write_vlq",
    "humanize",
    "quantize",
    "pair_notes",
    "note_to_midi",
    "midi_to_note",
    "get_scale_notes",
    "parse_progression",
    "generate_progression_midi",
]
