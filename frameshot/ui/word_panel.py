"""Word Assist panel: subtitle dialogue banner and expandable word definition cards.

Task 2.13, 4.1 in ``tasks.md``.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from frameshot.word_analyzer import WordResult

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from frameshot.ui.theme import Theme

logger = logging.getLogger(__name__)


class WordCard(QFrame):
    """An individual styled card for a detected hard word."""

    enrichment_ready = pyqtSignal(str)

    def __init__(
        self,
        result: WordResult,
        enrichment_service: Any = None,
        database: Any = None,
        context_text: str | None = None,
        movie_title: str | None = None,
        timestamp_ms: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.result = result
        self.enrichment_service = enrichment_service
        self.database = database
        self.context_text = context_text
        self.movie_title = movie_title
        self.timestamp_ms = timestamp_ms
        self.enrichment_ready.connect(self._on_enrichment_ready)
        self.setObjectName("wordCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header: Word Title + IPA Badge + POS Badge
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        title_label = QLabel(result.word.upper())
        title_label.setObjectName("wordTitle")
        header_layout.addWidget(title_label)

        if result.pronunciation:
            ipa_label = QLabel(result.pronunciation)
            ipa_label.setObjectName("ipaBadge")
            header_layout.addWidget(ipa_label)

        if result.part_of_speech:
            pos_label = QLabel(result.part_of_speech)
            pos_label.setObjectName("posBadge")
            header_layout.addWidget(pos_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Definition
        if result.definition:
            def_label = QLabel(result.definition)
            def_label.setObjectName("definitionText")
            def_label.setWordWrap(True)
            layout.addWidget(def_label)

        # Synonyms
        if result.synonyms:
            syn_str = ", ".join(result.synonyms[:4])
            syn_label = QLabel(f"Synonyms: {syn_str}")
            syn_label.setObjectName("synonymsText")
            layout.addWidget(syn_label)

        # Actions Row: More Details + Save Word
        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)

        self.dive_btn = QPushButton("More →")
        self.dive_btn.setObjectName("diveBtn")
        self.dive_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dive_btn.clicked.connect(self._on_toggle_deep_dive)
        actions_row.addWidget(self.dive_btn)

        self.save_btn = QPushButton("Save Word")
        self.save_btn.setProperty("class", "neutralBtn")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setToolTip("Bookmark this word to your Vocabulary Journal")

        if self.database and hasattr(self.database, "is_word_saved") and self.database.is_word_saved(self.result.word):
            self.save_btn.setText("Saved ✓")
            self.save_btn.setEnabled(False)
            self.save_btn.setStyleSheet(f"color: {Theme.SUCCESS};")
        else:
            self.save_btn.clicked.connect(self._on_save_clicked)

        actions_row.addWidget(self.save_btn)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        # Online Deep Dive Expandable Container
        self.dive_box = QFrame()
        self.dive_box.setObjectName("diveBox")
        self.dive_box.setVisible(False)
        dive_layout = QVBoxLayout(self.dive_box)
        dive_layout.setContentsMargins(10, 8, 10, 8)
        dive_layout.setSpacing(4)
        self.dive_content = QLabel()
        self.dive_content.setObjectName("diveContent")
        self.dive_content.setWordWrap(True)
        dive_layout.addWidget(self.dive_content)
        layout.addWidget(self.dive_box)

    def _on_save_clicked(self) -> None:
        """Save this word and its context to the user's SQLite vocabulary journal."""
        if self.database and hasattr(self.database, "save_journal_entry"):
            try:
                self.database.save_journal_entry(
                    word=self.result.word,
                    definition=self.result.definition,
                    context=self.context_text,
                    movie_title=self.movie_title,
                    timestamp_ms=self.timestamp_ms,
                )
            except Exception as exc:
                logger.warning("Could not save word %s to journal: %s", self.result.word, exc)

        self.save_btn.setText("Saved ✓")
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(f"color: {Theme.SUCCESS};")

    def _on_toggle_deep_dive(self) -> None:
        if self.dive_box.isVisible():
            self.dive_box.setVisible(False)
            self.dive_btn.setText("More →")
            return

        self.dive_box.setVisible(True)
        self.dive_btn.setText("Less ↑")

        if self.enrichment_service is None or not self.enrichment_service.is_enabled:
            self.dive_content.setText(
                "Online enrichment is currently disabled.\n"
                "Enable it from the system tray menu to fetch Wiktionary examples and etymology."
            )
            return

        self.dive_content.setText("Loading Wiktionary details...")
        threading.Thread(target=self._load_enrichment, daemon=True).start()

    def _on_enrichment_ready(self, text: str) -> None:
        self.dive_content.setText(text)

    def _load_enrichment(self) -> None:
        try:
            details = self.enrichment_service.enrich_word(self.result.word)
            text_lines: list[str] = []
            if details and details.definitions:
                for idx, d in enumerate(details.definitions[:2], 1):
                    pos = f"({d.part_of_speech}) " if d.part_of_speech else ""
                    text_lines.append(f"{idx}. {pos}{d.definition}")
                    if d.examples:
                        text_lines.append(f'   Example: "{d.examples[0]}"')
            else:
                if self.result.definition:
                    text_lines.append(f'Definition: {self.result.definition}')
                if self.result.synonyms:
                    text_lines.append(f"Synonyms: {', '.join(self.result.synonyms[:4])}")
                text_lines.append("No additional online details found.")

            full_text = "\n".join(text_lines)
            self.enrichment_ready.emit(full_text)
        except Exception as exc:
            logger.debug("Failed to load word enrichment: %s", exc)
            fallback = f'Definition: {self.result.definition}' if self.result.definition else "Could not fetch online details."
            self.enrichment_ready.emit(fallback)


