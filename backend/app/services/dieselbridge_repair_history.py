"""Complete operational RO snapshots; no expense, document or payment writes."""
import hashlib
import json
import re
from datetime import date, datetime, timezone
from app.models.dieselbridge import DieselBridgeRepairHistory as History, DieselBridgeHistorySync as Sync
from app.models.repair import Repair
from app.models.truck import Truck
from app.services import dieselbridge as d
from app.services import finance as f

VERSION = 'db094-repair-history-v1'
MAX_ITEMS = 1000
ITEM_FIELDS = {'repair_order_id','order_number','vehicle_id','vin','unit_number','status','description','created_at','work_completed_at','service_date','service_date_source','revision'}
SNAPSHOT_FIELDS = {'version','shop_id','customer_id','snapshot_id','complete','count','items'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')).hexdigest()


def invalid():
    f.fail('Invalid complete repair-history snapshot. No history changes were saved.', 'SOURCE_PROTOCOL_ERROR', 502)


def validate_snapshot(value, config):
    if not isinstance(value, dict) or set(value) != SNAPSHOT_FIELDS:
        invalid()
    if (value['version'] != VERSION or value['shop_id'] != str(config['shop_id'])
            or value['customer_id'] != str(config['bill_to_id']) or value['complete'] is not True
            or type(value['count']) is not int or not isinstance(value['items'], list)
            or value['count'] != len(value['items']) or value['count'] > MAX_ITEMS):
        invalid()
    seen = set()
    for item in value['items']:
        if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
            invalid()
        for field in ('repair_order_id','order_number','vehicle_id'):
            if not isinstance(item[field], str) or not item[field].strip() or len(item[field]) > 100:
                invalid()
        for field, limit in (('vin',100),('unit_number',100),('description',50000)):
            if item[field] is not None and (not isinstance(item[field], str) or len(item[field]) > limit):
                invalid()
        if item['repair_order_id'] in seen or item['status'] not in ('completed','invoiced','paid'):
            invalid()
        seen.add(item['repair_order_id'])
        created = d.timestamp(item['created_at'])
        completed = d.timestamp(item['work_completed_at']) if item['work_completed_at'] is not None else None
        expected_date = completed.date() if completed else created.date()
        expected_source = 'work_completed_at' if completed else 'created_at_fallback'
        if item['service_date'] != expected_date.isoformat() or item['service_date_source'] != expected_source:
            invalid()
        revision = item['revision']
        if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{64}', revision):
            invalid()
        if revision != digest({k:v for k,v in item.items() if k != 'revision'}):
            invalid()
    scope = {k:value[k] for k in ('version','shop_id','customer_id','items')}
    if value['snapshot_id'] != digest(scope):
        invalid()
    return value


def candidates(db, tenant, truck_id, payload):
    if not truck_id or not payload:
        return []
    return [r[0] for r in db.query(Repair.id).join(Truck, Repair.truck_id == Truck.id).filter(
        Truck.tenant_id == tenant, Repair.truck_id == truck_id,
        Repair.repair_date == date.fromisoformat(payload['service_date'])).order_by(Repair.id).all()]


def public(db, tenant, row):
    visible = row.state != 'source_unavailable'
    truck = db.query(Truck).filter_by(tenant_id=tenant, id=row.truck_id).first() if row.truck_id else None
    return {'id':row.id,'shop_id':row.shop_id,'repair_order_id':row.repair_order_id,
            'truck_id':row.truck_id,'truck_name':truck.name if truck else None,
            'revision':row.revision,'state':row.state,'review_reason':row.review_reason,
            'service':row.payload if visible else None,
            'legacy_repair_candidates':candidates(db,tenant,row.truck_id,row.payload) if visible else []}


async def sync_history(db, tenant, slug, dry_run=True):
    f.lock_business(db, tenant)
    config = d.config(tenant, slug)
    connection = d.connection(db, tenant, config)  # Scope changes cannot reuse a connection.
    response = await d.SourceClient(config).request('repair-orders')
    try:
        snapshot = validate_snapshot(response.json(), config)
    except (TypeError, ValueError):
        invalid()
    old_rows = db.query(History).filter_by(tenant_id=tenant, shop_id=str(config['shop_id'])).all()
    old = {r.repair_order_id:r for r in old_rows}
    result = {'dry_run':dry_run,'source_count':snapshot['count'],'matched':0,'review_required':0,
              'created':0,'updated':0,'unchanged':0,'source_unavailable':0,
              'legacy_candidate_count':0,'snapshot_id':snapshot['snapshot_id']}
    incoming = set()
    planned = []
    for item in snapshot['items']:
        rid = item['repair_order_id']; incoming.add(rid)
        row = old.get(rid)
        if row and row.customer_id != str(config['bill_to_id']):
            f.fail('Repair-order customer scope changed. Review the existing history first.', 'HISTORY_SCOPE_CONFLICT')
        match_id, reason = d.match(db, tenant, item['vin'])
        truck_id = row.truck_id if row and row.truck_id else match_id
        if row and row.truck_id and match_id != row.truck_id:
            reason = 'truck_identity_changed'
        matched = reason == 'cost_treatment_required'
        state = 'imported' if matched else 'review_required'
        reason = 'unique_vin_match' if matched else reason
        result['matched' if matched else 'review_required'] += 1
        result['legacy_candidate_count'] += bool(candidates(db,tenant,truck_id,item))
        unchanged = bool(row and (row.revision,row.payload,row.truck_id,row.state,row.review_reason) ==
                         (item['revision'],item,truck_id,state,reason))
        result['created' if row is None else 'unchanged' if unchanged else 'updated'] += 1
        planned.append((row,item,truck_id,state,reason,unchanged))
    absent = [r for r in old_rows if r.customer_id == str(config['bill_to_id']) and r.repair_order_id not in incoming]
    result['source_unavailable'] = len(absent)
    if dry_run:
        return result
    db.add(connection)
    for row,item,truck_id,state,reason,unchanged in planned:
        if unchanged:
            continue
        if row is None:
            row = History(tenant_id=tenant, source_system='dieselbridge', shop_id=str(config['shop_id']),
                          customer_id=str(config['bill_to_id']), repair_order_id=item['repair_order_id'])
            db.add(row)
        row.revision,row.payload,row.truck_id,row.state,row.review_reason = item['revision'],item,truck_id,state,reason
    for row in absent:
        row.state,row.review_reason = 'source_unavailable','source_scope_review_required'
    sync = db.query(Sync).filter_by(tenant_id=tenant,slug=slug).first()
    if sync and (sync.shop_id,sync.customer_id) != (str(config['shop_id']),str(config['bill_to_id'])):
        f.fail('History connection scope changed.', 'HISTORY_SCOPE_CONFLICT')
    if sync is None:
        sync = Sync(tenant_id=tenant,slug=slug,shop_id=str(config['shop_id']),customer_id=str(config['bill_to_id']))
        db.add(sync)
    sync.snapshot_id,sync.synced_at = snapshot['snapshot_id'],datetime.now(timezone.utc).isoformat()
    db.flush()
    return result
