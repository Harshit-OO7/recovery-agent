import pytest
from datetime import datetime, timezone

from app.data.generate import generate_dataset
from app.models.enums import PropensityProfile, RecoveryAction, DatasetSplit
from app.models.customer import Customer
from app.models.failed_payment import FailedPayment
from app.simulator.engine import (
    simulate_customer_response,
    simulate_no_intervention,
    _evaluate_action_match_modifier,
)
from app.simulator.models import SimulationOutcome, BaselineOutcome


def test_simulation_reproducibility():
    """
    Core Principle #5: Fully deterministic with fixed seed.
    Two independent simulation runs with the same seed MUST yield identical outcomes.
    """
    customers, payments = generate_dataset(seed=42, wipe_db=True)
    
    run1_outcomes = []
    for payment in payments:
        cust = payment.customer
        res = simulate_customer_response(
            customer=cust,
            payment=payment,
            action=RecoveryAction.PAYMENT_LINK,
            attempt_number=1,
            master_seed=42
        )
        run1_outcomes.append((res.outcome, res.delay_hours, res.effective_pay_probability))

    run2_outcomes = []
    for payment in payments:
        cust = payment.customer
        res = simulate_customer_response(
            customer=cust,
            payment=payment,
            action=RecoveryAction.PAYMENT_LINK,
            attempt_number=1,
            master_seed=42
        )
        run2_outcomes.append((res.outcome, res.delay_hours, res.effective_pay_probability))

    assert run1_outcomes == run2_outcomes


def test_no_intervention_baseline_reproducibility_and_rate():
    """
    Verify that baseline runs are deterministic and produce a realistic, low recovery rate.
    """
    customers, payments = generate_dataset(seed=42, wipe_db=True)

    base1 = [simulate_no_intervention(p.customer, p, master_seed=42).outcome for p in payments]
    base2 = [simulate_no_intervention(p.customer, p, master_seed=42).outcome for p in payments]

    assert base1 == base2

    # Baseline recovery rate over the 80 payments should be modest (~5% - 20%)
    self_recovered_count = sum(1 for o in base1 if o == BaselineOutcome.SELF_RECOVERED)
    baseline_recovery_rate = self_recovered_count / len(payments)
    
    assert 0.04 <= baseline_recovery_rate <= 0.25, f"Unexpected baseline rate: {baseline_recovery_rate}"


def test_contacted_recovery_significantly_beats_baseline():
    """
    Core Requirement: Contacted recovery rate must be meaningfully higher than the no-intervention baseline.
    """
    customers, payments = generate_dataset(seed=42, wipe_db=True)

    # 1. Measure baseline
    baseline_recovered = sum(
        1 for p in payments
        if simulate_no_intervention(p.customer, p, master_seed=42).outcome == BaselineOutcome.SELF_RECOVERED
    )

    # 2. Measure contacted recovery on 1st attempt with matched action
    contacted_recovered = 0
    for p in payments:
        cust = p.customer
        action = RecoveryAction.DISCOUNT_NUDGE if p.failure_code == "CHECKOUT_ABANDONED" else RecoveryAction.PAYMENT_LINK
        res = simulate_customer_response(
            customer=cust,
            payment=p,
            action=action,
            attempt_number=1,
            master_seed=42
        )
        if res.outcome in [SimulationOutcome.PAID_IMMEDIATELY, SimulationOutcome.PAID_LATER]:
            contacted_recovered += 1

    baseline_rate = baseline_recovered / len(payments)
    contacted_rate = contacted_recovered / len(payments)

    # Contacted recovery should exhibit significant lift over organic baseline (> 2.5x lift)
    assert contacted_rate > baseline_rate
    assert (contacted_rate - baseline_rate) >= 0.20, f"Lift not high enough: Contacted={contacted_rate}, Baseline={baseline_rate}"


def test_action_match_modifiers():
    """
    Test modifier boost when action matches failure cause vs penalty on mismatch.
    """
    # 1. Gateway Timeout matched with direct payment link
    boost, _ = _evaluate_action_match_modifier(
        failure_code="GATEWAY_ERROR",
        failure_reason="Gateway timeout while communicating with acquiring bank",
        action=RecoveryAction.PAYMENT_LINK
    )
    assert boost >= 1.30

    # 2. Insufficient funds matched with reminder vs mismatched with discount
    boost_funds, _ = _evaluate_action_match_modifier(
        failure_code="BAD_REQUEST_ERROR",
        failure_reason="Insufficient funds in customer account",
        action=RecoveryAction.PAYMENT_REMINDER
    )
    assert boost_funds >= 1.25

    mismatch_funds, _ = _evaluate_action_match_modifier(
        failure_code="BAD_REQUEST_ERROR",
        failure_reason="Insufficient funds in customer account",
        action=RecoveryAction.DISCOUNT_NUDGE
    )
    assert mismatch_funds < 1.0


def test_attempt_decay_and_rising_opt_out():
    """
    Test that subsequent attempts decay pay probability and raise opt-out chance.
    """
    cust = Customer(
        id="cust_test",
        name="Test User",
        phone="+919800000001",
        email="test@example.in",
        city="Bengaluru",
        history_avg_days_to_pay=1.5,
        propensity_profile=PropensityProfile.DISTRACTED
    )
    payment = FailedPayment(
        id="pay_test",
        razorpay_order_id="order_test_1",
        customer_id=cust.id,
        amount_paise=150000,
        method="upi",
        failure_code="BAD_REQUEST_ERROR",
        failure_reason="Payment failed at payment gateway",
        failed_at=datetime.now(timezone.utc),
        cart_summary="Test Item",
        dataset_split=DatasetSplit.TRAIN
    )

    res_att1 = simulate_customer_response(cust, payment, RecoveryAction.PAYMENT_LINK, attempt_number=1, master_seed=42)
    res_att2 = simulate_customer_response(cust, payment, RecoveryAction.PAYMENT_LINK, attempt_number=2, master_seed=42)
    res_att3 = simulate_customer_response(cust, payment, RecoveryAction.PAYMENT_LINK, attempt_number=3, master_seed=42)

    assert res_att1.effective_pay_probability > res_att2.effective_pay_probability
    assert res_att2.effective_pay_probability > res_att3.effective_pay_probability
    assert res_att3.opt_out_probability > res_att1.opt_out_probability


def test_paid_later_delay_is_positive():
    """
    Verify that paid_later returns realistic, positive delay hours.
    """
    cust = Customer(
        id="cust_test_2",
        name="Test User 2",
        phone="+919800000002",
        email="test2@example.in",
        city="Mumbai",
        history_avg_days_to_pay=2.5,
        propensity_profile=PropensityProfile.HESITANT
    )
    payment = FailedPayment(
        id="pay_test_2",
        razorpay_order_id="order_test_2",
        customer_id=cust.id,
        amount_paise=89900,
        method="card",
        failure_code="BAD_REQUEST_ERROR",
        failure_reason="OTP entered was incorrect or expired",
        failed_at=datetime.now(timezone.utc),
        cart_summary="Test Bedsheet",
        dataset_split=DatasetSplit.TRAIN
    )

    res = simulate_customer_response(cust, payment, RecoveryAction.PAYMENT_LINK, attempt_number=1, master_seed=999)
    assert res.is_simulated is True
    if res.outcome == SimulationOutcome.PAID_LATER:
        assert res.delay_hours > 0.0
