"""Cross-repository fixture emitted by DBN's actual v2 projection functions."""
import json
import pytest
from pathlib import Path
from decimal import Decimal
from app.models.dieselbridge import DieselBridgeRepairLink
from app.models.finance import FinanceEvent
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.services import dieselbridge_financial as financial
from tests.test_dieselbridge_financial import setup,source,sync,C


def test_actual_source_cash_projection_imports_principal_not_card_quote(monkeypatch,db):
    value=json.loads((Path(__file__).parent/'fixtures/db094-settlement-v2.json').read_text())
    config={**C,'shop_id':value['shop_id'],'bill_to_id':value['customer_id']}
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',json.dumps([config]))
    assert financial.validate_manifest(value,config)==value
    source(monkeypatch,value)
    result=sync(db);db.commit()
    assert result['created']==1
    repair=db.query(Repair).one();link=db.query(DieselBridgeRepairLink).one()
    assert repair.cost==Decimal('4886.38')
    assert repair.repair_date.isoformat()=='2026-08-24'
    assert link.accepted_payload['invoice']['total_amount']=='5057.40'
    bill=db.query(FinanceEvent).filter_by(kind='bill').one()
    assert bill.payload['amount']=='4886.38'
    state=financial.public_state(db,1,link)
    assert state['source_invoice_total']=='5057.40'
    assert state['booked_cost']=='4886.38'
    assert state['source_settlement']['principal_total']=='4886.38'
    cash=state['source_settlement']['payments'][0]
    assert cash['rail']=='cash' and cash['gross_received_amount']=='4886.38'
    assert cash['applied_card_fee_amount']=='0.00' and cash['actual_paid_date'] is None
    assert state['recorded_paid_amount']=='0.00'
    assert db.query(RepairReserveLedger).count()==0
    assert db.query(FinanceEvent).filter_by(kind='payment').count()==0
    assert sync(db,'contract-replay')['unchanged']==1
    assert db.query(Repair).count()==1


@pytest.mark.parametrize('fee',['35.00','NaN','',False,None,{},[],0,'0'])
def test_legacy_accept_cannot_bypass_conditional_card_fee_resolution(db,fee):
    import pytest
    from fastapi import HTTPException
    from app.services import dieselbridge as d
    from tests.test_dieselbridge import item as old_item
    staged=d.stage(db,1,C,old_item(vin='VIN609',total_amount='1035.00',service_fee_amount=fee))
    db.commit()
    with pytest.raises(HTTPException) as exc:d.accept(db,1,staged.id,staged.revision,'Reviewed the source quote')
    assert exc.value.detail['code']=='SETTLEMENT_IMPORT_REQUIRED'
    assert db.query(Repair).count()==db.query(FinanceEvent).count()==0
