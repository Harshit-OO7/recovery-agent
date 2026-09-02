from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class AuditLogBase(BaseModel):
    failed_payment_id: str
    stage: str
    input_summary: str
    decision: str
    reason: str
    confidence: Optional[float] = None
    policy_gates_evaluated: Dict[str, Any] = {}


class AuditLogCreate(AuditLogBase):
    id: str


class AuditLogRead(AuditLogBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
