from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.enums import PaymentMethod, PaymentStatus, DatasetSplit
from app.schemas.customer import CustomerAgentView


class FailedPaymentBase(BaseModel):
    razorpay_order_id: str
    customer_id: str
    amount_paise: int
    currency: str = "INR"
    method: PaymentMethod
    failure_code: str
    failure_reason: str
    failed_at: datetime
    cart_summary: str
    status: PaymentStatus = PaymentStatus.OPEN
    dataset_split: DatasetSplit = DatasetSplit.TRAIN


class FailedPaymentCreate(FailedPaymentBase):
    id: str


class FailedPaymentRead(FailedPaymentBase):
    id: str
    created_at: datetime
    amount_rupees: float
    customer: Optional[CustomerAgentView] = None

    model_config = ConfigDict(from_attributes=True)
