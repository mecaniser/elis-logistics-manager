"""Whole-invoice asset attribution, with explicit interim trailer-to-unit review."""
from datetime import datetime,timezone
from app.models.truck import Truck
from app.models.dieselbridge import DieselBridgeRepairLink as Link
from app.models.dieselbridge_equipment import DieselBridgeEquipmentAllocation as Allocation
from app.services import dieselbridge as d,finance as f


def public(row):
    return {name:getattr(row,name) for name in ('id','asset_id','work_equipment_type','interim_unit_allocation','reason','author','created_at','supersedes_id','source_vehicle_id','source_vin')}


def latest(db,tenant,config,rid):
    return db.query(Allocation).filter_by(tenant_id=tenant,slug=config['slug'],shop_id=str(config['shop_id']),customer_id=str(config['bill_to_id']),repair_order_id=rid).order_by(Allocation.id.desc()).first()


def resolve(db,tenant,config,row):
    if not row:return None,'source_unavailable',None
    decision=latest(db,tenant,config,row['repair_order_id'])
    if decision:
        asset=db.query(Truck).filter_by(tenant_id=tenant,id=decision.asset_id).first()
        if not asset or decision.source_vehicle_id!=row['vehicle_id'] or decision.source_vin!=d.normalize_vin(row['vin']):
            return None,'equipment_attribution_changed',public(decision)
        if asset.vehicle_type!=decision.work_equipment_type and not (decision.interim_unit_allocation and asset.vehicle_type=='truck' and decision.work_equipment_type=='trailer'):
            return None,'equipment_attribution_changed',public(decision)
        return asset.id,'cost_treatment_required',public(decision)
    vin=d.normalize_vin(row['vin'])
    assets=[a for a in db.query(Truck).filter_by(tenant_id=tenant).all() if vin and d.normalize_vin(a.vin)==vin]
    if len(assets)>1:return None,'duplicate_vin',None
    if not assets:return None,'missing_vin' if not vin else 'unmatched_vin',None
    if assets[0].vehicle_type not in ('truck','trailer'):return None,'vehicle_type_mismatch',None
    return assets[0].id,'cost_treatment_required',None


async def append(db,tenant,slug,rid,body,key,author):
    from app.services import dieselbridge_financial as financial
    financial.require_enabled();f.lock_business(db,tenant)
    config=d.config(tenant,slug)
    request_digest=financial.digest({'body':body.model_dump(mode='json'),'author':author,'scope':[str(config['shop_id']),str(config['bill_to_id'])]})
    prior=db.query(Allocation).filter_by(tenant_id=tenant,slug=slug,repair_order_id=rid,key=key).first()
    if prior:
        if prior.request_digest!=request_digest:f.fail('Idempotency key content changed.','IDEMPOTENCY_CONFLICT')
        return public(prior)
    if db.query(Link).filter_by(tenant_id=tenant,shop_id=str(config['shop_id']),repair_order_id=rid).first():
        f.fail('An imported repair needs an explicit financial reclassification review before changing equipment.','IMPORTED_ASSET_REVIEW_REQUIRED')
    value=await financial.manifest(config)
    row=next((r for r in value['items'] if r['repair_order_id']==rid),None)
    if not row or row['authorization']!='authorized':f.fail('Authorized source invoice is required.','SOURCE_ACCESS_REQUIRED')
    if row['revision']!=body.expected_source_revision:f.fail('Source changed. Refresh its preview.','STALE_INVOICE')
    asset=db.query(Truck).filter_by(tenant_id=tenant,id=body.asset_id).first()
    if not asset or asset.vehicle_type not in ('truck','trailer'):f.fail('Equipment not found.','RESOURCE_NOT_FOUND',404)
    if asset.vehicle_type!=body.work_equipment_type and not (body.interim_unit_allocation and asset.vehicle_type=='truck' and body.work_equipment_type=='trailer'):
        f.fail('Select matching equipment, or explicitly review interim trailer cost assignment to a truck unit.','EQUIPMENT_TYPE_MISMATCH')
    if body.interim_unit_allocation and not (asset.vehicle_type=='truck' and body.work_equipment_type=='trailer'):
        f.fail('Interim unit assignment is only for unidentified trailer work booked to its truck unit.','EQUIPMENT_TYPE_MISMATCH')
    previous=latest(db,tenant,config,rid)
    if (previous.id if previous else None)!=body.supersedes_id:f.fail('Equipment review changed. Refresh before correcting it.','STALE_ALLOCATION')
    record=Allocation(tenant_id=tenant,slug=slug,shop_id=str(config['shop_id']),customer_id=str(config['bill_to_id']),repair_order_id=rid,source_vehicle_id=row['vehicle_id'],source_vin=d.normalize_vin(row['vin']),asset_id=asset.id,work_equipment_type=body.work_equipment_type,interim_unit_allocation=int(body.interim_unit_allocation),reason=body.reason,author=author,created_at=datetime.now(timezone.utc).isoformat(),supersedes_id=body.supersedes_id,key=key,request_digest=request_digest)
    db.add(record);db.flush();return public(record)
