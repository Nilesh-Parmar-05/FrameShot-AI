"""Frame Insight panel: displays annotated frame and AI vision detections.

Tasks 2.14-2.15 in ``tasks.md``.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import urllib.parse
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from frameshot.vision_pipeline import FrameAnalysis

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from frameshot.ui.theme import CATEGORY_COLORS, Theme

logger = logging.getLogger(__name__)


class FrameCanvas(QLabel):
    """Draws the video frame with scaled bounding boxes and aspect-ratio preservation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setMaximumHeight(240)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background-color: {Theme.BG_BASE}; "
            f"border: 1px solid {Theme.BORDER_SUBTLE}; "
            f"border-radius: {Theme.RADIUS_MD};"
        )
        self._annotated_pixmap: QPixmap | None = None

    def _rescale_pixmap(self) -> None:
        if self._annotated_pixmap is not None and not self._annotated_pixmap.isNull():
            scaled = self._annotated_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale_pixmap()

    def set_frame(self, image_path: Path | str, detections: list[Any]) -> None:
        path = Path(image_path)
        if not path.is_file():
            self.setText("No Frame Captured")
            self._annotated_pixmap = None
            return

        image = QImage(str(path))
        if image.isNull():
            self.setText("Could Not Load Frame")
            self._annotated_pixmap = None
            return

        # Draw bounding boxes onto a copy of the image
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        painter.setFont(font)

        for d in detections:
            cat = getattr(d, "category", "object")
            fg_hex = CATEGORY_COLORS.get(cat, CATEGORY_COLORS["object"])[0]
            color = QColor(fg_hex)
            pen = QPen(color, 2)
            painter.setPen(pen)

            x1, y1, x2, y2 = d.bbox
            rect = QRect(x1, y1, x2 - x1, y2 - y1)
            painter.drawRect(rect)

            # Draw clean label tag above box
            tag = f"{d.label} {int(d.confidence * 100)}%"
            tag_rect = QRect(x1, max(0, y1 - 20), max(72, (x2 - x1)), 18)
            painter.fillRect(tag_rect, color)
            painter.setPen(QColor(Theme.TEXT_INVERSE))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag)

        painter.end()

        self._annotated_pixmap = QPixmap.fromImage(image)
        self._rescale_pixmap()


