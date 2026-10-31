"""Download the offline models listed in tech-stack.md §6.

Status: stub — task 2.1. Only the YOLO weights are reachable today (Ultralytics
downloads them on first use). Captioning and CLIP models need an explicit URL
decision from spike 0.9 first.

    python scripts/download_models.py --profile lite
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frameshot.config import AppConfig, ConfigError  # noqa: E402

PROFILE_ASSETS = {
    "lite": ["yolov8n.pt"],
    "balanced": ["yolov8s.pt", "florence-2-base"],
    "full": ["yolov8m.pt", "blip2-opt-2.7b-int8", "clip-vit-b32"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="lite", choices=sorted(PROFILE_ASSETS))
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    try:
        config = AppConfig.load(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    config.paths.models_dir.mkdir(parents=True, exist_ok=True)
    print(f"models directory: {config.paths.models_dir}")
    print(f"profile '{args.profile}' needs:")
    for asset in PROFILE_ASSETS[args.profile]:
        print(f"  - {asset}")
    print("\nNot implemented yet (tasks.md 2.1). Spike 0.9 decides the captioning model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
