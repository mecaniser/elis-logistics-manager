from datetime import date, datetime, timezone
from decimal import Decimal as D
import pytest
from sqlalchemy import func
from app.models.repair import Repair
from app.models.truck import Truck
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from app.models.chart_of_accounts import ChartOfAccount
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.services import accounting_service as a


def repair(db):
    truck=Truck(tenant_id=1,name='609',vehicle_type='truck');db.add(truck);db.flush()
    row=Repair(truck_id=truck.id,repair_date=date(2026,4,20),title='DBN repair',cost=D('1000.00'))
    db.add(row);db.flush();return row


def balances(db,journal):
    return {code:(D(debit),D(credit)) for code,debit,credit in db.query(ChartOfAccount.code,JournalEntryLine.debit,JournalEntryLine.credit).join(JournalEntryLine,ChartOfAccount.id==JournalEntryLine.account_id).filter(JournalEntryLine.journal_entry_id==journal.id)}


def test_unpaid_invoice_mirrors_payable_without_cash_and_replays(db):
    r=repair(db);j=a.create_dieselbridge_bill_journal(db,r,source_ref='ro-1')
    assert balances(db,j)=={'5100':(D('1000'),D('0')),'2000':(D('0'),D('1000'))}
    assert a.create_dieselbridge_bill_journal(db,r,source_ref='ro-1').id==j.id
    assert db.query(JournalEntry).count()==1


@pytest.mark.parametrize('payer,credit',[('business','1000'),('cash','1000'),('card','2105'),('owner','2300')])
def test_verified_partial_payment_mirrors_once_and_reverses_append_only(db,payer,credit):
    r=repair(db)
    j=a.create_dieselbridge_payment_journal(db,r,payment_id=9,amount=D('200.00'),paid_date=date(2026,5,1),payer=payer)
    assert balances(db,j)=={'2000':(D('200'),D('0')),credit:(D('0'),D('200'))}
    assert a.create_dieselbridge_payment_journal(db,r,payment_id=9,amount=D('200.00'),paid_date=date(2026,5,1),payer=payer).id==j.id
    rev=a.reverse_dieselbridge_payment_journal(db,payment_id=9,reversal_date=date(2026,5,2),reason='Correction')
    assert balances(db,rev)=={'2000':(D('0'),D('200')),credit:(D('200'),D('0'))}
    assert db.get(JournalEntry,j.id) is not None
    assert a.reverse_dieselbridge_payment_journal(db,payment_id=9,reversal_date=date(2026,5,2),reason='Correction').id==rev.id


def test_archived_repairs_excluded_from_lists_aggregates_and_relationships(db):
    r=repair(db);r.archived_at=datetime.now(timezone.utc);db.flush();db.expire_all()
    assert db.query(Repair).count()==0
    assert db.query(func.sum(Repair.cost)).scalar() is None
    assert db.query(Repair).execution_options(include_archived_repairs=True).count()==1
    truck=db.query(Truck).one();assert truck.repairs==[]


def test_reserve_reversal_nets_withdrawal_without_manual_adjustment(db):
    from app.routers.repair_reserves import _reserve_balance_query,_serialize_balance_row
    r=repair(db)
    w=RepairReserveLedger(tenant_id=1,truck_id=r.truck_id,entry_date=date(2026,5,1),entry_type='withdrawal',amount=D('200'),source_type='dbn_payment',source_id=9)
    db.add(w);db.flush()
    db.add(RepairReserveLedger(tenant_id=1,truck_id=r.truck_id,entry_date=date(2026,5,2),entry_type='withdrawal_reversal',amount=D('200'),source_type='dbn_payment',source_id=9,reversal_of_id=w.id));db.flush()
    result=_serialize_balance_row(_reserve_balance_query(db,1).one())
    assert result['withdrawals_total']==0 and result['adjustments_total']==0 and result['balance']==0


def test_legacy_journal_helpers_do_not_commit(db):
    r=repair(db);a.create_dieselbridge_bill_journal(db,r,source_ref='ro-1');db.rollback()
    assert db.query(JournalEntry).count()==0


def test_dashboard_reserve_spending_uses_ledger_payment_date_and_reversal(db):
    from app.routers.analytics import _get_dashboard_impl
    r=repair(db)
    assert _get_dashboard_impl(None,None,db,1)['repair_reserve_withdrawals']==[]
    w=RepairReserveLedger(tenant_id=1,truck_id=r.truck_id,entry_date=date(2026,5,1),entry_type='withdrawal',amount=D('200'),source_type='dbn_payment',source_id=9)
    db.add(w);db.flush()
    db.add(RepairReserveLedger(tenant_id=1,truck_id=r.truck_id,entry_date=date(2026,5,2),entry_type='withdrawal_reversal',amount=D('200'),source_type='dbn_payment_reverse',source_id=9,reversal_of_id=w.id));db.flush()
    rows=_get_dashboard_impl(None,None,db,1)['repair_reserve_withdrawals']
    assert [(e['payment_date'],e['amount'],e['basis']) for e in rows]==[
        ('2026-05-01',200.0,'verified_payment'),('2026-05-02',-200.0,'verified_payment')]
    other=Truck(tenant_id=1,name='603',vehicle_type='truck');db.add(other);db.flush()
    assert _get_dashboard_impl(other.id,None,db,1)['repair_reserve_withdrawals']==[]


def test_incurred_cost_appears_in_month_and_year_without_any_settlement(db):
    from app.routers.analytics import _get_time_series_impl
    r=repair(db)
    result=_get_time_series_impl('week_start',None,None,False,db,1)
    assert result['by_week']==[]  # Settlement weeks do not invent a cash payout.
    assert result['by_month'][0]['month_key']=='2026-04'
    assert result['by_month'][0]['repairs']==1000.0
    assert result['by_month'][0]['net_profit']==-1000.0
    assert result['by_month'][0]['settlement_count']==0
    assert result['by_year'][0]['repairs']==1000.0 and result['by_year'][0]['net_profit']==-1000.0
