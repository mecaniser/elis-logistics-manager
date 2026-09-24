from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, Date, UniqueConstraint
from app.database import Base


class BankMonitorConfig(Base):
    __tablename__ = 'bank_monitor_configs'
    tenant_id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    rules = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class BankMonitorRun(Base):
    __tablename__ = 'bank_monitor_runs'
    __table_args__ = (UniqueConstraint('tenant_id', 'scheduled_date', name='uq_bank_monitor_daily'),)
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    scheduled_date = Column(Date, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(40), nullable=False)
    result = Column(JSON, nullable=False, default=dict)


class BankRepaymentRun(Base):
    """On-demand repayment evaluations, separate from the daily scheduler slot."""
    __tablename__ = 'bank_repayment_runs'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(40), nullable=False)
    result = Column(JSON, nullable=False, default=dict)


class BankMonitorWorkerHeartbeat(Base):
    __tablename__ = 'bank_monitor_worker_heartbeats'
    tenant_id = Column(Integer, primary_key=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)


class BankMonitorConnectionCheck(Base):
    """Read-only, on-demand verification of the worker's bank access."""
    __tablename__ = 'bank_monitor_connection_checks'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    requested_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(40), nullable=False)
    result = Column(JSON, nullable=False, default=dict)


class BankTransferDraft(Base):
    __tablename__ = 'bank_transfer_drafts'
    __table_args__ = (UniqueConstraint('tenant_id', 'charge_reference', name='uq_bank_charge_reference'),)
    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    source_evidence = Column(String(64), unique=True)
    destination_evidence = Column(String(64), unique=True)
    charge_reference = Column(String(120), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    from_last4 = Column(String(4), nullable=False)
    to_last4 = Column(String(4), nullable=False)
    memo = Column(String(34), nullable=False)
    bank_state = Column(String(12))
    bank_effective_date = Column(Date)
    status = Column(String(40), nullable=False, default='reviewed')
    created_at = Column(DateTime(timezone=True), nullable=False)
