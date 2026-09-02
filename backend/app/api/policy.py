"""
Policy Configuration and What-If Simulation API Endpoints.
"""

from copy import deepcopy
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm.classifier import classify_payment_failure
from app.models.failed_payment import FailedPayment
from app.policy.policy import (
    POLICY_CONFIG,
    PolicyAction,
    decide,
)

logger = logging.getLogger("app.api.policy")
router = APIRouter(prefix="/api/policy", tags=["Deterministic Policy Engine & What-If Simulation"])


class GateDefinition(BaseModel):
    gate_id: str
    name: str
    description: str
    default_threshold: Any


class PolicyConfigResponse(BaseModel):
    policy_config: Dict[str, Any]
    gate_definitions: List[GateDefinition]


class SimulatePolicyRequest(BaseModel):
    cost_of_contact_threshold_rupees: Optional[float] = Field(None, ge=0.0, le=5000.0, description="Override cost floor in Rupees (default Rs 100)")
    max_recovery_attempts: Optional[int] = Field(None, ge=1, le=5, description="Override max contact attempts (default 2)")
    confidence_floor: Optional[float] = Field(None, ge=0.0, le=1.0, description="Override classifier confidence floor (default 0.55)")
    cooldown_hours: Optional[float] = Field(None, ge=1.0, le=72.0, description="Override cooldown hours (default 24h)")


class SimulatedSuppressionGate(BaseModel):
    gate_id: str
    gate_name: str
    count: int
    value_rupees: float
    percentage_of_batch: float


class SimulatePolicyResponse(BaseModel):
    total_evaluated: int
    total_cohort_value_rupees: float
    simulated_suppressed_count: int
    simulated_suppressed_value_rupees: float
    simulated_suppression_rate_pct: float
    simulated_eligible_count: int
    simulated_eligible_value_rupees: float
    suppression_breakdown: List[SimulatedSuppressionGate]
    action_distribution: Dict[str, int]
    parameters_applied: Dict[str, Any]
    notes: str


GATE_DEFINITIONS = [
    GateDefinition(
        gate_id="G1",
        name="do_not_contact",
        description="Permanently suppresses outreach if customer is marked high-risk or previously opted out.",
        default_threshold="is_risk_flagged=True or opted_out=True",
    ),
    GateDefinition(
        gate_id="G2",
        name="value_floor",
        description="Suppresses outreach for micro-amounts where cost of contact exceeds expected recovery.",
        default_threshold=f"Rs. {POLICY_CONFIG['COST_OF_CONTACT_THRESHOLD_PAISE']/100:.2f}",
    ),
    GateDefinition(
        gate_id="G3",
        name="max_attempts",
        description="Hard stop to prevent customer fatigue and brand spam.",
        default_threshold=f"{POLICY_CONFIG['MAX_RECOVERY_ATTEMPTS']} attempts max",
    ),
    GateDefinition(
        gate_id="G4",
        name="cooldown",
        description="Minimum mandatory rest duration between consecutive messages.",
        default_threshold=f"{POLICY_CONFIG['COOLDOWN_HOURS']} hours",
    ),
    GateDefinition(
        gate_id="G5",
        name="quiet_hours",
        description="Restricts outreach to respectable local daytime hours (09:00-20:00 IST).",
        default_threshold="09:00 - 20:00 IST",
    ),
    GateDefinition(
        gate_id="G6",
        name="confidence_floor",
        description="Escalates uncertain classifications to human support queue.",
        default_threshold=f"{POLICY_CONFIG['CONFIDENCE_FLOOR']*100:.0f}% confidence",
    ),
    GateDefinition(
        gate_id="G7",
        name="category_route",
        description="Routes surviving intent categories to frictionless 1-click links or conversational nudges.",
        default_threshold="5 intent category routes",
    ),
]


@router.get("", response_model=PolicyConfigResponse)
def get_live_policy_config():
    """
    Returns live POLICY_CONFIG thresholds and sequential gate definitions for the frontend UI.
    """
    return PolicyConfigResponse(
        policy_config=POLICY_CONFIG,
        gate_definitions=GATE_DEFINITIONS,
    )


