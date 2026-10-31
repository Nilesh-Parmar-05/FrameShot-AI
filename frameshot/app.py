"""Application orchestrator.

Owns the lifecycle: configuration -> database -> event bus -> (later) VLC
poller, analysis workers, and overlay. Phase 1 wires the VLC controller in
(tasks 1.6-1.9); Phase 2 adds the analysis and UI subscribers.

Kept intentionally thin: components publish and subscribe on the bus rather
than calling each other, so adding the overlay in Phase 2 does not require
touching the VLC poller.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from frameshot.config import AppConfig
from frameshot.database import Database
from frameshot.events import Event, EventBus, EventMessage

logger = logging.getLogger(__name__)


class AppState(StrEnum):
    """Mirrors the state machine in ``flow.md`` §6."""

    IDLE = "idle"
    CONNECTING = "connecting"
    MONITORING = "monitoring"
    PROCESSING = "processing"
    OVERLAY_VISIBLE = "overlay_visible"


class FrameShotApp:
    def __init__(
        self,
        config: AppConfig,
        bus: EventBus | None = None,
        database: Database | None = None,
    ) -> None:
        self.config = config
        self.bus = bus if bus is not None else EventBus()
        self.database = database if database is not None else Database(config.paths.database)
        self.state = AppState.IDLE

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        """Initialise resources and move to MONITORING.

        TODO(tasks.md 1.6-1.9): create the VLC poller and start it on a worker
        thread once ``vlc_controller.VLCController`` is implemented.
        """
        self._ensure_directories()
        logger.info("FrameShot-AI %s starting", self._version())
        logger.info(
            "database ready: %s (schema v%s)", self.database.path, self.database.schema_version
        )

        self.bus.subscribe(Event.VLC_CONNECTED, self._on_log_only)
        self.bus.subscribe(Event.VLC_DISCONNECTED, self._on_log_only)
        self.bus.subscribe(Event.PLAYBACK_PAUSED, self._on_log_only)
        self.bus.subscribe(Event.PLAYBACK_RESUMED, self._on_log_only)

        self.state = AppState.MONITORING
        logger.warning(
            "monitoring loop not implemented yet - see tasks.md Phase 1 (1.6-1.9). "
            "Run `python -m frameshot doctor` to verify your VLC setup."
        )

    def stop(self) -> None:
        self.state = AppState.IDLE
        self.bus.clear()
        self.database.close()
        logger.info("FrameShot-AI stopped")

    # ------------------------------------------------------------ internal

    def _ensure_directories(self) -> None:
        for directory in (
            self.config.paths.models_dir,
            self.config.paths.snapshot_dir,
            self.config.paths.log_dir,
            self.config.paths.database.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def _on_log_only(self, message: EventMessage) -> None:
        logger.debug("event %s payload=%r", message.event, message.payload)

    @staticmethod
    def _version() -> str:
        from frameshot import __version__

        return __version__
