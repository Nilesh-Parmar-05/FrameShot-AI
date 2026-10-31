"""Subtitle loading, indexing, and timestamp lookup.

Status: **stub** — tasks 1.11-1.16 in ``tasks.md``. The working reference
implementation is ``spikes/spike_subs.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_SUFFIXES = (".srt", ".ass", ".ssa")


@dataclass(frozen=True, slots=True)
class SubtitleEntry:
    index: int
    start_ms: int
    end_ms: int
    text: str  # markup stripped, ready for tokenization
    text_original: str  # markup preserved

    def contains(self, timestamp_ms: int) -> bool:
        return self.start_ms <= timestamp_ms < self.end_ms


class SubtitleParser:
    """Indexed subtitle track supporting O(log n) lookup by timestamp."""

    def __init__(self) -> None:
        self._entries: list[SubtitleEntry] = []
        self._sorted_starts: list[int] = []

    @property
    def entries(self) -> list[SubtitleEntry]:
        return self._entries

    def load(self, filepath: str | Path) -> None:
        """Load and index an SRT/ASS/SSA file (FR-10)."""
        raise NotImplementedError("tasks.md 1.11-1.12 - see spikes/spike_subs.py")

    def get_at(self, timestamp_ms: int, tolerance_ms: int = 2000) -> SubtitleEntry | None:
        """Binary search for the line covering ``timestamp_ms`` (FR-12).

        Falls back to the nearest preceding entry within ``tolerance_ms``
        (``flow.md`` §5); returns None when the gap is larger.
        """
        raise NotImplementedError("tasks.md 1.13 - see spikes/spike_subs.py")

    @staticmethod
    def auto_detect(video_path: str | Path) -> Path | None:
        """Find a sibling subtitle file matching the video name (FR-11)."""
        raise NotImplementedError("tasks.md 1.14 - see spikes/spike_subs.py --detect")

    @staticmethod
    def extract_embedded(video_path: str | Path, stream_index: int, out_path: str | Path) -> Path:
        """Extract an embedded subtitle track with ffmpeg (FR-13)."""
        raise NotImplementedError("tasks.md 1.15 - see spikes/spike_subs.py")
