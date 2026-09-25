from datetime import date, timedelta
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.services.retention import score, allocate
from app.services import finance as f
from app.schemas.finance import Command
from tests.test_finance import truck, doc, cmd, policy_setup, bank, bill, ASOF


@pytest.mark.parametrize('retained,expected,band', [('30','100.00','target_met'),('28','93.33','acceptable'),('25','83.33','below_floor'),('33','110.00','target_met'),('-3','-10.00','below_floor'),('27.999','93.33','below_floor')])
def test_score_thresholds(retained, expected, band):
    result = score(Decimal(retained), Decimal('100'), Decimal('30'), Decimal('28'))
    assert result['score'] == expected
    assert result['band'] == band


def test_no_positive_revenue_and_exact_overhead():
    assert score(Decimal('-5'),Decimal('0'),Decimal('30'),Decimal('28'))['score'] is None
    assert score(Decimal('5'),Decimal('-100'),Decimal('30'),Decimal('28'))['score'] is None
    weights = {3:Decimal('1'),1:Decimal('1'),2:Decimal('1')}
    allocation = allocate(Decimal('-1'), weights)
    assert allocation == {1:Decimal('-.34'),2:Decimal('-.33'),3:Decimal('-.33')}
    assert sum(allocation.values()) == -1


def settlement(db, d, truck):
    cmd(db, 'settlement', evidence_id=d,source_ref='s1',asset_id=truck.id,period_start='2026-09-21',period_end='2026-09-21',freight_gross='10000.00',carrier_retention='1000.00',deductions={'driver_pay':'3000.00','fuel':'3000.00'},reported_payout='3000.00')


def result(db, start=ASOF, end=ASOF):
    return f.report(db,1,start,end,end)['retention']['pairs'][0]


def test_outside_expenses_overhead_and_personal_payment_only_once(db,truck):
    d=policy_setup(db);settlement(db,d,truck)
    b=bill(db,d,truck)
    cmd(db,'payment',claim_id=b.id,amount='500.00',payer='owner',evidence_id=d)
    cmd(db,'bill',evidence_id=d,source_ref='shared',description='Office',amount='100.00',category='overhead')
    cmd(db,'financing',action='draw',facility='Personal',amount='2000.00',business_amount='0.00',evidence_id=d,use_description='Personal use')
    r=result(db)
    assert r['retained']=='2400.00'
    assert r['score']=='80.00'
    assert r['status']=='provisional'
    assert sum(Decimal(row['amount']) for row in r['bridge']) == Decimal(r['retained'])


def test_reserve_repair_coverage_and_payment_across_periods(db,truck):
    d=policy_setup(db);a,s=bank(db);settlement(db,d,truck)
    reserve=cmd(db,'reserve',pair_id=truck.id,purpose='repair',amount='1000.00',opening=True,note='Confirmed opening',evidence_id=d)
    b=bill(db,d,truck,reserve_id=reserve.id)
    assert result(db)['retained']=='3000.00'
    mapping=next(e for e in f.events(db,1) if e.kind=='csv_mapping')
    source=doc(db,b'Date,Amount,Description,ID\n2026-09-22,-500.00,Repair,r1\n')
    st=cmd(db,'statement',when='2026-09-22',account_id=a.id,mapping_id=mapping.id,evidence_id=source,start='2026-09-22',end='2026-09-22',opening='10000.00',closing='9500.00')
    cmd(db,'payment',when='2026-09-22',claim_id=b.id,amount='500.00',payer='business',transaction_id=st.payload['_transactions'][0]['id'])
    assert result(db,end=date(2026,9,22))['retained']=='3000.00'
    assert result(db,start=date(2026,9,22),end=date(2026,9,22))['retained']=='0.00'


def test_new_funding_counted_once_and_release_not_earnings(db,truck):
    d=policy_setup(db);bank(db);settlement(db,d,truck)
    reserve=cmd(db,'reserve',pair_id=truck.id,purpose='repair',amount='1000.00',note='New funding',evidence_id=d)
    bill(db,d,truck,reserve_id=reserve.id)
    assert result(db)['retained']=='2000.00'
    cmd(db,'reserve',pair_id=truck.id,purpose='repair',amount='-200.00',note='Release surplus',evidence_id=d)
    assert result(db)['retained']=='2000.00'


