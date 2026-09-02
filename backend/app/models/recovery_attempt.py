from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base
from app.models.enums import RecoveryChannel, AttemptOutcome


class RecoveryAttempt(Base):
    """
    Recovery Attempt entity.
    Tracks each outreach action taken by the system towards recovering a failed payment.
    """
    __tablename__ = "recovery_attempts"

    id = Column(String(50), primary_key=True, index=True)
    failed_payment_id = Column(String(50), ForeignKey("failed_payments.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)  # 1, 2, 3...
    channel = Column(SQLEnum(RecoveryChannel), nullable=False)
    action_taken = Column(String(100), nullable=False)

    # Razorpay Payment Link metadata (Test Mode)
    payment_link_id = Column(String(100), nullable=True, index=True)
    payment_link_url = Column(String(255), nullable=True)

    sent_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    outcome = Column(SQLEnum(AttemptOutcome), default=AttemptOutcome.PENDING, nullable=False, index=True)
    outcome_at = Column(DateTime, nullable=True)

    # Relationships
    failed_payment = relationship("FailedPayment", back_populates="recovery_attempts")

    def __repr__(self) -> str:
        return f"<RecoveryAttempt id={self.id} payment_id={self.failed_payment_id} attempt={self.attempt_number} outcome={self.outcome}>"
