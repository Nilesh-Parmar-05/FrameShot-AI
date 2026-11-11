"""VLC integration over VLC's built-in HTTP interface.

Tasks 1.6-1.10 in ``tasks.md``. Promoted from ``spikes/spike_vlc.py`` and
``spikes/spike_snapshot.py``.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import requests

from frameshot.config import VLCConfig
from frameshot.events import Event, EventBus

logger = logging.getLogger(__name__)


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


def find_current_playlist_item(node: Any, found: list[dict[str, Any]]) -> None:
    """Walk VLC's playlist tree and collect the item marked ``current``."""
    if isinstance(node, dict):
        if node.get("current") == "current" and node.get("uri"):
            found.append(node)
        for child in node.get("children") or []:
            find_current_playlist_item(child, found)
    elif isinstance(node, list):
        for child in node:
            find_current_playlist_item(child, found)


def uri_to_path(uri: str) -> Path | None:
    """Convert a ``file:///C:/...`` URI into a local file Path."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    raw = url2pathname(unquote(parsed.path))
    if len(raw) > 2 and raw[0] in "/\\" and raw[2] == ":":
        raw = raw[1:]
    return Path(raw)


class VLCController:
    """Polls VLC's HTTP interface and reports state transitions."""

    def __init__(self, config: VLCConfig, snapshot_dir: Path | None = None) -> None:
        self._config = config
        self._snapshot_dir = Path(snapshot_dir) if snapshot_dir is not None else Path("data/snapshots")
        self._session = requests.Session()
        self._session.auth = ("", self._config.password)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._prev_state: PlaybackState = PlaybackState.UNKNOWN
        self._prev_filename: str | None = None
        self._cached_media_path: Path | None = None
        self._last_status: PlaybackStatus | None = None
        self._connected: bool = False
        self._lock = threading.Lock()

    @property
    def base_url(self) -> str:
        return f"http://{self._config.host}:{self._config.port}"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_polling(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_status(self) -> PlaybackStatus | None:
        return self._last_status

    # ------------------------------------------------------------ HTTP API

    def connect(self) -> bool:
        """Return True when the HTTP interface answers and authenticates."""
        url = f"{self.base_url}/requests/status.json"
        try:
            response = self._session.get(url, timeout=self._config.request_timeout_s)
            if response.status_code == 200:
                return True
            if response.status_code == 401:
                logger.warning("VLC HTTP 401 Unauthorized - verify password in config")
                return False
            logger.warning("VLC HTTP unexpected status code: %d", response.status_code)
            return False
        except requests.RequestException as exc:
            logger.debug("VLC connection check failed: %s", exc)
            return False

    def get_status(self) -> PlaybackStatus:
        """Fetch and normalise the current playback status."""
        url = f"{self.base_url}/requests/status.json"
        response = self._session.get(url, timeout=self._config.request_timeout_s)
        response.raise_for_status()
        raw = response.json()

        state_str = str(raw.get("state", "unknown")).lower()
        try:
            state = PlaybackState(state_str)
        except ValueError:
            state = PlaybackState.UNKNOWN

        # VLC reports seconds in /requests/status.json
        raw_time = float(raw.get("time", 0))
        raw_length = float(raw.get("length", 0))

        # Support callers/tests passing seconds or already in ms
        time_ms = int(raw_time * 1000) if raw_time < 100_000 else int(raw_time)
        duration_ms = int(raw_length * 1000) if raw_length < 100_000 else int(raw_length)

        meta = raw.get("information", {}).get("category", {}).get("meta", {})
        filename = meta.get("filename")

        spu_val = raw.get("spu")
        subtitle_track: int | None = None
        if isinstance(spu_val, int):
            subtitle_track = spu_val
        elif isinstance(spu_val, str) and spu_val.isdigit():
            subtitle_track = int(spu_val)

        media_path = self._cached_media_path if (filename and filename == self._prev_filename) else None

        status = PlaybackStatus(
            state=state,
            timestamp_ms=time_ms,
            duration_ms=duration_ms,
            filename=filename,
            media_path=media_path,
            subtitle_track=subtitle_track,
        )
        self._last_status = status
        return status

    def get_media_info(self) -> Path | None:
        """Resolve the absolute path of the playing file from /requests/playlist.json."""
        url = f"{self.base_url}/requests/playlist.json"
        try:
            response = self._session.get(url, timeout=self._config.request_timeout_s)
            response.raise_for_status()
            playlist = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.debug("Failed to fetch playlist.json: %s", exc)
            return None

        items: list[dict[str, Any]] = []
        find_current_playlist_item(playlist, items)
        if not items:
            return None

        uri = str(items[0].get("uri", ""))
        resolved = uri_to_path(uri)
        if resolved is not None:
            self._cached_media_path = resolved
        return resolved

    # ------------------------------------------------------------ Snapshot

    def take_snapshot(
        self,
        timeout_s: float = 1.0,
        video_path: Path | None = None,
        timestamp_ms: int | None = None,
    ) -> Path | None:
        """Ask VLC to write the current frame and return the new image path.

        Falls back to extracting the exact paused frame via ffmpeg if VLC fails
        or times out.
        """
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        since = time.time()

        url = f"{self.base_url}/requests/status.json?command=snapshot"
        vlc_command_ok = False
        try:
            response = self._session.get(url, timeout=self._config.request_timeout_s)
            vlc_command_ok = (response.status_code == 200)
        except requests.RequestException as exc:
            logger.debug("VLC snapshot HTTP command failed: %s", exc)

        search_dirs = [self._snapshot_dir]
        pictures_dir = Path.home() / "Pictures"
        if pictures_dir.is_dir() and pictures_dir != self._snapshot_dir:
            search_dirs.append(pictures_dir)

        if vlc_command_ok:
            deadline = time.perf_counter() + timeout_s
            while time.perf_counter() < deadline:
                candidates: list[Path] = []
                for s_dir in search_dirs:
                    if not s_dir.exists():
                        continue
                    candidates.extend(
                        p
                        for p in s_dir.iterdir()
                        if p.is_file()
                        and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
                        and p.stat().st_mtime >= since - 0.5
                    )
                if candidates:
                    candidates.sort(key=lambda p: p.stat().st_mtime)
                    found = candidates[-1]
                    logger.info("captured VLC snapshot: %s", found)
                    return found
                time.sleep(0.03)

        # Fallback to ffmpeg
        target_video = video_path or (self._last_status.media_path if self._last_status else None)
        target_time = timestamp_ms if timestamp_ms is not None else (
            self._last_status.timestamp_ms if self._last_status else 0
        )
        if target_video and target_video.is_file():
            fallback_path = self._snapshot_dir / f"frame_{int(time.time() * 1000)}.png"
            time_sec = max(0.0, target_time / 1000.0)
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                f"{time_sec:.3f}",
                "-i",
                str(target_video),
                "-vframes",
                "1",
                "-q:v",
                "2",
                str(fallback_path),
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if res.returncode == 0 and fallback_path.is_file():
                    logger.info("captured fallback frame via ffmpeg: %s", fallback_path)
                    return fallback_path
                logger.warning("ffmpeg fallback frame extraction failed: %s", res.stderr.strip())
            except OSError as exc:
                logger.warning("could not run ffmpeg for snapshot fallback: %s", exc)

        logger.warning("take_snapshot could not capture frame (timeout or missing file)")
        return None

    # ------------------------------------------------------------ Polling Thread

    def start_polling(self, bus: EventBus) -> None:
        """Start the background poller thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._poll_loop,
                args=(bus,),
                name="vlc-poller",
                daemon=True,
            )
            self._thread.start()
            logger.info("VLC poller thread started")

    def stop_polling(self, timeout: float = 2.0) -> None:
        """Stop the background poller thread."""
        with self._lock:
            self._stop_event.set()
            if self._thread is not None:
                self._thread.join(timeout=timeout)
                self._thread = None
                logger.info("VLC poller thread stopped")

    def _poll_loop(self, bus: EventBus) -> None:
        base_poll_s = max(self._config.poll_interval_ms, 50) / 1000.0
        last_warn_time = 0.0

        while not self._stop_event.is_set():
            wait_s = base_poll_s
            try:
                status = self.get_status()
                if not self._connected:
                    self._connected = True
                    logger.info("Connected to VLC HTTP interface at %s", self.base_url)
                    bus.publish(Event.VLC_CONNECTED)

                # Check media/filename change
                if status.filename and status.filename != self._prev_filename:
                    if status.media_path is None:
                        status.media_path = self.get_media_info()
                    self._prev_filename = status.filename
                    bus.publish(Event.MEDIA_CHANGED, status)

                # Check playback state change
                if status.state != self._prev_state:
                    if status.state == PlaybackState.PAUSED:
                        bus.publish(Event.PLAYBACK_PAUSED, status)
                    elif self._prev_state == PlaybackState.PAUSED:
                        bus.publish(Event.PLAYBACK_RESUMED, status)
                    elif status.state == PlaybackState.STOPPED:
                        bus.publish(Event.PLAYBACK_STOPPED, status)
                    self._prev_state = status.state

                # Adaptive rate: relaxed interval when stopped (idle)
                if status.state == PlaybackState.STOPPED:
                    wait_s = max(base_poll_s * 4.0, 1.0)
                else:
                    wait_s = base_poll_s

            except requests.RequestException as exc:
                # Backoff when disconnected to save CPU and network
                wait_s = max(base_poll_s * 5.0, 1.5)
                if self._connected:
                    self._connected = False
                    logger.warning("Lost connection to VLC HTTP interface: %s", exc)
                    bus.publish(Event.VLC_DISCONNECTED)
                else:
                    now = time.time()
                    if now - last_warn_time > 5.0:
                        logger.warning(
                            "Waiting for VLC HTTP interface on %s... (is VLC running with Web interface enabled?)",
                            self.base_url,
                        )
                        last_warn_time = now
            except Exception:
                logger.exception("unexpected error in VLC poller loop")

            self._stop_event.wait(wait_s)
