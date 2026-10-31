# 🔄 FrameShot-AI — Application Flow

## 1. High-Level User Flow

```mermaid
flowchart TD
    A["🎬 User opens VLC & plays a video"] --> B["🖥️ FrameShot-AI runs in background"]
    B --> C{"User pauses VLC?"}
    C -- No --> B
    C -- Yes --> D["⏸️ Pause event detected"]
    D --> E["📸 Capture current frame"]
    D --> F["📝 Read subtitle at current timestamp"]
    E --> G["🧠 Vision Pipeline\n(Object Detection + Scene Analysis)"]
    F --> H["📖 Word Analyzer\n(Difficulty Classification + Dictionary Lookup)"]
    G --> I["🪟 Overlay Window"]
    H --> I
    I --> J["User reads overlay"]
    J --> K{"User clicks a word/object\nfor more info?"}
    K -- Yes, Online Mode --> L["🌐 Fetch enriched info\n(Wikipedia, product links, etc.)"]
    K -- No --> M["User resumes video"]
    L --> I
    M --> C
```

---

## 2. System Data Flow

```mermaid
flowchart LR
    subgraph VLC ["VLC Media Player"]
        V1["Video Playback"]
        V2["HTTP/Telnet Interface"]
    end

    subgraph FrameShot ["FrameShot-AI Engine"]
        direction TB
        C1["VLC Controller"]
        C2["Frame Capturer"]
        C3["Subtitle Parser"]
        C4["Word Analyzer"]
        C5["Vision Pipeline"]
        C6["Overlay Manager"]
    end

    subgraph Offline ["Offline Resources"]
        O1["Local Dictionary DB\n(WordNet / Offline Dict)"]
        O2["Word Frequency List\n(Difficulty Classifier)"]
        O3["Vision Model\n(YOLO / CLIP / BLIP-2)"]
    end

    subgraph Online ["Online Services (Optional)"]
        N1["Wikipedia / Wiktionary API"]
        N2["Landmark / Place DB"]
        N3["Product Recognition API"]
    end

    V2 -- "status, timestamp" --> C1
    C1 -- "pause event + timestamp" --> C2
    C1 -- "pause event + timestamp" --> C3
    V1 -- "frame grab" --> C2
    C2 -- "image" --> C5
    C3 -- "subtitle text" --> C4
    C4 -- "lookup" --> O1
    C4 -- "frequency check" --> O2
    C5 -- "inference" --> O3
    C4 -- "word results" --> C6
    C5 -- "vision results" --> C6
    C6 -- "enrichment request" --> N1
    C6 -- "enrichment request" --> N2
    C6 -- "enrichment request" --> N3
    C6 -- "render overlay" --> V1
```

---

## 3. Detailed Flow — Pause Event Handling

```mermaid
sequenceDiagram
    participant User
    participant VLC
    participant Controller as VLC Controller
    participant SubParser as Subtitle Parser
    participant WordAnalyzer as Word Analyzer
    participant FrameCap as Frame Capturer
    participant Vision as Vision Pipeline
    participant Overlay as Overlay Manager

    User->>VLC: Press Pause
    VLC->>Controller: Status = "paused" (via HTTP poll / event)
    
    par Subtitle Path
        Controller->>SubParser: get_subtitle(timestamp)
        SubParser->>SubParser: Lookup subtitle line by timestamp
        SubParser->>WordAnalyzer: raw subtitle text
        WordAnalyzer->>WordAnalyzer: Tokenize → filter stopwords → classify difficulty
        WordAnalyzer->>WordAnalyzer: Lookup hard words in offline dictionary
        WordAnalyzer-->>Overlay: {word, definition, difficulty_score}[]
    and Frame Path
        Controller->>FrameCap: capture_frame(timestamp)
        FrameCap->>VLC: Request snapshot / read frame
        VLC-->>FrameCap: Frame image (PNG/JPEG)
        FrameCap->>Vision: image
        Vision->>Vision: Object detection (YOLO)
        Vision->>Vision: Scene captioning (BLIP-2 / Florence-2)
        Vision->>Vision: Classify objects → landmarks, products, clothing, text
        Vision-->>Overlay: {label, category, confidence, bbox}[]
    end

    Overlay->>Overlay: Compose overlay layout
    Overlay->>User: Display overlay on top of VLC
    
    opt User clicks item for more info (Online Mode)
        User->>Overlay: Click on word/object
        Overlay->>Overlay: Fetch from Wikipedia / Product API
        Overlay->>User: Show enriched detail panel
    end

    User->>VLC: Press Play / Resume
    VLC->>Controller: Status = "playing"
    Controller->>Overlay: Hide overlay
```

---

## 4. Offline vs. Online Decision Flow

```mermaid
flowchart TD
    A["Data Ready\n(Word or Object)"] --> B{"Is offline\nresource available?"}
    B -- Yes --> C["Use offline resource\n(Local Dict / Local Model)"]
    C --> D["Show result in overlay"]
    B -- No --> E{"Is online mode\nenabled in settings?"}
    E -- Yes --> F{"Is internet\navailable?"}
    F -- Yes --> G["Fetch from online API"]
    G --> D
    F -- No --> H["Show 'Offline only' badge\nwith partial result"]
    H --> D
    E -- No --> H
```

---

## 5. Subtitle Timestamp Matching Flow

```mermaid
flowchart TD
    A["Receive current timestamp\nfrom VLC (e.g., 00:42:15.300)"] --> B["Load parsed SRT index\n(pre-built on file load)"]
    B --> C["Binary search for timestamp\nin subtitle entries"]
    C --> D{"Exact match found?"}
    D -- Yes --> E["Return subtitle text"]
    D -- No --> F["Find nearest preceding\nsubtitle entry"]
    F --> G{"Within tolerance\n(< 2 seconds gap)?"}
    G -- Yes --> E
    G -- No --> H["Return empty\n(no subtitle at this moment)"]
    E --> I["Pass to Word Analyzer"]
    H --> I
```

---

## 6. State Machine — Application States

```mermaid
stateDiagram-v2
    [*] --> Idle : App starts

    Idle --> Connecting : User starts VLC / clicks Connect
    Connecting --> Monitoring : VLC HTTP interface responds
    Connecting --> Idle : Connection failed (retry / alert)

    Monitoring --> Processing : VLC paused detected
    Monitoring --> Idle : VLC closed / disconnected

    Processing --> OverlayVisible : Analysis complete
    OverlayVisible --> Monitoring : VLC resumed (play)
    OverlayVisible --> OverlayVisible : User interacts with overlay
    OverlayVisible --> Idle : VLC closed

    Monitoring --> Monitoring : VLC playing (no action)
```
