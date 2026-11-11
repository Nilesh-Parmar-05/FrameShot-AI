"""Windows native window tracker and focus manager for VLC and Overlay.

Ensures that the FrameShot overlay is strictly limited to VLC and automatically
hides whenever the user switches away from VLC to another application.
"""

from __future__ import annotations

import logging
import platform
import sys

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    # Configure ctypes function signatures for 64-bit Windows safety
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL

    GA_ROOT = 2
    GWLP_HWNDPARENT = -8

    # SetWindowLongPtr signature
    if sys.maxsize > 2**32:
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HWND]
        user32.SetWindowLongPtrW.restype = wintypes.HWND
        _set_window_long = user32.SetWindowLongPtrW
    else:
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HWND]
        user32.SetWindowLongW.restype = wintypes.HWND
        _set_window_long = user32.SetWindowLongW


def get_foreground_hwnd() -> int:
    """Return the handle of the current foreground window."""
    if not IS_WINDOWS:
        return 0
    return int(user32.GetForegroundWindow() or 0)


def get_root_hwnd(hwnd: int) -> int:
    """Return the root ancestor of a window handle."""
    if not IS_WINDOWS or not hwnd:
        return hwnd
    root = user32.GetAncestor(hwnd, GA_ROOT)
    return int(root) if root else hwnd


def get_window_title(hwnd: int) -> str:
    """Return the title text of a window."""
    if not IS_WINDOWS or not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def get_window_class(hwnd: int) -> str:
    """Return the window class name."""
    if not IS_WINDOWS or not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Return (left, top, right, bottom) coordinates of a window."""
    if not IS_WINDOWS or not hwnd:
        return None
    rect = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right, rect.bottom)
    return None


def is_vlc_window(hwnd: int) -> bool:
    """Check if the given window handle belongs to VLC media player."""
    if not IS_WINDOWS or not hwnd:
        return False
    if not user32.IsWindow(hwnd):
        return False

    title = get_window_title(hwnd)
    if "VLC media player" in title or title.endswith(" - VLC"):
        return True

    cls_name = get_window_class(hwnd)
    return bool(
        ("Qt5QWindowIcon" in cls_name or "Qt6QWindowIcon" in cls_name or "VLC" in cls_name)
        and ("VLC" in title or "vlc" in title.lower())
    )


def find_vlc_window() -> tuple[int, tuple[int, int, int, int]] | None:
    """Find the main VLC window handle and its screen rectangle."""
    if not IS_WINDOWS:
        return None

    results: list[tuple[int, tuple[int, int, int, int]]] = []

    def enum_proc(hwnd: int, lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        if is_vlc_window(hwnd):
            r = get_window_rect(hwnd)
            if r is not None and (r[2] - r[0] > 100) and (r[3] - r[1] > 100):
                results.append((hwnd, r))
                return False  # found
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

    if results:
        return results[0]
    return None


def is_vlc_or_overlay_focused(overlay_hwnd: int, vlc_hwnd: int | None = None) -> bool:
    """Return True if either VLC or the overlay window currently holds foreground focus."""
    if not IS_WINDOWS:
        return True

    fg = get_foreground_hwnd()
    if not fg:
        return False

    root_fg = get_root_hwnd(fg)

    # 1. Is the foreground window our overlay?
    if overlay_hwnd and (fg == overlay_hwnd or root_fg == overlay_hwnd):
        return True

    # 2. Is the foreground window the known VLC handle?
    if vlc_hwnd and (fg == vlc_hwnd or root_fg == vlc_hwnd):
        return True

    # 3. Check if the foreground window is any VLC window
    return bool(is_vlc_window(fg) or is_vlc_window(root_fg))


def set_window_owner(overlay_hwnd: int, owner_hwnd: int) -> bool:
    """Set Win32 owner window hierarchy so overlay stays linked to owner."""
    if not IS_WINDOWS or not overlay_hwnd or not owner_hwnd:
        return False
    try:
        _set_window_long(overlay_hwnd, GWLP_HWNDPARENT, owner_hwnd)
        return True
    except Exception as exc:
        logger.debug("Could not set window owner: %s", exc)
        return False
