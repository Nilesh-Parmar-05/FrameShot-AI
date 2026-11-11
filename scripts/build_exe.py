"""Standalone executable packaging script for FrameShot-AI (Task 4.10).

Uses PyInstaller to bundle FrameShot-AI into a standalone Windows directory distribution
in dist/FrameShot-AI/, bundling Python, PyQt6, Ultralytics, PyTorch, NLTK, SQLite DBs,
and configuration templates.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENTRY_POINT = ROOT_DIR / "frameshot" / "__main__.py"
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
SPEC_FILE = ROOT_DIR / "frameshot.spec"


def generate_spec_file() -> None:
    """Generate frameshot.spec with appropriate paths, hidden imports, and datas."""
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

root_dir = Path(r'{ROOT_DIR}')

# Collect data files
datas = [
    (str(root_dir / 'config.example.yaml'), '.'),
]

# Include offline word frequency database if present
freq_db = root_dir / 'data' / 'word_frequency.db'
if freq_db.is_file():
    datas.append((str(freq_db), 'data'))

# Include models if present
models_dir = root_dir / 'models'
if models_dir.is_dir():
    for m in models_dir.glob('*.pt'):
        datas.append((str(m), 'models'))

# Collect ultralytics and nltk data
datas += collect_data_files('ultralytics')
datas += collect_data_files('nltk')

hiddenimports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'frameshot',
    'frameshot.app',
    'frameshot.config',
    'frameshot.database',
    'frameshot.events',
    'frameshot.logging_setup',
    'frameshot.vlc_controller',
    'frameshot.subtitle_parser',
    'frameshot.word_analyzer',
    'frameshot.vision_pipeline',
    'frameshot.overlay_manager',
    'frameshot.window_tracker',
    'frameshot.online.enrichment_service',
    'frameshot.online.wikipedia_client',
    'frameshot.online.wiktionary_client',
    'frameshot.ui.theme',
    'frameshot.ui.overlay_window',
    'frameshot.ui.word_panel',
    'frameshot.ui.vision_panel',
    'frameshot.ui.product_panel',
    'frameshot.ui.journal_window',
    'frameshot.ui.tray_icon',
    'ultralytics',
    'torch',
    'torchvision',
    'cv2',
    'PIL',
    'pysubs2',
    'requests',
    'yaml',
    'psutil',
]

a = Analysis(
    [r'{ENTRY_POINT}'],
    pathex=[r'{ROOT_DIR}'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FrameShot-AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FrameShot-AI',
)
"""
    SPEC_FILE.write_text(spec_content, encoding="utf-8")
    print(f"Generated spec file: {SPEC_FILE}")


def build_executable() -> int:
    """Run PyInstaller with the generated spec file."""
    print("=" * 72)
    print(" FRAMESHOT-AI PACKAGING: PYINSTALLER BUILD (TASK 4.10)")
    print("=" * 72)

    generate_spec_file()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_FILE),
    ]

    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), check=False)

    if result.returncode != 0:
        print(f"\n[ERROR] PyInstaller failed with exit code {result.returncode}")
        return result.returncode

    dist_app = DIST_DIR / "FrameShot-AI"
    exe_path = dist_app / "FrameShot-AI.exe"

    if exe_path.is_file():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 72)
        print(" [SUCCESS] FrameShot-AI build complete!")
        print(f" Output Location : {dist_app}")
        print(f" Executable      : {exe_path} ({size_mb:.2f} MB)")
        print("=" * 72)
        return 0
    else:
        print(f"\n[ERROR] Expected output executable not found: {exe_path}")
        return 1


if __name__ == "__main__":
    sys.exit(build_executable())
