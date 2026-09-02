"""
Customer Behavior Simulator Engine.

WHY THIS EXISTS:
In a simulated/hackathon environment, real customer outreach cannot be dispatched to living users.
This module simulates how a customer responds to post-checkout recovery attempts based on:
1. Ground-truth customer propensity (hidden from the recovery agent)
2. Contextual fit between the recovery action and the root failure cause
3. Outreach frequency decay & annoyance thresholds
4. Cart size and timing dynamics

All calculations are strictly deterministic and reproducible when given identical seeds.
"""

import hashlib
import random
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Union

from app.config import settings
from app.models.enums import (
    PropensityProfile,
    RecoveryAction,
    PaymentMethod,
)
from app.models.customer import Customer
from app.models.failed_payment import FailedPayment
from app.schemas.customer import CustomerSimulatorView
from app.simulator.models import (
    SimulationOutcome,
    SimulationResponse,
    BaselineOutcome,
    BaselineResponse,
)


# ==============================================================================
# BASE RECOVERY PROBABILITIES BY PROPENSITY PROFILE
# ==============================================================================
BASE_PROPENSITY_PROBABILITIES: Dict[PropensityProfile, float] = {
    PropensityProfile.RELIABLE: 0.75,     # High intent, wants the item
    PropensityProfile.DISTRACTED: 0.55,   # Moderate-high intent, forgot/interrupted
    PropensityProfile.HESITANT: 0.35,     # Needs price reassurance or incentive
    PropensityProfile.BROKE: 0.15,        # Severe liquidity constraint
    PropensityProfile.GHOST: 0.03,        # Fake/accidental checkout, nearly zero intent
}

# ==============================================================================
# NO-INTERVENTION (ORGANIC) BASELINE RECOVERY PROBABILITIES
# (What happens if no agent contacts the customer at all)
# ==============================================================================
ORGANIC_BASELINE_PROBABILITIES: Dict[PropensityProfile, float] = {
    PropensityProfile.RELIABLE: 0.18,     # Returns spontaneously to retry
    PropensityProfile.DISTRACTED: 0.10,   # Occasionally remembers cart
    PropensityProfile.HESITANT: 0.04,     # Rarely overcomes hesitation alone
    PropensityProfile.BROKE: 0.02,        # Unlikely to self-recover quickly
    PropensityProfile.GHOST: 0.00,        # Never returns
}


def _derive_seed(master_seed: int, payment_id: str, attempt_number: int = 1, prefix: str = "contact") -> int:
    """
    Derives a stable, deterministic integer seed from (master_seed, payment_id, attempt_number, prefix).
    Guarantees that a payment's outcome is mathematically independent of the order in which
    transactions are processed in batch runs.
    """
    raw_str = f"{master_seed}:{payment_id}:{attempt_number}:{prefix}"
    hash_hex = hashlib.md5(raw_str.encode("utf-8")).hexdigest()
    return int(hash_hex[:8], 16)


