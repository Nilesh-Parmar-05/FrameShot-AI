# 🛠️ FrameShot-AI — Technology Stack

---

## 1. Core Language & Runtime

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Language | **Python** | 3.11+ | Best-in-class ML/AI ecosystem; rich VLC/media libraries; rapid prototyping. |
| Package Manager | **pip + venv** (or Poetry) | Latest | Simple, reproducible environments. |

### Why Python?
- **ML Models**: PyTorch, Transformers, Ultralytics — all have first-class Python support.
- **VLC Bindings**: `python-vlc` exists, and VLC's HTTP API is easily consumed via `requests`.
- **Rapid Iteration**: Quick to prototype and iterate during spike phase.
- **Trade-off**: Slower than Rust/C++ for raw performance, but ML inference dominates the latency budget, not Python overhead.

### Alternatives Considered
| Alternative | Why Not |
|-------------|---------|
| C++ / Qt | Faster runtime, but ML model integration is significantly harder. |
| Electron + Node.js | Heavier RAM footprint (~200 MB base); Python ML ecosystem is superior. |
| Rust | Excellent performance, but ML ecosystem is immature; ONNX Runtime is an option but adds complexity. |

---

## 2. GUI Framework

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Desktop GUI | **PyQt6** or **PySide6** | 6.6+ | Native widgets, frameless/transparent windows, cross-platform. |

### Key Capabilities Needed
- ✅ Transparent / semi-transparent overlay windows
- ✅ Frameless, always-on-top windows
- ✅ Click-through regions (optional)
- ✅ Rich text rendering for definitions
- ✅ Image display with overlay annotations (bounding boxes)
- ✅ System tray icon support
- ✅ Global hotkey support (via `QShortcut` or platform APIs)

### Alternatives Considered
| Alternative | Why Not |
|-------------|---------|
| Tkinter | Limited transparency support; dated appearance. |
| Dear ImGui (Python) | Excellent for debug UIs, but harder to polish for end-user overlay. |
| Electron | Overkill; heavy memory overhead for a simple overlay. |
| CustomTkinter | Better than Tkinter, but still limited transparency/overlay capabilities. |

---

## 3. VLC Integration

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Communication | **VLC HTTP Interface** (port 8080) | Built-in, no plugins needed; works on all platforms; JSON API. |
| HTTP Client | **`requests`** (sync) / **`httpx`** (async) | Lightweight, reliable. |
| Frame Capture | **VLC snapshot command** via HTTP API | `/requests/status.json?command=snapshot`; saves frame to disk. |

### VLC HTTP API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /requests/status.json` | Get current state (playing/paused), timestamp, filename, length. |
| `GET /requests/status.json?command=snapshot` | Capture current frame as image. |
| `GET /requests/status.json?command=pl_pause` | Toggle pause (for testing). |
| `GET /requests/playlist.json` | Get playlist info / current file path. |

### Setup Required by User
The user must enable VLC's HTTP interface:
1. VLC → Tools → Preferences → Show All
2. Interface → Main interfaces → Check "Web"
3. Interface → Main interfaces → Lua → Set HTTP password

---

## 4. Subtitle Processing

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Subtitle Parser | **`pysubs2`** | 1.7+ | Supports SRT, ASS, SSA, MicroDVD; clean API; actively maintained. |
| Embedded Sub Extraction | **`ffprobe` + `ffmpeg`** | 6.x | Extract subtitle tracks from MKV/MP4 containers. |

---

## 5. NLP & Word Analysis

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Tokenization | **`nltk`** (word_tokenize) | 3.8+ | Lightweight; handles contractions; offline. |
| Stopword Filtering | **`nltk.corpus.stopwords`** | — | Standard English stopword list. |
| Lemmatization | **`nltk.stem.WordNetLemmatizer`** | — | Map word forms to base forms for dictionary lookup. |
| Dictionary | **`nltk.corpus.wordnet`** | — | Offline English dictionary: definitions, synonyms, examples. |
| Word Frequency | **SUBTLEXus** dataset (bundled as SQLite) | — | Word frequency based on movie subtitles — perfect for our use case. |
| Pronunciation | **`eng-to-ipa`** or CMU Pronouncing Dict | — | IPA transcription for English words. |

