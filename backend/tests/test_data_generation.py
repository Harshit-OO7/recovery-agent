import pytest
from app.data.generate import generate_dataset
from app.models.enums import DatasetSplit, PropensityProfile
from app.schemas.customer import CustomerAgentView, CustomerSimulatorView
from app.db import SessionLocal
from app.models.customer import Customer
from app.models.failed_payment import FailedPayment


def test_dataset_generation_counts_and_splits():
    customers, payments = generate_dataset(seed=42, wipe_db=True)
    
    assert len(customers) == 55
    assert len(payments) == 80
    
    train_count = sum(1 for p in payments if p.dataset_split == DatasetSplit.TRAIN)
    held_out_count = sum(1 for p in payments if p.dataset_split == DatasetSplit.HELD_OUT)
    
    assert train_count == 60
    assert held_out_count == 20


def test_dataset_generation_determinism():
    """
    Core Design Principle #5: Identical seed must produce identical data across runs.
    """
    cust1, pay1 = generate_dataset(seed=123, wipe_db=True)
    pay1_ids = [p.id for p in pay1]
    pay1_amounts = [p.amount_paise for p in pay1]
    pay1_orders = [p.razorpay_order_id for p in pay1]

    cust2, pay2 = generate_dataset(seed=123, wipe_db=True)
    pay2_ids = [p.id for p in pay2]
    pay2_amounts = [p.amount_paise for p in pay2]
    pay2_orders = [p.razorpay_order_id for p in pay2]

    assert pay1_ids == pay2_ids
    assert pay1_amounts == pay2_amounts
    assert pay1_orders == pay2_orders


def test_micro_amounts_and_risk_flags():
    """
    Verify test conditions for policy gates:
    - Micro transactions (< Rs 100 / 10000 paise) for cost-of-contact gate
    - Risk-flagged customers for do-not-contact gate
    """
    customers, payments = generate_dataset(seed=42, wipe_db=True)
    
    micro_payments = [p for p in payments if p.amount_paise < 10000]
    assert len(micro_payments) == 10
    for p in micro_payments:
        assert p.amount_rupees < 100.0

    risk_customers = [c for c in customers if c.is_risk_flagged]
    assert len(risk_customers) == 7


def test_ground_truth_leakage_protection():
    """
    CRITICAL ARCHITECTURAL SAFETY CHECK:
    The CustomerAgentView schema imported by agent code must NOT expose `propensity_profile`.
    Only CustomerSimulatorView contains `propensity_profile`.
    """
    db = SessionLocal()
    try:
        customer = db.query(Customer).first()
        assert customer is not None
        assert customer.propensity_profile in list(PropensityProfile)

        # Agent View conversion
        agent_view = CustomerAgentView.model_validate(customer)
        assert not hasattr(agent_view, "propensity_profile")
        assert "propensity_profile" not in agent_view.model_dump()

        # Simulator View conversion
        sim_view = CustomerSimulatorView.model_validate(customer)
        assert hasattr(sim_view, "propensity_profile")
        assert sim_view.propensity_profile == customer.propensity_profile
    finally:
        db.close()


def test_database_relationships():
    db = SessionLocal()
    try:
        payment = db.query(FailedPayment).first()
        assert payment is not None
        assert payment.customer is not None
        assert isinstance(payment.customer.name, str)
        assert hasattr(payment, "recovery_attempts")
        assert hasattr(payment, "audit_logs")
    finally:
        db.close()
