from __future__ import annotations

import threading
from collections import OrderedDict


class IdempotencyStore:
    def __init__(self, max_size: int = 10_000) -> None:
        self._executed: OrderedDict[str, None] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()

    def check_and_mark(self, key: str) -> bool:
        with self._lock:
            if key in self._executed:
                # Move to end (most recently used)
                self._executed.move_to_end(key)
                return True
            self._executed[key] = None
            if len(self._executed) > self._max_size:
                self._executed.popitem(last=False)  # LRU eviction
            return False

    def clear(self) -> None:
        with self._lock:
            self._executed.clear()


__all__ = ["IdempotencyStore"]