### Why Not spaCy?
- spaCy models are larger (50–500 MB) and include POS tagging, NER, and dependency parsing we don't need.
- NLTK's tokenizer + WordNet is sufficient and much lighter for our word-level analysis.
- We can upgrade to spaCy later if we need sentence-level understanding.

---

## 6. Vision / AI Models

### 6.1 Object Detection

| Component | Choice | Model Size | Rationale |
|-----------|--------|-----------|-----------|
| Framework | **Ultralytics (YOLOv8)** | — | Best Python API for YOLO; single-line inference. |
| Default Model | **YOLOv8n** (nano) | ~6 MB | Fast CPU inference (< 500ms); 80 COCO classes. |
| Upgraded Model | **YOLOv8s** (small) | ~22 MB | Better accuracy; used in "balanced" profile. |

### 6.2 Scene Captioning

| Component | Choice | Model Size | Rationale |
|-----------|--------|-----------|-----------|
| Framework | **HuggingFace Transformers** | — | Unified API for all captioning models. |
| Default Model | **BLIP-2 OPT-2.7B** (INT8 quantized) | ~1.4 GB | Good quality captions; INT8 reduces memory. |
| Lite Alternative | **Florence-2-base** | ~450 MB | Smaller, faster, acceptable quality. |

### 6.3 Embedding & Similarity (Landmarks / Products)

| Component | Choice | Model Size | Rationale |
|-----------|--------|-----------|-----------|
| Embedding Model | **CLIP ViT-B/32** | ~340 MB | General-purpose image-text embeddings. |
| Similarity Search | **FAISS** (CPU) | — | Fast approximate nearest neighbor search. |
| Landmark Index | Custom (curated ~1000 landmarks) | ~50 MB | Pre-computed CLIP embeddings + metadata. |
| Product Index | Custom (curated ~500 brands/products) | ~25 MB | Pre-computed CLIP embeddings + metadata. |

### Model Profiles Summary

| Profile | Object Detection | Captioning | CLIP | Total Size | Est. RAM |
|---------|-----------------|-----------|------|-----------|----------|
| **Lite** | YOLOv8n (6 MB) | None | None | ~56 MB | ~200 MB |
| **Balanced** | YOLOv8s (22 MB) | Florence-2-base (450 MB) | CLIP ViT-B/32 (340 MB) | ~890 MB | ~400 MB |
| **Full** | YOLOv8m (50 MB) | BLIP-2 OPT-2.7B INT8 (1.4 GB) | CLIP ViT-B/32 (340 MB) | ~1.85 GB | ~600 MB |

---

## 7. Data Storage

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Database | **SQLite** | Zero-config, file-based, perfect for desktop apps. |
| Config Format | **YAML** (`pyyaml`) | Human-readable, easy to edit manually. |
| Config Validation | **Pydantic** | Type-safe config loading with defaults. |

---

## 8. Online Enrichment APIs

| Service | API | Auth Required | Rate Limit | Notes |
|---------|-----|--------------|------------|-------|
| Wikipedia | REST API v1 (`/api/rest_v1/page/summary/`) | No | Generous | Summary + thumbnail |
| Wiktionary | MediaWiki API | No | Generous | Extended word definitions |
| OpenStreetMap / Nominatim | REST API | No | 1 req/sec | Place/landmark info |

> **Note:** All online APIs are optional and disabled by default (offline-first).

---

## 9. Testing

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Test Framework | **pytest** | De facto standard for Python. |
| Mocking | **`unittest.mock`** / **`pytest-mock`** | Mock VLC HTTP responses, model outputs. |
| Coverage | **`pytest-cov`** | Track code coverage. |

---

## 10. Packaging & Distribution

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Bundler | **PyInstaller** | Mature; handles PyQt6 + PyTorch well. |
| Installer (Windows) | **Inno Setup** | Free, reliable, widely used. |
| Alternative Bundler | **Nuitka** | Compiles to C; smaller output; better performance. |

---

## 11. Development Tools

| Tool | Purpose |
|------|---------|
| **Black** | Code formatting |
| **Ruff** | Fast linting |
| **mypy** | Static type checking |
| **pre-commit** | Git hooks for formatting/linting |
| **Git** | Version control |
