"""Safe, user-facing execution progress events for live chat updates."""

import asyncio
from typing import Dict


class ProgressBus:
    def __init__(self) -> None:
        self._queues: Dict[str, asyncio.Queue] = {}

    def subscribe(self, execution_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[execution_id] = queue
        return queue

    async def publish(self, execution_id: str, message: str, phase: str) -> None:
        queue = self._queues.get(execution_id)
        if queue is not None:
            await queue.put({"type": "progress", "phase": phase, "message": message})

    def publish_token(self, execution_id: str, delta: str) -> None:
        queue = self._queues.get(execution_id)
        if queue is not None:
            try:
                queue.put_nowait({"type": "token", "delta": delta})
            except Exception:
                pass

    async def publish_token_async(self, execution_id: str, delta: str) -> None:
        queue = self._queues.get(execution_id)
        if queue is not None:
            await queue.put({"type": "token", "delta": delta})

    def unsubscribe(self, execution_id: str) -> None:
        self._queues.pop(execution_id, None)


progress_bus = ProgressBus()
