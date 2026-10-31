# ✅ FrameShot-AI — Tasks & Progress Tracker

**Last Updated:** 2026-10-31

## Current Status

| Area | State |
|------|-------|
| Planning docs (PRD, architecture, flow, tech stack) | ✅ Written |
| Project scaffold (tasks 1.1-1.5) | ✅ Complete — `frameshot/` package, config, logging, event bus, SQLite, CLI, tests |
| Phase 0 spike harness | 🟡 Ready to run — `spikes/*.py`; results still have to be recorded |
| Core engine / vision / overlay | ⬜ Not started |

Verify the environment at any time with:

```bash
python -m frameshot doctor      # python, ffmpeg, VLC binary, VLC HTTP, DB, models
python -m frameshot             # start the app (monitoring loop still a stub)
```

---

## Legend

| Status | Meaning |
|--------|---------|
| ⬜ | Not started |
| 🟡 | In progress |
| ✅ | Complete |
| 🔴 | Blocked |
| ⏭️ | Deferred to future version |

---

## Phase 0 — Research & Spike

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 0.1 | Research VLC HTTP interface — endpoints, auth, capabilities | — | 🟡 | Harness: `spikes/spike_vlc.py --dump`. Findings: status.json has state/time/length; absolute path only in playlist.json |
| 0.2 | Spike: Connect to VLC HTTP, read status, detect pause/play | — | 🟡 | Harness: `spikes/spike_vlc.py --watch 20`. Record detection latency at 200 ms polling |
| 0.3 | Spike: Capture frame from VLC via snapshot command | — | 🟡 | Harness: `spikes/spike_snapshot.py --keep`. API takes no output path; VLC writes to its configured snapshot dir |
| 0.4 | Spike: Parse SRT file, lookup subtitle by timestamp | — | 🟡 | Harness: `spikes/spike_subs.py`. Verified on `tests/fixtures/sample.srt` (0.5 µs/lookup) |
| 0.5 | Spike: Parse ASS/SSA subtitle files | — | 🟡 | Harness: `spikes/spike_subs.py tests/fixtures/sample.ass`. Verified; markup stripped by `plaintext` |
| 0.6 | Research word frequency datasets (COCA, BNC, SUBTLEXus) | — | 🟡 | Harness: `spikes/spike_wordnet.py`. Fallback rank source = NLTK Brown until SUBTLEXus is chosen |
| 0.7 | Spike: WordNet offline dictionary lookup via NLTK | — | 🟡 | Harness: `spikes/spike_wordnet.py`. WordNet has no IPA → CMUdict + ARPAbet mapping |
| 0.8 | Spike: YOLOv8 nano inference on a sample image (CPU) | — | 🟡 | Harness: `spikes/spike_yolo.py`. Needs `requirements-vision.txt` + a captured frame |
| 0.9 | Spike: BLIP-2 / Florence-2 scene captioning (CPU, quantized) | — | ⬜ | Still the biggest open risk: < 1.5 s CPU captioning is unproven |
| 0.10 | Spike: PyQt6 transparent overlay window | — | ⬜ | PyQt6 not installed yet; test frameless + translucent + click-through |
| 0.11 | Document spike findings & finalize tech choices | — | ⬜ | Drafts exist; update with measured numbers from 0.1-0.10 |

---

## Phase 1 — Core Engine

### 1A. Project Setup

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1.1 | Initialize Python project (pyproject.toml, virtual env) | — | ✅ | `pyproject.toml` + extras (`ui`, `nlp`, `vision`, `online`, `dev`) |
| 1.2 | Set up project directory structure | — | ✅ | Layout from CONTRIBUTING.md; module stubs with task IDs |
| 1.3 | Set up logging framework | — | ✅ | `frameshot/logging_setup.py` (console + rotating file) |
| 1.4 | Set up configuration loader (YAML) | — | ✅ | `frameshot/config.py` (pydantic v2, strict keys) + `config.example.yaml` |
| 1.5 | Set up SQLite database initialization | — | ✅ | `frameshot/database.py` (schema v1, WAL, per-thread connections) |

### 1B. VLC Integration

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1.6 | Implement `VLCController` class — connection & status polling | — | ⬜ | |
| 1.7 | Implement pause/play state change detection | — | ⬜ | |
| 1.8 | Implement `take_snapshot()` — capture frame to file | — | ⬜ | |
| 1.9 | Implement `get_media_info()` — current file path, subtitle track | — | ⬜ | |
| 1.10 | Write unit tests for VLC Controller (mock HTTP responses) | — | ⬜ | |

### 1C. Subtitle Processing

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1.11 | Implement `SubtitleParser.load()` — SRT support | — | ⬜ | |
| 1.12 | Implement `SubtitleParser.load()` — ASS/SSA support | — | ⬜ | |
| 1.13 | Implement `SubtitleParser.get_at()` — binary search lookup | — | ⬜ | |
| 1.14 | Implement `SubtitleParser.auto_detect()` — find subtitle file | — | ⬜ | Match by video filename |
| 1.15 | Handle embedded subtitles extraction (ffprobe/ffmpeg) | — | ⬜ | |
| 1.16 | Write unit tests for Subtitle Parser | — | ⬜ | |

### 1D. Word Analysis

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1.17 | Prepare word frequency SQLite database from COCA/SUBTLEXus | — | ⬜ | Pre-processing script |
| 1.18 | Implement `WordAnalyzer.tokenize()` — handle contractions | — | ⬜ | |
| 1.19 | Implement `WordAnalyzer.classify_difficulty()` — frequency-based | — | ⬜ | |
| 1.20 | Implement `WordAnalyzer.lookup()` — WordNet definitions | — | ⬜ | |
| 1.21 | Implement synonym & pronunciation extraction | — | ⬜ | |
| 1.22 | Implement configurable difficulty threshold (beginner/int/adv) | — | ⬜ | |
| 1.23 | Write unit tests for Word Analyzer | — | ⬜ | |

