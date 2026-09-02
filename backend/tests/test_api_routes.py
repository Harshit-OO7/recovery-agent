"""
Comprehensive API Integration Test Suite for all FastAPI Endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.data.generate import generate_dataset
from app.db import SessionLocal, Base, engine
from app.executor.razorpay_client import MockRazorpayClient
from app.main import app
from app.models.failed_payment import FailedPayment
from app.orchestrator.runner import run_batch


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    generate_dataset(seed=42, wipe_db=True)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_root_and_health(client):
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "Welcome" in res_root.json()["message"]

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"


def test_post_runs_start(client):
    res = client.post("/api/runs", json={
        "mode": "baseline",
        "seed": 42,
        "split": "held_out",
        "reseed": False,
    })
    assert res.status_code == 202
    data = res.json()
    assert "run_id" in data
    assert data["status"] == "started"
    assert "/api/runs/" in data["stream_url"]


def test_get_run_events_and_exceptions(client):
    db = SessionLocal()
    try:
        summary = run_batch(mode="agent", seed=42, db=db, sleep_between_steps=False, razorpay_client=MockRazorpayClient())
        run_id = summary.run_id
    finally:
        db.close()

    # 1. Test /api/runs/{id}/events
    res_events = client.get(f"/api/runs/{run_id}/events?page=1&page_size=10")
    assert res_events.status_code == 200
    events_data = res_events.json()
    assert events_data["total_items"] == 80
    assert len(events_data["items"]) == 10
    assert events_data["page"] == 1

    # 2. Test /api/runs/{id}/exceptions
    res_exc = client.get(f"/api/runs/{run_id}/exceptions")
    assert res_exc.status_code == 200
    exc_data = res_exc.json()
    assert exc_data["total_exceptions"] > 0
    assert exc_data["total_suppressed"] >= 15
    assert exc_data["total_suppressed_value_rupees"] > 0.0


def test_get_payment_audit_trail(client):
    db = SessionLocal()
    try:
        run_batch(mode="agent", seed=42, db=db, sleep_between_steps=False, razorpay_client=MockRazorpayClient())
        first_pay = db.query(FailedPayment).first()
        pay_id = first_pay.id
    finally:
        db.close()

    res_audit = client.get(f"/api/payments/{pay_id}/audit")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["payment_id"] == pay_id
    assert "customer" in audit_data
    # Verify no propensity_profile in customer view (Zero data leakage)
    assert "propensity_profile" not in audit_data["customer"]
    assert "audit_logs" in audit_data
    assert len(audit_data["audit_logs"]) > 0


def test_get_policy_config(client):
    res = client.get("/api/policy")
    assert res.status_code == 200
    data = res.json()
    assert "policy_config" in data
    assert data["policy_config"]["COST_OF_CONTACT_THRESHOLD_PAISE"] == 10000
    assert len(data["gate_definitions"]) == 7


def test_post_policy_simulate_what_if_slider(client):
    # Simulate with custom value floor of Rs. 200 (20,000 paise) and max attempts = 1
    res = client.post("/api/policy/simulate", json={
        "cost_of_contact_threshold_rupees": 200.0,
        "max_recovery_attempts": 1,
        "confidence_floor": 0.60,
    })
    assert res.status_code == 200
    sim_data = res.json()
    assert sim_data["total_evaluated"] == 80
    assert sim_data["simulated_suppressed_count"] > 0
    assert sim_data["simulated_eligible_count"] > 0
    assert len(sim_data["suppression_breakdown"]) == 3
    assert sim_data["parameters_applied"]["cost_of_contact_threshold_rupees"] == 200.0


def test_get_runs_compare(client):
    res = client.get("/api/runs/compare?seed=42")
    assert res.status_code == 200
    data = res.json()
    assert data["seed"] == 42
    assert data["agent_recovery_rate_pct"] > data["baseline_recovery_rate_pct"]
    assert data["net_recovery_rate_lift_pct"] > 0
    assert data["net_revenue_lift_rupees"] > 0
