"""Command-line interface for Midi Forge."""
import os
import sys
import json
import argparse
from .midi_io import MidiFile
from .generator import generate_progression_midi
from .processors import humanize, quantize


def handle_generate(args: argparse.Namespace):
    """Generate MIDI file from chord progression."""
    print(f"\nGenerating progression: {args.progression} ({args.root} {args.scale}) at {args.bpm} BPM...")
    mf = generate_progression_midi(
        root=args.root,
        scale=args.scale,
        progression=args.progression,
        bpm=args.bpm,
    )
    if args.humanize:
        mf = humanize(mf, timing_jitter_ticks=12, velocity_variance=8)

    mf.save(args.out)
    print(f"[Success] Saved MIDI to {args.out}\n")


def handle_humanize(args: argparse.Namespace):
    """Add human timing and velocity drift."""
    if not os.path.exists(args.file):
        print(f"[Error] File not found: {args.file}")
        sys.exit(1)

    mf = MidiFile.load(args.file)
    mf = humanize(mf, timing_jitter_ticks=args.timing, velocity_variance=args.velocity)
    out_path = args.out or args.file
    mf.save(out_path)
    print(f"[Success] Humanized MIDI saved to {out_path}\n")


def handle_quantize(args: argparse.Namespace):
    """Quantize notes to musical grid."""
    if not os.path.exists(args.file):
        print(f"[Error] File not found: {args.file}")
        sys.exit(1)

    mf = MidiFile.load(args.file)
    mf = quantize(mf, grid=args.grid, strength=args.strength, swing=args.swing)
    out_path = args.out or args.file
    mf.save(out_path)
    print(f"[Success] Quantized ({args.grid}, str={args.strength}) saved to {out_path}\n")


def handle_inspect(args: argparse.Namespace):
    """Inspect MIDI file metadata and track events."""
    if not os.path.exists(args.file):
        print(f"[Error] File not found: {args.file}")
        sys.exit(1)

    mf = MidiFile.load(args.file)
    print(f"\n--- MIDI Inspection: {os.path.basename(args.file)} ---")
    print(f"  Format:          {mf.format_type}")
    print(f"  Ticks Per Beat:  {mf.ticks_per_beat}")
    print(f"  Tracks:          {len(mf.tracks)}")

    for i, track in enumerate(mf.tracks):
        note_ons = sum(1 for e in track.events if e.type == "note_on")
        tempos = [e.bpm for e in track.events if e.type == "set_tempo"]
        bpm_str = f"{tempos[0]} BPM" if tempos else "120.0 BPM (default)"
        print(f"\n  Track {i+1}: '{track.name}' ({len(track.events)} events, {note_ons} notes, {bpm_str})")


def handle_to_json(args: argparse.Namespace):
    """Export MIDI structure to JSON file."""
    if not os.path.exists(args.file):
        print(f"[Error] File not found: {args.file}")
        sys.exit(1)

    mf = MidiFile.load(args.file)
    data = mf.to_dict()
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[Success] Exported JSON to {args.out}\n")


def main():
    parser = argparse.ArgumentParser(description="Midi Forge: Algorithmic MIDI generator & processor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate chord progression MIDI")
    p_gen.add_argument("--root", default="C", help="Root key note (e.g. C, F#, Bb)")
    p_gen.add_argument("--scale", default="major", help="Scale type (major, minor, dorian, etc.)")
    p_gen.add_argument("--progression", default="I-V-vi-IV", help="Roman numeral progression")
    p_gen.add_argument("--bpm", type=float, default=120.0, help="Tempo in BPM")
    p_gen.add_argument("--humanize", action="store_true", help="Apply humanization")
    p_gen.add_argument("--out", default="progression.mid", help="Output MIDI file path")
    p_gen.set_defaults(func=handle_generate)

    # humanize
    p_hum = subparsers.add_parser("humanize", help="Add human timing/velocity jitter")
    p_hum.add_argument("file", help="Input MIDI file")
    p_hum.add_argument("--timing", type=int, default=15, help="Timing jitter in ticks")
    p_hum.add_argument("--velocity", type=int, default=10, help="Velocity variance")
    p_hum.add_argument("--out", help="Output MIDI file (defaults to overwrite input)")
    p_hum.set_defaults(func=handle_humanize)

    # quantize
    p_q = subparsers.add_parser("quantize", help="Snap MIDI notes to rhythmic grid")
    p_q.add_argument("file", help="Input MIDI file")
    p_q.add_argument("--grid", choices=["1/4", "1/8", "1/16", "1/32", "1/8T", "1/16T"], default="1/16")
    p_q.add_argument("--strength", type=float, default=1.0, help="Quantization strength [0.0 - 1.0]")
    p_q.add_argument("--swing", type=float, default=0.0, help="Swing factor [-1.0 - 1.0]")
    p_q.add_argument("--out", help="Output MIDI file")
    p_q.set_defaults(func=handle_quantize)

    # inspect
    p_ins = subparsers.add_parser("inspect", help="Display metadata and tracks of a MIDI file")
    p_ins.add_argument("file", help="Path to MIDI file")
    p_ins.set_defaults(func=handle_inspect)

    # to-json
    p_json = subparsers.add_parser("to-json", help="Convert MIDI file to structured JSON")
    p_json.add_argument("file", help="Path to MIDI file")
    p_json.add_argument("--out", default="midi.json", help="Output JSON path")
    p_json.set_defaults(func=handle_to_json)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()