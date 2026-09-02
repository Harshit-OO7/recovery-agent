"""
Action Executor.

Carries out the deterministic Decision reached by the Policy Engine:
- `send_payment_link`: Generates Razorpay test link, drafts copy, records attempt, simulates customer outcome.
- `send_reminder_no_link`: Drafts copy, records reminder attempt, simulates customer outcome.
- `wait`: Records delay scheduling and writes audit log.
- `suppress`: Enforces restraint, updates transaction status, writes audit log.
- `escalate_to_human`: Enqueues to merchant exception inbox, writes audit log.

Every action writes a permanent AuditLog row (Core Principle #2).
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.executor.razorpay_client import BaseRazorpayClient, get_razorpay_client
from app.llm.classifier import ClassificationResult
from app.llm.drafter import draft_recovery_message
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.enums import AttemptOutcome, PaymentStatus, RecoveryChannel
from app.models.failed_payment import FailedPayment
from app.models.recovery_attempt import RecoveryAttempt
from app.policy.policy import Decision, PolicyAction
from app.schemas.customer import CustomerAgentView
from app.simulator.engine import simulate_customer_response
from app.simulator.models import SimulationOutcome, SimulationResponse

logger = logging.getLogger("app.executor")


class ExecutionResult:
    """
    Summary returned after carrying out a policy decision.
    """
    def __init__(
        self,
        payment_id: str,
        action_executed: PolicyAction,
        success: bool,
        recovery_attempt_id: Optional[str] = None,
        payment_link_url: Optional[str] = None,
        message_sent: Optional[str] = None,
        simulated_outcome: Optional[SimulationResponse] = None,
        audit_log_id: Optional[str] = None,
        notes: str = "",
    ):
        self.payment_id = payment_id
        self.action_executed = action_executed
        self.success = success
        self.recovery_attempt_id = recovery_attempt_id
        self.payment_link_url = payment_link_url
        self.message_sent = message_sent
        self.simulated_outcome = simulated_outcome
        self.audit_log_id = audit_log_id
        self.notes = notes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payment_id": self.payment_id,
            "action_executed": self.action_executed.value,
            "success": self.success,
            "recovery_attempt_id": self.recovery_attempt_id,
            "payment_link_url": self.payment_link_url,
            "message_sent": self.message_sent,
            "simulated_outcome": self.simulated_outcome.model_dump() if self.simulated_outcome else None,
            "audit_log_id": self.audit_log_id,
            "notes": self.notes,
        }


def execute_decision(
    decision: Decision,
    payment: FailedPayment,
    customer: Union[Customer, CustomerAgentView],
    classification: ClassificationResult,
    db: Session,
    attempt_number: int = 1,
    razorpay_client: Optional[BaseRazorpayClient] = None,
) -> ExecutionResult:
    """
    Executes a Policy Decision and persists all attempt records and audit logs.
    """
    if razorpay_client is None:
        razorpay_client = get_razorpay_client()

    now = datetime.now(timezone.utc)
    gates_json = [g.model_dump() for g in decision.gates_evaluated]

    # --------------------------------------------------------------------------
    # BRANCH 1: SEND PAYMENT LINK
    # --------------------------------------------------------------------------
    if decision.action == PolicyAction.SEND_PAYMENT_LINK:
        reference_id = f"rec_{payment.id}_att{attempt_number}"
        amount_rupees = payment.amount_paise / 100.0

        # 1. Generate Razorpay Test Payment Link
        link = razorpay_client.create_payment_link(
            amount_paise=payment.amount_paise,
            customer_name=customer.name,
            customer_email=customer.email,
            customer_phone=customer.phone,
            description=f"Order {payment.razorpay_order_id} recovery: {payment.cart_summary}",
            reference_id=reference_id,
        )
        payment_link_id = link["id"]
        payment_link_url = link["short_url"]

        # 2. Draft Message with LLM Drafter
        draft_res = draft_recovery_message(
            category=classification.category,
            customer_name=customer.name,
            cart_summary=payment.cart_summary,
            amount_rupees=amount_rupees,
            attempt_number=attempt_number,
            channel=decision.channel,
        )
        final_message = draft_res.message.replace("{payment_link}", payment_link_url)

        # 3. Ask Simulator what customer does
        sim_res = simulate_customer_response(
            customer=customer,
            payment=payment,
            action=decision.action.value,
            attempt_number=attempt_number,
            contact_time=now,
        )

        # 4. Map Simulator Outcome to Model Enum
        outcome_map = {
            SimulationOutcome.PAID_IMMEDIATELY: AttemptOutcome.PAID,
            SimulationOutcome.PAID_LATER: AttemptOutcome.PAID,
            SimulationOutcome.IGNORED: AttemptOutcome.IGNORED,
            SimulationOutcome.OPTED_OUT: AttemptOutcome.OPTED_OUT,
        }
        attempt_outcome = outcome_map.get(sim_res.outcome, AttemptOutcome.PENDING)

        # 5. Persist RecoveryAttempt
        attempt_id = f"att_{payment.id}_{attempt_number}"
        attempt = RecoveryAttempt(
            id=attempt_id,
            failed_payment_id=payment.id,
            attempt_number=attempt_number,
            channel=decision.channel,
            action_taken=decision.action.value,
            payment_link_id=payment_link_id,
            payment_link_url=payment_link_url,
            sent_at=now,
            outcome=attempt_outcome,
            outcome_at=now if attempt_outcome == AttemptOutcome.PAID else None,
        )
        db.add(attempt)

        # 6. Update Payment Status
        if sim_res.outcome in [SimulationOutcome.PAID_IMMEDIATELY, SimulationOutcome.PAID_LATER]:
            payment.status = PaymentStatus.RECOVERED
        elif sim_res.outcome == SimulationOutcome.OPTED_OUT:
            payment.status = PaymentStatus.SUPPRESSED
        else:
            payment.status = PaymentStatus.IN_PROGRESS

        # 7. Write Audit Log
        audit_id = f"aud_{payment.id}_{attempt_number}_exec"
        audit = AuditLog(
            id=audit_id,
            failed_payment_id=payment.id,
            stage="EXECUTION",
            input_summary=f"Attempt #{attempt_number} | Category: {classification.category.value} | Link: {payment_link_id}",
            decision=decision.action.value,
            reason=f"{decision.reason} | Outcome: {sim_res.outcome.value} (P_pay: {sim_res.effective_pay_probability:.2f})",
            confidence=classification.confidence,
            policy_gates_evaluated=gates_json,
            created_at=now,
        )
        db.add(audit)
        db.commit()

        return ExecutionResult(
            payment_id=payment.id,
            action_executed=decision.action,
            success=True,
            recovery_attempt_id=attempt_id,
            payment_link_url=payment_link_url,
            message_sent=final_message,
            simulated_outcome=sim_res,
            audit_log_id=audit_id,
            notes=f"Dispatched recovery link {payment_link_id}. Customer outcome: {sim_res.outcome.value}",
        )

    # --------------------------------------------------------------------------
    # BRANCH 2: SEND REMINDER (NO LINK)
    # --------------------------------------------------------------------------
    elif decision.action == PolicyAction.SEND_REMINDER_NO_LINK:
        amount_rupees = payment.amount_paise / 100.0

        draft_res = draft_recovery_message(
            category=classification.category,
            customer_name=customer.name,
            cart_summary=payment.cart_summary,
            amount_rupees=amount_rupees,
            attempt_number=attempt_number,
            channel=decision.channel,
        )
        # Strip link placeholder if present
        clean_msg = draft_res.message.replace("{payment_link}", "").replace("  ", " ").strip()

        # Simulate outcome
        sim_res = simulate_customer_response(
            customer=customer,
            payment=payment,
            action=decision.action.value,
            attempt_number=attempt_number,
            contact_time=now,
        )

        attempt_id = f"att_{payment.id}_{attempt_number}"
        attempt = RecoveryAttempt(
            id=attempt_id,
            failed_payment_id=payment.id,
            attempt_number=attempt_number,
            channel=decision.channel,
            action_taken=decision.action.value,
            payment_link_id=None,
            payment_link_url=None,
            sent_at=now,
            outcome=AttemptOutcome.IGNORED,
        )
        db.add(attempt)

        payment.status = PaymentStatus.IN_PROGRESS

        audit_id = f"aud_{payment.id}_{attempt_number}_reminder"
        audit = AuditLog(
            id=audit_id,
            failed_payment_id=payment.id,
            stage="EXECUTION",
            input_summary=f"Attempt #{attempt_number} | Non-link Reminder | Category: {classification.category.value}",
            decision=decision.action.value,
            reason=f"{decision.reason} | Outcome: {sim_res.outcome.value}",
            confidence=classification.confidence,
            policy_gates_evaluated=gates_json,
            created_at=now,
        )
        db.add(audit)
        db.commit()

        return ExecutionResult(
            payment_id=payment.id,
            action_executed=decision.action,
            success=True,
            recovery_attempt_id=attempt_id,
            payment_link_url=None,
            message_sent=clean_msg,
            simulated_outcome=sim_res,
            audit_log_id=audit_id,
            notes="Dispatched conversational reminder without payment link.",
        )

    # --------------------------------------------------------------------------
    # BRANCH 3: WAIT
    # --------------------------------------------------------------------------
    elif decision.action == PolicyAction.WAIT:
        payment.status = PaymentStatus.IN_PROGRESS
        audit_id = f"aud_{payment.id}_{attempt_number}_wait"
        audit = AuditLog(
            id=audit_id,
            failed_payment_id=payment.id,
            stage="WAIT_DECISION",
            input_summary=f"Delay required: {decision.delay_seconds}s ({decision.delay_seconds/3600:.1f}h)",
            decision=decision.action.value,
            reason=decision.reason,
            confidence=classification.confidence,
            policy_gates_evaluated=gates_json,
            created_at=now,
        )
        db.add(audit)
        db.commit()

        return ExecutionResult(
            payment_id=payment.id,
            action_executed=decision.action,
            success=True,
            audit_log_id=audit_id,
            notes=f"Waiting state engaged. Scheduled delay: {decision.delay_seconds}s.",
        )

    # --------------------------------------------------------------------------
    # BRANCH 4: SUPPRESS
    # --------------------------------------------------------------------------
    elif decision.action == PolicyAction.SUPPRESS:
        payment.status = PaymentStatus.SUPPRESSED
        audit_id = f"aud_{payment.id}_{attempt_number}_suppress"
        audit = AuditLog(
            id=audit_id,
            failed_payment_id=payment.id,
            stage="SUPPRESSION",
            input_summary="Outreach permanently halted or skipped by policy gate",
            decision=decision.action.value,
            reason=decision.reason,
            confidence=classification.confidence,
            policy_gates_evaluated=gates_json,
            created_at=now,
        )
        db.add(audit)
        db.commit()

        return ExecutionResult(
            payment_id=payment.id,
            action_executed=decision.action,
            success=True,
            audit_log_id=audit_id,
            notes=f"Suppressed: {decision.reason}",
        )

    # --------------------------------------------------------------------------
    # BRANCH 5: ESCALATE TO HUMAN
    # --------------------------------------------------------------------------
    elif decision.action == PolicyAction.ESCALATE_TO_HUMAN:
        payment.status = PaymentStatus.IN_PROGRESS
        audit_id = f"aud_{payment.id}_{attempt_number}_escalate"
        audit = AuditLog(
            id=audit_id,
            failed_payment_id=payment.id,
            stage="HUMAN_ESCALATION",
            input_summary=f"Low confidence ({classification.confidence:.2f}) flagged for manual review",
            decision=decision.action.value,
            reason=decision.reason,
            confidence=classification.confidence,
            policy_gates_evaluated=gates_json,
            created_at=now,
        )
        db.add(audit)
        db.commit()

        return ExecutionResult(
            payment_id=payment.id,
            action_executed=decision.action,
            success=True,
            audit_log_id=audit_id,
            notes="Enqueued to merchant support exceptions queue.",
        )

    else:
        raise ValueError(f"Unrecognized policy action: {decision.action}")
