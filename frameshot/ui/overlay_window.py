"""Frameless, always-on-top, semi-transparent overlay window.

Status: stub — tasks 2.11-2.12, 2.20. Spike 0.10 establishes that PyQt6 can do
frameless + translucent + always-on-top + click-through on Windows.

Implementation notes for later:

* ``Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint``
* ``Qt.WidgetAttribute.WA_TranslucentBackground`` with a painted
  rounded-rect background for the glassmorphism look
* ``WA_TransparentForMouseEvents`` while showing results so clicks reach VLC
"""
