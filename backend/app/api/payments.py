"""
Payment Transactions and Audit Trail API Endpoints.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.enums import PaymentStatus
from app.models.failed_payment import FailedPayment
from app.models.recovery_attempt import RecoveryAttempt
from app.schemas.customer import CustomerAgentView

logger = logging.getLogger("app.api.payments")
router = APIRouter(prefix="/api/payments", tags=["Payment Audit Trails"])


class AuditLogItem(BaseModel):
    id: str
    stage: str
    decision: str
    reason: str
    confidence: Optional[float] = None
    input_summary: Optional[str] = None
    policy_gates_evaluated: Optional[Any] = None
    created_at: str


class RecoveryAttemptItem(BaseModel):
    id: str
    attempt_number: int
    channel: str
    action_taken: str
    payment_link_id: Optional[str] = None
    payment_link_url: Optional[str] = None
    sent_at: str
    outcome: str
    outcome_at: Optional[str] = None


class PaymentAuditTrailResponse(BaseModel):
    payment_id: str
    order_id: str
    amount_rupees: float
    currency: str
    method: str
    failure_code: str
    failure_reason: str
    failed_at: str
    cart_summary: str
    status: str
    customer: CustomerAgentView  # Strictly omits propensity_profile
    total_attempts: int
    recovery_attempts: List[RecoveryAttemptItem]
    audit_logs: List[AuditLogItem]


@router.get("/{id}/audit", response_model=PaymentAuditTrailResponse)
def get_payment_audit_trail(
    id: str = Path(..., description="The failed payment ID (e.g. pay_1001)"),
    db: Session = Depends(get_db),
):
    """
    Returns the complete, tamper-evident audit trail for a single payment,
    including non-sensitive customer profile, all outreach attempts, and sequential gate evaluations.
    """
    payment = db.query(FailedPayment).filter_by(id=id).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment '{id}' not found.")

    cust = payment.customer
    if not cust:
        raise HTTPException(status_code=404, detail="Associated customer not found.")

    cust_view = CustomerAgentView(
        id=cust.id,
        name=cust.name,
        phone=cust.phone,
        email=cust.email,
        city=cust.city,
        history_total_payments=cust.history_total_payments,
        history_failed_payments=cust.history_failed_payments,
        history_avg_days_to_pay=cust.history_avg_days_to_pay,
        is_risk_flagged=cust.is_risk_flagged,
    )

    attempts = db.query(RecoveryAttempt).filter_by(failed_payment_id=id).order_by(RecoveryAttempt.attempt_number.asc()).all()
    attempts_items = [
        RecoveryAttemptItem(
            id=a.id,
            attempt_number=a.attempt_number,
            channel=a.channel.value if hasattr(a.channel, "value") else str(a.channel),
            action_taken=a.action_taken,
            payment_link_id=a.payment_link_id,
            payment_link_url=a.payment_link_url,
            sent_at=a.sent_at.isoformat() if a.sent_at else "",
            outcome=a.outcome.value if hasattr(a.outcome, "value") else str(a.outcome),
            outcome_at=a.outcome_at.isoformat() if a.outcome_at else None,
        )
        for a in attempts
    ]

    audit_logs = db.query(AuditLog).filter_by(failed_payment_id=id).order_by(AuditLog.created_at.asc()).all()
    audit_items = [
        AuditLogItem(
            id=log.id,
            stage=log.stage,
            decision=log.decision,
            reason=log.reason,
            confidence=log.confidence,
            input_summary=log.input_summary,
            policy_gates_evaluated=log.policy_gates_evaluated,
            created_at=log.created_at.isoformat() if log.created_at else "",
        )
        for log in audit_logs
    ]

    return PaymentAuditTrailResponse(
        payment_id=payment.id,
        order_id=payment.razorpay_order_id,
        amount_rupees=payment.amount_rupees,
        currency=payment.currency,
        method=payment.method.value if hasattr(payment.method, "value") else str(payment.method),
        failure_code=payment.failure_code,
        failure_reason=payment.failure_reason,
        failed_at=payment.failed_at.isoformat() if payment.failed_at else "",
        cart_summary=payment.cart_summary,
        status=payment.status.value,
        customer=cust_view,
        total_attempts=len(attempts_items),
        recovery_attempts=attempts_items,
        audit_logs=audit_items,
    )


@router.get("", response_model=List[Dict[str, Any]])
def list_payments(
    status_filter: Optional[str] = Query(None, description="Filter by status (open, in_progress, recovered, abandoned, suppressed)"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Lists payment records with customer name, cart summary, and current recovery status.
    """
    query = db.query(FailedPayment)
    if status_filter:
        try:
            status_enum = PaymentStatus(status_filter.lower())
            query = query.filter(FailedPayment.status == status_enum)
        except ValueError:
            pass

    payments = query.order_by(FailedPayment.failed_at.desc()).limit(limit).all()
    return [
        {
            "id": p.id,
            "order_id": p.razorpay_order_id,
            "customer_name": p.customer.name if p.customer else "Unknown",
            "amount_rupees": p.amount_rupees,
            "cart_summary": p.cart_summary,
            "failure_code": p.failure_code,
            "failure_reason": p.failure_reason,
            "status": p.status.value,
            "failed_at": p.failed_at.isoformat() if p.failed_at else None,
        }
        for p in payments
    ]
