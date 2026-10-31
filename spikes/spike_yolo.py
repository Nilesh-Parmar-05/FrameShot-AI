"""Task 0.8 - YOLOv8 object detection on a captured frame (CPU).

Answers:

  * Cold model load and per-frame inference latency on this machine?
  * Are the 80 COCO classes enough for the "frame insight" feature, or do we
    need landmarks/products (CLIP index, tasks 2.5-2.8) anyway?
  * Peak memory: does YOLOv8n fit NFR-02's 500 MB budget?

Usage:

    pip install -r requirements-vision.txt
    python spikes/spike_yolo.py data/snapshots/frame.png
    python spikes/spike_yolo.py data/snapshots/frame.png --model yolov8s.pt --repeat 5
"""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

from _util import REPO_ROOT, banner, die, ensure_out_dir, step, verdict

MODELS_DIR = REPO_ROOT / "models"


def peak_rss_mb() -> float | None:
    """Peak resident memory of this process, if psutil is available."""
    try:
        import psutil
    except ImportError:
        return None
    return psutil.Process().memory_info().rss / (1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("image", type=Path, help="PNG/JPG frame captured by spike_snapshot.py")
    parser.add_argument("--model", default="yolov8n.pt", help="weights file (default yolov8n.pt)")
    parser.add_argument("--conf", type=float, default=0.25, help="confidence threshold")
    parser.add_argument("--repeat", type=int, default=3, help="timed inferences")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument(
        "--save-annotated", action="store_true", help="write an annotated copy to spikes/out/"
    )
    args = parser.parse_args()

    banner("Task 0.8 - YOLOv8 CPU inference")
    image_path = args.image if args.image.is_absolute() else (Path.cwd() / args.image)
    if not image_path.is_file():
        die(f"image not found: {image_path}\n  Run spikes/spike_snapshot.py first, or pass --keep.")

    try:
        import torch
        from ultralytics import YOLO
    except ImportError:
        die("vision dependencies are missing - run: pip install -r requirements-vision.txt")

    print(f"torch: {torch.__version__}  cuda available: {torch.cuda.is_available()}")
    print(f"cpu threads: {torch.get_num_threads()}")
    print(f"image: {image_path}  ({image_path.stat().st_size} bytes)")

    step(f"loading {args.model}")
    started = time.perf_counter()
    model = YOLO(args.model)  # downloads the weights on first use
    load_ms = (time.perf_counter() - started) * 1_000
    print(f"  loaded in {load_ms:.0f} ms")

    step("warm-up inference")
    model.predict(source=str(image_path), conf=args.conf, imgsz=args.imgsz, verbose=False)

    step(f"{args.repeat} timed inferences")
    latencies: list[float] = []
    result = None
    for index in range(args.repeat):
        started = time.perf_counter()
        result = model.predict(
            source=str(image_path), conf=args.conf, imgsz=args.imgsz, verbose=False
        )[0]
        latency = (time.perf_counter() - started) * 1_000
        latencies.append(latency)
        print(f"  {index + 1}: {latency:7.0f} ms")

    assert result is not None
    step(f"detections @ conf >= {args.conf}")
    boxes = result.boxes
    names = result.names
    detections: list[tuple[str, float, tuple[int, int, int, int]]] = []
    if boxes is None or len(boxes) == 0:
        print("  none")
    else:
        for box in boxes:
            label = names[int(box.cls[0])]
            confidence = float(box.conf[0])
            coordinates = tuple(int(value) for value in box.xyxy[0].tolist())
            detections.append((label, confidence, coordinates))  # type: ignore[arg-type]
        for label, confidence, coordinates in sorted(detections, key=lambda d: -d[1]):
            print(f"  {confidence:5.2f}  {label:<18} {coordinates}")

    if args.save_annotated and detections:
        from PIL import Image

        out_dir = ensure_out_dir()
        target = out_dir / f"yolo_{image_path.stem}.jpg"
        annotated = result.plot()  # BGR numpy array
        Image.fromarray(annotated[:, :, ::-1]).save(target)
        print(f"  annotated copy: {target}")

    mean_ms = statistics.mean(latencies)
    rss = peak_rss_mb()

    step("summary")
    print(f"  cold load:      {load_ms:.0f} ms")
    print(
        f"  inference mean: {mean_ms:.0f} ms (min {min(latencies):.0f}, max {max(latencies):.0f})"
    )
    print(f"  process RSS:    {f'{rss:.0f} MB' if rss else 'n/a (install psutil)'}")
    print(f"  detections:     {len(detections)}")

    ok = True
    ok &= verdict(len(detections) >= 1, "at least one object detected")
    ok &= verdict(mean_ms < 500, f"inference {mean_ms:.0f} ms (perf budget < 500 ms on CPU)")
    if rss is not None:
        ok &= verdict(rss < 500, f"RSS {rss:.0f} MB (NFR-02 budget 500 MB)")

    if not detections:
        print("\nZero detections usually means a black or near-black frame.")
        print("Re-run spikes/spike_snapshot.py --keep and check mean_luma, then relaunch")
        print("VLC with --avcodec-hw=none.")

    banner("Phase 0.8 verdict")
    print("What to record in tasks.md 0.8:")
    print(f"  - yolov8n @ {args.imgsz}px on this CPU: {mean_ms:.0f} ms/frame")
    print("  - COCO classes cover people/vehicles/furniture; they do NOT cover")
    print("    landmarks named in FR-32 or brands in FR-33.")
    print("  - therefore the CLIP + FAISS index (tasks 2.4-2.8) is not optional")
    print("    for the headline 'Eiffel Tower' acceptance criterion.")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
