"""
Tenant/Organization model for multi-tenant support
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    business_type = Column(String(50), nullable=False, default='logistics')  # 'logistics', 'tech', 'real_estate', etc.
    is_active = Column(Boolean, default=True)
    # Business details
    ein = Column(String(20), nullable=True)  # Employer Identification Number
    legal_name = Column(String(200), nullable=True)  # Legal business name (may differ from display name)
    address = Column(String(255), nullable=True)  # Business address
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    bank_accounts = Column(JSON, nullable=True)  # Array of bank account objects: [{"bank_name": "...", "account_number": "...", "routing_number": "..."}]
    notes = Column(String(1000), nullable=True)  # Additional notes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    trucks = relationship("Truck", back_populates="tenant")
    chart_of_accounts = relationship("ChartOfAccount", back_populates="tenant")
    journal_entries = relationship("JournalEntry", back_populates="tenant")