---

## Phase 2 — Vision & Overlay

### 2A. Vision Pipeline

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 2.1 | Set up model download & management scripts | — | ⬜ | Download YOLOv8, BLIP-2 |
| 2.2 | Implement `VisionPipeline.detect_objects()` — YOLOv8 | — | ⬜ | |
| 2.3 | Implement `VisionPipeline.caption_scene()` — BLIP-2/Florence-2 | — | ⬜ | |
| 2.4 | Implement CLIP embedding extraction for frame crops | — | ⬜ | |
| 2.5 | Build landmark embedding index (curated dataset) | — | ⬜ | ~1000 landmarks |
| 2.6 | Build product/brand embedding index | — | ⬜ | ~500 common brands |
| 2.7 | Implement `match_landmarks()` — cosine similarity search | — | ⬜ | |
| 2.8 | Implement `match_products()` — cosine similarity search | — | ⬜ | |
| 2.9 | Implement model profile switching (lite/balanced/full) | — | ⬜ | |
| 2.10 | Write tests for Vision Pipeline | — | ⬜ | |

### 2B. Overlay UI

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 2.11 | Design overlay mockup / wireframe | — | ⬜ | |
| 2.12 | Implement `OverlayWindow` — transparent, frameless, always-on-top | — | ⬜ | PyQt6 |
| 2.13 | Implement Word Assist panel — word list with expandable definitions | — | ⬜ | |
| 2.14 | Implement Frame Insight panel — annotated image with labels | — | ⬜ | |
| 2.15 | Implement bounding box drawing on frame image | — | ⬜ | |
| 2.16 | Implement auto-dismiss on VLC resume | — | ⬜ | |
| 2.17 | Implement keyboard shortcut toggle (Ctrl+Shift+F) | — | ⬜ | |
| 2.18 | Implement system tray icon with menu | — | ⬜ | |
| 2.19 | Implement settings panel UI | — | ⬜ | |
| 2.20 | Style overlay (dark theme, glassmorphism, animations) | — | ⬜ | |

### 2C. Integration

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 2.21 | Wire VLC Controller → Event Bus → Analysis pipelines | — | ⬜ | |
| 2.22 | Wire Analysis results → Overlay Manager → UI | — | ⬜ | |
| 2.23 | Implement parallel execution (word + vision run concurrently) | — | ⬜ | |
| 2.24 | End-to-end test: pause VLC → overlay appears with results | — | ⬜ | |

---

## Phase 3 — Online Enrichment

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 3.1 | Implement Wikipedia API client | — | ⬜ | REST API, summary endpoint |
| 3.2 | Implement Wiktionary API client | — | ⬜ | Extended definitions |
| 3.3 | Implement landmark detail fetcher (Wikipedia) | — | ⬜ | |
| 3.4 | Implement product search client | — | ⬜ | Search engine API |
| 3.5 | Implement response cache (SQLite with TTL) | — | ⬜ | |
| 3.6 | Implement online/offline toggle in settings | — | ⬜ | |
| 3.7 | Implement "click for more" interaction on overlay items | — | ⬜ | |
| 3.8 | Handle network errors gracefully (fallback to offline) | — | ⬜ | |
| 3.9 | Write tests for online enrichment with mocked APIs | — | ⬜ | |

---

## Phase 4 — Polish & Release

### 4A. Vocabulary Journal

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 4.1 | Implement "Save Word" button on overlay | — | ⬜ | |
| 4.2 | Implement vocabulary journal viewer | — | ⬜ | |
| 4.3 | Implement CSV export | — | ⬜ | |
| 4.4 | Implement Anki deck export | — | ⬜ | ⏭️ Maybe v2 |

### 4B. Performance & Quality

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 4.5 | Profile application memory usage | — | ⬜ | Target: ≤ 500 MB |
| 4.6 | Profile overlay latency (pause → display) | — | ⬜ | Target: ≤ 2 seconds |
| 4.7 | Optimize model loading (lazy load, keep warm) | — | ⬜ | |
| 4.8 | Optimize VLC polling (adaptive interval) | — | ⬜ | |
| 4.9 | Fix bugs from beta testing | — | ⬜ | |

### 4C. Packaging & Distribution

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 4.10 | Create PyInstaller build script | — | ⬜ | |
| 4.11 | Create Windows installer (Inno Setup) | — | ⬜ | |
| 4.12 | Test on clean Windows 10 VM | — | ⬜ | |
| 4.13 | Test on clean Windows 11 VM | — | ⬜ | |

### 4D. Documentation

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 4.14 | Write README.md with screenshots | — | ⬜ | |
| 4.15 | Write user guide (how to enable VLC HTTP interface) | — | ⬜ | |
| 4.16 | Write developer setup guide | — | ⬜ | |
| 4.17 | Record demo video / GIF | — | ⬜ | |

---

## Summary Dashboard

| Phase | Total Tasks | ⬜ Not Started | 🟡 In Progress | ✅ Done | 🔴 Blocked |
|-------|------------|----------------|-----------------|---------|------------|
| Phase 0 — Research | 11 | 2 | 9 | 0 | 0 |
| Phase 1 — Core | 23 | 18 | 0 | 5 | 0 |
| Phase 2 — Vision & Overlay | 24 | 24 | 0 | 0 | 0 |
| Phase 3 — Online | 9 | 9 | 0 | 0 | 0 |
| Phase 4 — Polish | 17 | 17 | 0 | 0 | 0 |
| **TOTAL** | **84** | **70** | **9** | **5** | **0** |
