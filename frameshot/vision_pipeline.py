"""Visual analysis of a captured frame: detection, captioning, matching.

Tasks 2.1-2.10 in ``tasks.md``.
Supports YOLOv8 object detection, scene captioning, and profile switching
(lite/balanced/full) with graceful degradation when weights are not yet present.
"""

from __future__ import annotations

import logging
import os
import time
import urllib.parse

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore[assignment]
try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from frameshot.config import ModelProfile

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Categories mapped from COCO-80 classes
CATEGORY_MAP: dict[str, str] = {
    "person": "person",
    "backpack": "clothing",
    "umbrella": "clothing",
    "handbag": "clothing",
    "tie": "clothing",
    "suitcase": "clothing",
    "bicycle": "vehicle",
    "car": "vehicle",
    "motorcycle": "vehicle",
    "airplane": "vehicle",
    "bus": "vehicle",
    "train": "vehicle",
    "truck": "vehicle",
    "boat": "vehicle",
    "bird": "animal",
    "cat": "animal",
    "dog": "animal",
    "horse": "animal",
    "sheep": "animal",
    "cow": "animal",
    "elephant": "animal",
    "bear": "animal",
    "zebra": "animal",
    "giraffe": "animal",
    "chair": "furniture",
    "couch": "furniture",
    "bed": "furniture",
    "dining table": "furniture",
    "desk": "furniture",
    "toilet": "furniture",
    "tv": "electronics",
    "laptop": "object",
    "mouse": "electronics",
    "remote": "electronics",
    "keyboard": "electronics",
    "cell phone": "electronics",
    "microwave": "appliance",
    "oven": "appliance",
    "toaster": "appliance",
    "sink": "appliance",
    "refrigerator": "appliance",
    "book": "object",
    "clock": "object",
    "vase": "object",
    "scissors": "object",
    "bottle": "object",
    "cup": "object",
    "bowl": "object",
}

PROFILE_WEIGHTS: dict[ModelProfile, str] = {
    ModelProfile.LITE: "yolov8n.pt",
    ModelProfile.BALANCED: "yolov8s.pt",
    ModelProfile.FULL: "yolov8m.pt",
}


@dataclass(frozen=True, slots=True)
class Detection:
    label: str
    category: str  # "object" | "landmark" | "product" | "clothing" | "vehicle" | "person"
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
    brand: str | None = None
    similarity: float = 0.85
    category: str = "Object"
    search_query: str = ""
    description: str = ""
    icon: str = "🛍️"
    color: str | None = None
    crop_path: str | None = None
    amazon_domain: str = "amazon.in"

    @property
    def query(self) -> str:
        if self.search_query:
            return self.search_query
        return f"{self.brand} {self.name}".strip() if self.brand else self.name

    @property
    def amazon_url(self) -> str:
        q = urllib.parse.quote_plus(self.query)
        domain = self.amazon_domain or "amazon.in"
        return f"https://www.{domain}/s?k={q}"

    @property
    def google_shopping_url(self) -> str:
        q = urllib.parse.quote_plus(self.query)
        return f"https://www.google.com/search?tbm=shop&q={q}"

    @property
    def web_url(self) -> str:
        q = urllib.parse.quote_plus(self.query)
        return f"https://www.google.com/search?q={q}"

    @property
    def google_lens_url(self) -> str:
        return "https://lens.google.com"


@dataclass(slots=True)
class FrameAnalysis:
    scene_caption: str = ""
    detections: list[Detection] = field(default_factory=list)
    landmarks: list[LandmarkMatch] = field(default_factory=list)
    products: list[ProductMatch] = field(default_factory=list)


def classify_category(label: str) -> str:
    """Map a class name to a high-level UI category."""
    clean = label.lower().strip()
    return CATEGORY_MAP.get(clean, "object")


