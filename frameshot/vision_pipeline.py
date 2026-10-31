"""Visual analysis of a captured frame: detection, captioning, matching.

Status: **stub** — tasks 2.1-2.10 in ``tasks.md``. The working reference
implementation is ``spikes/spike_yolo.py``.

Performance note: architecture.md §12 budgets < 1.5 s for BLIP-2 OPT-2.7B
captioning on CPU. Spike 0.9 must confirm that, otherwise the default profile
moves to Florence-2-base (tech-stack.md §6.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from frameshot.config import ModelProfile

if TYPE_CHECKING:  # numpy is an optional (vision) dependency
    import numpy as np


@dataclass(frozen=True, slots=True)
class Detection:
    label: str
    category: str  # "object" | "landmark" | "product" | "clothing"
    confidence: float
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    details: str | None = None


@dataclass(frozen=True, slots=True)
class LandmarkMatch:
    name: str
    similarity: float
    details_url: str | None = None


@dataclass(frozen=True, slots=True)
class ProductMatch:
    name: str
    brand: str | None
    similarity: float


@dataclass(slots=True)
class FrameAnalysis:
    scene_caption: str = ""
    detections: list[Detection] = field(default_factory=list)
    landmarks: list[LandmarkMatch] = field(default_factory=list)
    products: list[ProductMatch] = field(default_factory=list)


class VisionPipeline:
    """Runs the vision models over one captured frame."""

    def __init__(self, model_profile: ModelProfile = ModelProfile.BALANCED) -> None:
        self.model_profile = model_profile

    def analyze(self, image_path: str | Path) -> FrameAnalysis:
        """Run every enabled stage for the active model profile."""
        raise NotImplementedError("tasks.md 2.2-2.9 - see spikes/spike_yolo.py")

    def detect_objects(self, image: np.ndarray) -> list[Detection]:
        """YOLOv8 object detection (FR-30)."""
        raise NotImplementedError("tasks.md 2.2 - see spikes/spike_yolo.py")

    def caption_scene(self, image: np.ndarray) -> str:
        """Natural-language scene description (FR-31)."""
        raise NotImplementedError("tasks.md 2.3 - spike 0.9")

    def match_landmarks(self, crops: list[np.ndarray]) -> list[LandmarkMatch]:
        """CLIP cosine-similarity search against the landmark index (FR-32)."""
        raise NotImplementedError("tasks.md 2.5, 2.7")

    def match_products(self, crops: list[np.ndarray]) -> list[ProductMatch]:
        """CLIP cosine-similarity search against the product index (FR-33)."""
        raise NotImplementedError("tasks.md 2.6, 2.8")
