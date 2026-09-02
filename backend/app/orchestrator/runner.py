"""
Batch Recovery Run Loop Orchestrator.

Ties together:
1. Ingestion of open/abandoned payments.
2. LLM Classification & Copywriting.
3. Deterministic Policy Gating & Restraint.
4. Razorpay Test Mode execution & Simulator feedback.
5. Virtual Demo Clock acceleration and real-time SSE progress streaming.
"""

from collections import deque
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Union
import uuid

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.executor.executor import execute_decision
from app.executor.razorpay_client import BaseRazorpayClient, get_razorpay_client
from app.llm.classifier import classify_payment_failure
from app.models.audit_log import AuditLog
from app.models.enums import (
    AttemptOutcome,
    DatasetSplit,
    PaymentStatus,
    PropensityProfile,
)
from app.models.failed_payment import FailedPayment
from app.models.recovery_attempt import RecoveryAttempt
from app.orchestrator.clock import DemoClock, demo_clock
from app.orchestrator.events import event_manager
from app.policy.policy import (
    POLICY_CONFIG,
    Decision,
    PolicyAction,
    decide,
)
from app.simulator.engine import simulate_no_intervention
from app.simulator.models import BaselineOutcome

logger = logging.getLogger("app.orchestrator.runner")


class RunSummary(BaseModel):
    """
    Comprehensive summary report produced at the end of a recovery run.
    """
    run_id: str
    mode: str  # "agent" or "baseline"
    dataset_split: Optional[str] = "all"
    total_payments: int
    total_value_paise: int
    total_value_rupees: float

    # Outcome Funnel
    recovered_count: int
    recovered_value_paise: int
    recovered_value_rupees: float
    recovery_rate_pct: float

    suppressed_count: int
    suppression_rate_pct: float

    abandoned_count: int
    abandoned_rate_pct: float

    escalated_count: int

    # Operational metrics
    total_attempts_made: int
    total_audit_logs: int
    wall_clock_duration_seconds: float
    time_audit: Dict[str, Any]

    # Category breakdown (Agent mode)
    category_breakdown: Dict[str, int] = Field(default_factory=dict)
    actions_breakdown: Dict[str, int] = Field(default_factory=dict)


