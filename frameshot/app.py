"""Application orchestrator.

Owns the lifecycle: configuration -> database -> event bus -> VLC poller ->
subtitle parser -> parallel analysis (words + vision) -> live card display / overlay.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from enum import StrEnum
from pathlib import Path
from typing import Any

from frameshot.config import AppConfig
from frameshot.database import Database
from frameshot.events import Event, EventBus, EventMessage
from frameshot.online import EnrichmentService
from frameshot.subtitle_parser import SubtitleEntry, SubtitleParser
from frameshot.vision_pipeline import FrameAnalysis, VisionPipeline
from frameshot.vlc_controller import PlaybackStatus, VLCController
from frameshot.word_analyzer import WordAnalyzer, WordResult

logger = logging.getLogger(__name__)


class AppState(StrEnum):
    """Mirrors the state machine in ``flow.md`` §6."""

    IDLE = "idle"
    CONNECTING = "connecting"
    MONITORING = "monitoring"
    PROCESSING = "processing"
    OVERLAY_VISIBLE = "overlay_visible"


def format_time_ms(ms: int) -> str:
    """Format milliseconds into HH:MM:SS.mmm."""
    total_seconds = max(0, ms // 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    millis = max(0, ms % 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


class FrameShotApp:
    def __init__(
        self,
        config: AppConfig,
        bus: EventBus | None = None,
        database: Database | None = None,
        vlc: VLCController | None = None,
        subtitle_parser: SubtitleParser | None = None,
        word_analyzer: WordAnalyzer | None = None,
        vision_pipeline: VisionPipeline | None = None,
        enrichment_service: EnrichmentService | None = None,
        overlay_manager: Any = None,
        run_once: bool = False,
        enable_ui: bool = True,
    ) -> None:
        self.config = config
        self.bus = bus if bus is not None else EventBus()
        self.database = database if database is not None else Database(config.paths.database)
        self.vlc = (
            vlc
            if vlc is not None
            else VLCController(config.vlc, snapshot_dir=config.paths.snapshot_dir)
        )
        self.subtitle_parser = subtitle_parser if subtitle_parser is not None else SubtitleParser()
        self.word_analyzer = (
            word_analyzer
            if word_analyzer is not None
            else WordAnalyzer(
                difficulty_level=config.analysis.difficulty_level,
                freq_db_path=config.paths.word_freq,
            )
        )
        self.vision_pipeline = (
            vision_pipeline
            if vision_pipeline is not None
            else VisionPipeline(
                model_profile=config.analysis.model_profile,
                models_dir=config.paths.models_dir,
                confidence_threshold=config.analysis.confidence_threshold,
            )
        )

        self.enrichment_service = (
            enrichment_service
            if enrichment_service is not None
            else EnrichmentService(config, database=self.database)
        )

        self.overlay_manager = None
        if enable_ui:
            try:
                from frameshot.overlay_manager import OverlayManager

                self.overlay_manager = (
                    overlay_manager
                    if overlay_manager is not None
                    else OverlayManager(
                        config,
                        bus=self.bus,
                        database=self.database,
                        enrichment_service=self.enrichment_service,
                    )
                )
            except Exception as exc:
                logger.debug("Overlay manager disabled or unavailable: %s", exc)

        self.run_once = run_once
        self.state = AppState.IDLE
        self._pause_processed_event = threading.Event()

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        """Initialise resources, subscribe event handlers, and start monitoring."""
        self._ensure_directories()
        logger.info("FrameShot-AI %s starting", self._version())
        logger.info(
            "database ready: %s (schema v%s)", self.database.path, self.database.schema_version
        )

        self.bus.subscribe(Event.VLC_CONNECTED, self._on_vlc_connected)
        self.bus.subscribe(Event.VLC_DISCONNECTED, self._on_vlc_disconnected)
        self.bus.subscribe(Event.MEDIA_CHANGED, self._on_media_changed)
        self.bus.subscribe(Event.PLAYBACK_PAUSED, self._on_playback_paused)
        self.bus.subscribe(Event.PLAYBACK_RESUMED, self._on_playback_resumed)

        self.state = AppState.MONITORING
        self.vlc.start_polling(self.bus)
        logger.info("Monitoring VLC on %s (poll interval: %d ms)", self.vlc.base_url, self.config.vlc.poll_interval_ms)

        if self.vision_pipeline is not None:
            threading.Thread(
                target=self.vision_pipeline.warmup,
                name="vision-warmup",
                daemon=True,
            ).start()

    def stop(self) -> None:
        """Gracefully terminate polling, overlay, and close resources."""
        self.state = AppState.IDLE
        self.vlc.stop_polling()
        if self.overlay_manager is not None:
            self.overlay_manager.hide()
        self.bus.clear()
        self.database.close()
        self._pause_processed_event.set()
        logger.info("FrameShot-AI stopped")

    def wait_for_pause_processed(self, timeout: float | None = None) -> bool:
        """Wait until a pause event has been captured and processed (used in tests / --once)."""
        return self._pause_processed_event.wait(timeout)

    # ------------------------------------------------------------ event handlers

    def _on_vlc_connected(self, message: EventMessage) -> None:
        logger.info("Connected to VLC HTTP interface")

    def _on_vlc_disconnected(self, message: EventMessage) -> None:
        logger.warning("Disconnected from VLC HTTP interface")

    def _ensure_subtitles_loaded(self, status: PlaybackStatus) -> None:
        """Ensure subtitle track is loaded (sibling file or auto-extracted embedded track)."""
        media_path = status.media_path
        if media_path is None and status.filename:
            resolved = self.vlc.get_media_info()
            if isinstance(resolved, Path):
                status.media_path = resolved
                media_path = resolved

        if not isinstance(media_path, Path) or not media_path.is_file():
            return

        # If already loaded for this video, skip
        if (
            self.subtitle_parser.filepath is not None
            and isinstance(self.subtitle_parser.filepath, Path)
            and media_path.stem in self.subtitle_parser.filepath.stem
            and len(self.subtitle_parser.entries) > 0
        ):
            return

        # 1. Try sibling file
        sub_file = self.subtitle_parser.auto_detect(media_path)
        if sub_file:
            try:
                self.subtitle_parser.load(sub_file)
                logger.info("Loaded sibling subtitle: %s", sub_file.name)
                return
            except Exception as exc:
                logger.warning("Could not load sibling subtitle %s: %s", sub_file, exc)

        # 2. Try auto-extracting embedded subtitle from video file
        sub_dir = self.config.paths.snapshot_dir.parent / "subtitles"
        extracted_file = self.subtitle_parser.auto_extract_embedded(media_path, out_dir=sub_dir)
        if extracted_file:
            try:
                self.subtitle_parser.load(extracted_file)
                logger.info("Loaded embedded subtitle: %s", extracted_file.name)
            except Exception as exc:
                logger.warning("Could not load extracted embedded subtitle %s: %s", extracted_file, exc)

    def _on_media_changed(self, message: EventMessage) -> None:
        status: PlaybackStatus | None = message.payload
        if status is not None:
            self._ensure_subtitles_loaded(status)

    def _analyze_words(self, entry: SubtitleEntry | None) -> list[WordResult]:
        if entry is not None and entry.text:
            return self.word_analyzer.analyze(entry.text)
        return []

    def _analyze_vision(self, snapshot_path: Path | None) -> FrameAnalysis:
        if snapshot_path is not None and snapshot_path.is_file():
            return self.vision_pipeline.analyze(snapshot_path)
        return FrameAnalysis()

    def _on_playback_paused(self, message: EventMessage) -> None:
        status: PlaybackStatus | None = message.payload
        if status is None:
            return

        # Make sure subtitles are loaded (even if video was already playing before app started)
        self._ensure_subtitles_loaded(status)

        self.state = AppState.PROCESSING
        self.bus.publish(Event.ANALYSIS_STARTED, status)

        # 1. Capture snapshot frame
        snapshot_path = self.vlc.take_snapshot(
            timeout_s=1.0,
            video_path=status.media_path,
            timestamp_ms=status.timestamp_ms,
        )

        # 2. Look up subtitle entry at current timestamp
        entry = self.subtitle_parser.get_at(status.timestamp_ms)

        # 3. Parallel Execution: Analyze words & vision concurrently
        words: list[WordResult] = []
        frame_analysis: FrameAnalysis = FrameAnalysis()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            word_future = executor.submit(self._analyze_words, entry)
            vision_future = executor.submit(self._analyze_vision, snapshot_path)
            words = word_future.result()
            frame_analysis = vision_future.result()

        # 4. Render live CLI card
        self._render_pause_card(status, entry, words, snapshot_path, frame_analysis)

        # 5. Show GUI Overlay if active
        if self.overlay_manager is not None:
            media_title = (
                status.filename
                or (Path(status.media_path).stem if status.media_path else None)
            )
            self.overlay_manager.show_analysis(
                words=words,
                analysis=frame_analysis,
                subtitle_text=entry.text if entry else None,
                image_path=snapshot_path,
                movie_title=media_title,
                timestamp_ms=status.timestamp_ms,
            )

        # 6. Publish analysis complete
        analysis_payload = {
            "status": status,
            "subtitle": entry,
            "words": words,
            "vision": frame_analysis,
            "snapshot_path": snapshot_path,
        }
        self.bus.publish(Event.ANALYSIS_COMPLETE, analysis_payload)
        self.state = AppState.MONITORING

        self._pause_processed_event.set()
        if self.run_once:
            logger.info("Single pause run complete (--once). Stopping application.")
            self.stop()

    def _on_playback_resumed(self, message: EventMessage) -> None:
        self.state = AppState.MONITORING
        if self.overlay_manager is not None:
            self.overlay_manager.hide()
        self._pause_processed_event.clear()

    # ------------------------------------------------------------ presentation

    def _render_pause_card(
        self,
        status: PlaybackStatus,
        entry: SubtitleEntry | None,
        words: list[WordResult],
        snapshot_path: Path | None,
        frame_analysis: FrameAnalysis | None = None,
    ) -> None:
        time_str = format_time_ms(status.timestamp_ms)
        title = status.filename or "Unknown Media"

        print()
        print("=" * 72)
        print(f"⏸️  PAUSED: {time_str} | \"{title}\"")
        print("-" * 72)

        if entry is not None:
            print(f"💬 Subtitle: \"{entry.text}\"")
        else:
            print("💬 Subtitle: (no subtitle entry at this timestamp)")

        print()
        level_name = self.config.analysis.difficulty_level.value
        print(f"📖 Word Assist ({level_name}):")
        if words:
            for w in words:
                pos_str = f" ({w.part_of_speech})" if w.part_of_speech else ""
                ipa_str = f" [{w.pronunciation}]" if w.pronunciation else ""
                print(f"   • {w.word.upper()}{ipa_str}{pos_str}")
                if w.definition:
                    print(f"     \"{w.definition}\"")
                if w.synonyms:
                    print(f"     Synonyms: {', '.join(w.synonyms[:3])}")
        else:
            print("   (no hard words detected in this line)")

        if frame_analysis and (frame_analysis.scene_caption or frame_analysis.detections):
            print()
            print("📸 Frame Insight:")
            if frame_analysis.scene_caption:
                print(f"   • Scene: \"{frame_analysis.scene_caption}\"")
            if frame_analysis.detections:
                items_str = ", ".join(f"{d.label} ({int(d.confidence*100)}%)" for d in frame_analysis.detections[:5])
                print(f"   • Objects: {items_str}")

        print()
        if snapshot_path is not None:
            print(f"📸 Snapshot: {snapshot_path}")
        else:
            print("📸 Snapshot: (snapshot capture unavailable)")
        print("=" * 72)
        print()

    # ------------------------------------------------------------ internal

    def _ensure_directories(self) -> None:
        for directory in (
            self.config.paths.models_dir,
            self.config.paths.snapshot_dir,
            self.config.paths.log_dir,
            self.config.paths.database.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _version() -> str:
        from frameshot import __version__

        return __version__
