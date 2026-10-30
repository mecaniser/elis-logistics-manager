"""Durable scoped notification inbox, independent of financial source facts."""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from app.database import Base


class DieselBridgeFinancialInbox(Base):
    __tablename__ = 'dieselbridge_financial_inbox'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    slug = Column(String(60), nullable=False)
    event_id = Column(String(36), nullable=False)
    body_digest = Column(String(64), nullable=False)
    shop_id = Column(String(80), nullable=False)
    customer_id = Column(String(80), nullable=False)
    repair_order_id = Column(String(80), nullable=False)
    event_kind = Column(String(32), nullable=False)
    payload = Column(JSON, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=lambda:datetime.now(timezone.utc))
    status = Column(String(24), nullable=False, default='pending')
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(64), nullable=True)
    result = Column(JSON, nullable=True)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'slug', 'event_id', name='uq_dbn_financial_inbox_event'),
        Index('ix_dbn_financial_inbox_pending', 'status', 'next_attempt_at', 'id'),
    )
