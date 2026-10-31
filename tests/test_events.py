"""Tests for the in-process event bus."""

from __future__ import annotations

import threading

from frameshot.events import Event, EventBus, EventMessage


def test_publish_delivers_payload() -> None:
    bus = EventBus()
    received: list[EventMessage] = []
    bus.subscribe(Event.PLAYBACK_PAUSED, received.append)

    bus.publish(Event.PLAYBACK_PAUSED, {"timestamp_ms": 1234})

    assert len(received) == 1
    assert received[0].event is Event.PLAYBACK_PAUSED
    assert received[0].payload == {"timestamp_ms": 1234}


def test_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    received: list[EventMessage] = []
    unsubscribe = bus.subscribe(Event.PLAYBACK_PAUSED, received.append)

    bus.publish(Event.PLAYBACK_PAUSED)
    unsubscribe()
    bus.publish(Event.PLAYBACK_PAUSED)

    assert len(received) == 1
    assert bus.subscriber_count(Event.PLAYBACK_PAUSED) == 0


def test_unsubscribe_is_idempotent() -> None:
    bus = EventBus()
    unsubscribe = bus.subscribe(Event.PLAYBACK_PAUSED, lambda message: None)
    unsubscribe()
    unsubscribe()  # must not raise


def test_events_are_isolated_per_type() -> None:
    bus = EventBus()
    paused: list[EventMessage] = []
    resumed: list[EventMessage] = []
    bus.subscribe(Event.PLAYBACK_PAUSED, paused.append)
    bus.subscribe(Event.PLAYBACK_RESUMED, resumed.append)

    bus.publish(Event.PLAYBACK_PAUSED)

    assert len(paused) == 1
    assert resumed == []


def test_failing_handler_does_not_block_others() -> None:
    bus = EventBus()
    results: list[str] = []

    def broken(message: EventMessage) -> None:
        raise RuntimeError("handler exploded")

    bus.subscribe(Event.ANALYSIS_COMPLETE, broken)
    bus.subscribe(Event.ANALYSIS_COMPLETE, lambda message: results.append("ok"))

    bus.publish(Event.ANALYSIS_COMPLETE)

    assert results == ["ok"]


def test_publish_can_subscribe_from_another_thread() -> None:
    bus = EventBus()
    received: list[EventMessage] = []
    bus.subscribe(Event.OVERLAY_SHOWN, received.append)

    thread = threading.Thread(target=lambda: bus.publish(Event.OVERLAY_SHOWN))
    thread.start()
    thread.join()

    assert len(received) == 1


def test_clear_removes_all_subscribers() -> None:
    bus = EventBus()
    bus.subscribe(Event.PLAYBACK_PAUSED, lambda message: None)
    bus.clear()
    assert bus.subscriber_count(Event.PLAYBACK_PAUSED) == 0
