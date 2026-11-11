"""System tray icon and context menu for FrameShot-AI.

Task 2.18 in ``tasks.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frameshot.config import AppConfig

from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from frameshot.ui.theme import Theme


def create_tray_pixmap() -> QPixmap:
    """Create a high-contrast circular tray icon pixmap."""
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Accent filled circle
    painter.setBrush(QColor(Theme.ACCENT_DEFAULT))
    painter.setPen(QColor(Theme.BG_BASE))
    painter.drawEllipse(4, 4, 56, 56)

    # "FS" logo text
    painter.setPen(QColor(Theme.TEXT_INVERSE))
    painter.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
    painter.drawText(pix.rect(), 0x0084, "FS")  # Qt.AlignmentFlag.AlignCenter
    painter.end()

    return pix


class TrayIcon(QSystemTrayIcon):
    """System tray icon allowing background control and status monitoring."""

    def __init__(
        self,
        config: AppConfig,
        on_toggle_overlay: Callable[[], None],
        on_quit: Callable[[], None],
        on_toggle_online: Callable[[bool], None] | None = None,
        on_open_journal: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        icon = QIcon(create_tray_pixmap())
        super().__init__(icon, parent)
        self.config = config
        self._on_toggle = on_toggle_overlay
        self._on_quit = on_quit
        self._on_toggle_online = on_toggle_online
        self._on_open_journal = on_open_journal

        self.setToolTip("FrameShot: Smart VLC Companion")
        self._init_menu()

    def _init_menu(self) -> None:
        menu = QMenu()

        title_action = QAction("FrameShot", menu)
        title_action.setEnabled(False)
        menu.addAction(title_action)

        menu.addSeparator()

        toggle_action = QAction("Toggle Overlay (Ctrl+Shift+F)", menu)
        toggle_action.triggered.connect(self._on_toggle)
        menu.addAction(toggle_action)

        if self._on_open_journal is not None:
            journal_action = QAction("Vocabulary Journal...", menu)
            journal_action.triggered.connect(self._on_open_journal)
            menu.addAction(journal_action)

        # Difficulty submenu
        diff_menu = menu.addMenu("Difficulty Level")
        current_level = self.config.analysis.difficulty_level.value

        if diff_menu is not None:
            for level in ("beginner", "intermediate", "advanced"):
                act = QAction(level.capitalize(), diff_menu)
                act.setCheckable(True)
                act.setChecked(level == current_level)
                act.triggered.connect(
                    lambda checked, target_level=level: self._set_difficulty(target_level)
                )
                diff_menu.addAction(act)

        # Online enrichment toggle
        online_action = QAction("Online Enrichment", menu)
        online_action.setCheckable(True)
        online_action.setChecked(self.config.online.enabled)
        online_action.triggered.connect(self._handle_toggle_online)
        menu.addAction(online_action)

        menu.addSeparator()

        quit_action = QAction("Exit", menu)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_toggle()

    def _set_difficulty(self, level_str: str) -> None:
        from frameshot.config import DifficultyLevel

        self.config.analysis.difficulty_level = DifficultyLevel(level_str)
        self.showMessage(
            "FrameShot-AI",
            f"Vocabulary difficulty set to: {level_str.capitalize()}",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def _handle_toggle_online(self, checked: bool) -> None:
        self.config.online.enabled = checked
        if self._on_toggle_online is not None:
            self._on_toggle_online(checked)
        status_str = "Enabled" if checked else "Disabled"
        self.showMessage(
            "FrameShot-AI",
            f"Online Enrichment is now {status_str}.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )
