"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from frameshot.config import AppConfig


@pytest.fixture()
def config(tmp_path: Path) -> AppConfig:
    """Default config with every writable path redirected into tmp_path."""
    cfg = AppConfig()
    cfg.paths.models_dir = tmp_path / "models"
    cfg.paths.database = tmp_path / "data" / "frameshot.db"
    cfg.paths.word_freq = tmp_path / "data" / "word_frequency.db"
    cfg.paths.snapshot_dir = tmp_path / "data" / "snapshots"
    cfg.paths.log_dir = tmp_path / "logs"
    return cfg


@pytest.fixture()
def sample_srt(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "sample.srt"
    path.write_text(
        "1\n"
        "00:00:01,000 --> 00:00:03,500\n"
        "The edifice was resplendent under the moonlight.\n"
        "\n"
        "2\n"
        "00:00:05,000 --> 00:00:07,000\n"
        "<i>Nobody expects the Spanish Inquisition.</i>\n",
        encoding="utf-8",
    )
    yield path
