"""Task 0.3 - capture the paused frame through VLC's HTTP snapshot command.

Answers:

  * Does ``?command=snapshot`` work, and where does the file land?
  * How long does a capture take (perf budget: < 200 ms)?
  * Is the image black? (the classic hardware-decoding failure)
  * What resolution/format do we get, and is it the *paused* frame?

Usage:

    python spikes/spike_snapshot.py --snapshot-dir data/snapshots
    python spikes/spike_snapshot.py --repeat 5 --keep
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from _util import (
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    REPO_ROOT,
    banner,
    ensure_out_dir,
    format_ms,
    step,
    verdict,
    vlc_get,
    vlc_json,
    wait_for_new_file,
)

BLACK_LUMA_THRESHOLD = 8.0


def analyse_image(path: Path) -> dict[str, object]:
    """Return size, mode, and mean luma (needs Pillow; degrades gracefully)."""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return {"note": "Pillow not installed - skipping pixel analysis"}

    with Image.open(path) as image:
        image.load()
        rgb = image.convert("RGB")
        stat = ImageStat.Stat(rgb.convert("L"))
        mean_luma = float(stat.mean[0])
        return {
            "size": image.size,
            "mode": image.mode,
            "mean_luma": round(mean_luma, 2),
            "is_black": mean_luma < BLACK_LUMA_THRESHOLD,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=REPO_ROOT / "data" / "snapshots",
        help="must match VLC's configured snapshot directory",
    )
    parser.add_argument("--repeat", type=int, default=3, help="number of captures to time")
    parser.add_argument("--timeout", type=float, default=3.0, help="seconds to wait for the file")
    parser.add_argument("--keep", action="store_true", help="copy captures into spikes/out/")
    args = parser.parse_args()

    banner("Task 0.3 - VLC snapshot capture")
    snapshot_dir = args.snapshot_dir.resolve()
    print(f"snapshot dir: {snapshot_dir}")
    print(f"exists: {snapshot_dir.is_dir()}")
    if not snapshot_dir.is_dir():
        print("creating it (VLC still has to be pointed at the same folder)")
        snapshot_dir.mkdir(parents=True, exist_ok=True)

    status = vlc_json(args.host, args.port, args.password, "requests/status.json")
    print(f"VLC state: {status.get('state')} at {format_ms(status.get('time', 0))}")
    if status.get("state") != "paused":
        print("NOTE: pause the video first - the spike wants the *paused* frame.")

    step(f"capturing {args.repeat}x")
    latencies: list[float] = []
    captures: list[Path | None] = []
    for index in range(1, args.repeat + 1):
        since = time.time()
        response = vlc_get(
            args.host,
            args.port,
            args.password,
            "requests/status.json?command=snapshot",
            timeout=args.timeout,
        )
        if response.status_code != 200:
            print(f"  {index}: HTTP {response.status_code} - {response.text[:120]!r}")
            captures.append(None)
            continue
        found, latency_ms = wait_for_new_file(snapshot_dir, since, timeout_s=args.timeout)
        latencies.append(latency_ms)
        captures.append(found)
        if found is None:
            print(f"  {index}: no file appeared within {args.timeout:.1f}s")
        else:
            print(f"  {index}: {latency_ms:6.0f} ms  {found.name}  ({found.stat().st_size} bytes)")
        time.sleep(0.2)

    produced = [c for c in captures if c is not None]
    banner("Phase 0.3 verdict")
    if not produced:
        print("No snapshot was written. Checklist:")
        print("  1. VLC must be started with a matching path, e.g.")
        print(f'     --snapshot-path="{snapshot_dir}" --snapshot-format=png')
        print("     (or Preferences -> All -> Video -> Video snapshots -> Directory)")
        print("  2. Some builds ignore snapshots while no video output is active.")
        print("  3. Hardware decoding can produce black frames - retry with --avcodec-hw=none")
        return 1

    newest = produced[-1]
    details = analyse_image(newest)
    step("last capture")
    for key, value in details.items():
        print(f"  {key}: {value}")

    if args.keep:
        out_dir = ensure_out_dir()
        target = out_dir / f"snapshot_{int(time.time())}{newest.suffix}"
        shutil.copyfile(newest, target)
        print(f"  copied to: {target}")

    mean_ms = sum(latencies) / len(latencies)
    got_file = len(produced) == args.repeat
    black = bool(details.get("is_black", False))

    ok = True
    ok &= verdict(got_file, f"{len(produced)}/{args.repeat} captures produced a file")
    ok &= verdict(mean_ms < 200, f"mean capture latency {mean_ms:.0f} ms (budget < 200 ms)")
    ok &= verdict(not black, "capture is not a black frame")
    if black:
        print("\nBlack frames mean the video output is not readable by the snapshot")
        print("command. Fix: launch VLC with --avcodec-hw=none (disable hardware decoding)")
        print("and/or use the Direct3D11 output, then re-run this spike.")
    print("\nWhat to record in tasks.md 0.3:")
    print(f"  - latency: {mean_ms:.0f} ms, format: {details.get('size')}")
    print("  - VLC writes to its configured snapshot dir; the HTTP API takes no path.")
    print("  - frameshot must therefore own that directory (config.paths.snapshot_dir).")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
