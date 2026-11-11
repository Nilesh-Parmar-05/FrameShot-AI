"""Vocabulary Journal viewer: search, browse, and export saved subtitle words.

Tasks 4.2-4.3 in ``tasks.md``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from frameshot.database import Database

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from frameshot.ui.theme import Theme, compile_stylesheet

logger = logging.getLogger(__name__)


def format_ms(ms: int | None) -> str:
    """Format millisecond timestamp into mm:ss."""
    if ms is None or ms <= 0:
        return ""
    total_seconds = ms // 1000
    m = total_seconds // 60
    s = total_seconds % 60
    return f"{m:02d}:{s:02d}"


class JournalCard(QFrame):
    """Card displaying a saved vocabulary entry."""

    def __init__(
        self,
        entry: dict[str, Any],
        on_delete: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.entry = entry
        self.on_delete = on_delete
        self.setObjectName("journalCard")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header: Word + Date + Delete Button
        header = QHBoxLayout()
        header.setSpacing(8)

        word_label = QLabel(str(entry.get("word", "")).upper())
        word_label.setObjectName("wordTitle")
        header.addWidget(word_label)

        if saved_at := entry.get("saved_at"):
            date_str = str(saved_at)[:10]
            date_badge = QLabel(date_str)
            date_badge.setObjectName("ipaBadge")
            header.addWidget(date_badge)

        header.addStretch()

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("deleteBtn")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setToolTip("Remove from journal")
        delete_btn.clicked.connect(lambda: self.on_delete(int(entry["id"])))
        header.addWidget(delete_btn)

        layout.addLayout(header)

        # Definition
        if definition := entry.get("definition"):
            def_label = QLabel(definition)
            def_label.setObjectName("definitionText")
            def_label.setWordWrap(True)
            layout.addWidget(def_label)

        # Context line
        if context := entry.get("context"):
            ctx_label = QLabel(f'"{context}"')
            ctx_label.setObjectName("subtitleText")
            ctx_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-style: italic;")
            ctx_label.setWordWrap(True)
            layout.addWidget(ctx_label)

        # Source footer (Movie title & timestamp)
        movie_title = entry.get("movie_title")
        timestamp_ms = entry.get("timestamp_ms")
        if movie_title or timestamp_ms:
            parts = []
            if movie_title:
                parts.append(movie_title)
            if timestamp_ms:
                ts = format_ms(int(timestamp_ms))
                if ts:
                    parts.append(ts)
            footer_text = " · ".join(parts)
            footer_label = QLabel(footer_text)
            footer_label.setObjectName("synonymsText")
            layout.addWidget(footer_label)


class JournalWindow(QDialog):
    """Personal Vocabulary Journal search & export window."""

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self._drag_pos: QPoint | None = None

        self._init_window()
        self._init_ui()
        self.refresh_entries()

    def _init_window(self) -> None:
        self.setWindowTitle("Vocabulary Journal — FrameShot")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(520, 640)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        self.central_card = QFrame(self)
        self.central_card.setObjectName("centralCard")
        self.central_card.setStyleSheet(compile_stylesheet())

        card_layout = QVBoxLayout(self.central_card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        # Top Bar: Title + Close Button
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Vocabulary Journal")
        title_label.setObjectName("appTitle")
        top_bar.addWidget(title_label)

        self.count_badge = QLabel("0 words")
        self.count_badge.setObjectName("ipaBadge")
        top_bar.addWidget(self.count_badge)

        top_bar.addStretch()

        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Close Journal (Esc)")
        close_btn.clicked.connect(self.close)
        top_bar.addWidget(close_btn)

        card_layout.addLayout(top_bar)

        # Search Bar + Export CSV Action Row
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Search saved words, definitions, or subtitles...")
        self.search_input.textChanged.connect(self._on_search_changed)
        action_row.addWidget(self.search_input)

        export_btn = QPushButton("Export CSV")
        export_btn.setProperty("class", "neutralBtn")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setToolTip("Export vocabulary journal to a CSV file for Anki / study")
        export_btn.clicked.connect(self._on_export_csv)
        action_row.addWidget(export_btn)

        card_layout.addLayout(action_row)

        # Scroll Area for Saved Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 4, 2, 4)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        card_layout.addWidget(self.scroll_area)

        main_layout.addWidget(self.central_card)

    def refresh_entries(self, query: str | None = None) -> None:
        """Reload saved entries from SQLite and populate cards."""
        entries = self.database.get_journal_entries(query)

        # Clear existing
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item is not None and (widget := item.widget()) is not None:
                widget.deleteLater()

        count = len(entries)
        self.count_badge.setText(f"{count} {'word' if count == 1 else 'words'}")

        if entries:
            for e in entries:
                card = JournalCard(e, on_delete=self._on_delete_entry)
                self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        else:
            empty_frame = QFrame()
            empty_frame.setObjectName("emptyFrame")
            empty_layout = QVBoxLayout(empty_frame)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            msg_text = (
                "No saved words match your search."
                if query
                else "No saved words yet.\nClick 'Save' on any word card while watching videos to build your journal."
            )
            msg = QLabel(msg_text)
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setObjectName("emptyText")
            empty_layout.addWidget(msg)

            self.cards_layout.insertWidget(0, empty_frame)

    def _on_search_changed(self, text: str) -> None:
        self.refresh_entries(query=text.strip())

    def _on_delete_entry(self, entry_id: int) -> None:
        self.database.delete_journal_entry(entry_id)
        self.refresh_entries(query=self.search_input.text().strip())

    def _on_export_csv(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Vocabulary Journal to CSV",
            "vocabulary_journal.csv",
            "CSV Files (*.csv)",
        )
        if file_path:
            count = self.database.export_journal_to_csv(file_path)
            self.search_input.setPlaceholderText(f"Exported {count} words to CSV successfully!")

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

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

