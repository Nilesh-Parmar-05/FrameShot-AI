"""Frameless, always-on-top, translucent glassmorphic overlay window.

Tasks 2.11-2.12, 2.20 in ``tasks.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from frameshot.config import AppConfig
    from frameshot.vision_pipeline import FrameAnalysis
    from frameshot.word_analyzer import WordResult

from PyQt6.QtCore import QPoint, QPropertyAnimation, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from frameshot.ui.product_panel import ProductPanel
from frameshot.ui.theme import compile_stylesheet
from frameshot.ui.vision_panel import VisionPanel
from frameshot.ui.word_panel import WordPanel


class OverlayWindow(QWidget):
    """Semi-transparent, always-on-top companion window positioned above VLC."""

    def __init__(
        self,
        config: AppConfig,
        database: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.database = database
        self._drag_pos: QPoint | None = None

        self._init_window()
        self._init_layout()
        self._init_animation()

    def _init_window(self) -> None:
        self.setWindowTitle("FrameShot-AI Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Default size: 450px wide, anchored on right side
        self.resize(450, 680)
        self.position_on_screen()

    def _init_layout(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Central Glass Card
        self.central_card = QFrame(self)
        self.central_card.setObjectName("centralCard")
        self.central_card.setStyleSheet(compile_stylesheet())

        # Shadow effect (subtle directional depth)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 140))
        shadow.setOffset(0, 4)
        self.central_card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.central_card)
        card_layout.setContentsMargins(14, 12, 14, 14)
        card_layout.setSpacing(10)

        # Top Bar: App Title + Media Indicator + Close Button
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(2, 0, 2, 0)

        title_label = QLabel("FrameShot")
        title_label.setObjectName("appTitle")
        top_bar.addWidget(title_label)

        top_bar.addStretch()

        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Dismiss Overlay (Esc)")
        close_btn.clicked.connect(self.hide_animated)
        top_bar.addWidget(close_btn)

        card_layout.addLayout(top_bar)

        # Content Tabs: Words, Scene & Shop
        self.tabs = QTabWidget()
        self.word_panel = WordPanel(database=self.database)
        self.vision_panel = VisionPanel()
        self.product_panel = ProductPanel()

        self.tabs.addTab(self.word_panel, "Words")
        self.tabs.addTab(self.vision_panel, "Scene")
        self.tabs.addTab(self.product_panel, "Shop")

        card_layout.addWidget(self.tabs)
        main_layout.addWidget(self.central_card)

    def _init_animation(self) -> None:
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(160)

    def position_on_screen(self, vlc_rect: tuple[int, int, int, int] | None = None) -> None:
        """Position window anchored to VLC window geometry or desktop right side with DPI awareness."""
        from PyQt6.QtWidgets import QApplication

        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else None
        dpr = screen.devicePixelRatio() if screen is not None else 1.0

        if vlc_rect is not None:
            # Win32 GetWindowRect returns physical pixels; convert to logical pixels for Qt
            p_left, p_top, p_right, p_bottom = vlc_rect
            left = int(p_left / dpr)
            top = int(p_top / dpr)
            right = int(p_right / dpr)
            bottom = int(p_bottom / dpr)

            vlc_w = right - left
            vlc_h = bottom - top

            if vlc_w > 300 and vlc_h > 200:
                # Dock neatly inside the right margin of VLC
                target_w = min(460, max(380, int(vlc_w * 0.40)))
                target_h = max(320, vlc_h - 70)
                target_x = right - target_w - 18
                target_y = top + 42

                # Clamp to available screen geometry so it never goes off-screen
                if avail is not None:
                    target_w = min(target_w, avail.width() - 40)
                    target_h = min(target_h, avail.height() - 60)
                    target_x = max(avail.left() + 10, min(target_x, avail.right() - target_w - 10))
                    target_y = max(avail.top() + 10, min(target_y, avail.bottom() - target_h - 10))

                self.resize(target_w, target_h)
                self.move(target_x, target_y)
                return

        # Fallback to desktop screen right side
        if avail is not None:
            target_w = min(450, avail.width() - 40)
            target_h = min(680, avail.height() - 80)
            x = avail.right() - target_w - 24
            y = avail.top() + 48
            self.resize(target_w, target_h)
            self.move(x, y)

    def show_animated(self, vlc_rect: tuple[int, int, int, int] | None = None) -> None:
        """Fade in overlay window."""
        self.position_on_screen(vlc_rect)
        self.setWindowOpacity(0.0)
        self.show()
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(self.config.overlay.opacity)
        self.anim.start()

    def hide_animated(self) -> None:
        """Fade out and hide overlay window."""
        self.anim.stop()
        self.anim.setStartValue(self.windowOpacity())
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self._on_fade_out_finished)
        self.anim.start()

    def _on_fade_out_finished(self) -> None:
        self.anim.finished.disconnect(self._on_fade_out_finished)
        self.hide()

    def update_results(
        self,
        subtitle_text: str | None,
        words: list[WordResult],
        image_path: Path | str | None = None,
        analysis: FrameAnalysis | None = None,
        enrichment_service: Any = None,
        movie_title: str | None = None,
        timestamp_ms: int | None = None,
    ) -> None:
        """Feed new pause data into Word Assist and Frame Insight panels."""
        level = self.config.analysis.difficulty_level.value
        self.word_panel.update_content(
            subtitle_text,
            words,
            difficulty_level=level,
            enrichment_service=enrichment_service,
            movie_title=movie_title,
            timestamp_ms=timestamp_ms,
        )
        self.vision_panel.update_content(
            image_path,
            analysis,
            enrichment_service=enrichment_service,
        )
        self.product_panel.update_content(
            products=analysis.products if analysis is not None else [],
            detections=analysis.detections if analysis is not None else [],
        )

        # Automatically select Word tab if hard words exist, otherwise show vision if objects found
        if words:
            self.tabs.setCurrentIndex(0)
        elif analysis and analysis.detections:
            self.tabs.setCurrentIndex(1)

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.hide_animated()
        else:
            super().keyPressEvent(event)

    # Window dragging support
    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        self._drag_pos = None
