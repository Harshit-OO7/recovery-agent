from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base
from app.models.enums import PaymentMethod, PaymentStatus, DatasetSplit


class FailedPayment(Base):
    """
    Failed / Abandoned Payment entity.
    Represents an individual checkout transaction that failed or was dropped post-session.
    """
    __tablename__ = "failed_payments"

    id = Column(String(50), primary_key=True, index=True)
    razorpay_order_id = Column(String(100), nullable=False, unique=True, index=True)
    customer_id = Column(String(50), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)

    amount_paise = Column(Integer, nullable=False)  # Stored in lowest currency denomination (paise)
    currency = Column(String(10), default="INR", nullable=False)
    method = Column(SQLEnum(PaymentMethod), nullable=False)

    # Razorpay-style error classification
    failure_code = Column(String(100), nullable=False, index=True)
    failure_reason = Column(String(255), nullable=False)

    failed_at = Column(DateTime, nullable=False, index=True)
    cart_summary = Column(String(255), nullable=False)

    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.OPEN, nullable=False, index=True)
    dataset_split = Column(SQLEnum(DatasetSplit), default=DatasetSplit.TRAIN, nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="failed_payments")
    recovery_attempts = relationship("RecoveryAttempt", back_populates="failed_payment", cascade="all, delete-orphan", order_by="RecoveryAttempt.attempt_number")
    audit_logs = relationship("AuditLog", back_populates="failed_payment", cascade="all, delete-orphan", order_by="AuditLog.created_at")

    @property
    def amount_rupees(self) -> float:
        return self.amount_paise / 100.0

    def __repr__(self) -> str:
        return f"<FailedPayment id={self.id} order={self.razorpay_order_id} amount_inr={self.amount_rupees} status={self.status}>"
