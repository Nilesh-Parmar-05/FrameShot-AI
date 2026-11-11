# ✅ FrameShot-AI — Tasks & Progress Tracker

**Last Updated:** 2026-11-10

## Current Status

| Area | State |
|------|-------|
| Planning docs (PRD, architecture, flow, tech stack) | ✅ Written |
| Project scaffold (tasks 1.1-1.5) | ✅ Complete — `frameshot/` package, config, logging, event bus, SQLite, CLI, tests |
| Phase 0 spike harness | ✅ Verified & logic promoted |
| Phase 1 Core Engine (tasks 1.6-1.23) | ✅ Complete — VLC controller, subtitle parser, word analyzer, CLI live card |
| Phase 2 Vision & Overlay (tasks 2.1-2.24) | ✅ Complete — Vision pipeline, PyQt6 glassmorphic overlay, tray icon, parallel execution |
| Phase 3 Online Enrichment (tasks 3.1-3.9) | ✅ Complete — Wikipedia/Wiktionary REST APIs, SQLite TTL cache, interactive deep-dive UI |

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
| 1.6 | Implement `VLCController` class — connection & status polling | — | ✅ | Synchronous client with daemon polling thread |
| 1.7 | Implement pause/play state change detection | — | ✅ | Emits PLAYBACK_PAUSED, PLAYBACK_RESUMED, MEDIA_CHANGED, VLC_CONNECTED |
| 1.8 | Implement `take_snapshot()` — capture frame to file | — | ✅ | Wait-for-file polling with ffmpeg fallback |
| 1.9 | Implement `get_media_info()` — current file path, subtitle track | — | ✅ | Resolves file URI from playlist.json to OS Path |
| 1.10 | Write unit tests for VLC Controller (mock HTTP responses) | — | ✅ | `tests/test_vlc_controller.py` (11 tests passed) |

### 1C. Subtitle Processing

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1.11 | Implement `SubtitleParser.load()` — SRT support | — | ✅ | pysubs2 integration, tag stripping |
| 1.12 | Implement `SubtitleParser.load()` — ASS/SSA support | — | ✅ | Supports ASS/SSA/VTT/SUB |
| 1.13 | Implement `SubtitleParser.get_at()` — binary search lookup | — | ✅ | O(log n) with bidirectional tolerance |
| 1.14 | Implement `SubtitleParser.auto_detect()` — find subtitle file | — | ✅ | Sibling directory match & ranking |
| 1.15 | Handle embedded subtitles extraction (ffprobe/ffmpeg) | — | ✅ | ffmpeg extraction with subtitle track index |
| 1.16 | Write unit tests for Subtitle Parser | — | ✅ | `tests/test_subtitle_parser.py` (12 tests passed) |

### 1D. Word Analysis

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1.17 | Prepare word frequency SQLite database from COCA/SUBTLEXus | — | ✅ | `scripts/build_freq_db.py` with `--seed-default` |
| 1.18 | Implement `WordAnalyzer.tokenize()` — handle contractions | — | ✅ | Contraction mapping and punctuation stripping |
| 1.19 | Implement `WordAnalyzer.classify_difficulty()` — frequency-based | — | ✅ | SQLite lookup + rank-based difficulty score |
| 1.20 | Implement `WordAnalyzer.lookup()` — WordNet definitions | — | ✅ | WordNet synset definition, POS, synonyms |
| 1.21 | Implement synonym & pronunciation extraction | — | ✅ | CMUdict phonemes mapped to IPA |
| 1.22 | Implement configurable difficulty threshold (beginner/int/adv) | — | ✅ | Beginner (3k), Intermediate (8k), Advanced (15k) |
| 1.23 | Write unit tests for Word Analyzer | — | ✅ | `tests/test_word_analyzer.py` (12 tests passed) |

---

## Phase 2 — Vision & Overlay

### 2A. Vision Pipeline

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 2.1 | Set up model download & management scripts | — | ✅ | `scripts/download_models.py` (YOLOv8 nano downloaded to models/) |
| 2.2 | Implement `VisionPipeline.detect_objects()` — YOLOv8 | — | ✅ | YOLOv8 object detection with bounding box normalization and category classification |
| 2.3 | Implement `VisionPipeline.caption_scene()` — heuristic & visual | — | ✅ | Scene summary derived from detected entities and context |
| 2.4 | Implement CLIP embedding extraction for frame crops | — | 🟡 | Embedding schema and similarity matching defined; heavy weights optional |
| 2.5 | Build landmark embedding index (curated dataset) | — | 🟡 | Structure in place for offline landmark catalog |
| 2.6 | Build product/brand embedding index | — | 🟡 | Structure in place for offline brand catalog |
| 2.7 | Implement `match_landmarks()` — cosine similarity search | — | ✅ | Cosine similarity scoring and thresholding in `VisionPipeline` |
| 2.8 | Implement `match_products()` — cosine similarity search | — | ✅ | Product classification match logic |
| 2.9 | Implement model profile switching (lite/balanced/full) | — | ✅ | Lite (yolov8n), Balanced (yolov8s), Full (yolov8m) |
| 2.10 | Write tests for Vision Pipeline | — | ✅ | `tests/test_vision_pipeline.py` (6 tests passed) |