def _evaluate_action_match_modifier(failure_code: str, failure_reason: str, action: str) -> Tuple[float, str]:
    """
    Evaluates whether the chosen recovery action matches the root payment failure cause.

    Table of Action Matching Logic:
    - Gateway Timeout / Network Glitch / OTP Expiry -> direct payment link / 1-click retry: BOOST (1.40x)
    - Insufficient Funds -> payment reminder / delayed link: BOOST (1.30x)
    - Insufficient Funds -> spamming discount immediately: MISMATCH PENALTY (0.85x)
    - Checkout Abandoned -> discount nudge / smart incentive: BOOST (1.35x)
    - Generic matching action: (1.05x)
    """
    action_str = action.value if hasattr(action, "value") else str(action).lower()
    code_upper = str(failure_code).upper()
    reason_lower = str(failure_reason).lower()

    # 1. Technical / Transient failure (Gateway timeout or OTP issue)
    if "GATEWAY_ERROR" in code_upper or "otp" in reason_lower or "timeout" in reason_lower:
        if "link" in action_str or "retry" in action_str or action_str == RecoveryAction.PAYMENT_LINK.value:
            return 1.40, "Action matches transient failure: instant 1-click retry link provided (+40%)"
        else:
            return 0.80, "Action mismatch: non-direct action for a transient technical glitch (-20%)"

    # 2. Insufficient liquidity / balance
    elif "insufficient funds" in reason_lower or "funds" in reason_lower:
        if "reminder" in action_str or action_str == RecoveryAction.PAYMENT_REMINDER.value:
            return 1.30, "Action matches liquidity issue: considerate reminder giving breathing room (+30%)"
        elif "discount" in action_str or action_str == RecoveryAction.DISCOUNT_NUDGE.value:
            return 0.85, "Action mismatch: discount nudge does not resolve immediate bank liquidity shortfall (-15%)"
        else:
            return 1.00, "Neutral action match for liquidity constraint (1.00x)"

    # 3. Intentional Checkout Abandonment / Hesitation
    elif "ABANDONED" in code_upper or "abandoned" in reason_lower:
        if "discount" in action_str or action_str == RecoveryAction.DISCOUNT_NUDGE.value:
            return 1.35, "Action matches checkout drop-off: price incentive/discount nudge (+35%)"
        elif "link" in action_str or action_str == RecoveryAction.PAYMENT_LINK.value:
            return 1.20, "Action matches checkout drop-off: direct resumption link (+20%)"
        else:
            return 0.90, "Weak action match for abandoned cart (-10%)"

    # 4. Default / Card declined
    else:
        if "link" in action_str or "reminder" in action_str:
            return 1.05, "Standard recovery outreach (+5%)"
        return 0.95, "Minor action mismatch (-5%)"


