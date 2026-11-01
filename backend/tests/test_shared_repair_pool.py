"""Cross-equipment repair spending uses one fund with no artificial cash funding."""
from datetime import date
from decimal import Decimal
from app.models.truck import Truck
from app.models.tenant import Tenant
from app.models.settlement import Settlement
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger as Ledger
from app.services.business_funds import business_funds, repair_fund


def test_pool_uses_truck_contributions_for_trailer_and_retains_negative_balance(client,db,tenant_headers):
    a=Truck(tenant_id=1,name='603',vehicle_type='truck');b=Truck(tenant_id=1,name='609',vehicle_type='truck')
    trailer=Truck(tenant_id=1,name='Trailer',vehicle_type='trailer');db.add_all([a,b,trailer]);db.flush()
    one=Settlement(truck_id=a.id,settlement_date=date(2026,1,7),repair_reserve_amount=Decimal('400'))
    two=Settlement(truck_id=b.id,settlement_date=date(2026,1,7),repair_reserve_amount=Decimal('400'))
    db.add_all([one,two]);db.flush()
    # Derived trailer income and ledger copies must not fund the same money twice.
    db.add(Settlement(truck_id=trailer.id,settlement_date=date(2026,1,7),repair_reserve_amount=Decimal('400'),source_settlement_id=one.id))
    repair=Repair(truck_id=trailer.id,repair_date=date(2026,1,8),cost=Decimal('1000'),paid_from_reserve=True)
    db.add(repair);db.flush()
    db.add(Ledger(tenant_id=1,truck_id=a.id,entry_date=date(2026,1,7),entry_type='deposit',amount=400,source_type='settlement',source_id=one.id))
    db.add(Ledger(tenant_id=1,truck_id=trailer.id,entry_date=date(2026,1,8),entry_type='withdrawal',amount=1000,source_type='repair',source_id=repair.id))
    db.add(Tenant(id=2,name='Other company',business_type='logistics'));db.flush()
    other=Truck(tenant_id=2,name='Other truck',vehicle_type='truck');db.add(other);db.flush()
    db.add(Settlement(truck_id=other.id,settlement_date=date(2026,1,7),repair_reserve_amount=9000));db.commit()
    response=client.get('/api/repair-reserve-pool?as_of=2026-01-08',headers=tenant_headers)
    assert response.status_code==200
    assert response.json()['scope']=='company' and response.json()['allows_negative'] is True
    assert response.json()['fund']=={'opening':'0.00','added':'800.00','used':'1000.00','balance':'-200.00'}
    assert business_funds(db,1,date(2026,1,1),date(2026,1,8))['repair']==response.json()['fund']
    assert repair_fund(db,2,date(2026,1,1),date(2026,1,8))['balance']=='9000.00'
    assert client.get('/api/repair-reserve-pool?as_of=2099-01-01',headers=tenant_headers).status_code==422
    assert db.query(Ledger).count()==2  # GET never creates transfers or balances.
