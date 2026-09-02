"""
Unit tests for the Executor and Razorpay Client.
"""

from datetime import datetime, timezone
import pytest

from app.db import SessionLocal, Base, engine
from app.executor.razorpay_client import (
    MockRazorpayClient,
    RealRazorpayClient,
    RazorpayClientError,
)
from app.executor.executor import execute_decision, ExecutionResult
from app.llm.classifier import ClassificationCategory, ClassificationResult
from app.models.enums import PaymentStatus, RecoveryChannel, PaymentMethod, DatasetSplit, PropensityProfile
from app.models.customer import Customer
from app.models.failed_payment import FailedPayment
from app.models.recovery_attempt import RecoveryAttempt
from app.models.audit_log import AuditLog
from app.policy.policy import Decision, PolicyAction, GateEvaluation, GateStatus


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_customer():
    db = SessionLocal()
    cust = Customer(
        id="cust_exec_1",
        name="Harshit Sharma",
        phone="+919876543210",
        email="harshit@example.in",
        city="Bengaluru",
        history_total_payments=8,
        history_failed_payments=1,
        history_avg_days_to_pay=1.0,
        is_risk_flagged=False,
        propensity_profile=PropensityProfile.RELIABLE,
    )
    db.add(cust)
    db.commit()
    db.refresh(cust)
    db.close()
    return cust


@pytest.fixture
def test_payment(test_customer):
    db = SessionLocal()
    pay = FailedPayment(
        id="pay_exec_1",
        razorpay_order_id="order_exec_1001",
        customer_id=test_customer.id,
        amount_paise=249900,
        currency="INR",
        method=PaymentMethod.UPI,
        failure_code="GATEWAY_ERROR",
        failure_reason="Gateway timeout while communicating with bank",
        failed_at=datetime.now(timezone.utc),
        cart_summary="Mixer Grinder 750W",
        status=PaymentStatus.OPEN,
        dataset_split=DatasetSplit.TRAIN,
    )
    db.add(pay)
    db.commit()
    db.refresh(pay)
    db.close()
    return pay


def test_razorpay_client_idempotency_and_creation():
    client = MockRazorpayClient()
    ref_id = "test_order_123_att1"

    # First call creates link
    link1 = client.create_payment_link(
        amount_paise=249900,
        customer_name="Harshit",
        customer_email="harshit@example.in",
        customer_phone="+919876543210",
        description="Mixer Grinder 750W",
        reference_id=ref_id,
    )

    assert "id" in link1
    assert "short_url" in link1
    assert link1["id"].startswith("plink_mock_")
    assert link1["short_url"].startswith("https://rzp.io/i/")

    # Second call with identical reference_id MUST return identical link (Idempotency)
    link2 = client.create_payment_link(
        amount_paise=249900,
        customer_name="Harshit",
        customer_email="harshit@example.in",
        customer_phone="+919876543210",
        description="Mixer Grinder 750W",
        reference_id=ref_id,
    )

    assert link1["id"] == link2["id"]
    assert link1["short_url"] == link2["short_url"]


def test_real_client_rejects_live_keys():
    """
    CRITICAL SECURITY TEST: Real client must refuse to initialize with rzp_live keys.
    """
    with pytest.raises(RazorpayClientError) as exc_info:
        RealRazorpayClient(key_id="rzp_live_1234567890", key_secret="secret123")
    assert "Live Razorpay keys are strictly forbidden" in str(exc_info.value)


