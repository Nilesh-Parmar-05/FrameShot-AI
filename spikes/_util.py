"""Shared helpers for the Phase 0 spike scripts.

The spikes are deliberately standalone: they never import ``frameshot`` so they
can run before the package is complete. Run everything from the repo root:

    python spikes/spike_vlc.py
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "spikes" / "out"


def _force_utf8_stdout() -> None:
    """Spike output contains IPA glyphs and section signs; cp1252 cannot encode them."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(OSError, ValueError):
            reconfigure(encoding="utf-8", errors="replace")


_force_utf8_stdout()

# Same defaults as config.example.yaml; override with env vars if you use
# a different port or password.
DEFAULT_HOST = os.environ.get("FRAMESHOT_VLC_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("FRAMESHOT_VLC_PORT", "8080"))
DEFAULT_PASSWORD = os.environ.get("FRAMESHOT_VLC_PASSWORD", "frameshot")


class SpikeError(RuntimeError):
    """A spike could not run to completion."""


# ---------------------------------------------------------------- output


def banner(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def step(text: str) -> None:
    print(f"\n-- {text}")


def verdict(ok: bool, message: str) -> bool:
    """Print a PASS/FAIL line and return the flag for accumulation."""
    print(f"\n[{'PASS' if ok else 'FAIL'}] {message}")
    return ok


def die(message: str, code: int = 1) -> NoReturn:
    print(f"\n[FAIL] {message}", file=sys.stderr)
    raise SystemExit(code)


def ensure_out_dir() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR


# ---------------------------------------------------------------- time


def format_ms(milliseconds: float | int) -> str:
    """Format milliseconds as ``HH:MM:SS.mmm``."""
    total = max(int(milliseconds), 0)
    hours, remainder = divmod(total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def parse_timecode(value: str) -> int:
    """Parse ``83.4``, ``1:23.5``, ``00:01:23.400`` or ``834ms`` into ms."""
    text = value.strip().lower()
    if not text:
        raise ValueError("empty timecode")

    if text.endswith("ms"):
        return int(round(float(text[:-2])))
    if text.endswith("s"):
        text = text[:-1]

    if ":" in text:
        parts = text.split(":")
        if len(parts) > 3:
            raise ValueError(f"unrecognised timecode: {value!r}")
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
        return int(round(seconds * 1_000))

    return int(round(float(text) * 1_000))


# ---------------------------------------------------------------- VLC HTTP


def vlc_url(host: str, port: int, path: str) -> str:
    return f"http://{host}:{port}/{path.lstrip('/')}"


def vlc_get(
    host: str,
    port: int,
    password: str,
    path: str,
    timeout: float = 3.0,
) -> Any:
    """GET a VLC HTTP endpoint and return the raw ``requests.Response``."""
    try:
        import requests
    except ImportError:
        die("the 'requests' package is missing - run: pip install -r requirements.txt")

    url = vlc_url(host, port, path)
    try:
        return requests.get(url, auth=("", password), timeout=timeout)
    except requests.ConnectionError:
        die(
            f"no response from {url}\n"
            "  Is VLC running with the Web interface enabled?\n"
            "  Start it with:\n"
            '    & "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe" --extraintf=http '
            f"--http-host={host} --http-port={port} --http-password={password}"
        )
    except requests.RequestException as exc:
        die(f"request to {url} failed: {exc}")


def vlc_json(
    host: str,
    port: int,
    password: str,
    path: str,
    timeout: float = 3.0,
) -> dict[str, Any]:
    response = vlc_get(host, port, password, path, timeout)
    if response.status_code == 401:
        die("HTTP 401 Unauthorized - the password does not match VLC's Lua HTTP password")
    if response.status_code != 200:
        die(f"HTTP {response.status_code} for /{path.lstrip('/')}")
    try:
        data = response.json()
    except ValueError:
        die(f"response for /{path.lstrip('/')} was not JSON")
    return data  # type: ignore[no-any-return]


# ---------------------------------------------------------------- files


def files_newer_than(directory: Path, since: float) -> list[Path]:
    """Images in ``directory`` modified after the ``since`` epoch timestamp."""
    if not directory.is_dir():
        return []
    found = [
        path for path in directory.iterdir() if path.is_file() and path.stat().st_mtime > since
    ]
    return sorted(found, key=lambda p: p.stat().st_mtime)


def wait_for_new_file(
    directory: Path,
    since: float,
    timeout_s: float = 3.0,
    poll_s: float = 0.02,
) -> tuple[Path | None, float]:
    """Poll for a new file; return ``(path, latency_ms)``."""
    start = time.perf_counter()
    deadline = start + timeout_s
    while time.perf_counter() < deadline:
        found = files_newer_than(directory, since)
        if found:
            return found[-1], (time.perf_counter() - start) * 1_000
        time.sleep(poll_s)
    return None, (time.perf_counter() - start) * 1_000
