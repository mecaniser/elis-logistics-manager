"""Operational history is independent from repair expenses and invoice versions."""
from datetime import datetime, timezone
import hashlib
import json
import pytest
from app.models.truck import Truck
from app.models.repair import Repair
from app.models.finance import FinanceEvent
from app.services import dieselbridge as d

BASE = '/api/v1/accounting/dieselbridge'
C = {'slug':'shop','tenant_id':1,'shop_id':'shop-1','bill_to_id':'customer-1','base_url':'https://source.example','api_key_env':'TEST_DB094_HISTORY_KEY'}

@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.delenv('APP_AUTH_USERNAME', raising=False)
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1')
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',json.dumps([C]))
    monkeypatch.setenv('TEST_DB094_HISTORY_KEY','fixture-only')


def test_history_endpoint_is_separate_from_expenses(client, db):
    response=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'})
    assert response.status_code==200
    assert response.json()['items']==[]
    assert db.query(Repair).count()==0
    assert db.query(FinanceEvent).count()==0


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def item(n=1,vin='VIN603',**changes):
    value={'repair_order_id':f'ro-{n}','order_number':f'RO-{n:03}','vehicle_id':f'vehicle-{vin}','vin':vin,'unit_number':vin[-3:],'status':'paid','description':'Réparation du moteur','created_at':'2026-10-01T12:00:00+00:00','work_completed_at':'2026-10-08T13:00:00+00:00','service_date':'2026-10-08','service_date_source':'work_completed_at',**changes}
    value['revision']=digest(value)
    return value


def snapshot(items,**changes):
    scope={'version':'db094-repair-history-v1','shop_id':'shop-1','customer_id':'customer-1','items':items}
    value={**scope,'complete':True,'count':len(items),'snapshot_id':digest(scope),**changes}
    return value


def source(monkeypatch,value):
    import httpx
    async def request(self,path,params=None):
        assert path=='repair-orders'
        return httpx.Response(200,json=value)
    monkeypatch.setattr(d.SourceClient,'request',request)


def sync(client,dry=False):
    return client.post(BASE+'/connections/shop/repair-history/sync',headers={'X-Tenant-ID':'1'},params={'dry_run':dry})


@pytest.fixture
def trucks(db):
    rows=[Truck(tenant_id=1,name='603',vehicle_type='truck',vin='VIN603'),Truck(tenant_id=1,name='609',vehicle_type='truck',vin='VIN609')]
    db.add_all(rows);db.commit();return rows


def test_import_fifteen_preserves_expenses_and_replays(client,db,trucks,monkeypatch):
    from app.models.dieselbridge import DieselBridgeRepairHistory
    from app.models.journal_entry import JournalEntry
    from app.models.repair_reserve_ledger import RepairReserveLedger
    values=[item(n,vin='VIN603' if n<=6 else 'VIN609') for n in range(1,16)]
    source(monkeypatch,snapshot(values))
    preview=sync(client,True)
    assert preview.status_code==200 and preview.json()['source_count']==15
    assert db.query(DieselBridgeRepairHistory).count()==0
    result=sync(client)
    assert result.status_code==200,result.text
    assert result.json()['created']==15 and result.json()['matched']==15
    again=sync(client)
    assert again.status_code==200 and again.json()['created']==0 and again.json()['unchanged']==15
    assert db.query(DieselBridgeRepairHistory).count()==15
    assert db.query(DieselBridgeRepairHistory).filter_by(truck_id=trucks[0].id).count()==6
    assert db.query(DieselBridgeRepairHistory).filter_by(truck_id=trucks[1].id).count()==9
    for model in (Repair,FinanceEvent,JournalEntry,RepairReserveLedger):assert db.query(model).count()==0
    response=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'},params={'truck_id':trucks[0].id})
    assert response.json()['total']==6
    assert all(r['service']['service_date']=='2026-10-08' for r in response.json()['items'])


def test_existing_repairs_are_candidates_only(client,db,trucks,monkeypatch):
    from datetime import date
    existing=Repair(truck_id=trucks[0].id,repair_date=date(2026,10,8),invoice_number='old-renumbered',cost='300.00',paid_from_reserve=False)
    db.add(existing);db.commit()
    source(monkeypatch,snapshot([item()]))
    assert sync(client).status_code==200
    row=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'}).json()['items'][0]
    assert row['legacy_repair_candidates']==[existing.id]
    assert db.query(Repair).count()==1 and str(db.get(Repair,existing.id).cost)=='300.00'


@pytest.mark.parametrize('change',[{'complete':False},{'count':2},{'customer_id':'foreign'},{'shop_id':'foreign'},{'snapshot_id':'0'*64},{'version':'unknown'}])
def test_invalid_full_snapshot_never_mutates(client,db,trucks,monkeypatch,change):
    from app.models.dieselbridge import DieselBridgeRepairHistory
    source(monkeypatch,snapshot([item()],**change))
    assert sync(client).status_code==502
    assert db.query(DieselBridgeRepairHistory).count()==0


@pytest.mark.parametrize('values',[
    [item(),item()],
    [item(service_date='2026-10-19')],
    [item(total_amount='500.00')],
    [item(status='cancelled')],
    [item(work_completed_at=None,service_date_source='work_completed_at')],
])
def test_invalid_rows_rejected_as_whole_snapshot(client,db,trucks,monkeypatch,values):
    from app.models.dieselbridge import DieselBridgeRepairHistory
    source(monkeypatch,snapshot(values))
    assert sync(client).status_code==502
    assert db.query(DieselBridgeRepairHistory).count()==0


