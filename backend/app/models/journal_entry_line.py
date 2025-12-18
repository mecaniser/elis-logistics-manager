"""
Journal Entry Line model
"""
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)  # Explicit tenant isolation
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=False)
    debit = Column(Numeric(10, 2), nullable=False, default=0)
    credit = Column(Numeric(10, 2), nullable=False, default=0)
    description = Column(String(500), nullable=True)
    truck_id = Column(Integer, ForeignKey("trucks.id"), nullable=True)  # For operational tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("ChartOfAccount")
    truck = relationship("Truck")

