"""In-process event bus.

The VLC poller, analysis workers, and UI live on different threads
(``architecture.md`` §9), so every cross-boundary notification goes through
this bus. Handlers are called synchronously on the publishing thread; a
handler that must not block (e.g. the UI) is responsible for marshalling onto
its own thread.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[["EventMessage"], None]


class Event(StrEnum):
    """Every event the application can emit."""

    # VLC integration
    VLC_CONNECTED = "vlc.connected"
    VLC_DISCONNECTED = "vlc.disconnected"
    PLAYBACK_PAUSED = "playback.paused"
    PLAYBACK_RESUMED = "playback.resumed"
    PLAYBACK_STOPPED = "playback.stopped"

    # Analysis
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_COMPLETE = "analysis.complete"
    ANALYSIS_FAILED = "analysis.failed"

    # Presentation
    OVERLAY_SHOWN = "overlay.shown"
    OVERLAY_HIDDEN = "overlay.hidden"


@dataclass(frozen=True, slots=True)
class EventMessage:
    """An event plus its payload."""

    event: Event
    payload: Any = None


class EventBus:
    """Minimal thread-safe publish/subscribe bus."""

    def __init__(self) -> None:
        self._subscribers: dict[Event, list[Handler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event: Event, handler: Handler) -> Callable[[], None]:
        """Register ``handler`` for ``event``; returns an unsubscribe callable."""
        with self._lock:
            self._subscribers[event].append(handler)

        def unsubscribe() -> None:
            self.unsubscribe(event, handler)

        return unsubscribe

    def unsubscribe(self, event: Event, handler: Handler) -> None:
        with self._lock:
            handlers = self._subscribers.get(event)
            if not handlers:
                return
            try:
                handlers.remove(handler)
            except ValueError:
                logger.debug("handler %r was not subscribed to %s", handler, event)
            if not handlers:
                self._subscribers.pop(event, None)

    def publish(self, event: Event, payload: Any = None) -> None:
        """Deliver ``event`` to every subscriber.

        A failing handler is logged and does not prevent the others from
        running: one broken consumer must not take down the poller.
        """
        message = EventMessage(event=event, payload=payload)
        with self._lock:
            handlers = tuple(self._subscribers.get(event, ()))

        for handler in handlers:
            try:
                handler(message)
            except Exception:  # noqa: BLE001 - deliberate isolation boundary
                logger.exception("unhandled error in %s handler %r", event, handler)

    def clear(self) -> None:
        """Drop every subscription (used by tests and shutdown)."""
        with self._lock:
            self._subscribers.clear()

    def subscriber_count(self, event: Event) -> int:
        with self._lock:
            return len(self._subscribers.get(event, ()))
