"""
Exhaustive unit test suite for the Deterministic Policy Engine.
Verifies all 7 hard gates independently and guarantees no LLM output can bypass safety rules.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.llm.classifier import ClassificationCategory, ClassificationResult
from app.models.enums import AttemptOutcome, RecoveryAction, RecoveryChannel, PaymentMethod, PaymentStatus, DatasetSplit
from app.models.customer import Customer
from app.models.failed_payment import FailedPayment
from app.models.recovery_attempt import RecoveryAttempt
from app.policy.policy import (
    POLICY_CONFIG,
    PolicyAction,
    GateStatus,
    Decision,
    decide,
    IST_TIMEZONE,
)


@pytest.fixture
def base_customer():
    return Customer(
        id="cust_test_101",
        name="Harshit Sharma",
        phone="+919876543210",
        email="harshit@example.in",
        city="Bengaluru",
        history_total_payments=10,
        history_failed_payments=1,
        history_avg_days_to_pay=1.0,
        is_risk_flagged=False,
    )


@pytest.fixture
def base_payment(base_customer):
    return FailedPayment(
        id="pay_test_201",
        razorpay_order_id="order_test_201",
        customer_id=base_customer.id,
        customer=base_customer,
        amount_paise=249900,  # Rs. 2,499
        currency="INR",
        method=PaymentMethod.UPI,
        failure_code="GATEWAY_ERROR",
        failure_reason="Gateway timeout while communicating with bank",
        failed_at=datetime.now(timezone.utc),
        cart_summary="Mixer Grinder 750W",
        status=PaymentStatus.OPEN,
        dataset_split=DatasetSplit.TRAIN,
    )


@pytest.fixture
def daytime_ist():
    # 14:00 (2:00 PM) IST = within active hours (09:00 - 20:00)
    return datetime(2026, 9, 2, 14, 0, 0, tzinfo=IST_TIMEZONE)


@pytest.fixture
def nighttime_ist():
    # 22:30 (10:30 PM) IST = quiet hours
    return datetime(2026, 9, 2, 22, 30, 0, tzinfo=IST_TIMEZONE)


# ==============================================================================
# GATE 1: DO NOT CONTACT (Risk Flagged or Opted Out)
# ==============================================================================

def test_gate1_fires_on_risk_flagged_customer(base_customer, base_payment, daytime_ist):
    base_customer.is_risk_flagged = True
    classification = ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.99,
        reasoning="Customer had a transient glitch.",
        signals_used=["gateway_timeout"],
    )

    decision = decide(base_payment, base_customer, classification, attempt_history=[], current_time=daytime_ist)

    assert decision.action == PolicyAction.SUPPRESS
    g1 = next(g for g in decision.gates_evaluated if g.gate_id == "G1")
    assert g1.status == GateStatus.TRIGGERED
    assert "risk" in g1.reason.lower()


def test_gate1_fires_on_opted_out_customer(base_customer, base_payment, daytime_ist):
    opted_out_attempt = RecoveryAttempt(
        id="att_1",
        failed_payment_id=base_payment.id,
        attempt_number=1,
        channel=RecoveryChannel.WHATSAPP,
        action_taken="send_payment_link",
        sent_at=daytime_ist - timedelta(days=2),
        outcome=AttemptOutcome.OPTED_OUT,
    )
    classification = ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.95,
        reasoning="Technical glitch.",
        signals_used=[],
    )

    decision = decide(base_payment, base_customer, classification, attempt_history=[opted_out_attempt], current_time=daytime_ist)

    assert decision.action == PolicyAction.SUPPRESS
    g1 = next(g for g in decision.gates_evaluated if g.gate_id == "G1")
    assert g1.status == GateStatus.TRIGGERED
    assert "opted out" in g1.reason.lower()


# ==============================================================================
# GATE 2: VALUE FLOOR (Cost-of-Contact)
# ==============================================================================

def test_gate2_fires_on_micro_amount_under_rs_100(base_customer, base_payment, daytime_ist):
    base_payment.amount_paise = 4900  # Rs. 49 (< 10000 paise threshold)
    classification = ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.95,
        reasoning="Technical failure.",
        signals_used=[],
    )

    decision = decide(base_payment, base_customer, classification, attempt_history=[], current_time=daytime_ist)

    assert decision.action == PolicyAction.SUPPRESS
    g2 = next(g for g in decision.gates_evaluated if g.gate_id == "G2")
    assert g2.status == GateStatus.TRIGGERED
    assert "cost-of-contact" in g2.reason.lower() or "below" in g2.reason.lower()


def test_gate2_passes_on_amount_at_or_above_floor(base_customer, base_payment, daytime_ist):
    base_payment.amount_paise = 10000  # Rs. 100 (exactly at threshold)
    classification = ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.95,
        reasoning="Technical failure.",
        signals_used=[],
    )

    decision = decide(base_payment, base_customer, classification, attempt_history=[], current_time=daytime_ist)

    g2 = next(g for g in decision.gates_evaluated if g.gate_id == "G2")
    assert g2.status == GateStatus.PASSED


# ==============================================================================
# GATE 3: MAX ATTEMPTS (Anti-Spam / Fatigue)
# ==============================================================================

def test_gate3_fires_when_max_attempts_reached(base_customer, base_payment, daytime_ist):
    attempts = [
        RecoveryAttempt(
            id="att_1",
            failed_payment_id=base_payment.id,
            attempt_number=1,
            channel=RecoveryChannel.WHATSAPP,
            action_taken="send_payment_link",
            sent_at=daytime_ist - timedelta(days=3),
            outcome=AttemptOutcome.IGNORED,
        ),
        RecoveryAttempt(
            id="att_2",
            failed_payment_id=base_payment.id,
            attempt_number=2,
            channel=RecoveryChannel.WHATSAPP,
            action_taken="send_payment_link",
            sent_at=daytime_ist - timedelta(days=1),
            outcome=AttemptOutcome.IGNORED,
        ),
    ]
    classification = ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.95,
        reasoning="Technical glitch.",
        signals_used=[],
    )

    decision = decide(base_payment, base_customer, classification, attempt_history=attempts, current_time=daytime_ist)

    assert decision.action == PolicyAction.SUPPRESS
    g3 = next(g for g in decision.gates_evaluated if g.gate_id == "G3")
    assert g3.status == GateStatus.TRIGGERED
    assert "maximum" in g3.reason.lower() or "limit" in g3.reason.lower()


# ==============================================================================
# GATE 4: COOLDOWN (Rest Interval Between Attempts)
# ==============================================================================

def test_gate4_fires_when_cooldown_active(base_customer, base_payment, daytime_ist):
    # Attempt sent only 6 hours ago (< 24h cooldown)
    attempt = RecoveryAttempt(
        id="att_1",
        failed_payment_id=base_payment.id,
        attempt_number=1,
        channel=RecoveryChannel.WHATSAPP,
        action_taken="send_payment_link",
        sent_at=daytime_ist - timedelta(hours=6),
        outcome=AttemptOutcome.IGNORED,
    )
    classification = ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.95,
        reasoning="Technical glitch.",
        signals_used=[],
    )

    decision = decide(base_payment, base_customer, classification, attempt_history=[attempt], current_time=daytime_ist)

    assert decision.action == PolicyAction.WAIT
    assert decision.delay_seconds > 0
    g4 = next(g for g in decision.gates_evaluated if g.gate_id == "G4")
    assert g4.status == GateStatus.TRIGGERED


def test_gate4_passes_when_cooldown_satisfied(base_customer, base_payment, daytime_ist):
    # Attempt sent 26 hours ago (> 24h cooldown)
    attempt = RecoveryAttempt(
        id="att_1",
        failed_payment_id=base_payment.id,
        attempt_number=1,
        channel=RecoveryChannel.WHATSAPP,
        action_taken="send_reminder_no_link",
        sent_at=daytime_ist - timedelta(hours=26),
        outcome=AttemptOutcome.IGNORED,
    )
    classification = ClassificationResult(
        category=ClassificationCategory.INTENT_HESITATION,
        confidence=0.88,
        reasoning="Hesitation on checkout.",
        signals_used=[],
    )

    decision = decide(base_payment, base_customer, classification, attempt_history=[attempt], current_time=daytime_ist)

    g4 = next(g for g in decision.gates_evaluated if g.gate_id == "G4")
    assert g4.status == GateStatus.PASSED


# ==============================================================================
# GATE 5: QUIET HOURS (09:00 - 20:00 IST)
# ==============================================================================

def test_gate5_fires_during_nighttime_quiet_hours(base_customer, base_payment, nighttime_ist):
    classification = ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.95,
        reasoning="Technical glitch.",
        signals_used=[],
    )

    decision = decide(base_payment, base_customer, classification, attempt_history=[], current_time=nighttime_ist)

    assert decision.action == PolicyAction.WAIT
    assert decision.delay_seconds > 0
    g5 = next(g for g in decision.gates_evaluated if g.gate_id == "G5")
    assert g5.status == GateStatus.TRIGGERED
    assert "quiet" in g5.reason.lower() or "outside" in g5.reason.lower()


# ==============================================================================
# GATE 6: CONFIDENCE FLOOR (Escalate Low-Confidence Classifications)
# ==============================================================================

def test_gate6_fires_on_low_confidence_classification(base_customer, base_payment, daytime_ist):
    classification = ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.42,  # Low confidence (< 0.55 threshold)
        reasoning="Uncertain error signals.",
        signals_used=["vague_error"],
    )

    decision = decide(base_payment, base_customer, classification, attempt_history=[], current_time=daytime_ist)

    assert decision.action == PolicyAction.ESCALATE_TO_HUMAN
    g6 = next(g for g in decision.gates_evaluated if g.gate_id == "G6")
    assert g6.status == GateStatus.TRIGGERED
    assert "confidence" in g6.reason.lower()


# ==============================================================================
# GATE 7: CATEGORY ROUTE (Operational Action Assignment)
# ==============================================================================

def test_gate7_routes_technical_failure_to_instant_link(base_customer, base_payment, daytime_ist):
    classification = ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.90,
        reasoning="Acquiring bank timeout.",
        signals_used=[],
    )
    decision = decide(base_payment, base_customer, classification, attempt_history=[], current_time=daytime_ist)
    assert decision.action == PolicyAction.SEND_PAYMENT_LINK
    assert decision.delay_seconds == 0


def test_gate7_routes_authentication_drop_to_instant_link(base_customer, base_payment, daytime_ist):
    classification = ClassificationResult(
        category=ClassificationCategory.AUTHENTICATION_DROP,
        confidence=0.88,
        reasoning="OTP expired.",
        signals_used=[],
    )
    decision = decide(base_payment, base_customer, classification, attempt_history=[], current_time=daytime_ist)
    assert decision.action == PolicyAction.SEND_PAYMENT_LINK
    assert decision.delay_seconds == 0


def test_gate7_routes_insufficient_funds_to_delayed_link(base_customer, base_payment, daytime_ist):
    classification = ClassificationResult(
        category=ClassificationCategory.INSUFFICIENT_FUNDS,
        confidence=0.92,
        reasoning="Insufficient account balance.",
        signals_used=[],
    )
    decision = decide(base_payment, base_customer, classification, attempt_history=[], current_time=daytime_ist)
    assert decision.action == PolicyAction.SEND_PAYMENT_LINK
    assert decision.delay_seconds == int(POLICY_CONFIG["SALARY_CYCLE_DELAY_HOURS"] * 3600)


def test_gate7_routes_intent_hesitation_attempt1_to_reminder_no_link(base_customer, base_payment, daytime_ist):
    classification = ClassificationResult(
        category=ClassificationCategory.INTENT_HESITATION,
        confidence=0.85,
        reasoning="Abandoned cart.",
        signals_used=[],
    )
    decision = decide(base_payment, base_customer, classification, attempt_history=[], current_time=daytime_ist)
    assert decision.action == PolicyAction.SEND_REMINDER_NO_LINK
    assert decision.delay_seconds == 0


def test_gate7_routes_intent_hesitation_attempt2_to_link(base_customer, base_payment, daytime_ist):
    attempt1 = RecoveryAttempt(
        id="att_1",
        failed_payment_id=base_payment.id,
        attempt_number=1,
        channel=RecoveryChannel.WHATSAPP,
        action_taken="send_reminder_no_link",
        sent_at=daytime_ist - timedelta(hours=25),
        outcome=AttemptOutcome.IGNORED,
    )
    classification = ClassificationResult(
        category=ClassificationCategory.INTENT_HESITATION,
        confidence=0.85,
        reasoning="Abandoned cart.",
        signals_used=[],
    )
    decision = decide(base_payment, base_customer, classification, attempt_history=[attempt1], current_time=daytime_ist)
    assert decision.action == PolicyAction.SEND_PAYMENT_LINK


# ==============================================================================
# THE POINT TEST: ABSOLUTE RISK SUPPRESSION IRRESPECTIVE OF CLASSIFIER OUTPUT
# ==============================================================================

def test_risk_flagged_customer_cannot_receive_payment_link_under_any_circumstances(base_customer, base_payment, daytime_ist):
    """
    CRITICAL ARCHITECTURAL SAFETY INVARIANT:
    No matter what category, confidence, or reasoning the LLM classifier outputs,
    a risk-flagged customer must NEVER be approved for outreach.
    """
    base_customer.is_risk_flagged = True

    # Test against EVERY possible classification category with 100% confidence
    for cat in ClassificationCategory:
        hallucinated_perfect_classification = ClassificationResult(
            category=cat,
            confidence=1.0,
            reasoning="The model insisted 100% this customer wants to pay immediately.",
            signals_used=["fake_signal"],
        )

        decision = decide(
            payment=base_payment,
            customer=base_customer,
            classification=hallucinated_perfect_classification,
            attempt_history=[],
            current_time=daytime_ist,
        )

        assert decision.action == PolicyAction.SUPPRESS, (
            f"SECURITY VIOLATION: Risk-flagged customer received action {decision.action} "
            f"when classifier returned category {cat}."
        )
        assert decision.action != PolicyAction.SEND_PAYMENT_LINK
        assert decision.action != PolicyAction.SEND_REMINDER_NO_LINK
