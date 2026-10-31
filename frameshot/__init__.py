"""FrameShot-AI — a smart video companion for VLC.

Public entry points live in :mod:`frameshot.__main__`. Importing this package
must stay cheap: heavy optional dependencies (PyQt6, torch, nltk) are imported
lazily inside the modules that need them.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
