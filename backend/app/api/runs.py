"""
Runs and SSE Stream API Endpoints.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.data.generate import generate_dataset
from app.db import get_db
from app.orchestrator.events import event_manager
from app.orchestrator.runner import run_batch, RunSummary

logger = logging.getLogger("app.api.runs")
router = APIRouter(prefix="/api/runs", tags=["Orchestration Runs"])

# In-memory store of completed run summaries
_RUN_SUMMARIES: Dict[str, RunSummary] = {}


class StartRunRequest(BaseModel):
    mode: str = Field("agent", description="Execution mode: 'agent' or 'baseline'")
    seed: int = Field(default_factory=lambda: settings.RANDOM_SEED, description="Random seed for reproducibility")
    split: Optional[str] = Field("all", description="Dataset split filter ('train', 'held_out', or 'all')")
    reseed: bool = Field(True, description="Whether to re-generate synthetic dataset prior to run")
    time_multiplier: Optional[float] = Field(None, description="Optional override for demo clock time acceleration")


class StartRunResponse(BaseModel):
    run_id: str
    status: str
    mode: str
    stream_url: str


def _background_run_worker(
    run_id: str,
    mode: str,
    seed: int,
    split: Optional[str],
    reseed: bool,
    time_multiplier: Optional[float],
):
    """Executes the batch run in the background while broadcasting events."""
    try:
        if reseed:
            logger.info(f"Reseeding dataset with seed={seed} for run {run_id}...")
            generate_dataset(seed=seed, wipe_db=True)

        split_filter = None if split == "all" else split
        summary = run_batch(
            mode=mode,
            seed=seed,
            split=split_filter,
            run_id=run_id,
            time_multiplier=time_multiplier,
            sleep_between_steps=True,
        )
        _RUN_SUMMARIES[run_id] = summary

    except Exception as e:
        logger.error(f"Error executing batch run {run_id}: {e}", exc_info=True)
        event_manager.emit_sync(run_id, "run_error", {"error": str(e)})


@router.post("/start", response_model=StartRunResponse)
def start_recovery_run(
    req: StartRunRequest,
    background_tasks: BackgroundTasks,
):
    """
    Triggers an asynchronous recovery batch run (agent or baseline mode).
    Progress streams via SSE on /api/runs/{run_id}/stream.
    """
    run_id = f"run_{req.mode}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:6]}"
    
    background_tasks.add_task(
        _background_run_worker,
        run_id=run_id,
        mode=req.mode,
        seed=req.seed,
        split=req.split,
        reseed=req.reseed,
        time_multiplier=req.time_multiplier,
    )

    return StartRunResponse(
        run_id=run_id,
        status="started",
        mode=req.mode,
        stream_url=f"/api/runs/{run_id}/stream",
    )


@router.get("/{run_id}/stream")
async def stream_run_progress(run_id: str):
    """
    Server-Sent Events (SSE) streaming endpoint emitting real-time recovery progress.
    """
    queue = event_manager.subscribe(run_id)

    async def event_generator():
        try:
            while True:
                # Wait for next event with a periodic heartbeat
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield event.to_sse()

                    if event.event_type in ["run_completed", "run_error"]:
                        break
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep SSE connection alive through proxies
                    yield ": keep-alive heartbeat\n\n"
        finally:
            event_manager.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/{run_id}/summary")
def get_run_summary(run_id: str):
    """
    Returns final completed metrics summary for a specific run_id.
    """
    if run_id in _RUN_SUMMARIES:
        return _RUN_SUMMARIES[run_id]
    raise HTTPException(status_code=404, detail=f"Run summary for {run_id} not found or run still in progress.")
