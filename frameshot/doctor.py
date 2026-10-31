"""Environment self-check: ``python -m frameshot doctor``.

Answers the questions that block the Phase 0 spikes without needing the rest
of the app to work: is VLC reachable, is ffmpeg installed, is the database
writable, which models are present?
"""

from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from frameshot.config import AppConfig, ConfigError
from frameshot.database import Database
from frameshot.utils import format_ms

REQUIRED = "required"
OPTIONAL = "optional"

VLC_EXECUTABLE_CANDIDATES = (
    Path(r"C:\Program Files\VideoLAN\VLC\vlc.exe"),
    Path(r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"),
)

MODEL_MARKERS = {
    "YOLOv8": ("yolov8n.pt", "yolov8s.pt", "yolov8m.pt"),
    "Florence-2": ("florence-2-base",),
    "BLIP-2": ("blip2-opt-2.7b", "blip2-opt-2.7b-int8"),
    "CLIP": ("clip-vit-b32", "clip-vit-base-patch32"),
}


@dataclass(slots=True)
class Check:
    name: str
    ok: bool
    detail: str
    kind: str = REQUIRED


def run_doctor(config: AppConfig) -> int:
    """Print a report; return a process exit code (0 = all required checks pass)."""
    checks = [
        _check_python(),
        _check_ffmpeg(),
        _check_vlc_binary(),
        _check_directories(config),
        _check_database(config),
        _check_vlc_http(config),
        _check_models(config),
        _check_optional_dependency("PyQt6 (overlay UI)", "PyQt6"),
        _check_optional_dependency("nltk (word analysis)", "nltk"),
        _check_optional_dependency("ultralytics (vision)", "ultralytics"),
    ]

    width = max(len(c.name) for c in checks)
    print(
        f"FrameShot-AI doctor  |  {platform.system()} {platform.release()}  |  {sys.version.split()[0]}"
    )
    print("-" * (width + 64))
    for check in checks:
        status = "[ OK ]" if check.ok else ("[ !! ]" if check.kind == REQUIRED else "[ -- ]")
        print(f"{status} {check.name.ljust(width)}  {check.detail}")

    failed = [c for c in checks if not c.ok and c.kind == REQUIRED]
    print("-" * (width + 64))
    if failed:
        print(f"{len(failed)} required check(s) failed.")
        return 1
    print("All required checks passed.")
    return 0


# ---------------------------------------------------------------- checks


def _check_python() -> Check:
    version = sys.version_info
    ok = version >= (3, 11)
    return Check("python >= 3.11", ok, f"{version.major}.{version.minor}.{version.micro}")


def _check_ffmpeg() -> Check:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return Check("ffmpeg + ffprobe", True, Path(ffmpeg).parent.as_posix())
    missing = ", ".join(
        name for name, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not path
    )
    return Check("ffmpeg + ffprobe", False, f"missing from PATH: {missing}")


def _check_vlc_binary() -> Check:
    for candidate in VLC_EXECUTABLE_CANDIDATES:
        if candidate.is_file():
            return Check("VLC executable", True, str(candidate))
    on_path = shutil.which("vlc")
    if on_path:
        return Check("VLC executable", True, on_path)
    return Check("VLC executable", False, "not found; install VLC 3.x/4.x")


def _check_directories(config: AppConfig) -> Check:
    paths = config.paths
    targets = [
        paths.models_dir,
        paths.snapshot_dir,
        paths.log_dir,
        paths.database.parent,
    ]
    try:
        for target in targets:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".frameshot_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
    except OSError as exc:
        return Check("data directories writable", False, str(exc))
    return Check("data directories writable", True, f"{len(targets)} directories")


def _check_database(config: AppConfig) -> Check:
    try:
        db = Database(config.paths.database)
    except Exception as exc:  # noqa: BLE001 - any failure here is a failed check
        return Check("SQLite database", False, f"{type(exc).__name__}: {exc}")
    try:
        tables = db.table_names()
        return Check("SQLite database", True, f"{len(tables)} tables, schema v{db.schema_version}")
    finally:
        db.close()


def _check_vlc_http(config: AppConfig) -> Check:
    try:
        import requests
    except ImportError:
        return Check(
            "VLC HTTP interface", False, "requests not installed (pip install -r requirements.txt)"
        )

    vlc = config.vlc
    url = f"http://{vlc.host}:{vlc.port}/requests/status.json"
    try:
        response = requests.get(url, auth=("", vlc.password), timeout=vlc.request_timeout_s)
    except requests.ConnectionError:
        return Check(
            "VLC HTTP interface",
            False,
            f"no response on {vlc.host}:{vlc.port} - is VLC running with the Web interface enabled?",
        )
    except requests.RequestException as exc:
        return Check("VLC HTTP interface", False, str(exc))

    if response.status_code == 401:
        return Check("VLC HTTP interface", False, "401 Unauthorized - wrong Lua HTTP password")
    if response.status_code != 200:
        return Check("VLC HTTP interface", False, f"HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError:
        return Check("VLC HTTP interface", False, "response was not JSON")

    state = data.get("state", "?")
    position = format_ms(int(data.get("time", 0)))
    filename = (
        data.get("information", {})
        .get("category", {})
        .get("meta", {})
        .get("filename", "(no media)")
    )
    return Check("VLC HTTP interface", True, f"state={state} pos={position} file={filename}")


def _check_models(config: AppConfig) -> Check:
    models_dir = config.paths.models_dir
    if not models_dir.is_dir():
        return Check("model files", False, f"{models_dir} does not exist", kind=OPTIONAL)

    entries = {p.name for p in models_dir.iterdir() if p.is_file() and not p.name.startswith(".")}
    found = [label for label, markers in MODEL_MARKERS.items() if entries.intersection(markers)]
    if not entries:
        return Check(
            "model files", False, "none downloaded (scripts/download_models.py)", kind=OPTIONAL
        )
    detail = f"found: {', '.join(found)}" if found else f"{len(entries)} file(s), no known models"
    return Check("model files", bool(found), detail, kind=OPTIONAL)


def _check_optional_dependency(label: str, module: str) -> Check:
    from importlib.util import find_spec

    ok = find_spec(module) is not None
    return Check(label, ok, "installed" if ok else "not installed", kind=OPTIONAL)


def init_config(target: Path) -> int:
    """Copy the tracked example config to a user config file."""
    template = Path(__file__).resolve().parent.parent / "config.example.yaml"
    if target.exists():
        print(f"refusing to overwrite existing file: {target}")
        return 1
    if not template.is_file():
        print(f"example config not found: {template}")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, target)
    print(f"wrote {target}")
    return 0


__all__ = ["Check", "ConfigError", "init_config", "run_doctor"]
