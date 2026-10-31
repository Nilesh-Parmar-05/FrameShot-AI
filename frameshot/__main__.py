"""CLI entry point: ``python -m frameshot``.

python -m frameshot                       # run the app (core engine pending)
python -m frameshot doctor                # verify environment + VLC link
python -m frameshot init-config           # write ./config.yaml from the example
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from frameshot import __version__
from frameshot.app import FrameShotApp
from frameshot.config import AppConfig, ConfigError
from frameshot.doctor import init_config, run_doctor
from frameshot.logging_setup import configure_logging

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="frameshot",
        description="Smart video companion for VLC: offline word assist and frame insight.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=("run", "doctor", "init-config"),
        help="what to do (default: run)",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="path to config.yaml (default: ./config.yaml if present)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=LOG_LEVELS,
        help="console log level (default: INFO)",
    )
    parser.add_argument("--version", action="version", version=f"frameshot {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    raise SystemExit(run(argv))


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "init-config":
        target = args.config if args.config is not None else Path("config.yaml")
        return init_config(target)

    try:
        config = AppConfig.load(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    if args.command == "doctor":
        return run_doctor(config)

    configure_logging(args.log_level, log_dir=config.paths.log_dir)
    app = FrameShotApp(config)
    try:
        app.start()
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    finally:
        app.stop()
    return 0


if __name__ == "__main__":
    main()
