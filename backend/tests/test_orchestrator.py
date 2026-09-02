"""
Unit tests for Orchestrator Run Loop, Demo Clock, and Event Streaming.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.data.generate import generate_dataset
from app.db import SessionLocal, Base, engine
from app.main import app
from app.models.enums import PaymentStatus
from app.models.failed_payment import FailedPayment
from app.orchestrator.clock import DemoClock
from app.orchestrator.events import StreamEvent, event_manager
from app.orchestrator.runner import run_batch


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    generate_dataset(seed=42, wipe_db=True)
    yield
    Base.metadata.drop_all(bind=engine)


def test_demo_clock_compression_math():
    clock = DemoClock(multiplier=28800.0)
    real_24h_seconds = 86400.0

    compressed = clock.compress_duration(real_24h_seconds)
    # 86400 / 28800 == 3.0 seconds
    assert compressed == 3.0

    audit = clock.format_time_audit(real_24h_seconds)
    assert audit["real_duration_hours"] == 24.0
    assert audit["real_duration_days"] == 1.0
    assert audit["compressed_duration_seconds"] == 3.0
    assert audit["is_time_compressed"] is True


def test_baseline_run_batch_resolves_all():
    db = SessionLocal()
    try:
        summary = run_batch(mode="baseline", seed=42, db=db, sleep_between_steps=False)
        assert summary.total_payments == 80
        assert summary.mode == "baseline"
        assert summary.recovered_count > 0
        assert summary.recovered_count + summary.abandoned_count == summary.total_payments

        # Verify all payments in DB are terminal (RECOVERED or ABANDONED)
        payments = db.query(FailedPayment).all()
        for p in payments:
            assert p.status in [PaymentStatus.RECOVERED, PaymentStatus.ABANDONED]
    finally:
        db.close()


def test_agent_run_batch_resolves_all_and_generates_audits():
    db = SessionLocal()
    try:
        from app.executor.razorpay_client import MockRazorpayClient
        summary = run_batch(
            mode="agent",
            seed=42,
            db=db,
            sleep_between_steps=False,
            razorpay_client=MockRazorpayClient(),
        )
        assert summary.total_payments == 80
        assert summary.mode == "agent"
        assert summary.recovered_count >= 25
        assert summary.suppressed_count >= 15
        assert summary.total_audit_logs >= 80

        # Verify no open payments left
        open_count = db.query(FailedPayment).filter(FailedPayment.status == PaymentStatus.OPEN).count()
        assert open_count == 0
    finally:
        db.close()


def test_api_start_run_and_stream():
    client = TestClient(app)
    
    # 1. Start background run
    response = client.post("/api/runs/start", json={
        "mode": "baseline",
        "seed": 42,
        "reseed": False,
        "split": "held_out"
    })
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "started"
    assert "stream_url" in data
