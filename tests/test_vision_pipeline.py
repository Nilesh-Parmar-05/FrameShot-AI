"""Unit tests for frameshot.vision_pipeline (Tasks 2.1-2.10)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from frameshot.config import ModelProfile
from frameshot.vision_pipeline import (
    Detection,
    FrameAnalysis,
    VisionPipeline,
    classify_category,
)


def test_classify_category():
    assert classify_category("person") == "person"
    assert classify_category("backpack") == "clothing"
    assert classify_category("umbrella") == "clothing"
    assert classify_category("car") == "vehicle"
    assert classify_category("bicycle") == "vehicle"
    assert classify_category("dog") == "animal"
    assert classify_category("cat") == "animal"
    assert classify_category("laptop") == "object"
    assert classify_category("unknown_xyz") == "object"


def test_vision_pipeline_model_properties():
    pipe_lite = VisionPipeline(model_profile=ModelProfile.LITE, models_dir=Path("models"))
    assert pipe_lite.model_name == "yolov8n.pt"
    assert pipe_lite.model_path == Path("models/yolov8n.pt")

    pipe_bal = VisionPipeline(model_profile=ModelProfile.BALANCED, models_dir=Path("models"))
    assert pipe_bal.model_name == "yolov8s.pt"

    pipe_full = VisionPipeline(model_profile=ModelProfile.FULL, models_dir=Path("models"))
    assert pipe_full.model_name == "yolov8m.pt"


def test_caption_scene_with_detections():
    pipe = VisionPipeline()

    d1 = Detection(label="person", category="person", confidence=0.9, bbox=(10, 10, 50, 100))
    caption1 = pipe.caption_scene("dummy.png", detections=[d1])
    assert "person" in caption1

    d2 = Detection(label="car", category="vehicle", confidence=0.85, bbox=(60, 60, 200, 150))
    caption2 = pipe.caption_scene("dummy.png", detections=[d1, d2])
    assert "person" in caption2
    assert "car" in caption2

    d3 = Detection(label="dog", category="animal", confidence=0.8, bbox=(0, 0, 10, 10))
    caption3 = pipe.caption_scene("dummy.png", detections=[d1, d2, d3])
    assert "person" in caption3
    assert "car" in caption3
    assert "dog" in caption3


def test_caption_scene_no_detections():
    pipe = VisionPipeline()
    caption = pipe.caption_scene("dummy.png", detections=[])
    assert "scene" in caption.lower()


def test_analyze_missing_image():
    pipe = VisionPipeline()
    analysis = pipe.analyze(Path("nonexistent_frame_123.png"))
    assert isinstance(analysis, FrameAnalysis)
    assert len(analysis.detections) == 0


def test_detect_objects_mocked():
    pipe = VisionPipeline()
    pipe._model_loaded = True

    # Mock YOLO model
    mock_model = MagicMock()
    mock_model.names = {0: "person", 1: "bicycle", 2: "car"}

    # Mock box result
    mock_box = MagicMock()
    mock_box.cls = [0]
    mock_box.conf = [0.892]
    mock_box.xyxy = [[10.0, 20.0, 100.0, 200.0]]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    mock_model.predict.return_value = [mock_result]
    pipe._model = mock_model

    detections = pipe.detect_objects(Path("test.png"))
    assert len(detections) == 1
    d = detections[0]
    assert d.label == "person"
    assert d.category == "person"
    assert d.confidence == 0.892
    assert d.bbox == (10, 20, 100, 200)

