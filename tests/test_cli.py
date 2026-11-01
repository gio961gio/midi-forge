"""Tests for Midi Forge CLI commands and non-destructive file safety."""
import os
import tempfile
import pytest
from midi_forge.midi_io import MidiFile, MidiTrack
from midi_forge.generator import generate_progression_midi
from midi_forge.cli import safe_write_midi, safe_write_json, main


def test_safe_write_midi_prevents_overwrite_without_force():
    """Verify that safe_write_midi refuses to overwrite an existing file unless force=True."""
    with tempfile.TemporaryDirectory() as tmp:
        target_path = os.path.join(tmp, "output.mid")
        mf = generate_progression_midi(progression="I-V")
        mf.save(target_path)
        original_bytes = open(target_path, "rb").read()

        mf2 = generate_progression_midi(progression="ii-V-I")

        # Must raise FileExistsError when force=False
        with pytest.raises(FileExistsError, match="Destination file already exists"):
            safe_write_midi(mf2, target_path, force=False)

        # File content must remain unchanged
        assert open(target_path, "rb").read() == original_bytes

        # With force=True, write succeeds and content is updated
        safe_write_midi(mf2, target_path, force=True)
        assert open(target_path, "rb").read() != original_bytes


def test_safe_write_midi_refuses_same_source_and_destination():
    """Verify that writing to the identical canonical path without --force is rejected."""
    with tempfile.TemporaryDirectory() as tmp:
        src_path = os.path.join(tmp, "song.mid")
        mf = generate_progression_midi(progression="I-IV")
        mf.save(src_path)

        with pytest.raises(FileExistsError, match="matches source file"):
            safe_write_midi(mf, src_path, force=False, source_path=src_path)


def test_safe_write_json_prevents_overwrite():
    """Verify safe_write_json protects against accidental file replacement."""
    with tempfile.TemporaryDirectory() as tmp:
        json_path = os.path.join(tmp, "data.json")
        safe_write_json({"a": 1}, json_path, force=False)

        with pytest.raises(FileExistsError, match="Destination file already exists"):
            safe_write_json({"b": 2}, json_path, force=False)

        safe_write_json({"b": 2}, json_path, force=True)
        assert os.path.exists(json_path)


def test_cli_generate_and_non_destructive_flags(monkeypatch):
    """Verify CLI generate command respects --out and rejects collisions without --force."""
    with tempfile.TemporaryDirectory() as tmp:
        out_mid = os.path.join(tmp, "gen_prog.mid")

        # 1. First generation succeeds
        args = ["midi-forge", "generate", "--out", out_mid]
        monkeypatch.setattr("sys.argv", args)
        main()
        assert os.path.exists(out_mid)

        # 2. Second generation to same path without --force fails with sys.exit(1)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

        # 3. Third generation with --force succeeds
        args_force = ["midi-forge", "generate", "--out", out_mid, "--force"]
        monkeypatch.setattr("sys.argv", args_force)
        main()
        assert os.path.exists(out_mid)


def test_cli_humanize_and_quantize_default_filenames(monkeypatch):
    """Verify humanize and quantize default to <stem>_humanized.mid and <stem>_quantized.mid."""
    with tempfile.TemporaryDirectory() as tmp:
        input_mid = os.path.join(tmp, "riff.mid")
        mf = generate_progression_midi(progression="I-V-vi-IV")
        mf.save(input_mid)

        # Humanize without --out
        monkeypatch.setattr("sys.argv", ["midi-forge", "humanize", input_mid])
        main()
        expected_hum = os.path.join(tmp, "riff_humanized.mid")
        assert os.path.exists(expected_hum)
        assert expected_hum != input_mid

        # Quantize without --out
        monkeypatch.setattr("sys.argv", ["midi-forge", "quantize", input_mid])
        main()
        expected_q = os.path.join(tmp, "riff_quantized.mid")
        assert os.path.exists(expected_q)
        assert expected_q != input_mid