class WordPanel(QWidget):
    """Word Assist panel displaying subtitle dialogue and hard word cards."""

    def __init__(self, database: Any = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self._journal_window: Any = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # Subtitle banner
        self.subtitle_banner = QFrame()
        self.subtitle_banner.setObjectName("subtitleBanner")
        banner_layout = QVBoxLayout(self.subtitle_banner)
        banner_layout.setContentsMargins(12, 10, 12, 10)
        self.subtitle_label = QLabel("No active dialogue")
        self.subtitle_label.setObjectName("subtitleText")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        banner_layout.addWidget(self.subtitle_label)
        main_layout.addWidget(self.subtitle_banner)

        # Section header row with Journal Viewer shortcut
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        self.header_label = QLabel("Word Assist · intermediate")
        self.header_label.setObjectName("sectionHeader")
        header_row.addWidget(self.header_label)

        header_row.addStretch()

        self.journal_btn = QPushButton("Journal ↗")
        self.journal_btn.setProperty("class", "neutralBtn")
        self.journal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.journal_btn.setToolTip("View saved vocabulary words & export CSV")
        self.journal_btn.clicked.connect(self.open_journal)
        header_row.addWidget(self.journal_btn)

        main_layout.addLayout(header_row)

        # Scrollable container for word cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 2, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll_area)

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

    def update_content(
        self,
        subtitle_text: str | None,
        words: list[WordResult],
        difficulty_level: str = "intermediate",
        enrichment_service: Any = None,
        movie_title: str | None = None,
        timestamp_ms: int | None = None,
    ) -> None:
        """Update subtitle banner and populate word cards."""
        # 1. Update subtitle dialogue banner
        if subtitle_text:
            clean_text = subtitle_text.replace("\n", " ").strip()
            self.subtitle_label.setText(f'"{clean_text}"')
            self.subtitle_banner.show()
        else:
            self.subtitle_label.setText("(No subtitle dialogue at this timestamp)")
            self.subtitle_banner.show()

        self.header_label.setText(f"Word Assist · {difficulty_level}")

        # 2. Clear old cards
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item is not None and (widget := item.widget()) is not None:
                widget.deleteLater()

        # 3. Add new cards
        if words:
            for result in words:
                card = WordCard(
                    result,
                    enrichment_service=enrichment_service,
                    database=self.database,
                    context_text=subtitle_text,
                    movie_title=movie_title,
                    timestamp_ms=timestamp_ms,
                )
                self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        else:
            empty_frame = QFrame()
            empty_frame.setObjectName("emptyFrame")
            empty_layout = QVBoxLayout(empty_frame)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label = QLabel("All words in this line are common vocabulary.")
            empty_label.setObjectName("emptyText")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(empty_label)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, empty_frame)
