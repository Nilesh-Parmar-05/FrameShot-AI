"""Subtitle loading, indexing, and timestamp lookup.

Tasks 1.11-1.16 in ``tasks.md``. Promoted from ``spikes/spike_subs.py``.
"""

from __future__ import annotations

import bisect
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pysubs2

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES: tuple[str, ...] = (".srt", ".ass", ".ssa", ".vtt", ".sub")
DEFAULT_TOLERANCE_MS = 2_000


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
        self._filepath: Path | None = None

    @property
    def entries(self) -> list[SubtitleEntry]:
        return self._entries

    @property
    def filepath(self) -> Path | None:
        return self._filepath

    def load(self, filepath: str | Path) -> None:
        """Load and index an SRT/ASS/SSA file (FR-10)."""
        path = Path(filepath)
        if not path.is_file():
            raise FileNotFoundError(f"subtitle file not found: {path}")

        try:
            subs = pysubs2.load(str(path))
        except Exception as exc:
            raise ValueError(f"failed to parse subtitle file {path}: {exc}") from exc

        parsed_entries: list[SubtitleEntry] = []
        for idx, event in enumerate(subs):
            # pysubs2 event.start and event.end are in milliseconds
            text_clean = event.plaintext.strip()
            if not text_clean:
                continue
            parsed_entries.append(
                SubtitleEntry(
                    index=idx,
                    start_ms=int(event.start),
                    end_ms=int(event.end),
                    text=text_clean,
                    text_original=event.text,
                )
            )

        parsed_entries.sort(key=lambda entry: entry.start_ms)
        self._entries = parsed_entries
        self._sorted_starts = [entry.start_ms for entry in parsed_entries]
        self._filepath = path
        logger.info(
            "loaded subtitle %s (%d entries, range %d ms -> %d ms)",
            path.name,
            len(self._entries),
            self._sorted_starts[0] if self._sorted_starts else 0,
            self._entries[-1].end_ms if self._entries else 0,
        )

    def get_at(self, timestamp_ms: int, tolerance_ms: int = DEFAULT_TOLERANCE_MS) -> SubtitleEntry | None:
        """Binary search for the line covering ``timestamp_ms`` (FR-12).

        Falls back to the nearest preceding entry within ``tolerance_ms``
        (``flow.md`` §5), or lookahead to the next entry within ``tolerance_ms``;
        returns None when the gap is larger.
        """
        if not self._entries:
            return None

        index = bisect.bisect_right(self._sorted_starts, timestamp_ms) - 1

        if index >= 0:
            candidate = self._entries[index]
            # Exact overlap
            if candidate.start_ms <= timestamp_ms < candidate.end_ms:
                return candidate
            # Backward tolerance: paused shortly after line finished
            if timestamp_ms - candidate.end_ms <= tolerance_ms:
                return candidate

        # Forward lookahead: paused shortly before line begins
        if index + 1 < len(self._entries):
            following = self._entries[index + 1]
            if following.start_ms - timestamp_ms <= tolerance_ms:
                return following

        return None

    @staticmethod
    def auto_detect(video_path: str | Path) -> Path | None:
        """Find a sibling subtitle file matching the video name (FR-11)."""
        video = Path(video_path)
        if not video.parent.is_dir():
            return None

        stem = video.stem.lower()
        candidates = [
            path
            for path in video.parent.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        ]

        if not candidates:
            return None

        def rank(path: Path) -> tuple[int, int, str]:
            name = path.stem.lower()
            if name == stem:
                return (0, 0, name)  # exact stem match e.g. "Movie.srt" for "Movie.mkv"
            if name.startswith(stem):
                return (1, len(name), name)  # "Movie.en.srt", "Movie.forced.srt"
            return (2, len(name), name)

        sorted_candidates = sorted(candidates, key=rank)
        return sorted_candidates[0]

    @staticmethod
    def extract_embedded(
        video_path: str | Path,
        stream_index: int = 0,
        out_path: str | Path | None = None,
    ) -> Path:
        """Extract an embedded subtitle track with ffmpeg (FR-13)."""
        video = Path(video_path)
        if not video.is_file():
            raise FileNotFoundError(f"video file not found: {video}")

        if out_path is None:
            destination = video.parent / f"{video.stem}.extracted.srt"
        else:
            destination = Path(out_path)

        destination.parent.mkdir(parents=True, exist_ok=True)

        map_spec = (
            f"0:s:{stream_index}"
            if str(stream_index).isdigit() and int(stream_index) < 10
            else f"0:{stream_index}"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-map",
            map_spec,
            str(destination),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise RuntimeError(f"failed to execute ffmpeg: {exc}") from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg subtitle extraction failed (exit {result.returncode}): {result.stderr.strip()}"
            )

        return destination

    @staticmethod
    def auto_extract_embedded(
        video_path: str | Path,
        preferred_lang: str = "eng",
        out_dir: str | Path | None = None,
    ) -> Path | None:
        """Find the best embedded subtitle stream (preferring preferred_lang) and extract it."""
        import json

        video = Path(video_path)
        if not video.is_file():
            return None

        # Discover subtitle streams using ffprobe
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "s",
            "-show_entries",
            "stream=index,codec_name:stream_tags=language,title",
            "-of",
            "json",
            str(video),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode != 0 or not res.stdout:
                return None
            data = json.loads(res.stdout)
        except Exception as exc:
            logger.debug("ffprobe failed on %s: %s", video, exc)
            return None

        streams = data.get("streams", [])
        if not streams:
            return None

        # Filter by preferred language
        lang_lower = preferred_lang.lower()
        preferred_streams = [
            s
            for s in streams
            if s.get("tags", {}).get("language", "").lower() in {lang_lower, lang_lower[:2]}
        ]
        candidates = preferred_streams if preferred_streams else streams

        destination_dir = Path(out_dir) if out_dir is not None else video.parent
        destination_dir.mkdir(parents=True, exist_ok=True)

        # Check existing cached files first
        best_file: Path | None = None
        max_size = 0
        for stream in candidates:
            idx = stream.get("index")
            out_file = destination_dir / f"{video.stem}.embedded_{idx}.srt"
            if out_file.is_file() and out_file.stat().st_size > max_size:
                max_size = out_file.stat().st_size
                best_file = out_file

        if best_file is not None and max_size > 200:
            logger.info("Using cached extracted subtitle: %s", best_file.name)
            return best_file

        # Extract candidates and select the fullest subtitle track
        for stream in candidates:
            idx = stream.get("index")
            out_file = destination_dir / f"{video.stem}.embedded_{idx}.srt"
            try:
                SubtitleParser.extract_embedded(video, idx, out_file)
                if out_file.is_file() and out_file.stat().st_size > max_size:
                    max_size = out_file.stat().st_size
                    best_file = out_file
            except Exception as exc:
                logger.debug("Could not extract stream %s: %s", idx, exc)

        if best_file is not None:
            logger.info("Extracted embedded subtitle for %s -> %s", video.name, best_file.name)
        return best_file
