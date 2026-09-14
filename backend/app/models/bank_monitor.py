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
