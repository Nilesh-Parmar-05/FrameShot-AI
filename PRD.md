# 📄 FrameShot-AI — Product Requirements Document (PRD)

**Version:** 1.0  
**Author:** FrameShot-AI Team  
**Date:** 2026-10-20  
**Status:** Draft  

---

## 1. Problem Statement

When watching movies or TV shows with subtitles, viewers frequently encounter unfamiliar or complex English words. The current workflow is disruptive:

1. Pause the video.
2. Open a browser / phone.
3. Search for the word meaning.
4. Read the result.
5. Switch back to VLC and resume.

This breaks immersion, wastes time, and discourages vocabulary learning. Additionally, viewers miss out on identifying interesting visual elements in the scene — notable landmarks, famous products, recognizable clothing brands, or culturally significant objects — because there's no easy way to learn about what's on screen.

---

## 2. Proposed Solution

**FrameShot-AI** is a desktop companion application that hooks into VLC Media Player. When the user pauses a video:

1. **Word Assist** — The current subtitle line is analyzed. Hard or uncommon words are highlighted with inline definitions, synonyms, and pronunciation.
2. **Frame Insight** — A snapshot of the paused frame is analyzed using local AI vision models to identify and label interesting objects, landmarks, products, and clothing visible in the scene.

Results are shown in a sleek, semi-transparent overlay on top of the VLC window — no alt-tabbing required.

---

## 3. Target Users

### Primary Persona — "The Non-Native Viewer"
- **Who:** Non-native English speakers watching English-language content with subtitles.
- **Pain:** Frequently encounters unfamiliar words; pausing to Google disrupts the experience.
- **Goal:** Understand every word without leaving the player.

### Secondary Persona — "The Curious Viewer"
- **Who:** Movie enthusiasts, cinephiles, students of film or culture.
- **Pain:** Notices interesting locations, products, or references in films but has no quick way to identify them.
- **Goal:** Get instant context about what's visible in the frame.

### Tertiary Persona — "The Language Learner"
- **Who:** Students actively learning English through media consumption.
- **Pain:** Wants structured vocabulary exposure, not just one-off lookups.
- **Goal:** Build vocabulary while enjoying content; review hard words later.

---

## 4. Feature Requirements

### 4.1 VLC Integration (P0 — Must Have)

| ID | Requirement | Details |
|----|-------------|---------|
| FR-01 | Connect to VLC | Connect via VLC's HTTP interface (port 8080) or Telnet interface. |
| FR-02 | Detect pause/play state | Poll VLC status endpoint at ≤ 500ms intervals to detect pause events. |
| FR-03 | Retrieve current timestamp | Fetch the exact playback position (millisecond precision) when paused. |
| FR-04 | Retrieve media file path | Get the path of the currently playing file to locate associated subtitle files. |
| FR-05 | Capture frame | Use VLC's snapshot command or read the video frame at the current timestamp. |

### 4.2 Subtitle Processing (P0 — Must Have)

| ID | Requirement | Details |
|----|-------------|---------|
| FR-10 | Load subtitle files | Support `.srt`, `.ass`, `.ssa` formats. |
| FR-11 | Auto-detect subtitle file | Look for subtitle files in the same directory as the video file, matching by filename. |
| FR-12 | Timestamp-based lookup | Given a timestamp, return the active subtitle line(s). Use binary search on pre-indexed data. |
| FR-13 | Handle embedded subtitles | Extract embedded subtitle tracks from MKV/MP4 containers using `ffmpeg` / `ffprobe`. |
| FR-14 | Multi-language support | Detect subtitle language; adjust word difficulty analysis accordingly (v1: English only). |

### 4.3 Word Analysis (P0 — Must Have)

| ID | Requirement | Details |
|----|-------------|---------|
| FR-20 | Tokenize subtitle text | Split subtitle text into individual words, handling contractions and hyphenation. |
| FR-21 | Classify word difficulty | Use word frequency lists (e.g., COCA, BNC) to score words. Words below a configurable frequency threshold are flagged as "hard." |
| FR-22 | Offline dictionary lookup | Use an offline dictionary database (WordNet, or a bundled JSON dictionary) to fetch definitions. |
| FR-23 | Show pronunciation | Provide IPA pronunciation from the offline dictionary. |
| FR-24 | Show synonyms | List 2–3 simpler synonyms for each hard word. |
| FR-25 | Configurable difficulty threshold | Let users set their vocabulary level (beginner / intermediate / advanced) to control which words are flagged. |

### 4.4 Vision Analysis (P0 — Must Have)

