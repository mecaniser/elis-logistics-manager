"""Append-only equipment attribution; source vehicle and booked asset stay distinct."""
from sqlalchemy import Column,Integer,String,Text,ForeignKey,UniqueConstraint,event,DDL
from app.database import Base


class DieselBridgeEquipmentAllocation(Base):
    __tablename__='dbn_equipment_allocations'
    id=Column(Integer,primary_key=True)
    tenant_id=Column(Integer,ForeignKey('tenants.id'),nullable=False,index=True)
    slug=Column(String(60),nullable=False)
    shop_id=Column(String(80),nullable=False)
    customer_id=Column(String(80),nullable=False)
    repair_order_id=Column(String(80),nullable=False,index=True)
    source_vehicle_id=Column(String(100),nullable=False)
    source_vin=Column(String(100),nullable=False)
    asset_id=Column(Integer,ForeignKey('trucks.id'),nullable=False)
    work_equipment_type=Column(String(20),nullable=False)
    interim_unit_allocation=Column(Integer,nullable=False,default=0)
    reason=Column(Text,nullable=False)
    author=Column(String(255),nullable=False)
    created_at=Column(String(40),nullable=False)
    supersedes_id=Column(Integer,ForeignKey('dbn_equipment_allocations.id'),unique=True)
    key=Column(String(160),nullable=False)
    request_digest=Column(String(64),nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','slug','repair_order_id','key'),)


def immutable(mapper,connection,target):
    raise ValueError('Equipment attribution is immutable; append a reviewed correction.')


event.listen(DieselBridgeEquipmentAllocation,'before_update',immutable)
event.listen(DieselBridgeEquipmentAllocation,'before_delete',immutable)
for operation in ('UPDATE','DELETE'):
    event.listen(DieselBridgeEquipmentAllocation.__table__,'after_create',DDL(
        f"CREATE TRIGGER dbn_equipment_no_{operation.lower()} BEFORE {operation} ON dbn_equipment_allocations BEGIN SELECT RAISE(ABORT, 'Equipment attribution is immutable'); END"
    ).execute_if(dialect='sqlite'))
event.listen(DieselBridgeEquipmentAllocation.__table__,'after_create',DDL(
    "CREATE OR REPLACE FUNCTION dbn_equipment_immutable() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Equipment attribution is immutable'; END; $$ LANGUAGE plpgsql; "
    "CREATE TRIGGER dbn_equipment_immutable BEFORE UPDATE OR DELETE ON dbn_equipment_allocations FOR EACH ROW EXECUTE FUNCTION dbn_equipment_immutable();"
).execute_if(dialect='postgresql'))