def test_complete_absence_withholds_cached_content_and_reappearance_restores(client,db,trucks,monkeypatch):
    source(monkeypatch,snapshot([item()]));assert sync(client).status_code==200
    source(monkeypatch,snapshot([]));assert sync(client).status_code==200
    row=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'}).json()['items'][0]
    assert row['state']=='source_unavailable' and row['service'] is None
    assert row['truck_id']==trucks[0].id
    source(monkeypatch,snapshot([item()]));assert sync(client).status_code==200
    row=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'}).json()['items'][0]
    assert row['state']=='imported' and row['service']['description']=='Réparation du moteur'


def test_changed_source_vin_never_moves_original_history_link(client,db,trucks,monkeypatch):
    source(monkeypatch,snapshot([item()]));assert sync(client).status_code==200
    source(monkeypatch,snapshot([item(vin='VIN609')]));assert sync(client).status_code==200
    row=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'}).json()['items'][0]
    assert row['truck_id']==trucks[0].id and row['state']=='review_required'
    assert row['review_reason']=='truck_identity_changed'


def test_unchanged_source_rechecks_local_vin_identity(client,db,trucks,monkeypatch):
    source(monkeypatch,snapshot([item()]));assert sync(client).status_code==200
    trucks[0].vin='CHANGED';db.commit()
    assert sync(client).status_code==200
    row=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'}).json()['items'][0]
    assert row['truck_id']==trucks[0].id and row['state']=='review_required'


@pytest.mark.parametrize('vin,kind,reason',[('', 'truck','missing_vin'),('UNKNOWN','truck','unmatched_vin'),('VIN603','trailer','vehicle_type_mismatch'),('VIN603','suv','vehicle_type_mismatch')])
def test_unmatched_or_nontruck_kept_for_review(client,db,monkeypatch,vin,kind,reason):
    db.add(Truck(tenant_id=1,name='Asset',vehicle_type=kind,vin='VIN603'));db.commit()
    source(monkeypatch,snapshot([item(vin=vin)]));assert sync(client).status_code==200
    row=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'}).json()['items'][0]
    assert row['truck_id'] is None and row['state']=='review_required' and row['review_reason']==reason


def test_scope_headers_do_not_grant_history_authority(client,db,monkeypatch):
    assert client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'2'}).status_code==404
    assert client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'},params={'truck_id':999}).status_code==404
    monkeypatch.delenv('ELIS_FINANCE_LOCAL_TENANTS')
    assert client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'}).status_code==401


def test_partial_snapshot_cannot_remove_existing_history(client,db,trucks,monkeypatch):
    source(monkeypatch,snapshot([item()]));assert sync(client).status_code==200
    source(monkeypatch,snapshot([],complete=False))
    assert sync(client).status_code==502
    row=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'}).json()['items'][0]
    assert row['state']=='imported' and row['service']['order_number']=='RO-001'


def test_failed_apply_rolls_back_history_and_sync_progress(client,db,trucks,monkeypatch):
    from sqlalchemy import event
    from app.models.dieselbridge import DieselBridgeRepairHistory,DieselBridgeHistorySync,DieselBridgeConnection
    source(monkeypatch,snapshot([item()]));assert sync(client).status_code==200
    original=db.query(DieselBridgeHistorySync).one().snapshot_id
    def fail(mapper,connection,target):
        if target.repair_order_id=='ro-2':raise RuntimeError('fixture apply failure')
    event.listen(DieselBridgeRepairHistory,'before_insert',fail)
    source(monkeypatch,snapshot([item(description='Changed'),item(2)]))
    try:
        with pytest.raises(RuntimeError,match='fixture apply failure'):sync(client)
    finally:event.remove(DieselBridgeRepairHistory,'before_insert',fail)
    assert db.query(DieselBridgeRepairHistory).count()==1
    assert db.query(DieselBridgeRepairHistory).one().payload['description']=='Réparation du moteur'
    assert db.query(DieselBridgeHistorySync).one().snapshot_id==original


def test_history_scope_cannot_be_reassigned_through_new_connection(client,db,trucks,monkeypatch):
    source(monkeypatch,snapshot([item()]));assert sync(client).status_code==200
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',json.dumps([{**C,'slug':'other','bill_to_id':'customer-2'}]))
    value=snapshot([item()],customer_id='customer-2')
    value['snapshot_id']=digest({k:value[k] for k in ('version','shop_id','customer_id','items')})
    source(monkeypatch,value)
    response=client.post(BASE+'/connections/other/repair-history/sync',headers={'X-Tenant-ID':'1'},params={'dry_run':False})
    assert response.status_code==409
    row=client.get(BASE+'/repair-history',headers={'X-Tenant-ID':'1'}).json()['items'][0]
    assert row['service']['order_number']=='RO-001'


def test_history_migration_repeatable(db):
    from sqlalchemy import create_engine,inspect
    from app.database import Base
    from app.migration_runner import _add_dieselbridge_repair_history
    engine=create_engine('sqlite:///:memory:')
    for name in ('tenants','trucks'):Base.metadata.tables[name].create(engine)
    _add_dieselbridge_repair_history(engine);_add_dieselbridge_repair_history(engine)
    assert {'dieselbridge_repair_history','dieselbridge_history_sync'}<=set(inspect(engine).get_table_names())
