from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import RecoveryChannel, AttemptOutcome


class RecoveryAttemptBase(BaseModel):
    failed_payment_id: str
    attempt_number: int
    channel: RecoveryChannel
    action_taken: str
    payment_link_id: Optional[str] = None
    payment_link_url: Optional[str] = None
    outcome: AttemptOutcome = AttemptOutcome.PENDING
    outcome_at: Optional[datetime] = None


class RecoveryAttemptCreate(RecoveryAttemptBase):
    id: str
    sent_at: Optional[datetime] = None


class RecoveryAttemptRead(RecoveryAttemptBase):
    id: str
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)
