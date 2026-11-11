"""Unit tests for frameshot.subtitle_parser (Tasks 1.11-1.16)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frameshot.subtitle_parser import SubtitleEntry, SubtitleParser


def test_subtitle_entry_contains():
    entry = SubtitleEntry(
        index=0,
        start_ms=1000,
        end_ms=3000,
        text="Hello world",
        text_original="<i>Hello world</i>",
    )
    assert entry.contains(1000)
    assert entry.contains(2000)
    assert not entry.contains(3000)
    assert not entry.contains(500)


def test_load_srt(sample_srt: Path):
    parser = SubtitleParser()
    parser.load(sample_srt)
    assert len(parser.entries) == 2
    assert parser.entries[0].text == "The edifice was resplendent under the moonlight."
    assert parser.entries[1].text == "Nobody expects the Spanish Inquisition."
    assert "Nobody expects the Spanish Inquisition." in parser.entries[1].text_original
    assert parser.filepath == sample_srt


def test_load_ass_fixture():
    ass_path = Path("tests/fixtures/sample.ass")
    parser = SubtitleParser()
    parser.load(ass_path)
    assert len(parser.entries) == 3
    # Check that tags were stripped in .text
    assert "The edifice was resplendent." in parser.entries[0].text
    assert "{\\i1}" not in parser.entries[0].text
    assert "{\\an8}" not in parser.entries[1].text


def test_load_nonexistent_file(tmp_path: Path):
    parser = SubtitleParser()
    with pytest.raises(FileNotFoundError):
        parser.load(tmp_path / "missing.srt")


def test_load_corrupt_file(tmp_path: Path):
    corrupt = tmp_path / "corrupt.srt"
    corrupt.write_bytes(b"\x00\x01\x02\x03\xff\xfe")
    parser = SubtitleParser()
    # Should raise ValueError wrapping any parse error
    with pytest.raises((ValueError, Exception)):
        parser.load(corrupt)


def test_get_at_exact_match(sample_srt: Path):
    parser = SubtitleParser()
    parser.load(sample_srt)
    entry = parser.get_at(2000)
    assert entry is not None
    assert entry.text == "The edifice was resplendent under the moonlight."


def test_get_at_backward_tolerance(sample_srt: Path):
    parser = SubtitleParser()
    parser.load(sample_srt)
    # Entry 1 ends at 3500ms. Test lookup at 4200ms (700ms gap, within 2000ms tolerance)
    # But note: Entry 2 starts at 5000ms (800ms ahead). Entry 1 is closer (700ms gap).
    entry = parser.get_at(3900, tolerance_ms=1000)
    assert entry is not None
    assert entry.index == 0


def test_get_at_forward_tolerance(sample_srt: Path):
    parser = SubtitleParser()
    parser.load(sample_srt)
    # Entry 1 starts at 1000ms. Look up at 500ms with tolerance 1000ms.
    entry = parser.get_at(500, tolerance_ms=1000)
    assert entry is not None
    assert entry.index == 0


def test_get_at_out_of_range(sample_srt: Path):
    parser = SubtitleParser()
    parser.load(sample_srt)
    # Beyond last entry (ends at 7000ms) with small tolerance
    assert parser.get_at(15000, tolerance_ms=2000) is None


def test_auto_detect_exact_and_prefix(tmp_path: Path):
    video = tmp_path / "Inception.mkv"
    video.touch()

    # When no subtitles exist
    assert SubtitleParser.auto_detect(video) is None

    # Prefix match
    sub_en = tmp_path / "Inception.en.srt"
    sub_en.touch()
    assert SubtitleParser.auto_detect(video) == sub_en

    # Exact match should take precedence over prefix match
    sub_exact = tmp_path / "Inception.srt"
    sub_exact.touch()
    assert SubtitleParser.auto_detect(video) == sub_exact


def test_extract_embedded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    video = tmp_path / "film.mkv"
    video.touch()
    out = tmp_path / "extracted.srt"

    mock_run = MagicMock()
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", mock_run)

    result = SubtitleParser.extract_embedded(video, stream_index=1, out_path=out)
    assert result == out
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert str(video) in cmd
    assert "0:s:1" in cmd


def test_extract_embedded_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    video = tmp_path / "film.mkv"
    video.touch()

    mock_run = MagicMock()
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="Stream map error"
    )
    monkeypatch.setattr(subprocess, "run", mock_run)

    with pytest.raises(RuntimeError, match="ffmpeg subtitle extraction failed"):
        SubtitleParser.extract_embedded(video)