@router.post("/simulate", response_model=SimulatePolicyResponse)
def simulate_what_if_policy(
    req: SimulatePolicyRequest,
    db: Session = Depends(get_db),
):
    """
    Re-runs deterministic policy evaluation over current batch with custom overridden thresholds,
    WITHOUT re-calling the LLM (uses cached intent classifications).
    Powers the interactive what-if slider in the merchant UI.
    """
    payments = db.query(FailedPayment).all()
    if not payments:
        raise HTTPException(status_code=400, detail="No payment dataset loaded to simulate against.")

    # Override config temporarily
    custom_config = deepcopy(POLICY_CONFIG)
    if req.cost_of_contact_threshold_rupees is not None:
        custom_config["COST_OF_CONTACT_THRESHOLD_PAISE"] = int(req.cost_of_contact_threshold_rupees * 100)
    if req.max_recovery_attempts is not None:
        custom_config["MAX_RECOVERY_ATTEMPTS"] = req.max_recovery_attempts
    if req.confidence_floor is not None:
        custom_config["CONFIDENCE_FLOOR"] = req.confidence_floor
    if req.cooldown_hours is not None:
        custom_config["COOLDOWN_HOURS"] = req.cooldown_hours

    # Temporarily monkeypatch policy config for this simulation run
    import app.policy.policy as pol_module
    old_config = pol_module.POLICY_CONFIG
    pol_module.POLICY_CONFIG = custom_config

    total_val = sum(p.amount_rupees for p in payments)
    suppressed_counts = {"G1": (0, 0.0), "G2": (0, 0.0), "G3": (0, 0.0)}
    action_counts: Dict[str, int] = {}
    eligible_count = 0
    eligible_val = 0.0

    try:
        now = datetime(2026, 9, 2, 14, 0, 0, tzinfo=timezone.utc)  # Active daytime window
        for p in payments:
            classification = classify_payment_failure(payment=p, customer=p.customer)
            attempts = p.recovery_attempts
            decision = decide(
                payment=p,
                customer=p.customer,
                classification=classification,
                attempt_history=attempts,
                current_time=now,
            )

            act_str = decision.action.value
            action_counts[act_str] = action_counts.get(act_str, 0) + 1

            if decision.action == PolicyAction.SUPPRESS:
                # Identify which gate triggered suppression
                trig = next((g for g in decision.gates_evaluated if g.status.value == "triggered"), None)
                gid = trig.gate_id if trig else "G1"
                if gid in suppressed_counts:
                    c, v = suppressed_counts[gid]
                    suppressed_counts[gid] = (c + 1, v + p.amount_rupees)
            else:
                eligible_count += 1
                eligible_val += p.amount_rupees

    finally:
        pol_module.POLICY_CONFIG = old_config

    gate_names = {
        "G1": "do_not_contact (Risk Flagged / Opted Out)",
        "G2": f"value_floor (< Rs. {custom_config['COST_OF_CONTACT_THRESHOLD_PAISE']/100:.2f})",
        "G3": f"max_attempts (>= {custom_config['MAX_RECOVERY_ATTEMPTS']} attempts)",
    }

    supp_breakdown = [
        SimulatedSuppressionGate(
            gate_id=gid,
            gate_name=gate_names[gid],
            count=cnt,
            value_rupees=round(val, 2),
            percentage_of_batch=round(cnt / len(payments) * 100.0, 1),
        )
        for gid, (cnt, val) in suppressed_counts.items()
    ]

    total_supp_count = sum(g.count for g in supp_breakdown)
    total_supp_val = sum(g.value_rupees for g in supp_breakdown)

    return SimulatePolicyResponse(
        total_evaluated=len(payments),
        total_cohort_value_rupees=round(total_val, 2),
        simulated_suppressed_count=total_supp_count,
        simulated_suppressed_value_rupees=round(total_supp_val, 2),
        simulated_suppression_rate_pct=round(total_supp_count / len(payments) * 100.0, 1),
        simulated_eligible_count=eligible_count,
        simulated_eligible_value_rupees=round(eligible_val, 2),
        suppression_breakdown=supp_breakdown,
        action_distribution=action_counts,
        parameters_applied={
            "cost_of_contact_threshold_rupees": custom_config["COST_OF_CONTACT_THRESHOLD_PAISE"] / 100.0,
            "max_recovery_attempts": custom_config["MAX_RECOVERY_ATTEMPTS"],
            "confidence_floor": custom_config["CONFIDENCE_FLOOR"],
            "cooldown_hours": custom_config["COOLDOWN_HOURS"],
        },
        notes="Simulated instantaneously without re-calling LLM APIs.",
    )
