"""Append-only reconciliation evidence with explicitly reviewed occurrence decisions."""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Date, UniqueConstraint, event, DDL
from app.database import Base


class DieselBridgeReconciliationNote(Base):
    __tablename__ = 'dbn_reconciliation_notes'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    slug = Column(String(60), nullable=False)
    shop_id = Column(String(80), nullable=False)
    customer_id = Column(String(80), nullable=False)
    repair_order_id = Column(String(80), nullable=False, index=True)
    note = Column(Text, nullable=False)
    source_references = Column(JSON, nullable=False)
    confirmed_service_date = Column(Date)
    date_treatment = Column(String(30), nullable=False, server_default='note_only')
    source_revision = Column(String(64))
    original_invoice_date = Column(Date)
    amount_discrepancy = Column(Text)
    supersedes_note_id = Column(Integer, ForeignKey('dbn_reconciliation_notes.id'), unique=True)
    author = Column(String(255), nullable=False)
    created_at = Column(String(40), nullable=False)
    key = Column(String(160), nullable=False)
    request_digest = Column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id','slug','repair_order_id','key'),)


def immutable(mapper, connection, target):
    raise ValueError('Reconciliation history is immutable; append a correction.')


event.listen(DieselBridgeReconciliationNote,'before_update',immutable)
event.listen(DieselBridgeReconciliationNote,'before_delete',immutable)
for operation in ('UPDATE','DELETE'):
    event.listen(DieselBridgeReconciliationNote.__table__,'after_create',DDL(
        f"CREATE TRIGGER dbn_reconciliation_notes_no_{operation.lower()} BEFORE {operation} ON dbn_reconciliation_notes BEGIN SELECT RAISE(ABORT, 'Reconciliation history is immutable'); END"
    ).execute_if(dialect='sqlite'))
event.listen(DieselBridgeReconciliationNote.__table__,'after_create',DDL(
    "CREATE OR REPLACE FUNCTION dbn_reconciliation_notes_immutable() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Reconciliation history is immutable'; END; $$ LANGUAGE plpgsql; "
    "CREATE TRIGGER dbn_reconciliation_notes_immutable BEFORE UPDATE OR DELETE ON dbn_reconciliation_notes FOR EACH ROW EXECUTE FUNCTION dbn_reconciliation_notes_immutable();"
).execute_if(dialect='postgresql'))
