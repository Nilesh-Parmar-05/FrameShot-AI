"""Unit tests for frameshot.app (Application Orchestration & Event Wiring)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from frameshot.app import AppState, FrameShotApp, format_time_ms
from frameshot.config import AppConfig, DifficultyLevel
from frameshot.events import Event, EventBus
from frameshot.subtitle_parser import SubtitleParser
from frameshot.vlc_controller import PlaybackState, PlaybackStatus, VLCController
from frameshot.word_analyzer import WordAnalyzer


def test_format_time_ms():
    assert format_time_ms(0) == "00:00:00.000"
    assert format_time_ms(1500) == "00:00:01.500"
    assert format_time_ms(83450) == "00:01:23.450"
    assert format_time_ms(3661000) == "01:01:01.000"


def test_app_lifecycle(config: AppConfig):
    bus = EventBus()
    mock_vlc = MagicMock(spec=VLCController)
    mock_vlc.base_url = "http://127.0.0.1:8080"

    app = FrameShotApp(config, bus=bus, vlc=mock_vlc)
    assert app.state == AppState.IDLE

    app.start()
    assert app.state == AppState.MONITORING
    mock_vlc.start_polling.assert_called_once_with(bus)

    app.stop()
    assert app.state == AppState.IDLE
    mock_vlc.stop_polling.assert_called_once()


def test_app_media_changed_auto_loads_subtitle(config: AppConfig, tmp_path: Path):
    bus = EventBus()
    mock_vlc = MagicMock(spec=VLCController)
    mock_vlc.base_url = "http://127.0.0.1:8080"

    video = tmp_path / "Movie.mkv"
    video.touch()
    sub = tmp_path / "Movie.srt"
    sub.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nResplendent architecture.\n",
        encoding="utf-8",
    )

    parser = SubtitleParser()
    app = FrameShotApp(config, bus=bus, vlc=mock_vlc, subtitle_parser=parser)
    app.start()

    status = PlaybackStatus(
        state=PlaybackState.PLAYING,
        timestamp_ms=0,
        duration_ms=5000,
        filename="Movie.mkv",
        media_path=video,
    )
    bus.publish(Event.MEDIA_CHANGED, status)

    assert len(parser.entries) == 1
    assert parser.entries[0].text == "Resplendent architecture."
    app.stop()


def test_app_playback_paused_full_analysis(config: AppConfig, sample_srt: Path, tmp_path: Path):
    bus = EventBus()
    mock_vlc = MagicMock(spec=VLCController)
    mock_vlc.base_url = "http://127.0.0.1:8080"
    dummy_snap = tmp_path / "snap.png"
    dummy_snap.touch()
    mock_vlc.take_snapshot.return_value = dummy_snap

    parser = SubtitleParser()
    parser.load(sample_srt)

    analyzer = WordAnalyzer(difficulty_level=DifficultyLevel.INTERMEDIATE)

    app = FrameShotApp(
        config,
        bus=bus,
        vlc=mock_vlc,
        subtitle_parser=parser,
        word_analyzer=analyzer,
    )
    app.start()

    completed_payloads = []
    bus.subscribe(Event.ANALYSIS_COMPLETE, lambda msg: completed_payloads.append(msg.payload))

    # Pause at 2000 ms (line: "The edifice was resplendent under the moonlight.")
    status = PlaybackStatus(
        state=PlaybackState.PAUSED,
        timestamp_ms=2000,
        duration_ms=100000,
        filename="Sample.mkv",
    )
    bus.publish(Event.PLAYBACK_PAUSED, status)

    assert len(completed_payloads) == 1
    result = completed_payloads[0]
    assert result["status"] == status
    assert result["subtitle"] is not None
    assert result["subtitle"].text == "The edifice was resplendent under the moonlight."
    assert result["snapshot_path"] == dummy_snap

    words = [w.word for w in result["words"]]
    assert "edifice" in words
    assert "resplendent" in words

    app.stop()


def test_app_run_once(config: AppConfig, sample_srt: Path, tmp_path: Path):
    bus = EventBus()
    mock_vlc = MagicMock(spec=VLCController)
    mock_vlc.base_url = "http://127.0.0.1:8080"
    mock_vlc.take_snapshot.return_value = None

    parser = SubtitleParser()
    parser.load(sample_srt)

    app = FrameShotApp(
        config,
        bus=bus,
        vlc=mock_vlc,
        subtitle_parser=parser,
        run_once=True,
    )
    app.start()

    status = PlaybackStatus(
        state=PlaybackState.PAUSED,
        timestamp_ms=2000,
        duration_ms=10000,
        filename="Sample.mkv",
    )
    bus.publish(Event.PLAYBACK_PAUSED, status)

    # In run_once mode, the app stops automatically after processing
    assert app.wait_for_pause_processed(timeout=2.0) is True
    assert app.state == AppState.IDLE

