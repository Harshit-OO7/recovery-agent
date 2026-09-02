"""
Event Streaming Infrastructure for Real-Time SSE (Server-Sent Events) Progress.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("app.orchestrator.events")


class StreamEvent(BaseModel):
    event_type: str = Field(..., description="Type of progress event: run_started, step_processed, batch_progress, run_completed, run_error")
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: Dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        """Formats the event as an SSE message block."""
        payload = json.dumps({
            "event_type": self.event_type,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "data": self.data,
        })
        sse_str = f"event: {self.event_type}\ndata: {payload}\n\n"
        return sse_str


class RunEventManager:
    """
    In-memory pub/sub broker broadcasting recovery run progress to connected SSE clients.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=500)
        if run_id not in self._subscribers:
            self._subscribers[run_id] = []
        self._subscribers[run_id].append(queue)
        logger.info(f"SSE client subscribed to run_id={run_id} (active subscribers: {len(self._subscribers[run_id])})")
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        if run_id in self._subscribers:
            if queue in self._subscribers[run_id]:
                self._subscribers[run_id].remove(queue)
            if not self._subscribers[run_id]:
                del self._subscribers[run_id]
        logger.info(f"SSE client unsubscribed from run_id={run_id}")

    def emit_sync(self, run_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """Synchronously pushes an event into active subscriber queues."""
        if run_id not in self._subscribers:
            return

        event = StreamEvent(
            event_type=event_type,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data,
        )

        for queue in list(self._subscribers.get(run_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Subscriber queue full for run_id={run_id}, dropping event {event_type}")


event_manager = RunEventManager()
