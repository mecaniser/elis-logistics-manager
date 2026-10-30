"""DB-094 staging and durable page progress, separate from accounting."""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, UniqueConstraint
from app.database import Base


class DieselBridgeConnection(Base):
    __tablename__ = 'dieselbridge_connections'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    slug = Column(String(60), nullable=False)
    shop_id = Column(String(80), nullable=False)
    bill_to_id = Column(String(80), nullable=False)
    base_url = Column(String(500), nullable=False)
    watermark = Column(String(40))
    window_since = Column(String(40))
    window_before = Column(String(40))
    cursor = Column(Text)
    __table_args__ = (UniqueConstraint('tenant_id', 'slug'), UniqueConstraint('tenant_id', 'shop_id', 'bill_to_id'))


class DieselBridgeInvoice(Base):
    __tablename__ = 'dieselbridge_invoices'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    source_system = Column(String(30), nullable=False, default='dieselbridge')
    shop_id = Column(String(80), nullable=False)
    invoice_id = Column(String(80), nullable=False)
    bill_to_id = Column(String(80), nullable=False)
    revision = Column(String(40), nullable=False)
    event_id = Column(String(80))
    payload = Column(JSON, nullable=False)
    truck_id = Column(Integer, ForeignKey('trucks.id'))
    repair_id = Column(Integer, ForeignKey('repairs.id'), unique=True)
    state = Column(String(40), nullable=False)
    review_reason = Column(String(100), nullable=False)
    accepted_revision = Column(String(40))
    review_note = Column(Text)
    __table_args__ = (UniqueConstraint('tenant_id', 'source_system', 'shop_id', 'invoice_id'),)


class DieselBridgeRepairHistory(Base):
    """Operational service evidence; never a repair expense or payment."""
    __tablename__ = 'dieselbridge_repair_history'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    source_system = Column(String(30), nullable=False, default='dieselbridge')
    shop_id = Column(String(80), nullable=False)
    customer_id = Column(String(80), nullable=False)
    repair_order_id = Column(String(80), nullable=False)
    revision = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    truck_id = Column(Integer, ForeignKey('trucks.id'), nullable=True, index=True)
    state = Column(String(30), nullable=False)
    review_reason = Column(String(80), nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id', 'source_system', 'shop_id', 'repair_order_id'),)


class DieselBridgeHistorySync(Base):
    __tablename__ = 'dieselbridge_history_sync'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    slug = Column(String(60), nullable=False)
    shop_id = Column(String(80), nullable=False)
    customer_id = Column(String(80), nullable=False)
    snapshot_id = Column(String(64), nullable=False)
    synced_at = Column(String(40), nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id', 'slug'), UniqueConstraint('tenant_id', 'shop_id', 'customer_id'))