def test_business_equipment_payment_and_financing_schedule_not_double_counted(db,truck):
    d=policy_setup(db)
    a,st=bank(db,rows='2026-09-21,-1000.00,Principal,b1\n',closing='9000.00')
    settlement(db,d,truck)
    b=cmd(db,'owner_advance',evidence_id=d,source_ref='acquisition',description='Equipment',amount='5000.00',category='equipment',asset_id=truck.id,pair_id=truck.id)
    payment=cmd(db,'payment',claim_id=b.id,amount='1000.00',principal='1000.00',payer='business',transaction_id=st.payload['_transactions'][0]['id'])
    cmd(db,'financing',action='principal_payment',facility='HELOC',amount='1000.00',business_amount='1000.00',owner_claim_id=b.id,payment_id=payment.id,asset_id=truck.id,evidence_id=d,use_description='Trailer funding principal')
    assert result(db)['retained']=='2000.00'


def test_target_validation_prospective_history_and_tenant_scope(db,truck):
    d=policy_setup(db);settlement(db,d,truck)
    with pytest.raises(ValidationError):
        Command(effective_date=ASOF,payload={'kind':'retention_targets','target_percent':'25.00','acceptable_percent':'28.00'})
    with pytest.raises(Exception) as exc:
        cmd(db,'retention_targets',when='2000-01-01',target_percent='40.00',acceptable_percent='35.00')
    assert exc.value.detail['code']=='RETROACTIVE_TARGET'
    future=date.today()+timedelta(days=10)
    event=cmd(db,'retention_targets',when=future.isoformat(),target_percent='40.00',acceptable_percent='35.00')
    assert result(db)['score']=='100.00'
    report=f.report(db,1,future,future,future)
    assert report['retention']['targets']['target_percent']=='40.00'
    assert not f.report(db,2,future,future,future)['retention']['pairs']
    assert f.report(db,2,future,future,future)['retention']['targets']['target_percent']=='30.00'
    assert event.kind=='retention_targets'


@pytest.mark.parametrize('reimbursement', ['unknown', 'owed', 'reimbursed'])
def test_historical_repair_cost_survives_personal_payment_status(db, truck, reimbursement):
    from tests.test_repair_history import repair
    from tests.test_repair_owner_posting import personal
    from app.services.repair_confirmation import save_confirmation
    d = policy_setup(db); settlement(db, d, truck)
    r = repair(db, truck)
    save_confirmation(db, 1, personal(db, reimbursement=reimbursement)); db.commit()
    actual = result(db)
    assert actual['retained'] == '2500.00'
    assert actual['retained_per_100'] == '25.00'
    assert actual['score'] == '83.33'
    assert actual['source_repair_ids'] == ([] if reimbursement == 'owed' else [r.id])
    assert result(db, date(2026, 9, 1), date(2026, 9, 30))['retained'] == '2500.00'
    assert result(db, date(2026, 1, 1), date(2026, 12, 31))['retained'] == '2500.00'


def test_legacy_repair_period_and_business_isolation(db, truck):
    from tests.test_repair_history import repair
    from app.models.tenant import Tenant
    from app.models.truck import Truck
    d = policy_setup(db); settlement(db, d, truck)
    db.add(Tenant(id=2, name='Other', business_type='logistics')); db.commit()
    other = Truck(name='Other truck', tenant_id=2, vehicle_type='truck'); db.add(other); db.commit()
    repair(db, other)
    r = repair(db, truck); r.repair_date = date(2026, 9, 20); db.commit()
    assert result(db)['retained'] == '3000.00'
    assert result(db, date(2026, 9, 20), ASOF)['retained'] == '2500.00'


def test_trailer_repair_follows_dated_assignment_and_asof(db, truck):
    from app.models.truck import Truck
    from app.models.repair import Repair
    d = policy_setup(db); settlement(db, d, truck)
    trailer = Truck(name='Trailer', tenant_id=1, vehicle_type='trailer')
    db.add(trailer); db.commit()
    cmd(db, 'assignment', truck_id=truck.id, trailer_id=trailer.id, when='2026-09-01', end='2026-09-21')
    db.add_all([
        Repair(truck_id=trailer.id, repair_date=ASOF, cost=100, paid_from_reserve=False),
        Repair(truck_id=trailer.id, repair_date=date(2026,9,22), cost=200, paid_from_reserve=False),
    ]); db.commit()
    r = f.report(db, 1, date(2026,9,1), date(2026,9,30), ASOF)['retention']
    assert r['pairs'][0]['retained'] == '2900.00'
    assert r['unassigned_asset_result'] == '0.00'
    r = f.report(db, 1, date(2026,9,1), date(2026,9,30), date(2026,9,30))['retention']
    assert r['pairs'][0]['retained'] == '2900.00'
    assert r['unassigned_asset_result'] == '-200.00'
