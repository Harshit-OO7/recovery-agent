"""
Runs and Orchestration API Endpoints.

Provides:
- POST /api/runs: Trigger asynchronous recovery batch
- GET /api/runs/{id}: Run status and comprehensive metrics
- GET /api/runs/{id}/stream: Server-Sent Events (SSE) live decision stream
- GET /api/runs/{id}/events: Paginated processed events with full audit trace
- GET /api/runs/{id}/exceptions: Human escalations and policy suppressions
- GET /api/runs/compare: Agent vs Zero-Intervention Baseline uplift report
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.data.generate import generate_dataset
from app.db import get_db, SessionLocal
from app.eval.metrics import (
    ComparisonReport,
    RunMetrics,
    compare_runs,
    compute_run_metrics,
    run_evaluation_pipeline,
)
from app.models.audit_log import AuditLog
from app.models.enums import PaymentStatus
from app.models.failed_payment import FailedPayment
from app.models.recovery_attempt import RecoveryAttempt
from app.orchestrator.events import event_manager
from app.orchestrator.runner import run_batch, RunSummary

logger = logging.getLogger("app.api.runs")
router = APIRouter(prefix="/api/runs", tags=["Recovery Runs & Live Decision Stream"])

# In-memory store of completed run summaries and events
_RUN_SUMMARIES: Dict[str, RunSummary] = {}
_RUN_METRICS: Dict[str, RunMetrics] = {}
_RUN_EVENTS_STORE: Dict[str, List[Dict[str, Any]]] = {}


# ==============================================================================
# SCHEMAS
# ==============================================================================

class StartRunRequest(BaseModel):
    mode: str = Field("agent", description="Execution mode: 'agent' or 'baseline'")
    seed: int = Field(default_factory=lambda: settings.RANDOM_SEED, description="Random seed for reproducibility")
    split: Optional[str] = Field("all", description="Dataset split filter ('train', 'held_out', or 'all')")
    reseed: bool = Field(True, description="Whether to re-generate synthetic dataset prior to run")
    time_multiplier: Optional[float] = Field(None, description="Optional override for demo clock time acceleration (e.g. 28800x)")


class StartRunResponse(BaseModel):
    run_id: str
    status: str
    mode: str
    stream_url: str
    started_at: str


class ProcessedEventItem(BaseModel):
    payment_id: str
    order_id: str
    customer_name: str
    customer_city: str
    amount_rupees: float
    cart_summary: str
    failure_code: str
    failure_reason: str
    status: str
    classification: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None
    attempts_count: int = 0
    payment_link_url: Optional[str] = None
    last_action: Optional[str] = None
    last_outcome: Optional[str] = None


class PaginatedEventsResponse(BaseModel):
    run_id: str
    total_items: int
    page: int
    page_size: int
    total_pages: int
    items: List[ProcessedEventItem]


class ExceptionItem(BaseModel):
    payment_id: str
    order_id: str
    customer_name: str
    amount_rupees: float
    status: str
    type: str  # "SUPPRESSION" or "ESCALATION"
    reason: str
    gate_triggered: Optional[str] = None


class RunExceptionsResponse(BaseModel):
    run_id: str
    total_exceptions: int
    total_suppressed: int
    total_suppressed_value_rupees: float
    total_escalated: int
    total_escalated_value_rupees: float
    items: List[ExceptionItem]


# ==============================================================================
# WORKERS & RUN HANDLERS
# ==============================================================================

def _background_run_worker(
    run_id: str,
    mode: str,
    seed: int,
    split: Optional[str],
    reseed: bool,
    time_multiplier: Optional[float],
):
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

        # Compute full metrics
        db = SessionLocal()
        try:
            metrics = compute_run_metrics(summary, db=db, evaluate_held_out=(mode == "agent"))
            _RUN_METRICS[run_id] = metrics
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error executing batch run {run_id}: {e}", exc_info=True)
        event_manager.emit_sync(run_id, "run_error", {"error": str(e)})


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@router.post("", response_model=StartRunResponse, status_code=status.HTTP_202_ACCEPTED)
@router.post("/start", response_model=StartRunResponse, status_code=status.HTTP_202_ACCEPTED)
def start_recovery_run(
    req: StartRunRequest,
    background_tasks: BackgroundTasks,
):
    """
    Triggers an asynchronous recovery batch run in 'agent' or 'baseline' mode.
    Connect to /api/runs/{run_id}/stream to consume Server-Sent Events in real time.
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
        started_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/compare", response_model=ComparisonReport)
def compare_agent_and_baseline(
    seed: int = Query(42, description="Random seed used for reproducible counterfactual comparison"),
):
    """
    Computes head-to-head recovery uplift comparing Agentic Recovery against Zero-Intervention Baseline.
    Enforces identical random seed and dataset split integrity.
    """
    try:
        report, _ = run_evaluation_pipeline(seed=seed, export_path="../docs/results.md")
        return report
    except Exception as e:
        logger.error(f"Error comparing runs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")


