"""
Deterministic Policy Engine.

ARCHITECTURAL PRINCIPLE #1 & #3:
- The LLM classifies and drafts. It NEVER decides whether money moves.
- Hard-coded deterministic gates decide if, when, and how a customer is contacted.
- Restraint is a feature: suppression and stopping rules prevent brand damage and wasteful spend.
- NO LLM CALLS IN THIS MODULE.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.llm.classifier import ClassificationCategory, ClassificationResult
from app.models.enums import AttemptOutcome, RecoveryAction, RecoveryChannel
from app.models.customer import Customer
from app.models.failed_payment import FailedPayment
from app.models.recovery_attempt import RecoveryAttempt
from app.schemas.customer import CustomerAgentView


# ==============================================================================
# POLICY CONFIGURATION (Centralized Thresholds for Tuning & Dashboard Visibility)
# ==============================================================================
POLICY_CONFIG: Dict[str, Any] = {
    # G2 Value Floor: Minimum cart value in paise (Rs. 100 = 10,000 paise)
    "COST_OF_CONTACT_THRESHOLD_PAISE": 10000,

    # G3 Max Attempts: Hard cap on total contact attempts
    "MAX_RECOVERY_ATTEMPTS": 2,

    # G4 Cooldown: Minimum rest duration in hours between consecutive attempts
    "COOLDOWN_HOURS": 24.0,

    # G5 Quiet Hours: Outreach prohibited outside 09:00 - 20:00 IST (Indian Standard Time)
    "QUIET_HOURS_START_IST": 20,  # 8:00 PM IST
    "QUIET_HOURS_END_IST": 9,    # 9:00 AM IST

    # G6 Confidence Floor: LLM classification confidence required to proceed autonomously
    "CONFIDENCE_FLOOR": 0.55,

    # G7 Liquidity Delay: Delay window for insufficient funds to align with account reload
    "SALARY_CYCLE_DELAY_HOURS": 48.0,

    # Default delivery channel
    "DEFAULT_CHANNEL": RecoveryChannel.WHATSAPP,
}

IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


class PolicyAction(str, Enum):
    SEND_PAYMENT_LINK = "send_payment_link"
    SEND_REMINDER_NO_LINK = "send_reminder_no_link"
    WAIT = "wait"
    SUPPRESS = "suppress"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class GateStatus(str, Enum):
    PASSED = "passed"
    TRIGGERED = "triggered"
    SKIPPED = "skipped"


class GateEvaluation(BaseModel):
    gate_id: str
    name: str
    status: GateStatus
    reason: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    """
    Deterministic decision outcome returned by the policy engine.
    """
    action: PolicyAction
    channel: RecoveryChannel = RecoveryChannel.WHATSAPP
    delay_seconds: int = Field(0, description="Delay in seconds before dispatch (0 = immediate)")
    reason: str = Field(..., description="Plain-English explanation of why this policy decision was taken")
    gates_evaluated: List[GateEvaluation] = Field(default_factory=list, description="Ordered audit log of all gates evaluated")


def _calculate_seconds_until_next_quiet_window_end(dt: datetime) -> int:
    """
    Computes exact seconds until the next 09:00 IST morning window opens.
    """
    # Convert dt to IST
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_now = dt.astimezone(IST_TIMEZONE)

    # If currently in night window after 20:00 IST -> wait until tomorrow 09:00 IST
    # If early morning before 09:00 IST -> wait until today 09:00 IST
    if ist_now.hour >= POLICY_CONFIG["QUIET_HOURS_START_IST"]:
        target_ist = (ist_now + timedelta(days=1)).replace(
            hour=POLICY_CONFIG["QUIET_HOURS_END_IST"], minute=0, second=0, microsecond=0
        )
    else:
        target_ist = ist_now.replace(
            hour=POLICY_CONFIG["QUIET_HOURS_END_IST"], minute=0, second=0, microsecond=0
        )

    delta = (target_ist - ist_now).total_seconds()
    return max(0, int(delta))


def decide(
    payment: FailedPayment,
    customer: Union[Customer, CustomerAgentView],
    classification: ClassificationResult,
    attempt_history: Optional[List[RecoveryAttempt]] = None,
    current_time: Optional[datetime] = None,
) -> Decision:
    """
    Evaluates hard policy gates sequentially to determine the operational recovery action.

    G1: do_not_contact       -> Risk-flagged or opted-out customer => suppress
    G2: value_floor          -> Amount < Rs. 100 => suppress (cost-of-contact gate)
    G3: max_attempts         -> Prior attempts >= 2 => suppress
    G4: cooldown             -> Last attempt < 24h ago => wait
    G5: quiet_hours          -> Outside 09:00-20:00 IST => wait until 09:00 IST
    G6: confidence_floor     -> Classification confidence < 0.55 => escalate_to_human
    G7: category_route       -> Operational route per intent category

    Returns:
        Decision object with action, channel, delay_seconds, reason, and gate audit trail.
    """
    if attempt_history is None:
        attempt_history = []
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    elif current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    gates: List[GateEvaluation] = []
    default_channel = POLICY_CONFIG.get("DEFAULT_CHANNEL", RecoveryChannel.WHATSAPP)

    # --------------------------------------------------------------------------
    # G1: Do Not Contact (Risk Flagged or Opted Out)
    # --------------------------------------------------------------------------
    is_risk = getattr(customer, "is_risk_flagged", False)
    has_opted_out = any(
        att.outcome == AttemptOutcome.OPTED_OUT for att in attempt_history
    )

    if is_risk or has_opted_out:
        why = "Customer account is marked as high-risk/dispute-prone." if is_risk else "Customer previously opted out of recovery communications."
        gates.append(GateEvaluation(
            gate_id="G1",
            name="do_not_contact",
            status=GateStatus.TRIGGERED,
            reason=why,
            metadata={"is_risk_flagged": is_risk, "has_opted_out": has_opted_out}
        ))
        return Decision(
            action=PolicyAction.SUPPRESS,
            channel=default_channel,
            delay_seconds=0,
            reason=f"Gate G1 (do_not_contact) triggered: {why} Outreach permanently suppressed.",
            gates_evaluated=gates
        )
    else:
        gates.append(GateEvaluation(
            gate_id="G1",
            name="do_not_contact",
            status=GateStatus.PASSED,
            reason="Customer is not risk-flagged and has not opted out."
        ))

    # --------------------------------------------------------------------------
    # G2: Value Floor (Cost-of-Contact Gate)
    # --------------------------------------------------------------------------
    threshold_paise = POLICY_CONFIG["COST_OF_CONTACT_THRESHOLD_PAISE"]
    if payment.amount_paise < threshold_paise:
        amount_inr = payment.amount_paise / 100.0
        threshold_inr = threshold_paise / 100.0
        why = f"Cart amount (Rs. {amount_inr:.2f}) is below the cost-of-contact threshold (Rs. {threshold_inr:.2f})."
        gates.append(GateEvaluation(
            gate_id="G2",
            name="value_floor",
            status=GateStatus.TRIGGERED,
            reason=why,
            metadata={"amount_paise": payment.amount_paise, "threshold_paise": threshold_paise}
        ))
        return Decision(
            action=PolicyAction.SUPPRESS,
            channel=default_channel,
            delay_seconds=0,
            reason=f"Gate G2 (value_floor) triggered: {why} Contact costs exceed recovery value.",
            gates_evaluated=gates
        )
    else:
        gates.append(GateEvaluation(
            gate_id="G2",
            name="value_floor",
            status=GateStatus.PASSED,
            reason=f"Cart value (Rs. {payment.amount_paise/100:.2f}) exceeds economic threshold (Rs. {threshold_paise/100:.2f})."
        ))

    # --------------------------------------------------------------------------
    # G3: Max Attempts (Fatigue & Anti-Spam Gate)
    # --------------------------------------------------------------------------
    max_attempts = POLICY_CONFIG["MAX_RECOVERY_ATTEMPTS"]
    prior_attempt_count = len(attempt_history)
    if prior_attempt_count >= max_attempts:
        why = f"Prior outreach attempts ({prior_attempt_count}) reached the maximum limit ({max_attempts})."
        gates.append(GateEvaluation(
            gate_id="G3",
            name="max_attempts",
            status=GateStatus.TRIGGERED,
            reason=why,
            metadata={"prior_attempts": prior_attempt_count, "max_allowed": max_attempts}
        ))
        return Decision(
            action=PolicyAction.SUPPRESS,
            channel=default_channel,
            delay_seconds=0,
            reason=f"Gate G3 (max_attempts) triggered: {why} Suppressing further contact to prevent spam.",
            gates_evaluated=gates
        )
    else:
        gates.append(GateEvaluation(
            gate_id="G3",
            name="max_attempts",
            status=GateStatus.PASSED,
            reason=f"Attempt count ({prior_attempt_count}) is below limit ({max_attempts})."
        ))

    # --------------------------------------------------------------------------
    # G4: Cooldown Interval (Rest Period Between Attempts)
    # --------------------------------------------------------------------------
    if prior_attempt_count > 0:
        last_attempt = max(attempt_history, key=lambda a: a.sent_at)
        last_sent = last_attempt.sent_at
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        
        elapsed_seconds = (current_time - last_sent).total_seconds()
        required_seconds = POLICY_CONFIG["COOLDOWN_HOURS"] * 3600.0

        if elapsed_seconds < required_seconds:
            remaining_seconds = int(required_seconds - elapsed_seconds)
            why = f"Last attempt was sent {elapsed_seconds/3600:.1f}h ago. Cooldown requires {POLICY_CONFIG['COOLDOWN_HOURS']}h."
            gates.append(GateEvaluation(
                gate_id="G4",
                name="cooldown",
                status=GateStatus.TRIGGERED,
                reason=why,
                metadata={"elapsed_hours": elapsed_seconds/3600.0, "remaining_seconds": remaining_seconds}
            ))
            return Decision(
                action=PolicyAction.WAIT,
                channel=default_channel,
                delay_seconds=remaining_seconds,
                reason=f"Gate G4 (cooldown) triggered: {why} Postponing for {remaining_seconds//3600}h {(remaining_seconds%3600)//60}m.",
                gates_evaluated=gates
            )

    gates.append(GateEvaluation(
        gate_id="G4",
        name="cooldown",
        status=GateStatus.PASSED,
        reason="Cooldown duration satisfied."
    ))

    # --------------------------------------------------------------------------
    # G5: Quiet Hours (09:00 - 20:00 IST Window)
    # --------------------------------------------------------------------------
    ist_now = current_time.astimezone(IST_TIMEZONE)
    is_quiet_hour = (
        ist_now.hour >= POLICY_CONFIG["QUIET_HOURS_START_IST"]
        or ist_now.hour < POLICY_CONFIG["QUIET_HOURS_END_IST"]
    )

    if is_quiet_hour:
        delay_sec = _calculate_seconds_until_next_quiet_window_end(current_time)
        why = f"Current time is {ist_now.strftime('%H:%M')} IST, which is outside the active window (09:00 - 20:00 IST)."
        gates.append(GateEvaluation(
            gate_id="G5",
            name="quiet_hours",
            status=GateStatus.TRIGGERED,
            reason=why,
            metadata={"current_ist": ist_now.strftime("%H:%M:%S"), "delay_seconds": delay_sec}
        ))
        return Decision(
            action=PolicyAction.WAIT,
            channel=default_channel,
            delay_seconds=delay_sec,
            reason=f"Gate G5 (quiet_hours) triggered: {why} Postponing until 09:00 IST.",
            gates_evaluated=gates
        )
    else:
        gates.append(GateEvaluation(
            gate_id="G5",
            name="quiet_hours",
            status=GateStatus.PASSED,
            reason=f"Current time ({ist_now.strftime('%H:%M')} IST) is within active customer contact hours."
        ))

    # --------------------------------------------------------------------------
    # G6: Confidence Floor (Human Escalation Gate)
    # --------------------------------------------------------------------------
    conf_floor = POLICY_CONFIG["CONFIDENCE_FLOOR"]
    if classification.confidence < conf_floor:
        why = f"Classifier confidence ({classification.confidence:.2f}) is below confidence floor ({conf_floor:.2f})."
        gates.append(GateEvaluation(
            gate_id="G6",
            name="confidence_floor",
            status=GateStatus.TRIGGERED,
            reason=why,
            metadata={"confidence": classification.confidence, "threshold": conf_floor}
        ))
        return Decision(
            action=PolicyAction.ESCALATE_TO_HUMAN,
            channel=default_channel,
            delay_seconds=0,
            reason=f"Gate G6 (confidence_floor) triggered: {why} Escalating to merchant support queue.",
            gates_evaluated=gates
        )
    else:
        gates.append(GateEvaluation(
            gate_id="G6",
            name="confidence_floor",
            status=GateStatus.PASSED,
            reason=f"Classifier confidence ({classification.confidence:.2f}) meets autonomous operating threshold."
        ))

    # --------------------------------------------------------------------------
    # G7: Category Route (Action Mapping by Root Cause)
    # --------------------------------------------------------------------------
    cat = classification.category

    if cat == ClassificationCategory.TECHNICAL_FAILURE:
        action = PolicyAction.SEND_PAYMENT_LINK
        delay_sec = 0
        why = "Technical glitch at gateway: Immediate 1-click retry payment link."

    elif cat == ClassificationCategory.AUTHENTICATION_DROP:
        action = PolicyAction.SEND_PAYMENT_LINK
        delay_sec = 0
        why = "Authentication/OTP timeout: Immediate frictionless payment retry link."

    elif cat == ClassificationCategory.INSUFFICIENT_FUNDS:
        action = PolicyAction.SEND_PAYMENT_LINK
        delay_sec = int(POLICY_CONFIG["SALARY_CYCLE_DELAY_HOURS"] * 3600)
        why = f"Insufficient account funds: Delayed payment link (+{POLICY_CONFIG['SALARY_CYCLE_DELAY_HOURS']}h) to accommodate liquidity reload."

    elif cat == ClassificationCategory.INTENT_HESITATION:
        if prior_attempt_count == 0:
            action = PolicyAction.SEND_REMINDER_NO_LINK
            delay_sec = 0
            why = "Checkout drop-off (Attempt #1): Gentle conversational reminder without immediate payment pressure."
        else:
            action = PolicyAction.SEND_PAYMENT_LINK
            delay_sec = 0
            why = "Checkout drop-off (Attempt #2): Follow-up recovery link with discount/incentive."

    else:  # DO_NOT_PURSUE
        action = PolicyAction.SUPPRESS
        delay_sec = 0
        why = "Classified as do_not_pursue: Suppressing outreach."

    gates.append(GateEvaluation(
        gate_id="G7",
        name="category_route",
        status=GateStatus.TRIGGERED if action != PolicyAction.SUPPRESS else GateStatus.TRIGGERED,
        reason=why,
        metadata={"category": cat.value, "assigned_action": action.value}
    ))

    return Decision(
        action=action,
        channel=default_channel,
        delay_seconds=delay_sec,
        reason=f"Gate G7 (category_route): {why}",
        gates_evaluated=gates
    )
