"""Overlay window lifecycle, positioning, and EventBus signal bridging.

Tasks 2.12-2.17 in ``tasks.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from frameshot.config import AppConfig
    from frameshot.events import EventBus
    from frameshot.vision_pipeline import FrameAnalysis
    from frameshot.word_analyzer import WordResult

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from frameshot.events import Event
from frameshot.ui.window_tracker import (
    find_vlc_window,
    is_vlc_or_overlay_focused,
    set_window_owner,
)

logger = logging.getLogger(__name__)


class _BridgeSignals(QObject):
    """Qt signal bridge used to safely dispatch worker thread events to the Qt GUI thread."""

    show_signal = pyqtSignal(object)  # dict payload
    hide_signal = pyqtSignal()
    toggle_signal = pyqtSignal()


class OverlayManager:
    """Coordinates the native overlay window and system tray icon."""

    def __init__(
        self,
        config: AppConfig,
        bus: EventBus | None = None,
        database: Any = None,
        enrichment_service: Any = None,
    ) -> None:
        self.config = config
        self.bus = bus
        self.database = database
        self.enrichment_service = enrichment_service
        self._visible: bool = False
        self._window: Any = None
        self._tray: Any = None
        self._journal_window: Any = None
        self._is_active: bool = False
        self._vlc_hwnd: int | None = None
        self._last_vlc_rect: tuple[int, int, int, int] | None = None

        self._signals = _BridgeSignals()
        self._signals.show_signal.connect(self._on_show_signal)
        self._signals.hide_signal.connect(self._on_hide_signal)
        self._signals.toggle_signal.connect(self._on_toggle_signal)

        self._focus_timer = QTimer()
        self._focus_timer.setInterval(100)
        self._focus_timer.timeout.connect(self._on_focus_tick)

        if self.bus is not None:
            self._subscribe_events()

    def _subscribe_events(self) -> None:
        if self.bus is None:
            return
        self.bus.subscribe(Event.PLAYBACK_RESUMED, lambda msg: self.hide())

    def initialize_gui(self) -> None:
        """Create the OverlayWindow and TrayIcon on the Qt thread."""
        from PyQt6.QtWidgets import QApplication

        if QApplication.instance() is None:
            logger.debug("No QApplication instance; GUI initialization deferred or disabled")
            return

        from frameshot.ui.overlay_window import OverlayWindow
        from frameshot.ui.tray_icon import TrayIcon

        if self._window is None:
            self._window = OverlayWindow(self.config, database=self.database)
        if self._tray is None:
            self._tray = TrayIcon(
                self.config,
                on_toggle_overlay=self.toggle,
                on_quit=self._on_quit,
                on_toggle_online=self.set_online_enabled,
                on_open_journal=self.open_journal,
            )
            self._tray.show()

    @property
    def visible(self) -> bool:
        return self._visible

    # ------------------------------------------------------------ actions

    def open_journal(self) -> None:
        """Open the Vocabulary Journal window."""
        if self.database is None:
            return
        from frameshot.ui.journal_window import JournalWindow

        if self._journal_window is None:
            self._journal_window = JournalWindow(self.database)
        self._journal_window.refresh_entries()
        self._journal_window.show()
        self._journal_window.raise_()
        self._journal_window.activateWindow()

    def show_analysis(
        self,
        words: list[WordResult],
        analysis: FrameAnalysis | None = None,
        subtitle_text: str | None = None,
        image_path: Path | str | None = None,
        movie_title: str | None = None,
        timestamp_ms: int | None = None,
    ) -> None:
        """Dispatch show request to the Qt GUI thread."""
        payload = {
            "words": words,
            "analysis": analysis,
            "subtitle_text": subtitle_text,
            "image_path": image_path,
            "movie_title": movie_title,
            "timestamp_ms": timestamp_ms,
        }
        self._signals.show_signal.emit(payload)

    def hide(self) -> None:
        """Hide the overlay within the PRD auto-dismiss budget."""
        self._signals.hide_signal.emit()

    def toggle(self) -> None:
        """Toggle overlay visibility from hotkey or tray."""
        self._signals.toggle_signal.emit()

    def update_position(self) -> None:
        """Re-anchor overlay position."""
        if self._window is not None:
            self._window.position_on_screen()

    def set_online_enabled(self, enabled: bool) -> None:
        """Dynamically toggle online enrichment service state."""
        if self.enrichment_service is not None:
            self.enrichment_service.set_enabled(enabled)

    # ------------------------------------------------------------ Qt slots

    def _on_show_signal(self, payload: dict[str, Any]) -> None:
        self.initialize_gui()
        words = payload.get("words", [])
        analysis = payload.get("analysis")
        subtitle = payload.get("subtitle_text")
        image = payload.get("image_path")
        movie_title = payload.get("movie_title")
        timestamp_ms = payload.get("timestamp_ms")

        self._is_active = True
        vlc_info = find_vlc_window()
        vlc_rect = None
        if vlc_info:
            self._vlc_hwnd, vlc_rect = vlc_info
            self._last_vlc_rect = vlc_rect
            if self._window is not None:
                set_window_owner(int(self._window.winId()), self._vlc_hwnd)

        if self._window is not None:
            self._window.update_results(
                subtitle_text=subtitle,
                words=words,
                image_path=image,
                analysis=analysis,
                enrichment_service=self.enrichment_service,
                movie_title=movie_title,
                timestamp_ms=timestamp_ms,
            )

            overlay_hwnd = int(self._window.winId()) if self._window else 0
            is_focused = not self.config.overlay.vlc_only or is_vlc_or_overlay_focused(
                overlay_hwnd, self._vlc_hwnd
            )

            if is_focused:
                self._window.show_animated(vlc_rect)
                self._visible = True
                if self.bus is not None:
                    self.bus.publish(Event.OVERLAY_SHOWN)
            else:
                self._window.hide()
                self._visible = False

            if self.config.overlay.vlc_only:
                self._focus_timer.start()

    def _on_focus_tick(self) -> None:
        """Poll foreground window to guarantee overlay is visible ONLY when VLC is focused."""
        if not self._is_active or self._window is None:
            return

        if not self.config.overlay.vlc_only:
            return

        overlay_hwnd = int(self._window.winId()) if self._window else 0
        is_focused = is_vlc_or_overlay_focused(overlay_hwnd, self._vlc_hwnd)

        if is_focused:
            vlc_info = find_vlc_window()
            vlc_rect = None
            if vlc_info:
                self._vlc_hwnd, vlc_rect = vlc_info

            if not self._window.isVisible():
                self._window.show_animated(vlc_rect)
                self._visible = True
                if self.bus is not None:
                    self.bus.publish(Event.OVERLAY_SHOWN)
            elif vlc_rect and vlc_rect != self._last_vlc_rect:
                self._last_vlc_rect = vlc_rect
                self._window.position_on_screen(vlc_rect)
        else:
            # User switched to another window (browser, IDE, desktop, etc.)
            if self._window.isVisible():
                self._window.hide()
                self._visible = False

    def _on_hide_signal(self) -> None:
        self._is_active = False
        self._focus_timer.stop()
        if self._window is not None and self._visible:
            if self.config.overlay.auto_dismiss:
                self._window.hide_animated()
            else:
                self._window.hide()
            self._visible = False
            if self.bus is not None:
                self.bus.publish(Event.OVERLAY_HIDDEN)

    def _on_toggle_signal(self) -> None:
        if self._visible:
            self._on_hide_signal()
        elif self._window is not None:
            vlc_info = find_vlc_window()
            vlc_rect = vlc_info[1] if vlc_info else None
            self._window.show_animated(vlc_rect)
            self._visible = True
            self._is_active = True
            if self.config.overlay.vlc_only:
                self._focus_timer.start()
            if self.bus is not None:
                self.bus.publish(Event.OVERLAY_SHOWN)

    def _on_quit(self) -> None:
        self._focus_timer.stop()
        from PyQt6.QtWidgets import QApplication

        if self._window is not None:
            self._window.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()