def run_batch(
    mode: str = "agent",
    seed: int = settings.RANDOM_SEED,
    split: Optional[Union[str, DatasetSplit]] = None,
    db: Optional[Session] = None,
    run_id: Optional[str] = None,
    time_multiplier: Optional[float] = None,
    sleep_between_steps: bool = True,
    razorpay_client: Optional[BaseRazorpayClient] = None,
    inject_llm_failure: bool = False,
    corrupt_payment_id: Optional[str] = None,
) -> RunSummary:
    """
    Executes a complete recovery batch in 'agent' or 'baseline' mode.
    Loop terminates strictly when all transactions are resolved.
    """
    if run_id is None:
        run_id = f"run_{mode}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:6]}"

    local_clock = DemoClock(multiplier=time_multiplier) if time_multiplier is not None else demo_clock
    start_wall_clock = time.time()
    logger.info(f"Starting batch run {run_id} [mode={mode}, seed={seed}, split={split}]")

    owns_db_session = False
    if db is None:
        db = SessionLocal()
        owns_db_session = True

    try:
        # 1. Fetch Target Payments
        query = db.query(FailedPayment)
        if split:
            split_enum = DatasetSplit(split) if isinstance(split, str) else split
            query = query.filter(FailedPayment.dataset_split == split_enum)
        payments: List[FailedPayment] = query.order_by(FailedPayment.failed_at.asc()).all()

        total_count = len(payments)
        total_val_paise = sum(p.amount_paise for p in payments)

        event_manager.emit_sync(run_id, "run_started", {
            "run_id": run_id,
            "mode": mode,
            "total_payments": total_count,
            "total_value_rupees": total_val_paise / 100.0,
            "seed": seed,
            "split": str(split) if split else "all",
            "time_multiplier": local_clock.multiplier,
        })

        category_counts: Dict[str, int] = {}
        action_counts: Dict[str, int] = {}
        total_attempts = 0
        total_sim_delay_seconds = 0.0

        # ======================================================================
        # MODE 1: ZERO-INTERVENTION COUNTERFACTUAL BASELINE
        # ======================================================================
        if mode == "baseline":
            for idx, payment in enumerate(payments):
                cust = payment.customer
                base_res = simulate_no_intervention(customer=cust, payment=payment, master_seed=seed)

                now = datetime.now(timezone.utc)
                if base_res.outcome == BaselineOutcome.SELF_RECOVERED:
                    payment.status = PaymentStatus.RECOVERED
                    outcome_str = "self_recovered"
                else:
                    payment.status = PaymentStatus.ABANDONED
                    outcome_str = "unrecovered"

                audit = AuditLog(
                    id=f"aud_base_{payment.id}_{seed}",
                    failed_payment_id=payment.id,
                    stage="BASELINE_COUNTERFACTUAL",
                    input_summary="Zero-intervention counterfactual evaluation",
                    decision=outcome_str.upper(),
                    reason=f"Baseline simulation result: {outcome_str} (organic P_pay: {base_res.organic_pay_probability:.2f})",
                    confidence=1.0,
                    policy_gates_evaluated={},
                    created_at=now,
                )
                db.add(audit)
                db.commit()

                event_manager.emit_sync(run_id, "step_processed", {
                    "index": idx + 1,
                    "total": total_count,
                    "payment_id": payment.id,
                    "order_id": payment.razorpay_order_id,
                    "amount_rupees": payment.amount_rupees,
                    "customer_name": cust.name,
                    "mode": "baseline",
                    "status": payment.status.value,
                    "outcome": outcome_str,
                })

                if sleep_between_steps:
                    time.sleep(0.01)

        # ======================================================================
        # MODE 2: AGENTIC REVENUE RECOVERY (CLASSIFY -> DECIDE -> EXECUTE)
        # ======================================================================
        else:
            # Queue of pending items: (payment_id, current_attempt_number, eligible_virtual_time)
            # Starting virtual timeline anchored at the first payment failure
            base_sim_time = payments[0].failed_at if payments else datetime.now(timezone.utc)
            if base_sim_time.tzinfo is None:
                base_sim_time = base_sim_time.replace(tzinfo=timezone.utc)

            # Build initial work queue
            work_queue = deque([
                (p.id, 1, base_sim_time + timedelta(minutes=15)) for p in payments
            ])

            step_counter = 0

            while work_queue:
                payment_id, attempt_num, eligible_time = work_queue.popleft()
                payment = db.query(FailedPayment).filter_by(id=payment_id).first()
                if not payment:
                    continue

                cust = payment.customer
                step_counter += 1

                # If payment is already resolved in a prior attempt, skip
                if payment.status in [PaymentStatus.RECOVERED, PaymentStatus.SUPPRESSED] and attempt_num > 1:
                    continue

                # 1. CLASSIFY ROOT CAUSE & INTENT (LLM Layer)
                should_corrupt = (
                    inject_llm_failure and (
                        (corrupt_payment_id and payment.id == corrupt_payment_id) or
                        (not corrupt_payment_id and idx == 1)
                    )
                )
                classification = classify_payment_failure(
                    payment=payment,
                    customer=cust,
                    force_llm_failure=should_corrupt,
                )
                cat_key = classification.category.value
                category_counts[cat_key] = category_counts.get(cat_key, 0) + 1

                # 2. DECIDE OPERATIONAL ACTION (Deterministic Policy Engine)
                attempt_history = db.query(RecoveryAttempt).filter_by(failed_payment_id=payment.id).all()
                decision = decide(
                    payment=payment,
                    customer=cust,
                    classification=classification,
                    attempt_history=attempt_history,
                    current_time=eligible_time,
                )
                act_key = decision.action.value
                action_counts[act_key] = action_counts.get(act_key, 0) + 1

                # 3. EXECUTE ACTION
                exec_result = execute_decision(
                    decision=decision,
                    payment=payment,
                    customer=cust,
                    classification=classification,
                    db=db,
                    attempt_number=attempt_num,
                    razorpay_client=razorpay_client,
                )

                if decision.action in [PolicyAction.SEND_PAYMENT_LINK, PolicyAction.SEND_REMINDER_NO_LINK]:
                    total_attempts += 1

                # 4. HANDLE RE-QUEUEING & RESOLUTION RULES
                # If decision was WAIT (e.g. cooldown, quiet hours, salary window delay)
                if decision.action == PolicyAction.WAIT:
                    delay_sec = max(60, decision.delay_seconds)
                    total_sim_delay_seconds += delay_sec
                    next_eligible = eligible_time + timedelta(seconds=delay_sec)

                    if sleep_between_steps:
                        local_clock.sleep_compressed(delay_sec, max_sleep_cap=0.08)

                    # Re-queue for re-evaluation once wait window expires
                    work_queue.append((payment.id, attempt_num, next_eligible))

                # If customer ignored outreach and has remaining attempts -> re-queue for attempt #2 after 24h cooldown
                elif decision.action in [PolicyAction.SEND_PAYMENT_LINK, PolicyAction.SEND_REMINDER_NO_LINK]:
                    sim_out = exec_result.simulated_outcome
                    if sim_out and sim_out.outcome == AttemptOutcome.IGNORED or (sim_out and hasattr(sim_out, "outcome") and str(sim_out.outcome.value) == "ignored"):
                        max_allowed = POLICY_CONFIG["MAX_RECOVERY_ATTEMPTS"]
                        current_attempts_count = len(db.query(RecoveryAttempt).filter_by(failed_payment_id=payment.id).all())

                        if current_attempts_count < max_allowed:
                            cooldown_sec = int(POLICY_CONFIG["COOLDOWN_HOURS"] * 3600)
                            next_eligible = eligible_time + timedelta(seconds=cooldown_sec)
                            if sleep_between_steps:
                                local_clock.sleep_compressed(cooldown_sec, max_sleep_cap=0.08)
                            work_queue.append((payment.id, current_attempts_count + 1, next_eligible))
                        else:
                            # Max attempts reached without recovery -> mark abandoned
                            payment.status = PaymentStatus.ABANDONED
                            db.commit()

                # Broadcast progress step to SSE stream
                event_manager.emit_sync(run_id, "step_processed", {
                    "step_number": step_counter,
                    "payment_id": payment.id,
                    "order_id": payment.razorpay_order_id,
                    "amount_rupees": payment.amount_rupees,
                    "customer_name": cust.name,
                    "classification": classification.model_dump(),
                    "decision": decision.model_dump(),
                    "status": payment.status.value,
                    "attempt_number": attempt_num,
                    "payment_link_url": exec_result.payment_link_url,
                    "message_sent": exec_result.message_sent,
                    "simulated_outcome": exec_result.simulated_outcome.model_dump() if exec_result.simulated_outcome else None,
                })

                if sleep_between_steps:
                    time.sleep(0.01)

        # ----------------------------------------------------------------------
        # COMPILE FINAL RUN SUMMARY
        # ----------------------------------------------------------------------
        db.expire_all()
        final_payments = db.query(FailedPayment)
        if split:
            final_payments = final_payments.filter(FailedPayment.dataset_split == DatasetSplit(split))
        final_list = final_payments.all()

        recovered_payments = [p for p in final_list if p.status == PaymentStatus.RECOVERED]
        suppressed_payments = [p for p in final_list if p.status == PaymentStatus.SUPPRESSED]
        abandoned_payments = [p for p in final_list if p.status == PaymentStatus.ABANDONED]
        in_prog_payments = [p for p in final_list if p.status == PaymentStatus.IN_PROGRESS]

        recovered_val_paise = sum(p.amount_paise for p in recovered_payments)
        total_audit_count = db.query(AuditLog).count()

        wall_clock = time.time() - start_wall_clock
        time_audit = local_clock.format_time_audit(total_sim_delay_seconds)

        summary = RunSummary(
            run_id=run_id,
            mode=mode,
            dataset_split=str(split) if split else "all",
            total_payments=len(final_list),
            total_value_paise=total_val_paise,
            total_value_rupees=total_val_paise / 100.0,
            recovered_count=len(recovered_payments),
            recovered_value_paise=recovered_val_paise,
            recovered_value_rupees=recovered_val_paise / 100.0,
            recovery_rate_pct=round(len(recovered_payments) / len(final_list) * 100.0, 1) if final_list else 0.0,
            suppressed_count=len(suppressed_payments),
            suppression_rate_pct=round(len(suppressed_payments) / len(final_list) * 100.0, 1) if final_list else 0.0,
            abandoned_count=len(abandoned_payments),
            abandoned_rate_pct=round(len(abandoned_payments) / len(final_list) * 100.0, 1) if final_list else 0.0,
            escalated_count=len(in_prog_payments),
            total_attempts_made=total_attempts,
            total_audit_logs=total_audit_count,
            wall_clock_duration_seconds=round(wall_clock, 2),
            time_audit=time_audit,
            category_breakdown=category_counts,
            actions_breakdown=action_counts,
        )

        event_manager.emit_sync(run_id, "run_completed", summary.model_dump())
        logger.info(f"Run {run_id} complete. Recovery Rate: {summary.recovery_rate_pct}% ({summary.recovered_count}/{summary.total_payments})")
        return summary

    finally:
        if owns_db_session:
            db.close()
