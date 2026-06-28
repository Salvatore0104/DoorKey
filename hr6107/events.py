from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any


class EventBus:
    def __init__(self, log_path: Path, capacity: int = 2000):
        self.log_path = log_path
        self.events: deque[dict[str, Any]] = deque(maxlen=capacity)
        self.subscribers: set[asyncio.Queue] = set()
        self._next_id = 1
        self._lock = asyncio.Lock()

    async def publish(self, direction: str, level: str, message: str, **data: Any) -> dict[str, Any]:
        async with self._lock:
            event = {
                "id": self._next_id,
                "time": datetime.now().isoformat(timespec="milliseconds"),
                "direction": direction,
                "level": level,
                "message": message,
                "data": data,
            }
            self._next_id += 1
            self.events.append(event)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            for queue in tuple(self.subscribers):
                if not queue.full():
                    queue.put_nowait(event)
            return event

    async def since(self, event_id: int) -> list[dict[str, Any]]:
        async with self._lock:
            return [event for event in self.events if event["id"] > event_id]

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.subscribers.discard(queue)
