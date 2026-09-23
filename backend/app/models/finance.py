"""Append-only accounting v1 storage. Legacy reports are deliberately independent."""
from uuid import uuid4
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, JSON, Numeric, UniqueConstraint, CheckConstraint, event
from sqlalchemy.sql import func
from app.database import Base


def uid():
    return str(uuid4())


class FinanceEvent(Base):
    __tablename__ = 'finance_events'
    sequence = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String(36), unique=True, nullable=False, default=uid)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    key = Column(String(160), nullable=False)
    digest = Column(String(64), nullable=False)
    kind = Column(String(50), nullable=False, index=True)
    effective_date = Column(Date, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id', 'key', name='uq_finance_event_key'),)


class FinanceEvidence(Base):
    __tablename__ = 'finance_evidence'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    sha256 = Column(String(64), nullable=False)
    filename = Column(String(255), nullable=False)
    media_type = Column(String(100), nullable=False)
    # Exact original bytes; do not rely on an expiring remote URL as the source.
    content_base64 = Column(String, nullable=False)
    source_key = Column(String(160), nullable=False)
    supersedes_id = Column(String(36), nullable=True)
    extraction_version = Column(String(60), nullable=False)
    extracted = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id', 'sha256', name='uq_finance_evidence_hash'),)


class FinancePosting(Base):
    __tablename__ = 'finance_postings'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    event_id = Column(String(36), ForeignKey('finance_events.id'), nullable=False, unique=True)
    entry_date = Column(Date, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    reversal_of = Column(String(36), ForeignKey('finance_postings.id'), nullable=True, unique=True)


class FinanceLine(Base):
    __tablename__ = 'finance_lines'
    id = Column(String(36), primary_key=True, default=uid)
    posting_id = Column(String(36), ForeignKey('finance_postings.id'), nullable=False, index=True)
    account = Column(String(60), nullable=False)
    asset_id = Column(Integer, ForeignKey('trucks.id'), nullable=True)
    debit = Column(Numeric(18, 2), nullable=False, default=0)
    credit = Column(Numeric(18, 2), nullable=False, default=0)
    __table_args__ = (CheckConstraint('debit >= 0 AND credit >= 0 AND NOT (debit > 0 AND credit > 0)', name='ck_finance_line_amount'),)


class FinanceReport(Base):
    __tablename__ = 'finance_reports'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    result = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _immutable(mapper, connection, target):
    raise ValueError('Accounting history is immutable; append a correction or reversal.')


for model in (FinanceEvent, FinanceEvidence, FinancePosting, FinanceLine, FinanceReport):
    event.listen(model, 'before_update', _immutable)
    event.listen(model, 'before_delete', _immutable)

# Enforce append-only history for SQL/bulk operations as well as ORM changes.
from sqlalchemy import DDL
for model in (FinanceEvent, FinanceEvidence, FinancePosting, FinanceLine, FinanceReport):
    table = model.__tablename__
    for operation in ('UPDATE', 'DELETE'):
        trigger = f'{table}_no_{operation.lower()}'
        event.listen(model.__table__, 'after_create', DDL(
            f"CREATE TRIGGER {trigger} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'Accounting history is immutable'); END"
        ).execute_if(dialect='sqlite'))
    event.listen(model.__table__, 'after_create', DDL(
        f"CREATE OR REPLACE FUNCTION {table}_immutable() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Accounting history is immutable'; END; $$ LANGUAGE plpgsql; "
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_immutable();"
    ).execute_if(dialect='postgresql'))
