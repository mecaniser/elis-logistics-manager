"""
Chart of Accounts model
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    truck_id = Column(Integer, ForeignKey("trucks.id"), nullable=True, index=True)  # For per-asset accounting (LS logistics)
    code = Column(String(20), nullable=False)  # Account code (e.g., "4000")
    name = Column(String(200), nullable=False)  # Account name
    account_type = Column(String(20), nullable=False)  # Asset, Liability, Equity, Revenue, Expense
    parent_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=True)  # For account hierarchy
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="chart_of_accounts")
    truck = relationship("Truck")
    # Self-referential relationship for parent-child hierarchy
    parent = relationship("ChartOfAccount", remote_side=[id], backref="children")

    # Unique constraint: code must be unique per tenant (and per truck if truck_id is set)
    # For LS logistics: accounts are per-truck/trailer (truck_id set)
    # For other tenants: accounts are shared (truck_id is NULL)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'code', 'truck_id', name='unique_code_per_tenant_truck'),
        Index('idx_tenant_account_type_active', 'tenant_id', 'account_type', 'is_active'),
    )

