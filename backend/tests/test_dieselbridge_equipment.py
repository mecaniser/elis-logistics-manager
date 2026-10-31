import asyncio
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from app.models.truck import Truck
from app.models.repair import Repair
from app.models.dieselbridge import DieselBridgeRepairLink as Link
from app.models.dieselbridge_equipment import DieselBridgeEquipmentAllocation as Allocation
from app.models.repair_reserve_ledger import RepairReserveLedger as Reserve
from app.schemas.dieselbridge_financial import EquipmentAllocationInput
from app.services import dieselbridge_equipment as e,dieselbridge_financial as financial
from tests.test_dieselbridge_financial import setup,source,snapshot,item,sync,owner_payment


def allocate(db,row,asset=2,**changes):
    values=dict(asset_id=asset,expected_source_revision=row['revision'],work_equipment_type='trailer',reason='Reviewed trailer identity from original equipment record')
    values.update(changes)
    return asyncio.run(e.append(db,1,'shop',row['repair_order_id'],EquipmentAllocationInput(**values),'allocation-'+str(changes.get('supersedes_id','first')),'fixture-owner'))


def trailer(db):
    value=Truck(id=2,tenant_id=1,name='Trailer609',vehicle_type='trailer',vin='TRAILER609');db.add(value);db.commit();return value


def test_explicit_trailer_attribution_books_history_and_reserve_to_trailer(monkeypatch,db):
    trailer(db);row=item(description='Replace trailer tires');source(monkeypatch,snapshot([row]))
    assert asyncio.run(financial.preview_financial(db,1,'shop'))['rows'][0]['blockers']==['cost_asset_review_required']
    decision=allocate(db,row);db.commit()
    preview=asyncio.run(financial.preview_financial(db,1,'shop'))
    assert preview['rows'][0]['cost_asset_id']==2 and preview['rows'][0]['equipment_allocation']['id']==decision['id']
    sync(db);link=db.query(Link).one();repair=db.get(Repair,link.repair_id)
    assert repair.truck_id==2 and repair.cost==Decimal('1000.00')
    assert db.query(Reserve).count()==0
    owner_payment(db,link)
    assert db.query(Reserve).one().truck_id==2
    assert db.query(Repair).filter_by(truck_id=1).count()==0
    assert financial.public_state(db,1,link)['equipment_allocation']['work_equipment_type']=='trailer'
    from app.routers.analytics import get_vehicle_roi
    assert get_vehicle_roi(2,db=db,tenant_id=1)['cumulative_repair_costs']==1000.0
    assert get_vehicle_roi(1,db=db,tenant_id=1)['cumulative_repair_costs']==0.0


def test_interim_trailer_work_can_stay_under609_with_explicit_note(monkeypatch,db):
    row=item(description='Six trailer tires');source(monkeypatch,snapshot([row]))
    allocate(db,row,asset=1,interim_unit_allocation=True,reason='Owner assigns unidentified trailer tires to unit609 for now')
    sync(db);assert db.query(Repair).one().truck_id==1
    decision=db.query(Allocation).one()
    assert decision.work_equipment_type=='trailer' and decision.interim_unit_allocation==1


def test_exact_trailer_vin_matches_without_inferring_tow_truck(monkeypatch,db):
    trailer(db);row=item(vin=' trailer609 ',description='Trailer tire');source(monkeypatch,snapshot([row]));sync(db)
    assert db.query(Repair).one().truck_id==2


def test_duplicate_vin_across_truck_and_trailer_is_blocked(monkeypatch,db):
    db.add(Truck(tenant_id=1,name='Trailer',vehicle_type='trailer',vin='VIN609'));db.commit()
    source(monkeypatch,snapshot([item()]));assert sync(db)['blocked']==1


def test_attribution_cannot_grant_historical_access(monkeypatch,db):
    trailer(db);row=item(authorization='attribution_required');source(monkeypatch,snapshot([row]))
    with pytest.raises(HTTPException):allocate(db,row)
    assert db.query(Allocation).count()==0


