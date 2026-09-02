"""
Evaluation API Endpoints.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.eval.metrics import (
    ComparisonReport,
    RunMetrics,
    run_evaluation_pipeline,
)

logger = logging.getLogger("app.api.eval")
router = APIRouter(prefix="/api/eval", tags=["Evaluation & Benchmark Metrics"])

_LATEST_REPORT: Optional[ComparisonReport] = None
_LATEST_METRICS: Optional[RunMetrics] = None


@router.get("/metrics")
def get_evaluation_metrics(seed: int = Query(42, description="Random seed used for evaluation")):
    """
    Returns the latest evaluation report comparing agentic recovery against the zero-intervention baseline.
    """
    global _LATEST_REPORT, _LATEST_METRICS
    if _LATEST_REPORT is None:
        try:
            report, metrics = run_evaluation_pipeline(seed=seed, export_path="../docs/results.md")
            _LATEST_REPORT = report
            _LATEST_METRICS = metrics
        except Exception as e:
            logger.error(f"Failed to generate evaluation report: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Evaluation pipeline failed: {e}")

    return {
        "comparison_report": _LATEST_REPORT.model_dump(),
        "agent_metrics": _LATEST_METRICS.model_dump(),
    }


@router.post("/refresh")
def refresh_evaluation_report(seed: int = Query(42)):
    """
    Forces a fresh re-run of the evaluation pipeline and overwrites docs/results.md.
    """
    global _LATEST_REPORT, _LATEST_METRICS
    report, metrics = run_evaluation_pipeline(seed=seed, export_path="../docs/results.md")
    _LATEST_REPORT = report
    _LATEST_METRICS = metrics
    return {
        "message": "Evaluation report refreshed and exported successfully.",
        "net_recovery_rate_lift_pct": report.net_recovery_rate_lift_pct,
        "net_revenue_lift_rupees": report.net_revenue_lift_rupees,
    }
