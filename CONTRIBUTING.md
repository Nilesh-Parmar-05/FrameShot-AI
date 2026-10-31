# 🤝 FrameShot-AI — Contributing Guide

---

## 1. Development Setup

### Prerequisites
- **Python 3.11+** installed
- **VLC Media Player** installed with HTTP interface enabled
- **Git** installed
- **ffmpeg** installed and in PATH (for embedded subtitle extraction)

### Setup Steps

```bash
# 1. Clone the repository
git clone https://github.com/<your-org>/FrameShot-AI.git
cd FrameShot-AI

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 5. Download models (first time only)
python scripts/download_models.py

# 6. Initialize database
python scripts/init_db.py

# 7. Copy default config
python -m frameshot init-config

# 8. Verify your environment (VLC path, HTTP interface, ffmpeg, database)
python -m frameshot doctor

# 9. Run the application
python -m frameshot
```

### Enable VLC HTTP Interface
1. Open VLC → **Tools** → **Preferences**
2. Click **"Show All"** (bottom-left)
3. Navigate to **Interface** → **Main interfaces**
4. Check **"Web"**
5. Navigate to **Interface** → **Main interfaces** → **Lua**
6. Set a **Lua HTTP password** (e.g., `frameshot`)
7. Restart VLC

---

## 2. Project Structure

```
FrameShot-AI/
├── frameshot/                 # Main application package
│   ├── __init__.py
│   ├── __main__.py            # Entry point
│   ├── app.py                 # Application orchestrator
│   ├── vlc_controller.py      # VLC integration
│   ├── subtitle_parser.py     # Subtitle file handling
│   ├── word_analyzer.py       # Word difficulty & dictionary
│   ├── vision_pipeline.py     # AI vision analysis
│   ├── overlay_manager.py     # Overlay window management
│   ├── config.py              # Configuration management
│   ├── database.py            # SQLite database operations
│   ├── enrichment/            # Online enrichment clients
│   │   ├── __init__.py
│   │   ├── wikipedia.py
│   │   ├── wiktionary.py
│   │   └── cache.py
│   └── ui/                    # PyQt6 UI components
│       ├── __init__.py
│       ├── overlay_window.py
│       ├── word_panel.py
│       ├── vision_panel.py
│       ├── settings_dialog.py
│       └── tray_icon.py
├── models/                    # AI model files (gitignored)
├── data/                      # Database files + captured frames (gitignored)
├── tests/                     # Test suite
│   ├── test_vlc_controller.py
│   ├── test_subtitle_parser.py
│   ├── test_word_analyzer.py
│   ├── test_vision_pipeline.py
│   └── fixtures/              # Test data
├── spikes/                    # Phase 0 probes (throwaway, not shipped)
├── scripts/                   # Utility scripts
│   ├── download_models.py
│   ├── init_db.py
│   └── build_freq_db.py
├── resources/                 # UI resources
│   ├── icons/
│   └── styles/
├── config.example.yaml
├── requirements.txt
├── requirements-dev.txt
├── requirements-vision.txt
├── pyproject.toml
└── README.md
```

The planning documents (`plan.md`, `PRD.md`, `architecture.md`, `flow.md`,
`tech-stack.md`, `tasks.md`, `CONTRIBUTING.md`) live at the repository root;
a `docs/` folder is reserved for long-form guides added later.

---

## 3. Coding Standards

- **Formatter:** Black (line length 100)
- **Linter:** Ruff
- **Type Checker:** mypy (strict mode)
- **Docstrings:** Google style
- **Naming:** snake_case for functions/variables, PascalCase for classes

### Pre-commit Hooks
```bash
pip install pre-commit
pre-commit install
```

---

## 4. Branching Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable, release-ready code |
| `develop` | Integration branch for features |
| `feature/<name>` | New feature development |
| `bugfix/<name>` | Bug fixes |
| `spike/<name>` | Research / proof-of-concept work |

### Workflow
1. Create a branch from `develop`: `git checkout -b feature/word-analyzer`
2. Make changes, commit with descriptive messages.
3. Push and open a Pull Request to `develop`.
4. After review and CI pass, merge.

---

## 5. Commit Messages

Follow the Conventional Commits format:

```
<type>(<scope>): <short description>

[optional body]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`

**Examples:**
```
feat(word-analyzer): add WordNet dictionary lookup
fix(vlc-controller): handle connection timeout gracefully
docs(architecture): update concurrency model diagram
test(subtitle-parser): add ASS format parsing tests
```

---

## 6. Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=frameshot --cov-report=html

# Run specific module tests
pytest tests/test_word_analyzer.py -v
```

- Aim for **≥ 80%** code coverage on core modules.
- Mock external dependencies (VLC HTTP, model inference) in unit tests.
- Integration tests can use a running VLC instance (marked with `@pytest.mark.integration`).