def simulate_customer_response(
    customer: Union[Customer, CustomerSimulatorView],
    payment: FailedPayment,
    action: Union[str, RecoveryAction],
    attempt_number: int = 1,
    contact_time: Optional[datetime] = None,
    master_seed: int = settings.RANDOM_SEED,
) -> SimulationResponse:
    """
    Simulates a customer's probabilistic response to a recovery contact attempt.

    Returns:
        SimulationResponse with outcome in [PAID_IMMEDIATELY, PAID_LATER, IGNORED, OPTED_OUT]
    """
    propensity = (
        customer.propensity_profile
        if hasattr(customer, "propensity_profile")
        else PropensityProfile.DISTRACTED
    )
    base_prob = BASE_PROPENSITY_PROBABILITIES.get(propensity, 0.40)

    # Initialize seed-isolated RNG
    sim_seed = _derive_seed(master_seed, payment.id, attempt_number, prefix="contact")
    rng = random.Random(sim_seed)

    modifiers: Dict[str, float] = {}

    # 1. Action vs Failure Cause Match Modifier
    action_mod, action_reason = _evaluate_action_match_modifier(
        payment.failure_code, payment.failure_reason, action
    )
    modifiers[f"action_match: {action_reason}"] = action_mod

    # 2. Attempt Decay Modifier
    if attempt_number == 1:
        attempt_mod = 1.00
        modifiers["attempt_1: fresh contact context"] = attempt_mod
    elif attempt_number == 2:
        attempt_mod = 0.65
        modifiers["attempt_2: diminishing returns decay"] = attempt_mod
    else:  # attempt >= 3
        attempt_mod = 0.35
        modifiers["attempt_3_plus: heavy fatigue decay"] = attempt_mod

    # 3. Cart Size / High Amount Decay Modifier
    # High-ticket items (> Rs 10,000 / 1M paise) carry more buyer friction
    amount_rupees = payment.amount_paise / 100.0
    if amount_rupees >= 25000.0:
        amount_mod = 0.75
        modifiers["high_ticket_25k_plus: high buyer deliberation friction"] = amount_mod
    elif amount_rupees >= 10000.0:
        amount_mod = 0.85
        modifiers["high_ticket_10k_plus: moderate deliberation friction"] = amount_mod
    else:
        amount_mod = 1.00

    # 4. Antisocial Hour Modifier (Contact between 22:00 and 07:00 IST / local time)
    if contact_time is None:
        contact_time = datetime.now(timezone.utc)
    hour = contact_time.hour
    is_antisocial = hour >= 22 or hour < 7
    if is_antisocial:
        timing_mod = 0.70
        modifiers["antisocial_hour: night contact annoyance penalty"] = timing_mod
    else:
        timing_mod = 1.00

    # Compute Total Multiplicative Pay Probability
    total_mod = action_mod * attempt_mod * amount_mod * timing_mod
    effective_pay_prob = base_prob * total_mod
    # Clamp to realistic bounds [0.01, 0.95]
    effective_pay_prob = max(0.01, min(0.95, effective_pay_prob))

    # Opt-Out / Unsubscribe Probability Dynamics
    if attempt_number == 1:
        base_opt_out = 0.015
    elif attempt_number == 2:
        base_opt_out = 0.060
    else:
        base_opt_out = 0.250

    if is_antisocial:
        base_opt_out *= 1.5

    opt_out_prob = min(0.60, base_opt_out)

    # Roll probabilistic outcome using the isolated RNG
    pay_roll = rng.random()

    if pay_roll < effective_pay_prob:
        # Customer decides to pay!
        # Determine whether they pay immediately (within < 1 hour) or later
        # Reliable & Distracted on direct links pay immediately more often (~65%)
        immediate_chance = 0.65 if propensity in [PropensityProfile.RELIABLE, PropensityProfile.DISTRACTED] else 0.40
        if rng.random() < immediate_chance:
            outcome = SimulationOutcome.PAID_IMMEDIATELY
            delay_hours = round(rng.uniform(0.05, 0.8), 2)
        else:
            outcome = SimulationOutcome.PAID_LATER
            # Draw delay based on customer history avg days to pay
            avg_days = getattr(customer, "history_avg_days_to_pay", 1.0) or 1.0
            delay_days = rng.uniform(0.4, 1.4) * max(0.2, avg_days)
            delay_hours = round(delay_days * 24.0, 1)

    else:
        # Customer did not pay on this attempt. Roll for opt-out vs ignored
        opt_out_roll = rng.random()
        if opt_out_roll < opt_out_prob:
            outcome = SimulationOutcome.OPTED_OUT
        else:
            outcome = SimulationOutcome.IGNORED
        delay_hours = 0.0

    return SimulationResponse(
        outcome=outcome,
        delay_hours=delay_hours,
        effective_pay_probability=round(effective_pay_prob, 4),
        opt_out_probability=round(opt_out_prob, 4),
        modifiers_applied=modifiers,
        simulation_seed_used=sim_seed,
        is_simulated=True,
    )


def simulate_no_intervention(
    customer: Union[Customer, CustomerSimulatorView],
    payment: FailedPayment,
    master_seed: int = settings.RANDOM_SEED,
) -> BaselineResponse:
    """
    Simulates the zero-intervention counterfactual baseline.
    Represents what happens to this specific failed payment if NO agent takes any action.
    """
    propensity = (
        customer.propensity_profile
        if hasattr(customer, "propensity_profile")
        else PropensityProfile.DISTRACTED
    )
    organic_prob = ORGANIC_BASELINE_PROBABILITIES.get(propensity, 0.05)

    # Seed derived with identical master seed to ensure fair counterfactual comparison
    sim_seed = _derive_seed(master_seed, payment.id, attempt_number=0, prefix="no_intervention")
    rng = random.Random(sim_seed)

    roll = rng.random()
    if roll < organic_prob:
        outcome = BaselineOutcome.SELF_RECOVERED
        avg_days = getattr(customer, "history_avg_days_to_pay", 1.0) or 1.0
        delay_days = rng.uniform(0.8, 2.5) * max(0.5, avg_days)
        delay_hours = round(delay_days * 24.0, 1)
    else:
        outcome = BaselineOutcome.UNRECOVERED
        delay_hours = 0.0

    return BaselineResponse(
        outcome=outcome,
        delay_hours=delay_hours,
        organic_pay_probability=round(organic_prob, 4),
        simulation_seed_used=sim_seed,
        is_simulated=True,
    )
