# Phase 0 spikes

Throwaway-but-runnable probes for the unknown parts of the architecture. They
are standalone on purpose: **they never import `frameshot`**, so they work
before the package is finished, and their findings get promoted into
`frameshot/` afterwards.

Every spike prints a `[PASS]`/`[FAIL]` block and a "what to record" summary.
Copy those numbers into `tasks.md` and update `architecture.md` where the
guess was wrong.

---

## Prerequisites

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt          # requests, pysubs2, pydantic, pyyaml
pip install -e ".[nlp]"                  # nltk (for spike 0.6/0.7)
```

Start VLC with the interface and a snapshot folder it can write to:

```powershell
& "C:\Program Files\VideoLAN\VLC\vlc.exe" `
  --extraintf=http --http-host=127.0.0.1 --http-port=8080 --http-password=frameshot `
  --snapshot-path="C:\College\CODE\Projects\FrameShot-AI\data\snapshots" `
  --snapshot-format=png `
  --avcodec-hw=none
```

`--avcodec-hw=none` disables hardware decoding, which otherwise makes VLC
snapshots come out black. Open a video with subtitles and pause it before
running the capture spikes.

---

## Run order

| # | Command | Task | Question it answers |
|---|---------|------|---------------------|
| 1 | `python spikes/spike_vlc.py --dump` | 0.1, 0.2 | Which fields give state/position/file? Where is the absolute path? |
| 2 | `python spikes/spike_vlc.py --watch 20` | 0.2 | How fast do we see pause→resume at 200 ms polling? |
| 3 | `python spikes/spike_snapshot.py --repeat 5 --keep` | 0.3 | Does the snapshot command work, how fast, is it black? |
| 4 | `python spikes/spike_subs.py tests/fixtures/sample.srt --at 00:00:02` | 0.4 | SRT parsing, markup stripping, lookup correctness + speed |
| 5 | `python spikes/spike_subs.py tests/fixtures/sample.ass --at 00:00:04` | 0.5 | ASS/SSA through the same code path |
| 6 | `python spikes/spike_subs.py --detect "D:\Movies\Movie.mkv"` | 0.4 (FR-11) | Subtitle auto-detection ranking |
| 7 | `python spikes/spike_wordnet.py` | 0.6, 0.7 | Frequency ranking, WordNet defs, CMUdict→IPA |
| 8 | `pip install -r requirements-vision.txt` then `python spikes/spike_yolo.py data/snapshots/<file>.png` | 0.8 | YOLOv8n CPU latency + memory |
| 9 | *(manual)* PyQt6 frameless translucent window | 0.10 | Overlay feasibility |

---

## Known-answer checklist

These are the findings the planning docs already assume. If a spike
contradicts one, the docs are wrong, not the spike.

| Assumption in the docs | Confirmed by |
|---|---|
| `status.json` has no absolute media path | spike 1 (`--dump` shows `information.category.meta.filename` is a bare name) |
| `?command=snapshot` takes no output path | spike 3 (file only appears in VLC's configured folder) |
| 500 ms polling cannot hit a 200 ms auto-dismiss | spike 2 (`--watch` shows the detection window) |
| WordNet provides no IPA | spike 7 (IPA column comes from CMUdict) |
| COCO-80 has no landmark/brand classes | spike 8 (Eiffel Tower is "person/tower"-less in COCO) |
| BLIP-2 2.7B will not caption in < 1.5 s on CPU | spike 0.9, still open |

---

## Cleanup

`spikes/out/` and `data/snapshots/` are gitignored. Nothing here ships.
