from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Generic, Protocol, TypeVar


class Timestamped(Protocol):
    timestamp: datetime


T = TypeVar("T", bound=Timestamped)


class RingBuffer(Generic[T]):
    def __init__(self, retention_seconds: int | None = None) -> None:
        self.retention_seconds = retention_seconds
        self._items: deque[T] = deque()

    def append(self, item: T) -> None:
        self._items.append(item)
        self._trim(item.timestamp)

    def all(self) -> list[T]:
        return list(self._items)

    def window(self, window: str, now: datetime | None = None) -> list[T]:
        if window == "session":
            return self.all()

        seconds = parse_window_seconds(window)
        reference = now or (self._items[-1].timestamp if self._items else utc_now())
        cutoff = reference - timedelta(seconds=seconds)
        return [item for item in self._items if item.timestamp >= cutoff]

    def _trim(self, now: datetime) -> None:
        if self.retention_seconds is None:
            return
        cutoff = now - timedelta(seconds=self.retention_seconds)
        while self._items and self._items[0].timestamp < cutoff:
            self._items.popleft()

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterable[T]:
        return iter(self._items)


def parse_window_seconds(window: str) -> int:
    value = window.strip().lower()
    if value.endswith("m"):
        return int(value[:-1]) * 60
    if value.endswith("h"):
        return int(value[:-1]) * 3600
    if value.endswith("s"):
        return int(value[:-1])
    raise ValueError(f"unsupported history window: {window}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