def test_correction_preserves_prior_record_and_cannot_reassign_imported_cost(monkeypatch,db):
    trailer(db);row=item(description='Trailer tire');source(monkeypatch,snapshot([row]))
    first=allocate(db,row,asset=1,interim_unit_allocation=True)
    second=allocate(db,row,supersedes_id=first['id']);db.commit()
    assert db.query(Allocation).count()==2 and second['supersedes_id']==first['id']
    sync(db)
    with pytest.raises(HTTPException):allocate(db,row,asset=1,interim_unit_allocation=True,supersedes_id=second['id'])
    assert db.query(Repair).one().truck_id==2


def test_type_mismatch_and_stale_revision_rejected(monkeypatch,db):
    row=item();source(monkeypatch,snapshot([row]))
    with pytest.raises(HTTPException):allocate(db,row,asset=1)
    with pytest.raises(HTTPException):allocate(db,row,asset=1,work_equipment_type='truck',expected_source_revision='0'*64)


def test_source_vehicle_change_does_not_reuse_old_allocation(monkeypatch,db):
    trailer(db);row=item();source(monkeypatch,snapshot([row]));allocate(db,row)
    source(monkeypatch,snapshot([item(vehicle_id='different-source-vehicle')]))
    assert sync(db)['blocked']==1


def test_allocation_history_database_guard(db,monkeypatch):
    trailer(db);row=item();source(monkeypatch,snapshot([row]));allocate(db,row);db.commit()
    with pytest.raises(Exception):db.execute(text('DELETE FROM dbn_equipment_allocations'))
    db.rollback();assert db.query(Allocation).count()==1


def test_cross_tenant_equipment_not_selectable(monkeypatch,db):
    from app.models.tenant import Tenant
    db.add(Tenant(id=2,name='Other business',business_type='logistics'));db.flush()
    db.add(Truck(id=2,tenant_id=2,name='Other trailer',vehicle_type='trailer',vin='OTHER'));db.commit()
    row=item();source(monkeypatch,snapshot([row]))
    with pytest.raises(HTTPException):allocate(db,row)
    assert db.query(Allocation).count()==0


def test_scope_change_does_not_reuse_equipment_decision(monkeypatch,db):
    from tests.test_dieselbridge_financial import C
    trailer(db);row=item();source(monkeypatch,snapshot([row]));allocate(db,row)
    config={**C,'bill_to_id':'another-customer'}
    assert e.latest(db,1,config,row['repair_order_id']) is None


def test_confirmed_trailer_tire_job_stays_with_actual_trailer_when_sync_disabled(monkeypatch,db):
    asset=trailer(db);asset.name='T1003130';asset.vin='7VGAA5324T1003130';db.commit()
    row=item(description='Repair work')
    row['invoice']['line_items']={'labor':[],'parts':[{'name':'Trailer Tire Aufine','quantity':6}]}
    row['invoice']['revision']=financial.digest({k:v for k,v in row['invoice'].items() if k!='revision'})
    row['revision']=financial.digest({k:v for k,v in row.items() if k not in ('revision','settlement')})
    source(monkeypatch,snapshot([row]))
    assert 'cost_asset_review_required' in asyncio.run(financial.preview_financial(db,1,'shop'))['rows'][0]['blockers']
    monkeypatch.delenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED')
    allocate(db,row,reason='Owner confirms six Aufine tires belong to trailer T1003130; source tractor retained.')
    db.commit();assert db.query(Repair).count()==db.query(Reserve).count()==0
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','1')
    sync(db);db.commit();sync(db,'repeat-trailer');db.commit()
    assert db.query(Repair).one().truck_id==2
    assert db.query(Repair).filter_by(truck_id=1).count()==0
    assert db.query(Link).one().accepted_payload['vin']=='VIN609'
