# 📋 FrameShot-AI — Project Plan

## 1. Vision

**FrameShot-AI** is a smart companion tool for VLC Media Player that activates when a video is paused, providing an intelligent overlay with:

1. **Word Assist** — Detects hard/complex words from the current subtitle line and shows their meaning, pronunciation, and simplified explanation.
2. **Frame Insight** — Captures a snapshot of the paused frame and uses vision AI to identify interesting elements — landmarks, buildings, products, clothing brands, notable objects, etc.

The system follows an **offline-first** philosophy: every feature that *can* run locally *will* run locally. Online APIs are used only for enrichment tasks that genuinely require internet (e.g., product lookups, landmark detail pages).

---

## 2. Goals & Non-Goals

### Goals
| # | Goal |
|---|------|
| G1 | Seamlessly integrate with VLC without modifying VLC source code (use VLC's HTTP/Telnet interface or extension API). |
| G2 | Detect when a video is paused and instantly display the overlay. |
| G3 | Parse the active subtitle file (SRT/ASS/SSA) and identify the subtitle text at the current timestamp. |
| G4 | Classify words by difficulty and provide offline dictionary definitions for hard words. |
| G5 | Capture the current video frame and run local vision inference to detect objects, landmarks, text, and products. |
| G6 | Provide an optional online-enrichment mode for deeper lookups (Wikipedia summaries, product links, place info). |
| G7 | Run as a lightweight, always-on background process with minimal resource usage when idle. |

### Non-Goals (v1)
- Modifying or forking VLC Player itself.
- Real-time (non-paused) continuous analysis — only triggers on pause.
- Mobile platform support (desktop-only for v1).
- Support for players other than VLC (future scope).

---

## 3. Phased Roadmap

### Phase 0 — Research & Spike (Week 1–2)
- [ ] Evaluate VLC integration methods (HTTP interface, Telnet, Lua extensions, DBus on Linux).
- [ ] Spike: capture frame from VLC programmatically.
- [ ] Spike: parse SRT subtitle file and map timestamps.
- [ ] Evaluate offline NLP models for word difficulty classification.
- [ ] Evaluate offline vision models (YOLO, CLIP, BLIP-2, Florence-2).

### Phase 1 — Core Engine (Week 3–5)
- [ ] VLC Controller module — connect, detect play/pause state, fetch current timestamp.
- [ ] Subtitle Parser — load SRT/ASS/SSA, index by timestamp, retrieve current line.
- [ ] Word Analyzer — tokenize subtitle text, classify difficulty, offline dictionary lookup.
- [ ] Frame Capturer — grab the current frame as an image from VLC.

### Phase 2 — Vision & Overlay (Week 6–8)
- [ ] Vision Pipeline — run local object detection + scene captioning on captured frame.
- [ ] Overlay UI — design and implement the transparent overlay window (PyQt / Electron).
- [ ] Integrate Word Analyzer results into Overlay.
- [ ] Integrate Vision Pipeline results into Overlay.

### Phase 3 — Online Enrichment (Week 9–10)
- [ ] Wikipedia / Wiktionary API integration for extended word info.
- [ ] Google Lens-style reverse lookups for identified objects (optional, online).
- [ ] Landmark detail fetcher (Wikipedia / OpenStreetMap).
- [ ] Settings panel — toggle offline-only vs. online-enriched mode.

### Phase 4 — Polish & Release (Week 11–12)
- [ ] Performance profiling & optimization (model load times, memory).
- [ ] Installer / packaging (PyInstaller / electron-builder).
- [ ] User documentation & README.
- [ ] Beta testing & bug fixes.

---

## 4. Key Milestones

| Milestone | Target | Deliverable |
|-----------|--------|-------------|
| M0 — Spike Complete | End of Week 2 | Proof-of-concept: pause VLC → capture frame + read subtitle. |
| M1 — Core Engine | End of Week 5 | CLI tool that prints word meanings + frame description on pause. |
| M2 — Overlay MVP | End of Week 8 | GUI overlay appears on VLC pause with word + vision results. |
| M3 — Online Mode | End of Week 10 | Online enrichment toggle functional. |
| M4 — v1.0 Release | End of Week 12 | Packaged installer, documentation, stable release. |

---

## 5. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| VLC HTTP interface latency | Overlay feels slow | Pre-fetch subtitle data; cache parsed SRT in memory. |
| Large vision models → high RAM | Unusable on low-end machines | Offer "lite" vs "full" model profiles; lazy-load models. |
| Subtitle file not embedded / missing | No word analysis possible | Prompt user to load subtitle file; auto-detect `.srt` in same folder. |
| VLC updates break integration | Module stops working | Abstract VLC communication behind an interface; pin tested VLC versions. |

---

## 6. Success Criteria

- Overlay appears within **2 seconds** of pausing.
- Word difficulty detection accuracy ≥ **85%** (measured against a curated word list).
- Vision pipeline identifies at least **3 salient objects** per frame.
- Runs with ≤ **500 MB** additional RAM on a mid-range laptop.
- Works fully offline (core features) without internet.
