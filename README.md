# FrameShot-AI

<div align="center">

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Tests](https://img.shields.io/badge/tests-99%2F99%20passing-brightgreen.svg)
![Status](https://img.shields.io/badge/status-Production%20Ready-success.svg)

**Intelligent, real-time contextual awareness overlay for VLC Media Player.**  
*Instantly understand complex vocabulary, identify scene objects, and discover apparel and products when you pause video.*

</div>

---

## 💡 The Concept

Watching international films and high-concept cinema often presents two friction points:
1. **Unfamiliar Vocabulary**: Subtitles frequently include advanced words (*"resplendent"*, *"serendipitous"*, *"labyrinthine"*). Pausing to look them up on a phone or browser breaks narrative immersion.
2. **Visual Curiosity**: Intriguing attire, landmarks, tech gear, or apparel appear in the frame, but identifying them requires manual searching or taking screenshots.

**FrameShot-AI** runs silently in the background alongside VLC Media Player. The moment you press **Pause**, a non-intrusive dark-glass overlay appears on the right edge of the video with:
- **Word Assist**: Instant definitions, CEFR difficulty tiers, IPA pronunciation, and synonyms for uncommon words in the current subtitle line.
- **Frame Insight**: Object detection and scene composition summary powered by local YOLOv8 neural vision.
- **Products & Apparel**: Identification of clothing, color palette, fabric pattern (plaid, striped, solid), and direct search links for Google Lens, Amazon, and Google Shopping.
- **Vocabulary Journal**: One-click bookmarking of words with movie context, timestamp, and CSV export.

Press **Play**, and the overlay instantly dismisses in under 200 ms.

---

## ✨ Core Features

| Feature | Description | Offline First |
|---------|-------------|:-------------:|
| **Word Assist** | Analyzes subtitle cues at current timestamp using $O(\log n)$ binary search; flags uncommon words via frequency ranks. | ✅ |
| **Definitions & Phonemes** | WordNet synset definitions, grammatical part-of-speech tags, and CMUdict IPA phonemes. | ✅ |
| **YOLOv8 Neural Vision** | Detects people, electronics, vehicles, accessories, and furnishings on the paused frame in < 120 ms. | ✅ |
| **Apparel & Product Intelligence** | Analyzes garments, dominant colors, and fabric patterns (plaid/striped/solid) with direct shopping actions. | ✅ |
| **Vocabulary Journal** | Persistent SQLite vocabulary notebook with live search filter, movie metadata, and CSV export. | ✅ |
| **Online Knowledge Deep-Dive** | Optional Wikipedia entity extracts and extended Wiktionary etymology on demand. | 🌐 (Opt-in) |
| **Dark-Glass Design System** | Clean, modern design tokens with rgba translucent glass styling, 4px grid spacing, and directional drop shadows. | ✅ |

---

## ⚡ Performance Benchmarks

All benchmarks measured on standard CPU hardware running Python 3.11 on Windows 11:

| Metric | Measured Value | Target Budget | Status |
|--------|----------------|---------------|:------:|
| **Idle Memory (Background Polling)** | 56.6 MB | $\le$ 65 MB | **PASS** |
| **Word Assist Active Memory** | 243.0 MB | $\le$ 300 MB | **PASS** |
| **Combined Pipeline (YOLOv8 LITE)** | 580.0 MB | $\le$ 650 MB | **PASS** |
| **Subtitle Binary Search (5,000 cues)** | < 0.01 ms | $\le$ 5.0 ms | **PASS** |
| **Word Tokenization & Synsets** | 16.3 ms | $\le$ 50.0 ms | **PASS** |
| **YOLOv8 Object Detection (720p HD)** | 115.7 ms | $\le$ 400.0 ms | **PASS** |
| **Total Pause-to-Display Latency** | **115.7 ms** | $\le$ 2,000.0 ms | **PASS** |

*(Run `python scripts/profile_app.py` anytime to reproduce local benchmarks).*

---

## 🚀 Quick Start

### 1. Prerequisites
- **Windows 10 / 11** (64-bit)
- **[VLC Media Player](https://www.videolan.org/)** (3.x or 4.x)
- **Python 3.11+**
- **FFmpeg** on system `PATH` *(recommended for embedded subtitle extraction)*

### 2. Configure VLC Media Player
FrameShot-AI communicates with VLC via its standard Lua HTTP interface.  
Follow the illustrated step-by-step setup in [**docs/vlc_setup.md**](docs/vlc_setup.md):
1. In VLC, go to **Tools → Preferences (Show Settings: All) → Interface → Main interfaces** and check **Web**.
2. Under **Main interfaces → Lua**, set Lua HTTP password to `frameshot`.
3. Restart VLC.

### 3. Install FrameShot-AI

```powershell
# Clone the repository
git clone https://github.com/Nilesh-Parmar-05/FrameShot-AI.git
cd FrameShot-AI

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install package with all dependencies
pip install -e .[dev,nlp,vision,online,ui]

# Download vision weights and seed word frequency database
python scripts/download_models.py
python scripts/build_freq_db.py --seed-default

# Verify your environment
python -m frameshot doctor
```

### 4. Run the Application

```powershell
python -m frameshot
```

Open a video with subtitles in VLC Media Player. Whenever you pause, FrameShot-AI will display the context overlay!

---

## ⌨️ Controls & Shortcuts

| Action | Control / Shortcut |
|--------|-------------------|
| **Toggle Overlay** | `Ctrl + Shift + F` or click the System Tray icon |
| **Vocabulary Journal** | Right-click System Tray → *Vocabulary Journal...* |
| **Save Word** | Click *Save Word* on any word card in Word Assist |
| **Difficulty Tier** | Right-click System Tray → *Difficulty Level* (Beginner / Intermediate / Advanced) |
| **Online Enrichment** | Right-click System Tray → *Online Knowledge Enrichment* (Toggle) |
| **Close Overlay** | Click `×` top-right or resume playback in VLC |

---

## 📦 Building Standalone Executable & Installer

### 1. Build Standalone `.exe` (PyInstaller)
Bundles FrameShot-AI and all model dependencies into `dist/FrameShot-AI/`:

```powershell
python scripts/build_exe.py
```

### 2. Compile Windows Installer (Inno Setup)
Generates `dist/installer/FrameShot-AI-Setup-v0.1.0.exe`:

```powershell
ISCC.exe installer/FrameShot-AI.iss
```

---

## 📚 Documentation & Architecture

- [**docs/vlc_setup.md**](docs/vlc_setup.md) — Comprehensive VLC HTTP interface setup guide.
- [**docs/development.md**](docs/development.md) — Developer setup, architecture patterns, and contribution guidelines.
- [**architecture.md**](architecture.md) — Technical architecture, concurrency model, and data flow.
- [**tasks.md**](tasks.md) — Complete roadmap and implementation milestone tracker.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
