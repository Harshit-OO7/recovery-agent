"""
Pydantic schemas and Enums for the Customer Behavior Simulator.
"""

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field


class SimulationOutcome(str, Enum):
    PAID_IMMEDIATELY = "paid_immediately"
    PAID_LATER = "paid_later"
    IGNORED = "ignored"
    OPTED_OUT = "opted_out"


class SimulationResponse(BaseModel):
    """
    Result of a simulated customer contact interaction.
    """
    outcome: SimulationOutcome
    delay_hours: float = Field(0.0, description="Payment delay in hours if paid_later or paid_immediately")
    effective_pay_probability: float = Field(..., description="Calculated probability of payment after modifiers")
    opt_out_probability: float = Field(..., description="Calculated probability of opting out/unsubscribing")
    modifiers_applied: Dict[str, float] = Field(default_factory=dict, description="Detailed trace of all multiplicative modifiers")
    simulation_seed_used: int = Field(..., description="Deterministic seed derived for this specific transaction & attempt")
    is_simulated: bool = Field(True, description="Explicit badge indicating this outcome is simulated")


class BaselineOutcome(str, Enum):
    SELF_RECOVERED = "self_recovered"
    UNRECOVERED = "unrecovered"


class BaselineResponse(BaseModel):
    """
    Result of the zero-intervention counterfactual baseline.
    """
    outcome: BaselineOutcome
    delay_hours: float = Field(0.0, description="Organic recovery delay in hours if customer self-recovered")
    organic_pay_probability: float = Field(..., description="Natural baseline recovery probability without any agent contact")
    simulation_seed_used: int = Field(..., description="Deterministic seed derived for this baseline calculation")
    is_simulated: bool = Field(True, description="Explicit badge indicating this outcome is simulated")
