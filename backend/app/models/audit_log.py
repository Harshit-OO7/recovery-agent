from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.db import Base


class AuditLog(Base):
    """
    Audit Log entity.
    Enforces Core Design Principle #2 (Every action is logged with its reason)
    and #3 (Restraint is a feature).
    """
    __tablename__ = "audit_logs"

    id = Column(String(50), primary_key=True, index=True)
    failed_payment_id = Column(String(50), ForeignKey("failed_payments.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(50), nullable=False, index=True)  # CLASSIFICATION, POLICY_GATE, DISPATCH, RESTRAINT, SIMULATION
    input_summary = Column(Text, nullable=False)
    decision = Column(String(100), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)

    # Evaluation results of all deterministic policy gates
    policy_gates_evaluated = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    failed_payment = relationship("FailedPayment", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} stage={self.stage} decision={self.decision}>"