def extract_dominant_color(bgr_crop: Any) -> str:
    """Classify the perceived dominant color of an image crop."""
    if cv2 is None or bgr_crop is None:
        return "neutral"

    try:
        h, w = bgr_crop.shape[:2]
        if h < 4 or w < 4:
            return "neutral"

        # Center crop to avoid background edge bleeding
        center = bgr_crop[int(h * 0.15) : max(1, int(h * 0.85)), int(w * 0.15) : max(1, int(w * 0.85))]
        if center.size == 0:
            center = bgr_crop

        small = cv2.resize(center, (32, 32))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

        votes: dict[str, int] = {
            "black": 0, "white": 0, "grey": 0, "red": 0, "orange": 0, "yellow": 0,
            "green": 0, "teal": 0, "blue": 0, "navy": 0, "purple": 0, "brown": 0,
            "maroon": 0,
        }

        for pixel in hsv.reshape(-1, 3):
            h_val, s_val, v_val = int(pixel[0]), int(pixel[1]), int(pixel[2])
            # 1. Achromatic / Neutrals (only true black when pitch dark or dark & desaturated)
            if v_val < 22 or (v_val < 45 and s_val < 38):
                votes["black"] += 1
            elif s_val < 35 and v_val > 155:
                votes["white"] += 1
            elif s_val < 35:
                votes["grey"] += 1
            # 2. Chromatic Colors
            elif 130 <= h_val < 165 and s_val >= 35:
                # Purple / Violet
                votes["purple"] += 1
            elif 100 <= h_val < 125:
                if v_val < 110:
                    votes["navy"] += 1
                else:
                    votes["blue"] += 1
            elif 85 <= h_val < 100:
                votes["teal"] += 1
            elif 38 <= h_val < 85:
                votes["green"] += 1
            elif 22 <= h_val < 38:
                votes["yellow"] += 1
            elif 10 <= h_val < 25 and s_val > 25:
                # Warm earthy tones (tan, khaki, brown)
                votes["brown"] += 1
            elif 10 <= h_val < 22:
                votes["orange"] += 1
            elif (h_val < 10 or h_val >= 165) and s_val >= 35:
                # Red / Maroon / Wine / Burgundy
                if v_val < 115:
                    votes["maroon"] += 1
                else:
                    votes["red"] += 1
            else:
                votes["grey"] += 1

        return max(votes.items(), key=lambda x: x[1])[0]
    except Exception:
        return "neutral"


def analyze_garment_pattern(bgr_crop: Any) -> str:
    """Classify if garment has a plaid/checkered, striped, or solid pattern."""
    if cv2 is None or np is None or bgr_crop is None:
        return "solid"
    try:
        h, w = bgr_crop.shape[:2]
        if h < 20 or w < 20:
            return "solid"
        center = bgr_crop[int(h * 0.15) : int(h * 0.85), int(w * 0.15) : int(w * 0.85)]
        if center.size == 0:
            center = bgr_crop
        gray = cv2.cvtColor(center, cv2.COLOR_BGR2GRAY)
        sobel_x = np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3))
        sobel_y = np.abs(cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))
        edges = cv2.Canny(gray, 40, 120)
        edge_density = float(np.count_nonzero(edges) / edges.size)
        mean_gx = float(np.mean(sobel_x))
        mean_gy = float(np.mean(sobel_y))

        # Plaid / Checkered: strong balanced 2D gradients in both X and Y
        if mean_gx > 14 and mean_gy > 10 and edge_density > 0.035:
            return "plaid"
        elif (mean_gx > 10 and mean_gy < 12) or (mean_gx > 1.15 * mean_gy and mean_gx > 7):
            return "striped"
        return "solid"
    except Exception:
        return "solid"


