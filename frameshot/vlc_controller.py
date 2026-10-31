"""VLC integration over VLC's built-in HTTP interface.

Status: **stub** — tasks 1.6-1.10 in ``tasks.md``. The working reference
implementation is ``spikes/spike_vlc.py`` and ``spikes/spike_snapshot.py``;
promote that logic here once the Phase 0 results are recorded.

Design decision (open item): this is a *synchronous* ``requests`` client meant
to run on a worker thread, because the app's event loop is Qt's. The
``async``/``httpx`` variant in ``architecture.md`` §5.1 requires ``qasync`` to
integrate with PyQt6 and buys nothing at a 200 ms poll rate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from frameshot.config import VLCConfig


class PlaybackState(StrEnum):
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class PlaybackStatus:
    """Normalised snapshot of ``/requests/status.json`` (FR-03, FR-04)."""

    state: PlaybackState
    timestamp_ms: int
    duration_ms: int
    filename: str | None = None
    media_path: Path | None = None
    subtitle_track: int | None = None


StatusCallback = Callable[[PlaybackStatus], None]


class VLCController:
    """Polls VLC's HTTP interface and reports state transitions."""

    def __init__(self, config: VLCConfig) -> None:
        self._config = config

    @property
    def base_url(self) -> str:
        return f"http://{self._config.host}:{self._config.port}"

    # ------------------------------------------------------------ TODO 1.6

    def connect(self) -> bool:
        """Return True when the HTTP interface answers and authenticates."""
        raise NotImplementedError("tasks.md 1.6 - see spikes/spike_vlc.py")

    def get_status(self) -> PlaybackStatus:
        """Fetch and normalise the current playback status."""
        raise NotImplementedError("tasks.md 1.6 - see spikes/spike_vlc.py")

    def get_media_info(self) -> Path | None:
        """Resolve the absolute path of the playing file.

        Note: ``status.json`` only exposes the file *name*; the absolute URI
        comes from ``/requests/playlist.json`` (spike 0.2 confirmed this).
        """
        raise NotImplementedError("tasks.md 1.9 - see spikes/spike_vlc.py")

    # ------------------------------------------------------------ TODO 1.7

    def poll_loop(self, on_change: StatusCallback, stop_event: object) -> None:
        """Blocking poll loop; invoke ``on_change`` on every state transition."""
        raise NotImplementedError("tasks.md 1.7 - see spikes/spike_vlc.py --watch")

    # ------------------------------------------------------------ TODO 1.8

    def take_snapshot(self) -> Path:
        """Ask VLC to write the current frame and return the new image path.

        VLC's ``?command=snapshot`` accepts no output path: the file lands in
        VLC's configured snapshot directory, which must equal
        ``config.paths.snapshot_dir`` (spike 0.3).
        """
        raise NotImplementedError("tasks.md 1.8 - see spikes/spike_snapshot.py")