def test_execute_send_payment_link(test_customer, test_payment):
    db = SessionLocal()
    try:
        # Load fresh payment
        pay = db.query(FailedPayment).filter_by(id=test_payment.id).first()
        cust = db.query(Customer).filter_by(id=test_customer.id).first()

        decision = Decision(
            action=PolicyAction.SEND_PAYMENT_LINK,
            channel=RecoveryChannel.WHATSAPP,
            delay_seconds=0,
            reason="Gateway timeout: 1-click payment link recovery.",
            gates_evaluated=[
                GateEvaluation(gate_id="G1", name="do_not_contact", status=GateStatus.PASSED, reason="Passed"),
                GateEvaluation(gate_id="G7", name="category_route", status=GateStatus.TRIGGERED, reason="Routed to link"),
            ]
        )
        classification = ClassificationResult(
            category=ClassificationCategory.TECHNICAL_FAILURE,
            confidence=0.92,
            reasoning="Gateway timeout.",
            signals_used=["gateway_error"],
        )

        mock_rzp = MockRazorpayClient()
        result = execute_decision(
            decision=decision,
            payment=pay,
            customer=cust,
            classification=classification,
            db=db,
            attempt_number=1,
            razorpay_client=mock_rzp,
        )

        assert result.success is True
        assert result.payment_link_url is not None
        assert "rzp.io" in result.payment_link_url
        assert result.recovery_attempt_id is not None
        assert result.audit_log_id is not None

        # Verify DB records
        attempt = db.query(RecoveryAttempt).filter_by(id=result.recovery_attempt_id).first()
        assert attempt is not None
        assert attempt.payment_link_id is not None
        assert attempt.action_taken == "send_payment_link"

        audit = db.query(AuditLog).filter_by(id=result.audit_log_id).first()
        assert audit is not None
        assert audit.stage == "EXECUTION"
        assert audit.decision == "send_payment_link"

    finally:
        db.close()


def test_execute_suppress(test_customer, test_payment):
    db = SessionLocal()
    try:
        pay = db.query(FailedPayment).filter_by(id=test_payment.id).first()
        cust = db.query(Customer).filter_by(id=test_customer.id).first()

        decision = Decision(
            action=PolicyAction.SUPPRESS,
            channel=RecoveryChannel.WHATSAPP,
            delay_seconds=0,
            reason="Cart amount < Rs. 100.",
            gates_evaluated=[
                GateEvaluation(gate_id="G2", name="value_floor", status=GateStatus.TRIGGERED, reason="Under Rs 100"),
            ]
        )
        classification = ClassificationResult(
            category=ClassificationCategory.TECHNICAL_FAILURE,
            confidence=0.85,
            reasoning="Glitch",
            signals_used=[],
        )

        result = execute_decision(
            decision=decision,
            payment=pay,
            customer=cust,
            classification=classification,
            db=db,
            attempt_number=1,
        )

        assert result.success is True
        assert pay.status == PaymentStatus.SUPPRESSED

        audit = db.query(AuditLog).filter_by(id=result.audit_log_id).first()
        assert audit is not None
        assert audit.stage == "SUPPRESSION"
        assert audit.decision == "suppress"

    finally:
        db.close()


def test_execute_escalate_to_human(test_customer, test_payment):
    db = SessionLocal()
    try:
        pay = db.query(FailedPayment).filter_by(id=test_payment.id).first()
        cust = db.query(Customer).filter_by(id=test_customer.id).first()

        decision = Decision(
            action=PolicyAction.ESCALATE_TO_HUMAN,
            channel=RecoveryChannel.WHATSAPP,
            delay_seconds=0,
            reason="Confidence < 0.55",
            gates_evaluated=[
                GateEvaluation(gate_id="G6", name="confidence_floor", status=GateStatus.TRIGGERED, reason="Low confidence"),
            ]
        )
        classification = ClassificationResult(
            category=ClassificationCategory.TECHNICAL_FAILURE,
            confidence=0.40,
            reasoning="Uncertain",
            signals_used=[],
        )

        result = execute_decision(
            decision=decision,
            payment=pay,
            customer=cust,
            classification=classification,
            db=db,
            attempt_number=1,
        )

        assert result.success is True
        audit = db.query(AuditLog).filter_by(id=result.audit_log_id).first()
        assert audit is not None
        assert audit.stage == "HUMAN_ESCALATION"
        assert audit.decision == "escalate_to_human"

    finally:
        db.close()
