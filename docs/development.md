# FrameShot-AI — Developer Guide

This guide covers setting up your development environment, codebase architecture, testing procedures, profiling benchmarks, and packaging.

---

## 1. Environment Setup

### Prerequisites
- **Python**: 3.11.x (recommended) or 3.12.x
- **OS**: Windows 10/11
- **VLC**: 3.0.x or higher
- **FFmpeg**: Installed on system `PATH` (used as snapshot fallback)

### Installation
Clone the repository and set up a virtual environment:

```powershell
git clone https://github.com/Nilesh-Parmar-05/FrameShot-AI.git
cd FrameShot-AI

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install package in editable mode with development dependencies
pip install -e .[dev,nlp,vision,online,ui]

# Download models and build default word frequency database
python scripts/download_models.py
python scripts/build_freq_db.py --seed-default
```

---

## 2. Project Architecture & Directory Structure

```
FrameShot-AI/
├── frameshot/                  # Core package
│   ├── ui/                     # PyQt6 user interface components
│   │   ├── theme.py            # Central design tokens & QSS stylesheet compiler
│   │   ├── overlay_window.py   # Dark-glass translucent, frameless overlay window
│   │   ├── word_panel.py       # Word assist panel with CEFR difficulty filtering
│   │   ├── vision_panel.py     # Frame insight panel with bounding box canvas
│   │   ├── product_panel.py    # Fashion, apparel, gear shopping & Google Lens
│   │   ├── journal_window.py   # Vocabulary journal manager & CSV export
│   │   └── tray_icon.py        # System tray menu and global shortcuts
│   ├── online/                 # Online enrichment clients
│   │   ├── enrichment_service.py # Parallel aggregator & SQLite TTL cache
│   │   ├── wikipedia_client.py # Wikipedia REST summary API client
│   │   └── wiktionary_client.py# Wiktionary definitions & etymology
│   ├── app.py                  # Application lifecycle and event coordination
│   ├── config.py               # Pydantic v2 configuration schema
│   ├── database.py             # SQLite WAL database & journal repository
│   ├── events.py               # Thread-safe in-memory publish-subscribe bus
│   ├── logging_setup.py        # Rotating file & console logging
│   ├── subtitle_parser.py      # Binary-search O(log n) subtitle parser (SRT/ASS/VTT)
│   ├── vision_pipeline.py      # Ultralytics YOLOv8 inference & color/pattern heuristics
│   ├── vlc_controller.py       # VLC HTTP client with adaptive polling loop
│   └── word_analyzer.py        # Frequency rank classifier & WordNet synset mapper
├── installer/                  # Inno Setup Windows installer scripts
├── scripts/                    # Build, download, and benchmarking scripts
│   ├── build_exe.py            # Standalone PyInstaller build script
│   ├── profile_app.py          # Memory and latency profiling suite
│   ├── download_models.py      # YOLOv8 weight fetcher
│   └── build_freq_db.py        # Word frequency SQLite compiler
└── tests/                      # Pytest automated test suite (99 unit tests)
```

---

## 3. Running & Testing

### Running the Application
```powershell
# Run diagnostics check
python -m frameshot doctor

# Launch FrameShot-AI
python -m frameshot
```

### Running Automated Tests
FrameShot-AI maintains a strict 100% test pass rate:

```powershell
# Run full unit test suite
pytest tests/ -v

# Run with test coverage report
pytest --cov=frameshot tests/
```

### Type Checking & Linting
```powershell
# Static type checking
mypy frameshot

# Fast linting and style enforcement
ruff check frameshot tests
```

---

## 4. Performance & Profiling Benchmarks

To verify memory targets ($\le 500$ MB) and pause-to-display latency ($\le 2.0$ seconds):

```powershell
python scripts/profile_app.py
```

### Benchmark Targets
| Milestone / Operation | Measured Value | Performance Target | Status |
|-----------------------|----------------|--------------------|--------|
| Idle Background RSS   | 56.6 MB        | $\le$ 65 MB        | PASS   |
| Word Assist Mode RSS  | 243.0 MB       | $\le$ 300 MB       | PASS   |
| Combined Hybrid (LITE)| 580.0 MB       | $\le$ 650 MB       | PASS   |
| Subtitle Binary Search| 0.00 ms        | $\le$ 5 ms         | PASS   |
| Word Synset Lookup    | 16.3 ms        | $\le$ 50 ms        | PASS   |
| YOLOv8 CPU Inference  | 115.7 ms       | $\le$ 400 ms       | PASS   |
| Total Pause Latency   | 115.7 ms       | $\le$ 2,000 ms     | PASS   |

---

## 5. Building & Packaging

### Standalone Executable (PyInstaller)
Generates `dist/FrameShot-AI/FrameShot-AI.exe`:

```powershell
python scripts/build_exe.py
```

### Windows Installer (Inno Setup)
Compiles `installer/FrameShot-AI.iss` using Inno Setup 6:

```powershell
ISCC.exe installer/FrameShot-AI.iss
```
Output setup wizard is placed in `dist/installer/FrameShot-AI-Setup-v0.1.0.exe`.