class VisionPipeline:
    """Runs vision AI inference over captured video frames."""

    def __init__(
        self,
        model_profile: ModelProfile = ModelProfile.LITE,
        models_dir: Path | None = None,
        confidence_threshold: float = 0.35,
    ) -> None:
        self.model_profile = model_profile
        self.models_dir = Path(models_dir) if models_dir is not None else Path("models")
        self.crops_dir = self.models_dir.parent / "data" / "crops"
        self.crops_dir.mkdir(parents=True, exist_ok=True)
        self.confidence_threshold = confidence_threshold
        self._model: Any = None
        self._model_loaded: bool = False
        self._ultralytics_available: bool | None = None

    @property
    def model_name(self) -> str:
        return PROFILE_WEIGHTS.get(self.model_profile, "yolov8n.pt")

    @property
    def model_path(self) -> Path:
        return self.models_dir / self.model_name

    def is_available(self) -> bool:
        """Return True if vision inference dependencies and models are ready."""
        self._ensure_model_loaded()
        return self._model is not None

    def _ensure_model_loaded(self) -> None:
        """Lazy-load the YOLOv8 model."""
        if self._model_loaded:
            return
        self._model_loaded = True

        # Prevent ultralytics permission errors on Windows
        cfg_dir = self.models_dir.parent / "data" / ".ultralytics"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(cfg_dir.resolve()))

        try:
            from ultralytics import YOLO  # type: ignore[attr-defined]

            self._ultralytics_available = True
        except ImportError:
            self._ultralytics_available = False
            logger.debug("ultralytics not installed; vision detection disabled (pip install -e .[vision])")
            return

        # 1. Prefer requested profile weights if present on disk
        weights_file: Path | str | None = self.model_path if self.model_path.is_file() else None

        # 2. If configured weights are absent, fallback to any available local YOLO weights
        if weights_file is None:
            for fallback_name in ("yolov8s.pt", "yolov8n.pt", "yolov8m.pt"):
                candidate = self.models_dir / fallback_name
                if candidate.is_file():
                    weights_file = candidate
                    logger.info(
                        "Configured weights '%s' not found; using available local model '%s'",
                        self.model_name,
                        fallback_name,
                    )
                    break

        if weights_file is None:
            weights_file = self.model_name

        try:
            self._model = YOLO(str(weights_file))
            logger.info("Loaded vision model '%s' (profile: %s)", weights_file, self.model_profile.value)
        except Exception as exc:
            logger.warning("Could not load vision model '%s': %s", weights_file, exc)
            self._model = None

    def detect_objects(self, image_input: str | Path | np.ndarray) -> list[Detection]:
        """Run YOLOv8 object detection (FR-30)."""
        self._ensure_model_loaded()
        if self._model is None:
            return []

        try:
            # Predict with confidence threshold
            results = self._model.predict(
                source=str(image_input) if isinstance(image_input, Path) else image_input,
                conf=self.confidence_threshold,
                verbose=False,
            )
        except Exception as exc:
            logger.warning("YOLO detection error: %s", exc)
            return []

        if not results:
            return []

        detections: list[Detection] = []
        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        names = getattr(self._model, "names", {})

        for box in boxes:
            try:
                cls_id = int(box.cls[0].item()) if hasattr(box.cls[0], "item") else int(box.cls[0])
                label = names.get(cls_id, f"class_{cls_id}")
                conf = float(box.conf[0].item()) if hasattr(box.conf[0], "item") else float(box.conf[0])
                coords = (
                    box.xyxy[0].tolist()
                    if hasattr(box.xyxy[0], "tolist")
                    else list(box.xyxy[0])
                )
                bbox = (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))

                detections.append(
                    Detection(
                        label=label,
                        category=classify_category(label),
                        confidence=round(conf, 3),
                        bbox=bbox,
                    )
                )
            except Exception as exc:
                logger.debug("Error parsing detection box: %s", exc)

        return detections

    def caption_scene(
        self,
        image_input: str | Path | np.ndarray,
        detections: list[Detection] | None = None,
    ) -> str:
        """Natural-language scene description (FR-31)."""
        if detections:
            unique_labels = []
            seen = set()
            for d in detections:
                if d.label not in seen:
                    seen.add(d.label)
                    unique_labels.append(d.label)

            if len(unique_labels) == 1:
                return f"A scene featuring a {unique_labels[0]}."
            if len(unique_labels) == 2:
                return f"A scene with a {unique_labels[0]} and a {unique_labels[1]}."
            if len(unique_labels) >= 3:
                items_str = ", ".join(unique_labels[:3])
                return f"A scene depicting {items_str}."

        return "Paused video scene."

    def match_landmarks(self, crops: list[Any]) -> list[LandmarkMatch]:
        """Cosine-similarity search against landmark embeddings (FR-32)."""
        # Landmark embeddings index lookup stub
        return []

    def match_products(
        self,
        crops: list[Any] | None = None,
        detections: list[Detection] | None = None,
        image_path: str | Path | None = None,
    ) -> list[ProductMatch]:
        """Identify recognizable products, apparel, electronics, and gear with exact visual color and crop."""
        if not detections:
            return []

        products: list[ProductMatch] = []
        labels = {d.label.lower() for d in detections}

        # Load image for visual crop extraction and color analysis
        bgr_img: Any = None
        img_h, img_w = 0, 0
        if cv2 is not None and image_path is not None:
            p = Path(image_path)
            if p.is_file():
                try:
                    bgr_img = cv2.imread(str(p))
                    if bgr_img is not None:
                        img_h, img_w = bgr_img.shape[:2]
                except Exception as exc:
                    logger.debug("Could not read image for product crops: %s", exc)

        timestamp_ms = int(time.time() * 1000)

        # Helper to crop, classify color, and save thumbnail
        def process_crop(
            box: tuple[int, int, int, int], prefix: str
        ) -> tuple[str, str | None]:
            if bgr_img is None or cv2 is None or img_w == 0 or img_h == 0:
                return "neutral", None
            x1, y1, x2, y2 = box
            x1, x2 = max(0, min(x1, img_w - 1)), max(0, min(x2, img_w))
            y1, y2 = max(0, min(y1, img_h - 1)), max(0, min(y2, img_h))
            if x2 <= x1 or y2 <= y1:
                return "neutral", None

            crop = bgr_img[y1:y2, x1:x2]
            color = extract_dominant_color(crop)

            crop_filename = f"crop_{prefix}_{timestamp_ms}.jpg"
            dest_path = self.crops_dir / crop_filename
            try:
                cv2.imwrite(str(dest_path), crop)
                return color, str(dest_path)
            except Exception:
                return color, None

        # 1. Clothing & Apparel (from person detections with reliable confidence)
        person_dets = [d for d in detections if d.label.lower() == "person" and d.confidence >= 0.70]
        for idx, pd in enumerate(person_dets[:2]):
            px1, py1, px2, py2 = pd.bbox
            pw, ph = px2 - px1, py2 - py1
            aspect = ph / max(pw, 1)

            # Classify shot framing to avoid incorrect crops or hallucinating pants
            is_closeup = aspect < 1.35 or (py2 >= img_h * 0.85 and aspect < 1.6 and ph < img_h * 0.88)
            is_fullbody = aspect >= 1.8 and (ph >= img_h * 0.65 or py2 < img_h * 0.88)
            is_medium = not is_closeup and not is_fullbody

            pants_y1 = py2
            pants_y2 = py2

            # Check if bbox is a tight headshot (ends high up in the frame, py2 < img_h * 0.82)
            if py2 < int(img_h * 0.82) and aspect < 1.6:
                # Headshot: torso is located below the chin
                sy1 = py1 + int(ph * 0.65)
                sy2 = min(img_h, py2 + int(ph * 0.50))
                sx1 = max(0, px1 - int(pw * 0.45))
                sx2 = min(img_w, px2 + int(pw * 0.45))
                has_pants = False
            elif is_closeup:
                # In close-up/bust shot, head is top 0-40%, shirt is from 40% to 80% (avoiding table/food)
                sy1 = py1 + int(ph * 0.40)
                sy2 = min(py2, py1 + int(ph * 0.80))
                sx1 = px1 + int(pw * 0.12)
                sx2 = px2 - int(pw * 0.12)
                has_pants = False
            elif is_medium:
                # In waist-up / seated shot, torso is 25% to 65%
                sy1 = py1 + int(ph * 0.25)
                sy2 = py1 + int(ph * 0.65)
                sx1 = px1 + int(pw * 0.15)
                sx2 = px2 - int(pw * 0.15)
                has_pants = (py2 - (py1 + int(ph * 0.68))) > 40
                pants_y1 = py1 + int(ph * 0.68)
                pants_y2 = py2
            else:
                # In full-body shot, torso is 15% to 52%, pants are 55% to 95%
                sy1 = py1 + int(ph * 0.15)
                sy2 = py1 + int(ph * 0.52)
                sx1 = px1 + int(pw * 0.15)
                sx2 = px2 - int(pw * 0.15)
                has_pants = True
                pants_y1 = py1 + int(ph * 0.55)
                pants_y2 = py1 + int(ph * 0.95)

            shirt_color, shirt_crop = process_crop((sx1, sy1, sx2, sy2), f"shirt_{idx}")
            shirt_bgr = cv2.imread(shirt_crop) if (cv2 is not None and shirt_crop) else None
            pattern = analyze_garment_pattern(shirt_bgr)

            # Tailor garment title and search query to detected color & pattern
            c_name = shirt_color.capitalize() if shirt_color != "neutral" else "Classic"

            if pattern == "plaid":
                shirt_title = f"{c_name} Plaid Casual Button-Up Shirt"
                shirt_query = f"{shirt_color} plaid checkered button down shirt casual flannel"
                shirt_desc = f"Patterned {shirt_color} plaid collared shirt"
                shirt_icon = "👔"
            elif pattern == "striped":
                shirt_title = f"{c_name} Striped Casual Button-Down Shirt"
                shirt_query = f"{shirt_color} striped casual button down shirt"
                shirt_desc = f"Patterned {shirt_color} striped collared shirt"
                shirt_icon = "👔"
            elif shirt_color == "maroon":
                if pattern == "striped":
                    shirt_title = "Maroon Striped Button-Up Shirt"
                    shirt_query = "maroon burgundy striped button down shirt casual"
                    shirt_desc = "Casual maroon striped button-down shirt"
                    shirt_icon = "👔"
                else:
                    shirt_title = "Maroon Casual Cotton Top"
                    shirt_query = "maroon burgundy casual crewneck t shirt top"
                    shirt_desc = "Casual maroon cotton top"
                    shirt_icon = "👕"
            elif shirt_color == "purple":
                shirt_title = "Purple Casual Cotton Crewneck"
                shirt_query = "purple mauve oversized crewneck cotton graphic t shirt"
                shirt_desc = "Casual purple oversized cotton t-shirt"
                shirt_icon = "👕"
            elif shirt_color == "white":
                shirt_title = "White Collared Work Polo Shirt"
                shirt_query = "white short sleeve collared polo work shirt"
                shirt_desc = "Classic white collared casual work shirt"
                shirt_icon = "👔"
            elif shirt_color in ("black", "grey"):
                shirt_title = f"{c_name} Casual Cotton Crewneck"
                shirt_query = f"{shirt_color} casual cotton crewneck t shirt short sleeve"
                shirt_desc = f"Casual {shirt_color} cotton top"
                shirt_icon = "👕"
            elif shirt_color in ("navy", "blue"):
                shirt_title = f"{c_name} Casual Cotton Crewneck"
                shirt_query = f"{shirt_color} cotton crewneck t shirt casual"
                shirt_desc = f"Casual {shirt_color} crewneck top"
                shirt_icon = "👕"
            elif shirt_color == "yellow":
                shirt_title = "Yellow Casual Crewneck T-Shirt"
                shirt_query = "yellow crewneck cotton t shirt casual"
                shirt_desc = "Casual yellow cotton t-shirt"
                shirt_icon = "👕"
            elif shirt_color in ("brown", "orange"):
                shirt_title = f"{c_name} Casual Button-Up Shirt"
                shirt_query = f"{shirt_color} casual button down shirt overshirt"
                shirt_desc = f"Casual {shirt_color} button-up shirt"
                shirt_icon = "👔"
            else:
                shirt_title = f"{c_name} Casual Shirt"
                shirt_query = f"{shirt_color} casual shirt top button down"
                shirt_desc = f"Detected {shirt_color} apparel item from scene"
                shirt_icon = "👔"

            products.append(
                ProductMatch(
                    name=shirt_title,
                    category="Clothing",
                    search_query=shirt_query,
                    description=shirt_desc,
                    icon=shirt_icon,
                    similarity=0.92,
                    color=shirt_color,
                    crop_path=shirt_crop,
                )
            )

            # Lower body (pants / trousers) - ONLY when shot framing actually contains lower body
            if has_pants:
                pants_color, pants_crop = process_crop(
                    (px1 + int(pw * 0.10), pants_y1, px2 - int(pw * 0.10), pants_y2),
                    f"pants_{idx}",
                )
                pants_c_name = pants_color.capitalize() if pants_color != "neutral" else "Tailored"
                products.append(
                    ProductMatch(
                        name=f"{pants_c_name} Office Work Trousers",
                        category="Clothing",
                        search_query=f"{pants_color} stretch office dress pants slacks trousers",
                        description=f"Tailored {pants_color} stretch office trousers",
                        icon="👖",
                        similarity=0.88,
                        color=pants_color,
                        crop_path=pants_crop,
                    )
                )

        # 2. Electronics & Computing (Monitors, CPU / Computer towers, Laptops)
        tv_dets = [d for d in detections if d.label.lower() in ("tv", "laptop")]
        for idx, td in enumerate(tv_dets[:2]):
            tv_color, tv_crop = process_crop(td.bbox, f"screen_{idx}")
            is_laptop = td.label.lower() == "laptop"
            name = "Portable Laptop Computer" if is_laptop else "Slim-Bezel LCD Desktop Monitor"
            query = f"laptop computer notebook {tv_color}" if is_laptop else f"24 inch 27 inch ips lcd desktop computer monitor {tv_color}"
            products.append(
                ProductMatch(
                    name=name,
                    category="Electronics",
                    search_query=query,
                    description="Workplace computing display / laptop device",
                    icon="💻" if is_laptop else "🖥️",
                    similarity=0.94,
                    color=tv_color,
                    crop_path=tv_crop,
                )
            )

        if "tv" in labels or "laptop" in labels:
            products.append(
                ProductMatch(
                    name="Desktop PC Tower Workstation",
                    category="Electronics",
                    search_query="desktop pc tower computer workstation case black",
                    description="Workstation desktop computer tower / PC system chassis",
                    icon="💻",
                    similarity=0.91,
                    color="black",
                )
            )

        # 3. Furniture (Chairs, Sofas, Beds, Desks)
        chair_dets = [d for d in detections if d.label.lower() == "chair"]
        for idx, cd in enumerate(chair_dets[:2]):
            chair_color, chair_crop = process_crop(cd.bbox, f"chair_{idx}")
            c_label = chair_color.capitalize() if chair_color != "neutral" else "Ergonomic"
            products.append(
                ProductMatch(
                    name=f"{c_label} Swivel Mesh Office Chair",
                    category="Furniture",
                    search_query=f"{chair_color} ergonomic swivel mesh office chair high back",
                    description=f"{c_label} high-back computer desk chair with lumbar support",
                    icon="🪑",
                    similarity=0.93,
                    color=chair_color,
                    crop_path=chair_crop,
                )
            )

        couch_dets = [d for d in detections if d.label.lower() in ("couch", "sofa")]
        for idx, cd in enumerate(couch_dets[:2]):
            couch_color, couch_crop = process_crop(cd.bbox, f"couch_{idx}")
            c_label = couch_color.capitalize() if couch_color != "neutral" else "Comfort"
            products.append(
                ProductMatch(
                    name=f"{c_label} Living Room Sofa / Couch",
                    category="Furniture",
                    search_query=f"{couch_color} living room sofa couch cushion upholstery",
                    description=f"{c_label} upholstered living room couch / seating",
                    icon="🛋️",
                    similarity=0.92,
                    color=couch_color,
                    crop_path=couch_crop,
                )
            )

        bed_dets = [d for d in detections if d.label.lower() == "bed"]
        for idx, bd in enumerate(bed_dets[:1]):
            bed_color, bed_crop = process_crop(bd.bbox, f"bed_{idx}")
            c_label = bed_color.capitalize() if bed_color != "neutral" else "Modern"
            products.append(
                ProductMatch(
                    name=f"{c_label} Bedroom Bed / Bedframe",
                    category="Furniture",
                    search_query=f"{bed_color} modern bed frame upholstered headboard",
                    description=f"{c_label} bedroom bed frame and headboard",
                    icon="🛏️",
                    similarity=0.91,
                    color=bed_color,
                    crop_path=bed_crop,
                )
            )

        if ("dining table" in labels or "tv" in labels) and not any("Desk" in p.name for p in products):
            products.append(
                ProductMatch(
                    name="Modern Office Workstation Desk",
                    category="Furniture",
                    search_query="modern office computer workstation desk cable management",
                    description="Sturdy workplace writing desk / computer workstation",
                    icon="🏢",
                    similarity=0.86,
                )
            )

        # 4. Appliances (Microwave, Refrigerator)
        mw_dets = [d for d in detections if d.label.lower() == "microwave"]
        for idx, md in enumerate(mw_dets[:1]):
            mw_color, mw_crop = process_crop(md.bbox, f"microwave_{idx}")
            c_label = mw_color.capitalize() if mw_color != "neutral" else "Countertop"
            products.append(
                ProductMatch(
                    name=f"{c_label} Countertop Microwave Oven",
                    category="Appliances",
                    search_query=f"{mw_color} compact countertop microwave oven 900w",
                    description=f"Digital {mw_color} countertop microwave with turntable",
                    icon="🍳",
                    similarity=0.92,
                    color=mw_color,
                    crop_path=mw_crop,
                )
            )

        fridge_dets = [d for d in detections if d.label.lower() == "refrigerator"]
        for idx, fd in enumerate(fridge_dets[:1]):
            fridge_color, fridge_crop = process_crop(fd.bbox, f"fridge_{idx}")
            c_label = fridge_color.capitalize() if fridge_color != "neutral" else "Compact"
            products.append(
                ProductMatch(
                    name=f"{c_label} Mini Refrigerator / Cooler",
                    category="Appliances",
                    search_query=f"{fridge_color} compact mini fridge single door",
                    description=f"Single-door {fridge_color} beverage and snack mini fridge",
                    icon="🧊",
                    similarity=0.89,
                    color=fridge_color,
                    crop_path=fridge_crop,
                )
            )

        # 5. Daily Gear & Personal Devices (Bags, Phones, Bottles, Drinkware)
        phone_dets = [d for d in detections if d.label.lower() == "cell phone"]
        for idx, pd in enumerate(phone_dets[:1]):
            phone_color, phone_crop = process_crop(pd.bbox, f"phone_{idx}")
            products.append(
                ProductMatch(
                    name="Smartphone / Mobile Device",
                    category="Electronics",
                    search_query="smartphone 5g mobile phone oled",
                    description="Modern touchscreen smartphone mobile device",
                    icon="📱",
                    similarity=0.90,
                    color=phone_color,
                    crop_path=phone_crop,
                )
            )

        cup_dets = [d for d in detections if d.label.lower() in ("cup", "bottle", "wine glass")]
        for idx, cpd in enumerate(cup_dets[:1]):
            cup_color, cup_crop = process_crop(cpd.bbox, f"drink_{idx}")
            c_label = cup_color.capitalize() if cup_color != "neutral" else "Classic"
            is_bottle = cpd.label.lower() == "bottle"
            item_name = "Water / Beverage Bottle" if is_bottle else "Ceramic Coffee Mug / Cup"
            item_query = (
                f"{cup_color} stainless steel water bottle reusable"
                if is_bottle
                else f"{cup_color} ceramic coffee mug cup"
            )
            products.append(
                ProductMatch(
                    name=f"{c_label} {item_name}",
                    category="Kitchen",
                    search_query=item_query,
                    description=f"{c_label} {item_name.lower()}",
                    icon="🍾" if is_bottle else "☕",
                    similarity=0.89,
                    color=cup_color,
                    crop_path=cup_crop,
                )
            )

        bag_dets = [d for d in detections if d.label.lower() in ("backpack", "handbag", "suitcase")]
        for idx, bg in enumerate(bag_dets[:1]):
            bag_color, bag_crop = process_crop(bg.bbox, f"bag_{idx}")
            c_label = bag_color.capitalize() if bag_color != "neutral" else "Travel"
            b_type = bg.label.lower()
            name_map = {
                "backpack": "Everyday Backpack",
                "handbag": "Shoulder Handbag",
                "suitcase": "Rolling Travel Suitcase",
            }
            products.append(
                ProductMatch(
                    name=f"{c_label} {name_map.get(b_type, 'Bag')}",
                    category="Accessories",
                    search_query=f"{bag_color} {b_type} waterproof lightweight",
                    description=f"{c_label} {b_type} for daily commute / travel",
                    icon="🎒" if b_type == "backpack" else ("🧳" if b_type == "suitcase" else "👜"),
                    similarity=0.91,
                    color=bag_color,
                    crop_path=bag_crop,
                )
            )

        return products

    def analyze(self, image_path: str | Path) -> FrameAnalysis:
        """Run enabled vision stages on a captured frame image."""
        path = Path(image_path)
        if not path.is_file():
            logger.debug("Vision analysis skipped: image not found at %s", path)
            return FrameAnalysis()

        detections = self.detect_objects(path)
        caption = self.caption_scene(path, detections=detections)
        products = self.match_products(image_path=path, detections=detections)

        return FrameAnalysis(
            scene_caption=caption,
            detections=detections,
            landmarks=self.match_landmarks([]),
            products=products,
        )