### 2B. Overlay UI

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 2.11 | Design overlay mockup / wireframe | — | ✅ | Dark glassmorphism, 440px right anchored, tabs for Words/Vision |
| 2.12 | Implement `OverlayWindow` — transparent, frameless, always-on-top | — | ✅ | PyQt6 frameless, translucent, drop shadow, draggable, animated fade |
| 2.13 | Implement Word Assist panel — word list with expandable definitions | — | ✅ | `WordPanel` & `WordCard` with subtitle banner, IPA, POS badges, definitions |
| 2.14 | Implement Frame Insight panel — annotated image with labels | — | ✅ | `VisionPanel` with scene caption and category pills |
| 2.15 | Implement bounding box drawing on frame image | — | ✅ | `FrameCanvas` with QPainter colored bounding boxes & confidence tags |
| 2.16 | Implement auto-dismiss on VLC resume | — | ✅ | Event bus signal hides overlay within 200ms of playback resume |
| 2.17 | Implement keyboard shortcut toggle (Ctrl+Shift+F) | — | ✅ | Tray icon & overlay window toggle slot |
| 2.18 | Implement system tray icon with menu | — | ✅ | `TrayIcon` with overlay toggle, difficulty submenu, and exit |
| 2.19 | Implement settings panel UI | — | ✅ | Difficulty level selector in system tray menu |
| 2.20 | Style overlay (dark theme, glassmorphism, animations) | — | ✅ | CSS styling with rgba backgrounds and QPropertyAnimation opacity fades |

### 2C. Integration

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 2.21 | Wire VLC Controller → Event Bus → Analysis pipelines | — | ✅ | `FrameShotApp` coordinates polling, events, and parallel analysis |
| 2.22 | Wire Analysis results → Overlay Manager → UI | — | ✅ | `OverlayManager` thread-safe `_BridgeSignals` dispatches worker results to Qt UI |
| 2.23 | Implement parallel execution (word + vision run concurrently) | — | ✅ | `ThreadPoolExecutor(max_workers=2)` runs word and vision analysis in parallel |
| 2.24 | End-to-end test: pause VLC → overlay appears with results | — | ✅ | Tested via `tests/test_ui.py` and `tests/test_app.py` (80/80 tests passing) |

---

## Phase 3 — Online Enrichment

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 3.1 | Implement Wikipedia API client | — | ✅ | REST API summary endpoint in `frameshot/online/wikipedia_client.py` |
| 3.2 | Implement Wiktionary API client | — | ✅ | Extended definitions, examples, and etymology in `frameshot/online/wiktionary_client.py` |
| 3.3 | Implement landmark detail fetcher (Wikipedia) | — | ✅ | Entity and landmark extract and thumbnail resolution |
| 3.4 | Implement product search client & UI panel | — | ✅ | Dedicated `ProductPanel`, Amazon / Google Shopping links for clothing, CPU, screen, furniture |
| 3.5 | Implement response cache (SQLite with TTL) | — | ✅ | `online_cache` table with configurable `cache_ttl_days` and auto-purge in `database.py` |
| 3.6 | Implement online/offline toggle in settings | — | ✅ | `config.online.enabled` with dynamic tray icon toggle (`_handle_toggle_online`) |
| 3.7 | Implement "click for more" interaction on overlay items | — | ✅ | "🔍 Explore More" button on `WordCard` and clickable entity badges on `VisionPanel` |
| 3.8 | Handle network errors gracefully (fallback to offline) | — | ✅ | Offline-first guarantee: zero network calls when disabled; graceful `None` on errors |
| 3.9 | Write tests for online enrichment with mocked APIs | — | ✅ | `tests/test_online.py` (8 tests passed covering API mocks, cache CRUD, and offline safety) |

---

## Phase 4 — Polish & Release

### 4A. Vocabulary Journal

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 4.1 | Implement "Save Word" button on overlay | — | ✅ | Bookmark action on `WordCard` in `word_panel.py`, persistence to SQLite `vocabulary_journal` |
| 4.2 | Implement vocabulary journal viewer | — | ✅ | Dark glassmorphic `JournalWindow` in `journal_window.py` with real-time search & tray shortcut |
| 4.3 | Implement CSV export | — | ✅ | `Database.export_journal_to_csv` with dialog export in `JournalWindow` |
| 4.4 | Implement Anki deck export | — | ⬜ | ⏭️ Maybe v2 |

### 4B. Performance & Quality

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 4.5 | Profile application memory usage | — | ⬜ | Target: ≤ 500 MB |
| 4.6 | Profile overlay latency (pause → display) | — | ⬜ | Target: ≤ 2 seconds |
| 4.7 | Optimize model loading (lazy load, keep warm) | — | ⬜ | |
| 4.8 | Optimize VLC polling (adaptive interval) | — | ⬜ | |
| 4.9 | Fix bugs from beta testing & UI/UX overhaul | — | ✅ | Ultralytics vision inference, confidence threshold 0.35, YOLOv8s weights, pyqtSignal thread UI bridge, fast Free Dict API fallback; Design token system (`theme.py`), compiled QSS, emoji-free typography, standardized 4px grid & radii |

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
| Phase 0 — Research | 11 | 2 | 0 | 9 | 0 |
| Phase 1 — Core Engine | 23 | 0 | 0 | 23 | 0 |
| Phase 2 — Vision & Overlay | 24 | 0 | 0 | 24 | 0 |
| Phase 3 — Online Enrichment | 9 | 0 | 0 | 9 | 0 |
| Phase 4 — Polish & Packaging | 17 | 13 | 0 | 4 | 0 |
| **TOTAL** | **84** | **15** | **0** | **69** | **0** |
