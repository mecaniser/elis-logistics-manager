"""
Journal Entry model
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    entry_date = Column(Date, nullable=False)
    reference_type = Column(String(50), nullable=True)  # 'settlement', 'repair', 'manual', etc.
    reference_id = Column(Integer, nullable=True)  # ID of the referenced record (settlement_id, repair_id, etc.)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="journal_entries")
    lines = relationship("JournalEntryLine", back_populates="journal_entry", cascade="all, delete-orphan")

    # Check constraint: reference_type must be valid if reference_id is set
    __table_args__ = (
        CheckConstraint(
            "(reference_type IS NULL AND reference_id IS NULL) OR (reference_type IS NOT NULL AND reference_id IS NOT NULL)",
            name='check_reference_consistency'
        ),
    )

