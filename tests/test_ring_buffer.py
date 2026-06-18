from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import ServerStatus, Snapshot
from app.ring_buffer import RingBuffer, parse_window_seconds


def _snapshot_at(timestamp: datetime) -> Snapshot:
    return Snapshot(
        timestamp=timestamp,
        server=ServerStatus(base_url="http://llama.test"),
    )


def test_ring_buffer_trims_by_retention() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    buffer: RingBuffer[Snapshot] = RingBuffer(retention_seconds=60)

    buffer.append(_snapshot_at(start))
    buffer.append(_snapshot_at(start + timedelta(seconds=30)))
    buffer.append(_snapshot_at(start + timedelta(seconds=90)))

    retained = buffer.all()
    assert len(retained) == 2
    assert retained[0].timestamp == start + timedelta(seconds=30)


def test_ring_buffer_returns_requested_window() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    buffer: RingBuffer[Snapshot] = RingBuffer()
    buffer.append(_snapshot_at(start))
    buffer.append(_snapshot_at(start + timedelta(minutes=10)))

    window = buffer.window("5m", now=start + timedelta(minutes=10))

    assert len(window) == 1
    assert window[0].timestamp == start + timedelta(minutes=10)


def test_parse_window_seconds() -> None:
    assert parse_window_seconds("5m") == 300
    assert parse_window_seconds("2h") == 7200
    assert parse_window_seconds("30s") == 30
    with pytest.raises(ValueError):
        parse_window_seconds("sessionish")
