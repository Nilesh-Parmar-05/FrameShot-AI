# 🎬 FrameShot-AI

> **Smart Video Companion for VLC** — Instantly understand hard words from subtitles and discover interesting things in every frame, right inside your player.

---

## 🧩 The Problem

You're watching a movie with subtitles. A character says *"The edifice was resplendent under the moonlight."* You don't know what "edifice" or "resplendent" means. You pause, open Google, search, read, then switch back. Flow broken. Immersion gone.

Meanwhile, the scene shows the Eiffel Tower in the background, a character wearing a Rolex, and a vintage Porsche parked on the street — but you had no idea.

## 💡 The Solution

**FrameShot-AI** is a desktop companion that hooks into VLC Media Player. When you pause a video:

1. **📖 Word Assist** — Hard/uncommon words from the current subtitle are highlighted with definitions, synonyms, and pronunciation. All offline.
2. **📸 Frame Insight** — The paused frame is analyzed by local AI models to identify landmarks, products, clothing, and notable objects in the scene.

Results appear in a sleek overlay — no alt-tabbing, no Googling.

---

## ✨ Key Features

| Feature | Description | Offline? |
|---------|-------------|----------|
| 🔤 Word Difficulty Detection | Flags hard words based on frequency analysis | ✅ |
| 📚 Instant Definitions | WordNet-powered definitions, synonyms, pronunciation | ✅ |
| 🏛️ Landmark Recognition | Identifies famous places & buildings in the frame | ✅ |
| 🛍️ Product / Brand Detection | Spots recognizable products & logos | ✅ |
| 👗 Clothing Detection | Identifies notable fashion items | ✅ |
| 🖼️ Scene Captioning | AI-generated description of the scene | ✅ |
| 🌐 Online Enrichment | Wikipedia summaries, product links (optional) | ❌ |
| 📓 Vocabulary Journal | Save & export hard words for review | ✅ |

> **Offline-First:** All core features work without internet. Online enrichment is optional and disabled by default.

---

## 🚀 Quick Start

### Prerequisites
- [VLC Media Player](https://www.videolan.org/) (3.x or 4.x)
- Python 3.11+
- ffmpeg (for embedded subtitle extraction)

### Install & Run

```bash
# Clone the repository
git clone https://github.com/<your-org>/FrameShot-AI.git
cd FrameShot-AI

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/macOS

# Install dependencies (core + Qt overlay)
pip install -r requirements.txt

# Create your local config
python -m frameshot init-config

# Verify python / ffmpeg / VLC / database / VLC HTTP interface
python -m frameshot doctor

# Download AI models (first run only — not implemented yet, see tasks.md 2.1)
python scripts/download_models.py

# Run
python -m frameshot
```

> **Status:** the plan, architecture and project scaffold are in place. The VLC
> controller, subtitle engine, vision pipeline and overlay are still stubs —
> see [Tasks & Progress](tasks.md). Start with the Phase 0 spikes in
> [`spikes/`](spikes/README.md).

### Enable VLC HTTP Interface
1. VLC → Tools → Preferences → Show All
2. Interface → Main interfaces → Check **"Web"**
3. Interface → Main interfaces → Lua → Set HTTP password
4. Restart VLC

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [📋 Project Plan](plan.md) | Vision, roadmap, milestones, and risk register |
| [🔄 Application Flow](flow.md) | User flows, data flows, and state diagrams |
| [📄 PRD](PRD.md) | Product Requirements — features, user stories, acceptance criteria |
| [🏗️ Architecture](architecture.md) | Software design, module APIs, database schema, concurrency model |
| [✅ Tasks & Progress](tasks.md) | Full task breakdown with progress tracking |
| [🧪 Phase 0 Spikes](spikes/README.md) | Runnable probes for the risky unknowns (VLC, subtitles, models) |
| [🛠️ Tech Stack](tech-stack.md) | Technology choices with rationale and alternatives |
| [🤝 Contributing](CONTRIBUTING.md) | Development setup, coding standards, branching strategy |

---

## 🏗️ Architecture Overview

```
VLC Player  ◄──HTTP──►  VLC Controller  ──►  Event Bus
                                               │
                                    ┌──────────┴──────────┐
                                    ▼                     ▼
                              Subtitle Parser       Frame Capturer
                                    │                     │
                                    ▼                     ▼
                              Word Analyzer         Vision Pipeline
                                    │                     │
                                    └──────────┬──────────┘
                                               ▼
                                         Overlay UI
```

---

## 📄 License

[MIT License](LICENSE) — free for personal and commercial use.

---

## 🙏 Acknowledgments

- [VLC Media Player](https://www.videolan.org/) for the HTTP interface
- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) for object detection
- [HuggingFace Transformers](https://huggingface.co/) for vision-language models
- [NLTK WordNet](https://www.nltk.org/) for the offline dictionary
- [pysubs2](https://github.com/tkarabela/pysubs2) for subtitle parsing
