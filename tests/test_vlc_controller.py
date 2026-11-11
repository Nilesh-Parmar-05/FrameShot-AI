"""Unit tests for frameshot.vlc_controller (Tasks 1.6-1.10)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from frameshot.config import VLCConfig
from frameshot.events import Event, EventBus
from frameshot.vlc_controller import (
    PlaybackState,
    VLCController,
    find_current_playlist_item,
    uri_to_path,
)


@pytest.fixture()
def vlc_config() -> VLCConfig:
    return VLCConfig(
        host="127.0.0.1",
        port=8080,
        password="test_password",
        poll_interval_ms=50,
        request_timeout_s=1.0,
    )


def test_uri_to_path():
    assert uri_to_path("file:///C:/Movies/Inception.mkv") == Path("C:/Movies/Inception.mkv")
    assert uri_to_path("file:///D:/Folder%20Name/Film.mp4") == Path("D:/Folder Name/Film.mp4")
    assert uri_to_path("http://example.com/video.mp4") is None


def test_find_current_playlist_item():
    tree = {
        "id": "1",
        "name": "Root",
        "children": [
            {
                "id": "2",
                "name": "Item 1",
                "uri": "file:///C:/Movies/Old.mkv",
            },
            {
                "id": "3",
                "name": "Item 2",
                "current": "current",
                "uri": "file:///C:/Movies/Current.mkv",
            },
        ],
    }
    found = []
    find_current_playlist_item(tree, found)
    assert len(found) == 1
    assert found[0]["uri"] == "file:///C:/Movies/Current.mkv"


def test_connect_success(vlc_config: VLCConfig, monkeypatch: pytest.MonkeyPatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    controller = VLCController(vlc_config)
    controller._session = mock_session

    assert controller.connect() is True
    mock_session.get.assert_called_once_with(
        "http://127.0.0.1:8080/requests/status.json", timeout=1.0
    )


def test_connect_failure(vlc_config: VLCConfig, monkeypatch: pytest.MonkeyPatch):
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.ConnectionError("Connection refused")

    controller = VLCController(vlc_config)
    controller._session = mock_session

    assert controller.connect() is False


def test_connect_unauthorized(vlc_config: VLCConfig):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    controller = VLCController(vlc_config)
    controller._session = mock_session

    assert controller.connect() is False


def test_get_status_playing(vlc_config: VLCConfig):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "state": "playing",
        "time": 83,
        "length": 7200,
        "spu": 2,
        "information": {
            "category": {
                "meta": {
                    "filename": "Movie.mkv",
                }
            }
        },
    }
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    controller = VLCController(vlc_config)
    controller._session = mock_session

    status = controller.get_status()
    assert status.state == PlaybackState.PLAYING
    assert status.timestamp_ms == 83000
    assert status.duration_ms == 7200000
    assert status.filename == "Movie.mkv"
    assert status.subtitle_track == 2


def test_get_status_paused(vlc_config: VLCConfig):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "state": "paused",
        "time": 10,
        "length": 100,
    }
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    controller = VLCController(vlc_config)
    controller._session = mock_session

    status = controller.get_status()
    assert status.state == PlaybackState.PAUSED
    assert status.timestamp_ms == 10000


def test_get_media_info(vlc_config: VLCConfig):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "children": [
            {
                "current": "current",
                "uri": "file:///C:/Movies/Film.mkv",
            }
        ]
    }
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    controller = VLCController(vlc_config)
    controller._session = mock_session

    path = controller.get_media_info()
    assert path == Path("C:/Movies/Film.mkv")


def test_take_snapshot_detected(vlc_config: VLCConfig, tmp_path: Path):
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()

    controller = VLCController(vlc_config, snapshot_dir=snapshot_dir)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp
    controller._session = mock_session

    # Create dummy snapshot image file immediately
    new_snap = snapshot_dir / "vlcsnap-test.png"
    new_snap.touch()

    captured = controller.take_snapshot(timeout_s=0.2)
    assert captured == new_snap


def test_take_snapshot_ffmpeg_fallback(
    vlc_config: VLCConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    video_file = tmp_path / "dummy_video.mkv"
    video_file.touch()

    controller = VLCController(vlc_config, snapshot_dir=snapshot_dir)

    # Make VLC command fail or timeout
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp
    controller._session = mock_session

    # Mock ffmpeg subprocess
    def mock_subprocess_run(cmd, **kwargs):
        out_path = Path(cmd[-1])
        out_path.touch()
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    captured = controller.take_snapshot(timeout_s=0.05, video_path=video_file, timestamp_ms=5000)
    assert captured is not None
    assert captured.exists()
    assert "frame_" in captured.name


def test_poller_detects_pause_and_resume(vlc_config: VLCConfig):
    bus = EventBus()
    events_received = []

    bus.subscribe(Event.PLAYBACK_PAUSED, lambda msg: events_received.append("paused"))
    bus.subscribe(Event.PLAYBACK_RESUMED, lambda msg: events_received.append("resumed"))
    bus.subscribe(Event.VLC_CONNECTED, lambda msg: events_received.append("connected"))

    controller = VLCController(vlc_config)

    # Simulate sequence of responses: playing -> paused -> playing
    statuses = [
        {"state": "playing", "time": 1, "length": 100},
        {"state": "paused", "time": 2, "length": 100},
        {"state": "playing", "time": 3, "length": 100},
    ]

    def mock_get(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if statuses:
            mock_resp.json.return_value = statuses.pop(0)
        else:
            mock_resp.json.return_value = {"state": "playing", "time": 4, "length": 100}
        return mock_resp

    mock_session = MagicMock()
    mock_session.get.side_effect = mock_get
    controller._session = mock_session

    controller.start_polling(bus)
    assert controller.is_polling is True

    # Allow polling thread to execute cycles
    time.sleep(0.25)
    controller.stop_polling()

    assert controller.is_polling is False
    assert "connected" in events_received
    assert "paused" in events_received
    assert "resumed" in events_received
