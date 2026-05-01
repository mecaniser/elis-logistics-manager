"""
Repair reserve ledger

Entry lifecycle:
  settlement deposit  -> reserve funded
  repair withdrawal   -> reserve spent
  manual adjustment   -> reserve corrected upward
"""
from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class RepairReserveLedger(Base):
    __tablename__ = "repair_reserve_ledger"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    truck_id = Column(Integer, ForeignKey("trucks.id"), nullable=False, index=True)
    entry_date = Column(Date, nullable=False, index=True)
    entry_type = Column(String(20), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(String(255), nullable=True)
    source_type = Column(String(20), nullable=True)
    source_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "entry_type", name="uq_reserve_source"),
        Index("ix_reserve_truck_type_amount", "truck_id", "entry_type", "amount"),
        CheckConstraint(
            "entry_type IN ('deposit', 'withdrawal', 'adjustment')",
            name="check_reserve_entry_type",
        ),
        CheckConstraint("amount > 0", name="check_reserve_amount_positive"),
    )

    tenant = relationship("Tenant")
    truck = relationship("Truck")
