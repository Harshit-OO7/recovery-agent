from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import PropensityProfile


class CustomerBase(BaseModel):
    name: str
    phone: str
    email: str
    city: str
    history_total_payments: int = 0
    history_failed_payments: int = 0
    history_avg_days_to_pay: float = 0.0
    is_risk_flagged: bool = False


class CustomerCreate(CustomerBase):
    id: str
    propensity_profile: PropensityProfile


class CustomerAgentView(CustomerBase):
    """
    Agent-facing view of customer data.
    IMPORTANT: `propensity_profile` is intentionally NOT present in this schema.
    The recovery agent code must only import and work with CustomerAgentView to guarantee
    zero ground-truth leakage.
    """
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerSimulatorView(CustomerBase):
    """
    Simulator-facing view of customer data.
    Used ONLY by the customer behavior simulator engine.
    """
    id: str
    propensity_profile: PropensityProfile
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
