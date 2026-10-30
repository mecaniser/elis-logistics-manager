"""Source invoices are expenses; only their actual payment ledger spends reserves."""
from datetime import date
from decimal import Decimal
import pytest
from app.models.dieselbridge import DieselBridgeRepairLink
from app.models.finance import FinanceEvidence
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger as Ledger
from app.models.settlement import Settlement
from app.services.business_funds import business_funds
from tests.test_finance import truck


def fixture(db,truck,flag):
    proof=FinanceEvidence(tenant_id=truck.tenant_id,sha256='f'*64,filename='fixture.json',media_type='application/json',content_base64='e30=',source_key='fixture',extraction_version='fixture',extracted={})
    db.add(proof)
    repair=Repair(truck_id=truck.id,repair_date=date(2026,4,20),cost=Decimal('1000'),paid_from_reserve=flag)
    db.add(repair);db.flush()
    db.add(DieselBridgeRepairLink(tenant_id=truck.tenant_id,slug='fixture',shop_id='shop',customer_id='customer',repair_order_id='source-ro',repair_id=repair.id,
        accepted_invoice_id='invoice',accepted_revision='f'*64,accepted_snapshot_id='a'*64,accepted_payload={},evidence_id=proof.id))
    db.add(Settlement(truck_id=truck.id,settlement_date=date(2026,10,1),repair_reserve_amount=Decimal('300')))
    db.flush()


@pytest.mark.parametrize('flag',[False,True])
def test_dbn_invoice_never_spends_full_cost_even_if_old_flag_true(db,truck,flag):
    fixture(db,truck,flag)
    assert business_funds(db,truck.tenant_id,date(2026,4,1),date(2026,10,19))['repair']=={
        'opening':'0.00','added':'300.00','used':'0.00','balance':'300.00'}
    db.add(Ledger(tenant_id=truck.tenant_id,truck_id=truck.id,entry_date=date(2026,10,20),entry_type='withdrawal',amount=Decimal('200'),source_type='dbn_payment',source_id=17))
    db.flush()
    assert business_funds(db,truck.tenant_id,date(2026,10,1),date(2026,10,20))['repair']=={
        'opening':'0.00','added':'300.00','used':'200.00','balance':'100.00'}


def test_dbn_payment_reversal_restores_funds_on_actual_reversal_date(db,truck):
    fixture(db,truck,False)
    paid=Ledger(tenant_id=truck.tenant_id,truck_id=truck.id,entry_date=date(2026,10,20),entry_type='withdrawal',amount=Decimal('200'),source_type='dbn_payment',source_id=17)
    db.add(paid);db.flush()
    db.add(Ledger(tenant_id=truck.tenant_id,truck_id=truck.id,entry_date=date(2026,10,21),entry_type='withdrawal_reversal',amount=Decimal('200'),source_type='dbn_payment_reverse',source_id=17,reversal_of_id=paid.id))
    db.flush()
    assert business_funds(db,truck.tenant_id,date(2026,10,20),date(2026,10,20))['repair']=={
        'opening':'300.00','added':'0.00','used':'200.00','balance':'100.00'}
    assert business_funds(db,truck.tenant_id,date(2026,10,21),date(2026,10,21))['repair']=={
        'opening':'100.00','added':'200.00','used':'0.00','balance':'300.00'}


def test_legacy_repair_and_its_synced_ledger_copy_count_once(db,truck):
    repair=Repair(truck_id=truck.id,repair_date=date(2026,9,22),cost=Decimal('100'),paid_from_reserve=True)
    db.add(repair);db.flush()
    db.add(Ledger(tenant_id=truck.tenant_id,truck_id=truck.id,entry_date=repair.repair_date,entry_type='withdrawal',amount=repair.cost,source_type='repair',source_id=repair.id))
    db.flush()
    assert business_funds(db,truck.tenant_id,date(2026,9,1),date(2026,9,30))['repair']['used']=='100.00'
