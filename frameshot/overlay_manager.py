"""Overlay window lifecycle and positioning.

Status: **stub** — tasks 2.11-2.20 in ``tasks.md``. PyQt6 is imported lazily so
that ``import frameshot`` works without the UI extra installed.
"""

from __future__ import annotations

from frameshot.vision_pipeline import FrameAnalysis
from frameshot.word_analyzer import WordResult


class OverlayManager:
    """Composes and shows the overlay above the VLC window."""

    def __init__(self) -> None:
        self._visible = False

    @property
    def visible(self) -> bool:
        return self._visible

    def show(self, words: list[WordResult], analysis: FrameAnalysis) -> None:
        """Render both panels and show the window (FR-40, FR-41)."""
        raise NotImplementedError("tasks.md 2.12-2.14")

    def hide(self) -> None:
        """Hide the overlay, e.g. when playback resumes (FR-44)."""
        raise NotImplementedError("tasks.md 2.16")

    def toggle(self) -> None:
        """Show/hide from the global hotkey (FR-45)."""
        raise NotImplementedError("tasks.md 2.17")

    def update_position(self) -> None:
        """Re-anchor to the current VLC window geometry."""
        raise NotImplementedError("tasks.md 2.12")