@router.get("/{id}", response_model=Dict[str, Any])
def get_run_details(
    id: str = Path(..., description="The unique run_id"),
    db: Session = Depends(get_db),
):
    """
    Returns live or completed execution status, recovery metrics, and audit statistics.
    """
    if id in _RUN_SUMMARIES:
        summary = _RUN_SUMMARIES[id]
        metrics = _RUN_METRICS.get(id)
        return {
            "run_id": id,
            "status": "completed",
            "summary": summary.model_dump(),
            "metrics": metrics.model_dump() if metrics else None,
        }

    # If run in progress or database contains payments
    total_count = db.query(FailedPayment).count()
    recovered_count = db.query(FailedPayment).filter(FailedPayment.status == PaymentStatus.RECOVERED).count()

    if total_count > 0:
        return {
            "run_id": id,
            "status": "in_progress",
            "processed_count": total_count,
            "recovered_count": recovered_count,
            "message": "Run is currently active. Connect to SSE stream for live updates.",
        }

    raise HTTPException(status_code=404, detail=f"Run '{id}' not found.")


@router.get("/{id}/stream")
async def stream_run_progress(
    id: str = Path(..., description="The unique run_id to subscribe to"),
):
    """
    Server-Sent Events (SSE) live decision feed.
    Emits step-by-step classification, deterministic policy gate evaluations, and simulated outcomes.
    """
    queue = event_manager.subscribe(id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield event.to_sse()

                    if event.event_type in ["run_completed", "run_error"]:
                        break
                except asyncio.TimeoutError:
                    yield ": keep-alive heartbeat\n\n"
        finally:
            event_manager.unsubscribe(id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/{id}/events", response_model=PaginatedEventsResponse)
def get_run_events(
    id: str = Path(..., description="The unique run_id"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, description="Optional filter by status (recovered, suppressed, abandoned, in_progress)"),
    db: Session = Depends(get_db),
):
    """
    Returns paginated list of processed transactions with root cause classification,
    evaluated policy gates, outreach links, and outcomes.
    """
    query = db.query(FailedPayment)
    if status_filter:
        try:
            status_enum = PaymentStatus(status_filter.lower())
            query = query.filter(FailedPayment.status == status_enum)
        except ValueError:
            pass

    total_items = query.count()
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    payments = query.order_by(FailedPayment.failed_at.desc()).offset(offset).limit(page_size).all()

    items: List[ProcessedEventItem] = []
    for p in payments:
        cust = p.customer
        attempts = p.recovery_attempts
        last_attempt = attempts[-1] if attempts else None
        
        # Latest audit log for gate details
        last_audit = db.query(AuditLog).filter_by(failed_payment_id=p.id).order_by(AuditLog.created_at.desc()).first()

        items.append(ProcessedEventItem(
            payment_id=p.id,
            order_id=p.razorpay_order_id,
            customer_name=cust.name if cust else "Unknown",
            customer_city=cust.city if cust else "Unknown",
            amount_rupees=p.amount_rupees,
            cart_summary=p.cart_summary,
            failure_code=p.failure_code,
            failure_reason=p.failure_reason,
            status=p.status.value,
            attempts_count=len(attempts),
            payment_link_url=last_attempt.payment_link_url if last_attempt else None,
            last_action=last_attempt.action_taken if last_attempt else None,
            last_outcome=last_attempt.outcome.value if last_attempt else None,
            decision={
                "reason": last_audit.reason if last_audit else None,
                "gates": last_audit.policy_gates_evaluated if last_audit else None,
            } if last_audit else None,
        ))

    return PaginatedEventsResponse(
        run_id=id,
        total_items=total_items,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.get("/{id}/exceptions", response_model=RunExceptionsResponse)
def get_run_exceptions(
    id: str = Path(..., description="The unique run_id"),
    db: Session = Depends(get_db),
):
    """
    Returns all policy suppressions (restraint) and human escalations with reasons and value protected.
    """
    suppressed = db.query(FailedPayment).filter(FailedPayment.status == PaymentStatus.SUPPRESSED).all()
    escalated = db.query(FailedPayment).filter(FailedPayment.status == PaymentStatus.IN_PROGRESS).all()

    items: List[ExceptionItem] = []
    supp_val = 0.0
    for p in suppressed:
        amt = p.amount_rupees
        supp_val += amt
        last_audit = db.query(AuditLog).filter_by(failed_payment_id=p.id).order_by(AuditLog.created_at.desc()).first()
        gate_name = "G1_do_not_contact" if p.customer and p.customer.is_risk_flagged else ("G2_value_floor" if p.amount_paise < 10000 else "G3_max_attempts")

        items.append(ExceptionItem(
            payment_id=p.id,
            order_id=p.razorpay_order_id,
            customer_name=p.customer.name if p.customer else "Unknown",
            amount_rupees=amt,
            status=p.status.value,
            type="SUPPRESSION",
            reason=last_audit.reason if last_audit else "Outreach suppressed by policy gate",
            gate_triggered=gate_name,
        ))

    esc_val = 0.0
    for p in escalated:
        amt = p.amount_rupees
        esc_val += amt
        last_audit = db.query(AuditLog).filter_by(failed_payment_id=p.id).order_by(AuditLog.created_at.desc()).first()
        items.append(ExceptionItem(
            payment_id=p.id,
            order_id=p.razorpay_order_id,
            customer_name=p.customer.name if p.customer else "Unknown",
            amount_rupees=amt,
            status=p.status.value,
            type="ESCALATION",
            reason=last_audit.reason if last_audit else "Flagged for human support review",
            gate_triggered="G6_confidence_floor",
        ))

    return RunExceptionsResponse(
        run_id=id,
        total_exceptions=len(items),
        total_suppressed=len(suppressed),
        total_suppressed_value_rupees=round(supp_val, 2),
        total_escalated=len(escalated),
        total_escalated_value_rupees=round(esc_val, 2),
        items=items,
    )
