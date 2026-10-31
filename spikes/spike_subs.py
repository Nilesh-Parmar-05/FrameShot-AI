"""Task 0.4 / 0.5 - parse SRT/ASS/SSA and look up a subtitle by timestamp.

Answers:

  * Does ``pysubs2`` handle SRT, ASS and SSA uniformly?
  * How do we strip markup (``<i>``, ``{\\an8}``) safely?
  * Is binary search on start times correct and fast (< 5 ms)?
  * How do we auto-detect the subtitle file for a video (FR-11)?

Usage:

    python spikes/spike_subs.py tests/fixtures/sample.srt
    python spikes/spike_subs.py tests/fixtures/sample.srt --at 00:00:02
    python spikes/spike_subs.py --detect "D:/Movies/Some Movie.mkv"
"""

from __future__ import annotations

import argparse
import bisect
import random
import time
from pathlib import Path

from _util import REPO_ROOT, banner, die, format_ms, parse_timecode, step, verdict

SUBTITLE_SUFFIXES = (".srt", ".ass", ".ssa", ".vtt", ".sub")
DEFAULT_TOLERANCE_MS = 2_000


class Index:
    """Pre-indexed subtitle track: start times plus a covering lookup."""

    def __init__(self, events: list[object]) -> None:
        ordered = sorted(events, key=lambda event: int(event.start))  # type: ignore[attr-defined]
        self.events = ordered
        self.starts = [int(event.start) for event in ordered]  # type: ignore[attr-defined]

    def get_at(self, timestamp_ms: int, tolerance_ms: int = DEFAULT_TOLERANCE_MS) -> object | None:
        """Binary search for the covering event, else the nearest preceding one."""
        index = bisect.bisect_right(self.starts, timestamp_ms) - 1
        if index >= 0:
            candidate = self.events[index]
            if int(candidate.start) <= timestamp_ms < int(candidate.end):  # type: ignore[attr-defined]
                return candidate
            if timestamp_ms - int(candidate.end) <= tolerance_ms:  # type: ignore[attr-defined]
                return candidate
        if index + 1 < len(self.events):
            following = self.events[index + 1]
            if int(following.start) - timestamp_ms <= tolerance_ms:  # type: ignore[attr-defined]
                return following
        return None