| ID | Requirement | Details |
|----|-------------|---------|
| FR-30 | Object detection | Run a local object detection model (e.g., YOLOv8) to detect and label objects with bounding boxes. |
| FR-31 | Scene captioning | Generate a natural language description of the frame using a captioning model (e.g., BLIP-2 or Florence-2). |
| FR-32 | Landmark recognition | Identify famous landmarks, buildings, or places visible in the frame. |
| FR-33 | Product / brand detection | Identify recognizable products, logos, or brands (offline model + optional online lookup). |
| FR-34 | Clothing / fashion detection | Identify notable clothing items, styles, or accessories. |
| FR-35 | Confidence filtering | Only show detections above a configurable confidence threshold (default: 70%). |

### 4.5 Overlay UI (P0 — Must Have)

| ID | Requirement | Details |
|----|-------------|---------|
| FR-40 | Semi-transparent overlay | Display results in a frosted-glass / semi-transparent overlay anchored to the VLC window. |
| FR-41 | Two-panel layout | Left panel: Word Assist results. Right panel: Frame Insight results with annotated image. |
| FR-42 | Clickable words | Clicking a hard word expands its definition inline. |
| FR-43 | Clickable objects | Clicking a detected object shows more details (label, confidence, category). |
| FR-44 | Auto-dismiss on play | Overlay automatically hides when the user resumes playback. |
| FR-45 | Keyboard shortcut | Toggle overlay visibility with a configurable hotkey (default: `Ctrl+Shift+F`). |

### 4.6 Online Enrichment (P1 — Should Have)

| ID | Requirement | Details |
|----|-------------|---------|
| FR-50 | Wikipedia word lookup | Fetch a short Wikipedia summary for a clicked word (if online). |
| FR-51 | Landmark info | Fetch Wikipedia / Google Maps info for identified landmarks. |
| FR-52 | Product links | Link identified products to search results or shopping pages. |
| FR-53 | Offline/online toggle | Global setting to disable all online features. |
| FR-54 | Cache online results | Cache fetched online data locally to avoid repeated requests. |

### 4.7 Vocabulary Journal (P2 — Nice to Have)

| ID | Requirement | Details |
|----|-------------|---------|
| FR-60 | Save words | Let users save hard words to a personal vocabulary journal. |
| FR-61 | Export journal | Export saved words as CSV / Anki flashcard deck. |
| FR-62 | Review mode | In-app review mode to quiz saved vocabulary. |

---

## 5. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | Overlay latency | ≤ 2 seconds from pause to overlay display. |
| NFR-02 | Memory usage | ≤ 500 MB RAM (idle: ≤ 50 MB). |
| NFR-03 | CPU usage (idle) | < 2% CPU when video is playing (polling only). |
| NFR-04 | Offline capability | All P0 features must work without internet. |
| NFR-05 | Platform support | Windows 10/11 (v1). Linux & macOS (v2). |
| NFR-06 | VLC versions | Compatible with VLC 3.x and 4.x. |
| NFR-07 | Startup time | Application ready within 5 seconds of launch. |
| NFR-08 | Model size | Total offline model footprint ≤ 2 GB on disk. |

---

## 6. User Stories

| ID | As a... | I want to... | So that... |
|----|---------|-------------|------------|
| US-01 | Non-native viewer | See meanings of hard words when I pause | I don't have to leave VLC to Google words |
| US-02 | Curious viewer | Know what landmark is shown in a scene | I can learn about real places in movies |
| US-03 | Language learner | Adjust the difficulty threshold | I only see words I actually don't know |
| US-04 | Privacy-conscious user | Use the app fully offline | My viewing habits aren't sent anywhere |
| US-05 | Casual user | Have the overlay auto-hide on resume | It doesn't interfere with my viewing |
| US-06 | Power user | Use a keyboard shortcut to toggle overlay | I have quick control without mouse |
| US-07 | Film student | See what products/brands appear in a scene | I can study product placement in cinema |
| US-08 | Language learner | Save hard words for later review | I can build vocabulary over time |

---

## 7. Out of Scope (v1)

- Real-time (during playback) continuous word/vision analysis.
- Support for media players other than VLC.
- Mobile or web versions.
- Multiplayer / shared overlay sessions.
- Audio analysis (accent detection, speech-to-text) — subtitle-based only.
- Auto-generated subtitles (user must provide subtitle file or embedded subs).

---

## 8. Acceptance Criteria

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Basic word assist | A video with SRT subtitles is playing in VLC | The user pauses at a frame with subtitle "The edifice was resplendent" | The overlay shows definitions for "edifice" and "resplendent" |
| Frame insight | A video showing the Eiffel Tower is playing | The user pauses on that frame | The overlay identifies "Eiffel Tower" as a landmark |
| Offline mode | Internet is disconnected | The user pauses a video | Word definitions and object labels still appear (from local models/dict) |
| Auto-dismiss | The overlay is visible | The user presses play in VLC | The overlay hides within 200ms |
| No subtitle | A video without subtitles is playing | The user pauses | The overlay shows "No subtitle detected" in the word panel; vision panel works normally |