class VisionPanel(QWidget):
    """Frame Insight panel showing scene description and object tags."""

    wiki_ready = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.wiki_ready.connect(self._on_wiki_ready)
        self._init_ui()

    def _on_wiki_ready(self, text: str) -> None:
        self.wiki_extract.setText(text)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        self.header_label = QLabel("SCENE INSIGHT")
        self.header_label.setObjectName("sectionHeader")
        layout.addWidget(self.header_label)

        # Frame Canvas
        self.canvas = FrameCanvas()
        layout.addWidget(self.canvas)

        # Scene Caption
        self.caption_card = QFrame()
        self.caption_card.setObjectName("sectionBanner")
        cap_layout = QVBoxLayout(self.caption_card)
        cap_layout.setContentsMargins(12, 8, 12, 8)
        self.caption_label = QLabel("Paused scene")
        self.caption_label.setObjectName("subtitleText")
        self.caption_label.setWordWrap(True)
        cap_layout.addWidget(self.caption_label)
        layout.addWidget(self.caption_card)

        # Detection tags container
        self.tags_scroll = QScrollArea()
        self.tags_scroll.setWidgetResizable(True)
        self.tags_scroll.setMaximumHeight(70)
        self.tags_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.tags_widget = QWidget()
        self.tags_widget.setStyleSheet("background: transparent;")
        self.tags_layout = QHBoxLayout(self.tags_widget)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(6)
        self.tags_layout.addStretch()

        self.tags_scroll.setWidget(self.tags_widget)
        layout.addWidget(self.tags_scroll)

        # Wikipedia Entity Detail Box
        self.wiki_box = QFrame()
        self.wiki_box.setObjectName("wikiBox")
        self.wiki_box.setVisible(False)
        wiki_layout = QVBoxLayout(self.wiki_box)
        wiki_layout.setContentsMargins(12, 10, 12, 10)
        wiki_layout.setSpacing(6)
        self.wiki_title = QLabel()
        self.wiki_title.setObjectName("wikiTitle")
        wiki_layout.addWidget(self.wiki_title)
        self.wiki_extract = QLabel()
        self.wiki_extract.setObjectName("wikiExtract")
        self.wiki_extract.setWordWrap(True)
        wiki_layout.addWidget(self.wiki_extract)

        self.wiki_actions = QHBoxLayout()
        self.wiki_actions.setContentsMargins(0, 4, 0, 0)
        self.wiki_shop_btn = QPushButton("Search Google Shopping →")
        self.wiki_shop_btn.setProperty("class", "neutralBtn")
        self.wiki_shop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.wiki_actions.addWidget(self.wiki_shop_btn)
        self.wiki_actions.addStretch()
        wiki_layout.addLayout(self.wiki_actions)

        layout.addWidget(self.wiki_box)

        self.enrichment_service: Any = None

    def update_content(
        self,
        image_path: Path | str | None,
        analysis: FrameAnalysis | None,
        enrichment_service: Any = None,
    ) -> None:
        """Update canvas, scene caption, and item badges."""
        self.enrichment_service = enrichment_service
        detections = analysis.detections if analysis is not None else []
        caption = (
            analysis.scene_caption
            if analysis is not None and analysis.scene_caption
            else "Paused frame."
        )

        if image_path:
            self.canvas.set_frame(image_path, detections)
            self.canvas.show()
        else:
            self.canvas.setText("No Snapshot Available")

        self.caption_label.setText(caption)

        # Clear old tags
        while self.tags_layout.count() > 1:
            item = self.tags_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        # Add badge tags
        if detections:
            for d in detections:
                badge = QPushButton(f"{d.label.capitalize()}  {int(d.confidence * 100)}%")
                badge.setCursor(Qt.CursorShape.PointingHandCursor)
                cat = getattr(d, "category", "object")
                fg, bg, border = CATEGORY_COLORS.get(cat, CATEGORY_COLORS["object"])
                badge.setStyleSheet(
                    f"QPushButton {{"
                    f"  color: {fg};"
                    f"  background-color: {bg};"
                    f"  border: 1px solid {border};"
                    f"  border-radius: {Theme.RADIUS_SM};"
                    f"  padding: 3px 8px;"
                    f"  font-size: 11px;"
                    f"  font-weight: 500;"
                    f"}}"
                    f"QPushButton:hover {{"
                    f"  background-color: {border};"
                    f"  color: #ffffff;"
                    f"}}"
                )
                badge.clicked.connect(lambda checked, label=d.label: self._on_badge_clicked(label))
                self.tags_layout.insertWidget(self.tags_layout.count() - 1, badge)
        else:
            none_label = QLabel("(No objects detected)")
            none_label.setObjectName("emptyText")
            self.tags_layout.insertWidget(self.tags_layout.count() - 1, none_label)

    def _on_badge_clicked(self, label: str) -> None:
        clean_label = label.capitalize()
        if self.wiki_box.isVisible() and self.wiki_title.text() == clean_label:
            self.wiki_box.setVisible(False)
            return

        self.wiki_box.setVisible(True)
        self.wiki_title.setText(clean_label)

        with contextlib.suppress(TypeError):
            self.wiki_shop_btn.clicked.disconnect()
        encoded_query = urllib.parse.quote_plus(label)
        self.wiki_shop_btn.setText(f"Search '{clean_label}' on Google Shopping →")
        self.wiki_shop_btn.clicked.connect(
            lambda checked, q=encoded_query: webbrowser.open(
                f"https://www.google.com/search?tbm=shop&q={q}"
            )
        )

        if self.enrichment_service is None or not self.enrichment_service.is_enabled:
            self.wiki_extract.setText(
                "Online enrichment is currently disabled. Enable it from the system tray menu to fetch Wikipedia summaries."
            )
            return

        self.wiki_extract.setText("Loading Wikipedia summary...")
        threading.Thread(target=self._load_wiki_entity, args=(label,), daemon=True).start()

    def _load_wiki_entity(self, label: str) -> None:
        try:
            summary = self.enrichment_service.enrich_entity(label)
            if summary and summary.extract:
                text = summary.extract
                if len(text) > 300:
                    text = text[:297] + "..."
            else:
                text = f"No Wikipedia summary found for '{label}'."
            self.wiki_ready.emit(text)
        except Exception as exc:
            logger.debug("Failed to fetch entity summary for '%s': %s", label, exc)
            self.wiki_ready.emit(f"Could not fetch Wikipedia summary for '{label}'.")
