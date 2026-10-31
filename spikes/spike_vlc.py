"""Task 0.1 / 0.2 - VLC HTTP interface: connect, read status, detect pause.

Answers the Phase 0 questions:

  * Does ``/requests/status.json`` answer, and with which auth?
  * Which fields carry state, position, duration, and filename? (FR-02..FR-04)
  * Where does the absolute media path live? (``/requests/playlist.json``)
  * How fast is one poll, and how quickly do we notice a pause?

Usage (VLC playing a video, Web interface enabled):

    python spikes/spike_vlc.py --dump
    python spikes/spike_vlc.py --watch 20
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from _util import (
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    banner,
    die,
    format_ms,
    step,
    verdict,
    vlc_json,
)


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
    """Convert a ``file:///C:/...`` URI into a Windows path."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    raw = url2pathname(unquote(parsed.path))
    # url2pathname keeps a leading slash before the drive letter on Windows.
    if len(raw) > 2 and raw[0] in "/\\" and raw[2] == ":":
        raw = raw[1:]
    return Path(raw)


def summarise(status: dict[str, Any]) -> dict[str, Any]:
    meta = status.get("information", {}).get("category", {}).get("meta", {})
    return {
        "state": status.get("state"),
        "time_ms": status.get("time", 0),
        "length_ms": status.get("length", 0),
        "filename": meta.get("filename"),
        "spu": status.get("spu"),  # active subtitle track id, "Disable" or a number
        "volume": status.get("volume"),
        "rate": status.get("rate"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--dump", action="store_true", help="print the full status + playlist JSON")
    parser.add_argument(
        "--watch", type=float, metavar="SECONDS", help="poll and report state transitions"
    )
    parser.add_argument(
        "--interval", type=float, default=200.0, help="poll interval in ms (default 200)"
    )
    args = parser.parse_args()

    banner("Task 0.1/0.2 - VLC HTTP interface")
    print(f"endpoint: http://{args.host}:{args.port}/requests/status.json")
    print(f"password: {'(empty)' if not args.password else '***'}")

    step("status.json")
    started = time.perf_counter()
    status = vlc_json(args.host, args.port, args.password, "requests/status.json")
    first_poll_ms = (time.perf_counter() - started) * 1_000
    info = summarise(status)
    print(json.dumps(info, indent=2))
    print(f"round trip: {first_poll_ms:.0f} ms")

    if args.dump:
        step("full status.json")
        print(json.dumps(status, indent=2))
        step("playlist.json (current item(s) only)")
        playlist = vlc_json(args.host, args.port, args.password, "requests/playlist.json")
        items: list[dict[str, Any]] = []
        find_current_playlist_item(playlist, items)
        print(json.dumps(items, indent=2))

    step("absolute media path")
    playlist = vlc_json(args.host, args.port, args.password, "requests/playlist.json")
    items = []
    find_current_playlist_item(playlist, items)
    media_path: Path | None = None
    if not items:
        print("no 'current' item in playlist.json (no media loaded?)")
    for item in items:
        uri = str(item.get("uri", ""))
        resolved = uri_to_path(uri)
        print(f"uri:  {uri}")
        print(f"path: {resolved}")
        if resolved is not None:
            media_path = resolved
            print(f"exists: {resolved.exists()}")
            print(f"folder: {resolved.parent}")
            if resolved.exists():
                siblings = sorted(
                    p.name
                    for p in resolved.parent.iterdir()
                    if p.suffix.lower() in {".srt", ".ass", ".ssa"}
                )
                print(f"subtitle files next to it: {siblings or '(none)'}")
            break

    checks = []
    checks.append(verdict(bool(info.get("state")), f"state field present: {info.get('state')!r}"))
    checks.append(
        verdict(
            isinstance(info.get("time_ms"), int), f"position exposed in ms: {info.get('time_ms')}"
        )
    )
    checks.append(
        verdict(
            isinstance(info.get("length_ms"), int),
            f"duration exposed in ms: {info.get('length_ms')}",
        )
    )
    checks.append(
        verdict(
            bool(info.get("filename")),
            f"'filename' is a bare name, not a path: {info.get('filename')!r}",
        )
    )
    checks.append(verdict(media_path is not None, "absolute path obtained from playlist.json"))
    checks.append(
        verdict(first_poll_ms < 50, f"single poll < 50 ms (perf budget): {first_poll_ms:.1f} ms")
    )

    if args.watch:
        step(f"watching state transitions for {args.watch:.0f}s at {args.interval:.0f}ms")
        print("Press Pause, then Play in VLC to exercise both transitions.\n")
        latencies: list[float] = []
        transitions: list[str] = []
        last_state = info.get("state")
        last_change = time.perf_counter()
        deadline = last_change + args.watch
        poll_s = max(args.interval, 50.0) / 1_000

        while time.perf_counter() < deadline:
            tick = time.perf_counter()
            try:
                current = vlc_json(
                    args.host, args.port, args.password, "requests/status.json", timeout=2.0
                )
            except SystemExit:
                print("VLC stopped responding; ending watch early.")
                break
            latencies.append((time.perf_counter() - tick) * 1_000)
            state = current.get("state")
            if state != last_state:
                latency_ms = (time.perf_counter() - last_change - poll_s) * 1_000
                line = (
                    f"{format_ms(current.get('time', 0))}  "
                    f"{last_state!s:>7} -> {state!s:<7} "
                    f"(detected after <= {latency_ms:.0f} ms)"
                )
                transitions.append(line)
                print(line)
                last_state = state
                last_change = time.perf_counter()
            time.sleep(poll_s)

        print(
            f"\npolls: {len(latencies)}  mean: {statistics.mean(latencies):.1f} ms  "
            f"max: {max(latencies):.1f} ms"
        )
        if transitions:
            print("transitions observed:")
            for line in transitions:
                print(f"  {line}")
        else:
            print("no state transition observed - did you pause/play during the watch window?")
        checks.append(
            verdict(len(transitions) >= 2, "pause AND resume detected within the watch window")
        )

    banner("Phase 0.2 verdict")
    print("What to record in tasks.md 0.1/0.2:")
    print(f"  - poll cost: {first_poll_ms:.1f} ms per /requests/status.json")
    print(f"  - media path source: playlist.json -> file URI -> {media_path}")
    print("  - VLC does NOT return the media path in status.json; the controller")
    print("    must call playlist.json on every media change (cached per filename).")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        die("interrupted", 130)
