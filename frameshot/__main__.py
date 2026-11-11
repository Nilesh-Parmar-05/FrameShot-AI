"""CLI entry point: ``python -m frameshot``.

python -m frameshot                       # run the app and monitor VLC
python -m frameshot --once                # process single pause event and exit
python -m frameshot doctor                # verify environment + VLC link
python -m frameshot init-config           # write ./config.yaml from the example
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from frameshot import __version__
from frameshot.app import AppState, FrameShotApp
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
        "--once",
        action="store_true",
        help="wait for a single pause event, process word assist & snapshot, then exit",
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="disable Qt overlay UI and run purely in terminal mode",
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

    ui_enabled = not args.no_ui
    qapp = None

    if ui_enabled:
        try:
            from PyQt6.QtCore import QTimer
            from PyQt6.QtWidgets import QApplication

            qapp = QApplication.instance()
            if qapp is None:
                qapp = QApplication(list(argv) if argv is not None else sys.argv)
                qapp.setApplicationName("FrameShot-AI")
                qapp.setQuitOnLastWindowClosed(False)
        except Exception:
            ui_enabled = False

    app = FrameShotApp(config, run_once=args.once, enable_ui=ui_enabled)

    if ui_enabled and app.overlay_manager is not None:
        app.overlay_manager.initialize_gui()

    try:
        app.start()
        if args.once:
            app.wait_for_pause_processed()
        elif qapp is not None:
            # Wake Qt periodically so Python signal handlers (Ctrl+C) can be processed
            import signal

            signal.signal(signal.SIGINT, lambda *_: qapp.quit())
            timer = QTimer()
            timer.timeout.connect(lambda: None)
            timer.start(500)
            qapp.exec()
        else:
            while app.state != AppState.IDLE:
                time.sleep(0.2)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    finally:
        app.stop()
    return 0


if __name__ == "__main__":
    main()
