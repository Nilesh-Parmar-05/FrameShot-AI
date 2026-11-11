"""Download offline vision models listed in tech-stack.md §6.

Task 2.1 in ``tasks.md``.
Downloads YOLOv8 weights into ``config.paths.models_dir``.

Usage:
    python scripts/download_models.py --profile lite
    python scripts/download_models.py --profile balanced
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.request import urlretrieve

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frameshot.config import AppConfig, ConfigError  # noqa: E402

# Official Ultralytics weights URLs
MODEL_URLS: dict[str, str] = {
    "yolov8n.pt": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt",
    "yolov8s.pt": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt",
    "yolov8m.pt": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8m.pt",
}

PROFILE_ASSETS = {
    "lite": ["yolov8n.pt"],
    "balanced": ["yolov8s.pt"],
    "full": ["yolov8m.pt"],
}


def download_file(url: str, dest: Path) -> bool:
    """Download url to dest with progress indication."""
    print(f"Downloading {url} -> {dest.name}...")
    try:
        def reporthook(block_num: int, block_size: int, total_size: int) -> None:
            if total_size > 0:
                percent = min(100.0, (block_num * block_size / total_size) * 100)
                sys.stdout.write(f"\r  {dest.name}: {percent:.1f}% ({total_size / (1024*1024):.1f} MB)")
                sys.stdout.flush()

        urlretrieve(url, str(dest), reporthook=reporthook)
        print("\n  Done.")
        return True
    except Exception as exc:
        print(f"\n  Download failed: {exc}", file=sys.stderr)
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="lite", choices=sorted(PROFILE_ASSETS))
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    try:
        config = AppConfig.load(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    models_dir = config.paths.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)

    print(f"Models directory: {models_dir}")
    print(f"Target profile: '{args.profile}'")

    assets = PROFILE_ASSETS[args.profile]
    success = True
    for asset in assets:
        target_path = models_dir / asset
        if target_path.is_file():
            print(f"  [ OK ] {asset} already exists ({target_path.stat().st_size} bytes)")
            continue

        url = MODEL_URLS.get(asset)
        if not url:
            print(f"  [ !! ] No download URL configured for {asset}")
            success = False
            continue

        if not download_file(url, target_path):
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