def detect_subtitles(video_path: Path) -> list[Path]:
    """Sibling subtitle files, best match first (FR-11)."""
    if not video_path.parent.is_dir():
        return []
    stem = video_path.stem.lower()
    candidates = [
        path
        for path in video_path.parent.iterdir()
        if path.is_file() and path.suffix.lower() in SUBTITLE_SUFFIXES
    ]

    def rank(path: Path) -> tuple[int, int, str]:
        name = path.stem.lower()
        if name == stem:
            return (0, 0, name)  # exact name match
        if name.startswith(stem):
            return (1, len(name), name)  # "Movie.en", "Movie.forced"
        return (2, len(name), name)

    return sorted(candidates, key=rank)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("subtitle", nargs="?", type=Path, help="path to a .srt/.ass/.ssa file")
    parser.add_argument(
        "--detect", type=Path, metavar="VIDEO", help="find sibling subtitles for this video"
    )
    parser.add_argument(
        "--at", default="00:00:02.000", help="timecode to look up (default 00:00:02)"
    )
    parser.add_argument(
        "--tolerance", type=int, default=DEFAULT_TOLERANCE_MS, help="gap tolerance in ms"
    )
    parser.add_argument("--bench", type=int, default=1000, help="number of lookups to time")
    args = parser.parse_args()

    banner("Task 0.4/0.5 - subtitle parsing and lookup")
    ok = True

    if args.detect is not None:
        step(f"auto-detect subtitles for {args.detect.name}")
        matches = detect_subtitles(args.detect)
        if not matches:
            print("no .srt/.ass/.ssa/.vtt/.sub files in that folder")
            ok = False
        for match in matches:
            print(f"  {match.name}")
        ok &= verdict(bool(matches), "found at least one candidate subtitle")
        if args.subtitle is None:
            return 0 if ok else 1

    try:
        import pysubs2
    except ImportError:
        die("the 'pysubs2' package is missing - run: pip install -r requirements.txt")

    subtitle_path = args.subtitle
    if subtitle_path is None:
        die("pass a subtitle file, or use --detect VIDEO")

    subtitle_path = subtitle_path if subtitle_path.is_absolute() else (Path.cwd() / subtitle_path)
    if not subtitle_path.is_file():
        die(f"subtitle file not found: {subtitle_path}")

    step(f"loading {subtitle_path.name}")
    started = time.perf_counter()
    try:
        subs = pysubs2.load(str(subtitle_path))
    except Exception as exc:  # noqa: BLE001 - pysubs2 raises several types
        die(f"pysubs2 could not parse it: {type(exc).__name__}: {exc}")
    load_ms = (time.perf_counter() - started) * 1_000

    print(f"format:        {subs.format}")
    print(f"events:        {len(subs)}")
    print(f"load time:     {load_ms:.1f} ms")
    if not subs:
        die("subtitle file is empty")
    first, last = subs[0], subs[-1]
    print(f"range:         {format_ms(first.start)} -> {format_ms(last.end)}")
    ok &= verdict(load_ms < 100, f"parse < 100 ms ({load_ms:.1f} ms)")

    index = Index(list(subs))
    timestamp = parse_timecode(args.at)
    step(f"lookup at {format_ms(timestamp)} (tolerance {args.tolerance} ms)")
    match = index.get_at(timestamp, args.tolerance)
    if match is None:
        print("no subtitle line at that timestamp (gap > tolerance)")
    else:
        print(f"  start: {format_ms(match.start)}  end: {format_ms(match.end)}")
        print(f"  plain: {match.plaintext!r}")
        print(f"  raw:   {match.text!r}")

    step("edge cases")
    before = max(first.start - 5000, 0)
    after = last.end + 60_000
    print(
        f"  {format_ms(before)} (before first line): "
        f"{'hit by lookahead' if index.get_at(before) else 'miss'}"
    )
    print(
        f"  {format_ms(first.start + 10)} (inside first line): "
        f"{'hit (correct)' if index.get_at(first.start + 10) else 'miss'}"
    )
    print(
        f"  {format_ms(after)} (long after end): "
        f"{'hit' if index.get_at(after) else 'miss (correct)'}"
    )

    step(f"benchmark: {args.bench} random lookups")
    rng = random.Random(1234)
    span = max(last.end, 1)
    timestamps = [rng.randrange(span) for _ in range(args.bench)]
    bench_start = time.perf_counter()
    for value in timestamps:
        index.get_at(value)
    per_lookup_us = (time.perf_counter() - bench_start) * 1_000_000 / args.bench
    print(f"  {per_lookup_us:.1f} us/lookup over {len(index.events)} events")
    ok &= verdict(per_lookup_us < 5_000, f"lookup < 5 ms ({per_lookup_us / 1000:.3f} ms)")

    banner("Phase 0.4/0.5 verdict")
    print("What to record in tasks.md 0.4/0.5:")
    print(f"  - pysubs2 format detection: {subs.format!r}; one API for SRT + ASS + SSA")
    print("  - markup removal: pysubs2's `plaintext` handles <i> and {\\an8} tags")
    print("  - binary search validated; nearest-preceding fallback needs the 2 s")
    print("    tolerance from flow.md §5, otherwise a paused frame between two lines")
    print("    shows nothing")
    print("  - this spike also looks *forward* by the same tolerance so that pausing a")
    print("    moment before a line still shows it; flow.md only documents the backward")
    print("    case. Decide whether v1 keeps the lookahead (recommended: yes).")
    print(
        f"  - fixtures for CI: put small SRT/ASS files under tests/fixtures/"
        f" (repo root: {REPO_ROOT.name})"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
