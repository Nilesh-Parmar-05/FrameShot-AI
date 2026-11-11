"""Unit tests for FrameShot-AI PyQt6 UI components (Phase 2B & 2C)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from frameshot.config import AppConfig
from frameshot.overlay_manager import OverlayManager
from frameshot.ui.overlay_window import OverlayWindow
from frameshot.ui.vision_panel import FrameCanvas, VisionPanel
from frameshot.ui.word_panel import WordCard, WordPanel
from frameshot.vision_pipeline import Detection, FrameAnalysis
from frameshot.word_analyzer import WordResult


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QApplication exists for UI tests, running offscreen."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


def test_word_card(qapp):
    result = WordResult(
        word="resplendent",
        difficulty_score=0.82,
        is_hard=True,
        definition="having great beauty and splendor",
        part_of_speech="adjective",
        pronunciation="rɪˈsplɛndənt",
        synonyms=["glorious", "splendid"],
    )
    card = WordCard(result)
    assert card is not None
    # Check that widgets inside card are created
    labels = card.findChildren(object, "wordTitle")
    assert len(labels) == 1
    assert labels[0].text() == "RESPLENDENT"


def test_word_panel_update_content(qapp):
    panel = WordPanel()
    assert panel.subtitle_label.text() == "No active dialogue"

    # Update with empty words
    panel.update_content(subtitle_text="Hello world", words=[], difficulty_level="intermediate")
    assert "Hello world" in panel.subtitle_label.text()

    # Update with a hard word
    res = WordResult(
        word="edifice",
        difficulty_score=0.88,
        is_hard=True,
        definition="a structure that has a roof and walls",
        part_of_speech="noun",
        pronunciation="ˈɛdɪfɪs",
        synonyms=["building"],
    )
    panel.update_content(subtitle_text="Look at that edifice.", words=[res], difficulty_level="advanced")
    assert "Look at that edifice" in panel.subtitle_label.text()
    assert "advanced" in panel.header_label.text()


def test_vision_panel_update_content(qapp):
    panel = VisionPanel()
    analysis = FrameAnalysis(
        scene_caption="A busy street with pedestrians and vehicles",
        detections=[
            Detection(label="person", category="person", confidence=0.92, bbox=(10, 10, 50, 100)),
            Detection(label="car", category="vehicle", confidence=0.88, bbox=(60, 60, 120, 150)),
        ],
    )
    panel.update_content(analysis=analysis, image_path=None)
    assert "A busy street" in panel.caption_label.text()


def test_frame_canvas_missing_image(qapp):
    canvas = FrameCanvas()
    canvas.set_frame(Path("nonexistent_frame_abc.png"), detections=[])
    assert canvas.text() == "No Frame Captured"


def test_overlay_window_lifecycle(qapp, config: AppConfig):
    window = OverlayWindow(config)
    assert window.windowTitle() == "FrameShot-AI Overlay"
    assert window.word_panel is not None
    assert window.vision_panel is not None

    # Test update results
    window.update_results(
        subtitle_text="Test subtitle",
        words=[],
        image_path=None,
        analysis=FrameAnalysis(),
    )
    assert "Test subtitle" in window.word_panel.subtitle_label.text()


def test_overlay_manager_bridge(qapp, config: AppConfig):
    # Test with vlc_only=False so it displays directly without a live VLC process
    config.overlay.vlc_only = False
    manager = OverlayManager(config)
    manager.initialize_gui()

    assert manager._window is not None
    assert manager.visible is False

    # Dispatch show analysis
    res = WordResult(word="test", difficulty_score=0.5, is_hard=True)
    manager.show_analysis(words=[res], subtitle_text="Sample subtitle")

    # In Qt event loop, signal emits and triggers _on_show_signal
    assert manager.visible is True
    assert manager._window.isVisible() is True

    # Dispatch hide
    manager.hide()
    assert manager.visible is False


def test_overlay_manager_vlc_only_focus_tracking(qapp, config: AppConfig, monkeypatch):
    config.overlay.vlc_only = True
    manager = OverlayManager(config)
    manager.initialize_gui()

    # Simulate VLC is NOT focused
    monkeypatch.setattr("frameshot.overlay_manager.is_vlc_or_overlay_focused", lambda *args: False)
    res = WordResult(word="test", difficulty_score=0.5, is_hard=True)
    manager.show_analysis(words=[res], subtitle_text="Sample subtitle")
    assert manager.visible is False

    # Simulate user switches back to VLC
    monkeypatch.setattr("frameshot.overlay_manager.is_vlc_or_overlay_focused", lambda *args: True)
    manager._on_focus_tick()
    assert manager.visible is True
    assert manager._window.isVisible() is True

    # User switches away to another app
    monkeypatch.setattr("frameshot.overlay_manager.is_vlc_or_overlay_focused", lambda *args: False)
    manager._on_focus_tick()
    assert manager.visible is False
    assert manager._window.isVisible() is False


def test_word_card_deep_dive_interaction(qapp):
    res = WordResult(word="ephemeral", difficulty_score=0.8, is_hard=True)
    card = WordCard(res, enrichment_service=None)
    card.show()

    assert card.dive_box.isHidden() is True

    # Click Explore More
    card.dive_btn.click()
    assert card.dive_box.isHidden() is False
    assert "disabled" in card.dive_content.text().lower()

    # Click again to collapse
    card.dive_btn.click()
    assert card.dive_box.isHidden() is True


def test_vision_panel_badge_click_interaction(qapp):
    panel = VisionPanel()
    panel.show()
    analysis = FrameAnalysis(
        detections=[Detection(label="cat", category="animal", confidence=0.95, bbox=(0, 0, 10, 10))]
    )
    panel.update_content(image_path=None, analysis=analysis)

    assert panel.wiki_box.isHidden() is True

    # Click the badge
    panel._on_badge_clicked("cat")
    assert panel.wiki_box.isHidden() is False
    assert "Cat" in panel.wiki_title.text()

    # Click again to toggle closed
    panel._on_badge_clicked("cat")
    assert panel.wiki_box.isHidden() is True


def test_word_card_save_interaction(qapp, tmp_path):
    from frameshot.database import Database

    db = Database(tmp_path / "journal_test.db")
    res = WordResult(word="serendipity", definition="a pleasant surprise", difficulty_score=0.85, is_hard=True)

    card = WordCard(
        res,
        database=db,
        context_text="Finding this cafe was pure serendipity.",
        movie_title="Travel Log",
        timestamp_ms=10500,
    )
    card.show()

    assert card.save_btn.text() == "Save Word"
    assert card.save_btn.isEnabled() is True

    # Click Save Word
    card.save_btn.click()
    assert card.save_btn.text() == "Saved ✓"
    assert card.save_btn.isEnabled() is False

    # Check database
    assert db.is_word_saved("serendipity") is True
    entries = db.get_journal_entries()
    assert len(entries) == 1
    assert entries[0]["word"] == "serendipity"
    assert entries[0]["movie_title"] == "Travel Log"

    # Creating a new card for the same saved word starts as "Saved ✓"
    card2 = WordCard(res, database=db)
    assert card2.save_btn.text() == "Saved ✓"
    assert card2.save_btn.isEnabled() is False


def test_journal_window_ui(qapp, tmp_path):
    from frameshot.database import Database
    from frameshot.ui.journal_window import JournalWindow

    db = Database(tmp_path / "journal_window_test.db")
    db.save_journal_entry(
        word="mellifluous",
        definition="sweet or musical; pleasant to hear",
        context="Her mellifluous voice filled the room.",
        movie_title="Opera Night",
        timestamp_ms=32000,
    )
    db.save_journal_entry(
        word="solitude",
        definition="the state of being alone",
        context="He enjoyed the quiet solitude.",
        movie_title="Nature Doc",
        timestamp_ms=15000,
    )

    win = JournalWindow(db)
    win.show()

    assert win.count_badge.text() == "2 words"
    assert win.cards_layout.count() >= 3  # 2 cards + stretch

    # Test search filter
    win.search_input.setText("solitude")
    assert win.count_badge.text() == "1 word"

    # Reset search
    win.search_input.setText("")
    assert win.count_badge.text() == "2 words"

    # Test CSV export
    export_file = tmp_path / "exported_journal.csv"
    count = db.export_journal_to_csv(export_file)
    assert count == 2
    assert export_file.is_file()

