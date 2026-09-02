"""
Unit tests for Evaluation Metrics, Benchmark Comparisons, and Honest Reporting.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.data.generate import generate_dataset
from app.db import SessionLocal, Base, engine
from app.eval.metrics import (
    ASSUMED_CONTACT_COST_INR,
    HONEST_LIMITATIONS,
    RunMetrics,
    ComparisonReport,
    compute_run_metrics,
    compare_runs,
    export_results_markdown,
)
from app.executor.razorpay_client import MockRazorpayClient
from app.main import app
from app.orchestrator.runner import run_batch


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    generate_dataset(seed=42, wipe_db=True)
    yield
    Base.metadata.drop_all(bind=engine)


def test_metrics_computation_and_unit_economics():
    db = SessionLocal()
    try:
        summary = run_batch(
            mode="agent",
            seed=42,
            db=db,
            sleep_between_steps=False,
            razorpay_client=MockRazorpayClient(),
        )
        metrics = compute_run_metrics(summary, db=db, evaluate_held_out=True)

        assert metrics.total_payments == 80
        assert metrics.value_at_risk_rupees > 400000.0
        assert metrics.recovered_count > 0
        assert metrics.recovery_rate_pct == summary.recovery_rate_pct
        assert metrics.contacts_sent == summary.total_attempts_made

        # Check unit economics formula
        expected_cost = metrics.contacts_sent * ASSUMED_CONTACT_COST_INR
        assert metrics.total_contact_cost_rupees == round(expected_cost, 2)
        assert metrics.cost_per_recovery_rupees > 0.0

        # Check suppression breakdown
        assert len(metrics.suppression_breakdown) == 3
        g1 = next(g for g in metrics.suppression_breakdown if g.gate_id == "G1")
        assert g1.count >= 7  # 7 risk-flagged accounts in dataset
        assert g1.value_rupees > 0.0

        # Check held-out intent classification evaluation
        assert metrics.classification_eval is not None
        assert metrics.classification_eval.overall_accuracy_pct >= 90.0
        assert metrics.classification_eval.held_out_count == 20

        # Check honest limitations disclosure presence
        assert "synthetic" in metrics.limitations["dataset_type"].lower()
        assert "simulated" in metrics.limitations["customer_behavior"].lower()
    finally:
        db.close()


def test_compare_runs_integrity_guard_rejects_mismatched_seeds():
    """
    CRITICAL BENCHMARK GUARD:
    Refuse to compare and raise a clear error if the seeds differ.
    """
    db = SessionLocal()
    try:
        summary_agent = run_batch(mode="agent", seed=42, db=db, sleep_between_steps=False, razorpay_client=MockRazorpayClient())
        metrics_agent = compute_run_metrics(summary_agent, db=db, evaluate_held_out=False)

        summary_base = run_batch(mode="baseline", seed=99, db=db, sleep_between_steps=False)
        metrics_base = compute_run_metrics(summary_base, db=db, evaluate_held_out=False)
        # Explicitly set seed to 99 on base metrics
        metrics_base.seed = 99

        with pytest.raises(ValueError) as exc_info:
            compare_runs(metrics_agent, metrics_base)

        assert "Cannot compare runs with different seeds" in str(exc_info.value)
    finally:
        db.close()


def test_markdown_export_and_limitations_content(tmp_path):
    db = SessionLocal()
    try:
        # Run baseline
        base_summary = run_batch(mode="baseline", seed=42, db=db, sleep_between_steps=False)
        base_metrics = compute_run_metrics(base_summary, db=db, evaluate_held_out=False)

        # Run agent
        generate_dataset(seed=42, wipe_db=True)
        agent_summary = run_batch(mode="agent", seed=42, db=db, sleep_between_steps=False, razorpay_client=MockRazorpayClient())
        agent_metrics = compute_run_metrics(agent_summary, db=db, evaluate_held_out=True)

        report = compare_runs(agent_metrics, base_metrics)
        out_file = tmp_path / "results_test.md"
        content = export_results_markdown(report, agent_metrics, output_path=out_file)

        assert out_file.exists()
        assert "Executive Summary & Recovery Lift" in content
        assert "Unit Economics & ROI" in content
        assert "Restraint & Policy Suppression Audit" in content
        assert "Root Cause Classifier Performance" in content

        # Verify Mandatory Honest Limitations Section
        assert "Honest Methodology & Evaluation Limitations" in content
        assert "Synthetic Dataset" in content
        assert "Simulated Customer Response" in content
        assert "Sample Size" in content
        assert "Zero Live Merchant Data" in content
    finally:
        db.close()


def test_eval_api_endpoint():
    client = TestClient(app)
    response = client.get("/api/eval/metrics?seed=42")
    assert response.status_code == 200
    data = response.json()
    assert "comparison_report" in data
    assert "agent_metrics" in data
    assert data["comparison_report"]["net_recovery_rate_lift_pct"] > 0
