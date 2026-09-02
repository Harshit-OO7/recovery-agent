from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db import Base
from app.models.enums import PropensityProfile


class Customer(Base):
    """
    Customer entity.
    Tracks customer demographic details, historical payment track record, and risk flag.
    """
    __tablename__ = "customers"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False, unique=True, index=True)
    email = Column(String(120), nullable=False, unique=True, index=True)
    city = Column(String(100), nullable=False)

    # Observable historical metrics (available to the Agent)
    history_total_payments = Column(Integer, default=0, nullable=False)
    history_failed_payments = Column(Integer, default=0, nullable=False)
    history_avg_days_to_pay = Column(Float, default=0.0, nullable=False)
    is_risk_flagged = Column(Boolean, default=False, nullable=False, index=True)

    # PRIVATE GROUND TRUTH (Simulator ONLY - NEVER expose to Agent)
    # See app.models.enums.PropensityProfile docstring for rationale.
    propensity_profile = Column(SQLEnum(PropensityProfile), nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    failed_payments = relationship("FailedPayment", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Customer id={self.id} name={self.name} risk_flagged={self.is_risk_flagged}>"
