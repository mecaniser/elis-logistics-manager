from copy import deepcopy
from datetime import date
from decimal import Decimal

from app.models.settlement import Settlement
from app.models.truck import Truck
from app.routers.analytics import _get_time_series_impl
from app.services.settlement_transfers import audit_transfers, reporting
from app.services.settlement_history import review_rows, attachment_url
from app.utils.pdf_parser import _parse_77_cargo_pdf


def records():
    common = dict(settlement_date=date(2026, 9, 28), week_start=date(2026, 9, 21), week_end=date(2026, 9, 28),
                  settlement_type='77 Cargo LLC', trailer_income_split_amount=400, repair_reserve_amount=400,
                  miles_driven=1000)
    return [dict(common, id=1, truck_id=1, gross_revenue=9672, expenses=8901.04, net_profit=770.96,
                 cash_settlement_amount=1570.96, expense_categories={'deduct':947.27,'fuel':7953.77},
                 deduction_details=[{'description':'Carryover Adjustment: Settlement #2636','amount':947.27}]),
            dict(common, id=2, truck_id=2, gross_revenue=3688, expenses=5435.27, net_profit=-1747.27,
                 cash_settlement_amount=0, expense_categories={'fuel':5435.27,'reimbursement':947.27},
                 reimbursement_details=[{'description':'Carryover Adjustment: Settlement #2636','amount':947.27}])]


def test_legacy_projection_separates_loss_and_transfer_without_mutation():
    rows = records(); before = deepcopy(rows)
    a,b = [reporting(r) for r in rows]
    assert a['operating_net'] + 800 == Decimal('2518.23')
    assert b['operating_net'] + 800 == Decimal('-947.27')
    assert a['settlement_net'] + 800 == Decimal('1570.96')
    assert b['settlement_net'] + 800 == 0
    assert a['operating_expenses'] == Decimal('7953.77')
    assert a['transfer'] + b['transfer'] == 0
    assert rows == before


def test_no_amount_matching_or_ordinary_reimbursement_reclassification():
    r = records()[1]
    r['reimbursement_details'][0]['description'] = 'Fuel reimbursement'
    assert reporting(r)['transfer'] == 0
    assert reporting(r)['settlement_net'] == Decimal('-1747.27')
    r['reimbursement_details'][0]['description'] = 'Carryover Adjustment: Settlement #2636'
    r['expense_categories']['reimbursement'] = 100
    assert reporting(r)['review_required']
    assert reporting(r)['settlement_net'] == r['net_profit']
    r['net_profit'] = None
    assert reporting(r)['settlement_net'] is None


def test_transfer_audit_does_not_match_across_business_dates_or_duplicate_entries():
    rows = records()
    assert audit_transfers(rows)[0]['status'] == 'matched'
    assert audit_transfers(rows[:1])[0]['status'] == 'needs_review'
    assert audit_transfers(rows + [rows[1]])[0]['status'] == 'needs_review'
    rows[1]['tenant_id'] = 2
    assert all(x['status'] == 'needs_review' for x in audit_transfers(rows))
    rows[1].pop('tenant_id');rows[1]['settlement_date'] = date(2026,10,5)
    assert all(x['status'] == 'needs_review' for x in audit_transfers(rows))


def test_week_month_year_and_individual_scopes_use_same_transfer_basis(db):
    db.add_all([Truck(id=i, tenant_id=1, name=str(i), vehicle_type='truck') for i in [1,2]])
    db.add_all([Settlement(**r) for r in records()]);db.commit()
    result = _get_time_series_impl('week_start', None, 'truck', False, db, 1)
    for periods in [result['by_week'], result['by_month'], result['by_year']]:
        period = periods[0]
        assert round(period['settlement_remainder'] + period['trailer_income_split_amount'] + period['repair_reserve_amount'],2) == 1570.96
        assert period['cross_truck_transfer'] == 0
        assert period['expenses'] == 13389.04
        assert period['deduct'] == 0
    for truck_id, expected, transfer in [(1,1570.96,-947.27),(2,0,947.27)]:
        period = _get_time_series_impl('week_start', truck_id, 'truck', False, db, 1)['by_week'][0]
        assert round(period['settlement_remainder'] + 800,2) == expected
        assert period['cross_truck_transfer'] == transfer
    db.expire_all()
    assert db.get(Settlement,1).expenses == Decimal('8901.04')
    assert db.get(Settlement,2).net_profit == Decimal('-1747.27')


def test_pdf_attached_is_not_missing_or_verified():
    r = records()[0];r.update(name='603',settlement_date='2026-09-28',pdf_file_path='https://res.cloudinary.com/example/raw/upload/statement.pdf')
    row = review_rows([r],{})[0]
    assert row['status'] == 'needs_review'
    assert row['original_available'] and row['attachment_url'] == r['pdf_file_path']
    assert row['difference'] is None and row['basis'] == 'stored_unverified'
    assert attachment_url('javascript:alert(1)') is None
    assert attachment_url('https://untrusted.example/test.pdf') is None
    assert attachment_url('/private/path/uploads/test.pdf') == '/uploads/test.pdf'


def parser_text(addition=False):
    # Synthetic source format: do not depend on private carrier PDFs.
    return '''77 Cargo LLC
Settlement #2636
Date: 09/28/26
Pay rate: 88%
Load# Pickup Delivery Description Empty Loaded % Rate Amount
5153 09/21/26 09/28/26 0 1000 88% $5,100.00 $4,488.00
Subtotal: 0 1000 $5,100.00 $4,488.00
Fuel ...1234
Date Description Amount
09/21/26 Fuel -$3,228.41
Subtotal: -$3,228.41
Tolls ...1234
Date Description Amount
09/21/26 Toll -$229.36
Subtotal -$229.36
''' + ('''Additions
Load# Date Description Amount
- 09/28/26 Carryover Adjustment: Settlement #2636 $947.27
Subtotal: $947.27
''' if addition else '') + '''Deductions
# Date Description Amount
5153 09/21/26 Test [Drv] #5153 Route -$1,530.00
- 09/28/26 Cargo and Liability Insurance Unit 609 -$300.00
- 10/01/26 Logbook and Pre-Pass Subscription - Unit 609 -$147.50
Subtotal: -$1,977.50
Settlement total: $0.00
Balance due: $0.00
'''


def test_new_parser_keeps_transfer_out_of_reimbursement_and_operating_costs():
    parsed = _parse_77_cargo_pdf(parser_text(True))
    assert parsed['net_profit'] == -947.27
    assert parsed['cash_settlement_amount'] == 0
    assert 'reimbursement' not in parsed['expense_categories']
    assert parsed['cash_adjustments'][0]['type'] == 'cross_truck_transfer'
    assert reporting(parsed)['settlement_net'] == 0
    text = parser_text(True).replace('Carryover Adjustment: Settlement #2636', 'Fuel reimbursement')
    assert _parse_77_cargo_pdf(text)['expense_categories']['reimbursement'] == 947.27


def test_existing_balance_offsets_affect_settlement_result_not_operating_profit():
    r = records()[1]
    r['reimbursement_details'] = None
    r['expense_categories'].pop('reimbursement')
    r['cash_adjustments'] = [{'type':'prior_balance_offset','description':'Balance out: payment covered by another unit','amount':947.27}]
    result = reporting(r)
    assert result['operating_net'] == Decimal('-1747.27')
    assert result['settlement_net'] + 800 == 0
    assert result['transfer'] == 0  # No invented reference or pairing.
    assert result['other_cash_adjustment'] == Decimal('947.27')
    assert audit_transfers([r])[0]['status'] == 'needs_review'


def test_dashboard_totals_and_serialized_settlement_reporting(db):
    from app.routers.analytics import _get_dashboard_impl
    from app.schemas.settlement import SettlementResponse
    db.add_all([Truck(id=i, tenant_id=1, name=str(i), vehicle_type='truck') for i in [1,2]])
    db.add_all([Settlement(**r) for r in records()]);db.commit()
    data = _get_dashboard_impl(None, 'truck', db, 1)
    assert round(data['trucks']['net_profit'] + 1600,2) == 1570.96
    for truck_id, expected in [(1,1570.96),(2,0)]:
        data = _get_dashboard_impl(truck_id, 'truck', db, 1)
        assert round(data['trucks']['net_profit'] + 800,2) == expected
    result = SettlementResponse.model_validate(db.get(Settlement,1)).model_dump(mode='json')
    assert result['reporting']['transfer'] == '-947.27'
    assert result['reporting']['operating_expenses'] == '7953.77'


def test_mixed_transfer_and_ordinary_reimbursement_are_not_combined():
    text = parser_text(True).replace('Subtotal: $947.27', '- 09/28/26 Fuel reimbursement $100.00\nSubtotal: $1,047.27').replace('Settlement total: $0.00', 'Settlement total: $100.00').replace('Balance due: $0.00', 'Balance due: $100.00')
    parsed = _parse_77_cargo_pdf(text)
    assert parsed['cash_adjustments'][0]['amount'] == 947.27
    assert parsed['expense_categories']['reimbursement'] == 100
    assert parsed['cash_settlement_amount'] == 100


def test_parser_debit_preserves_operating_earnings_and_signed_transfer():
    text = parser_text(False).replace('Subtotal: -$1,977.50', '- 09/28/26 Carryover Adjustment: Settlement #2636 -$947.27\nSubtotal: -$2,924.77').replace('Settlement total: $0.00', 'Settlement total: $-1,894.54').replace('Balance due: $0.00', 'Balance due: $-1,894.54')
    # Reported negative amount formatting is outside this parser's current pattern;
    # absence of that field retains calculated payout and verifies the transfer math.
    parsed = _parse_77_cargo_pdf(text)
    assert parsed['net_profit'] == -947.27
    assert parsed['cash_adjustments'][0]['amount'] == -947.27
    assert parsed['cash_settlement_amount'] == -1894.54
    assert parsed['expenses'] == 5435.27


def test_duplicate_transfer_storage_requires_review_instead_of_double_credit():
    r=records()[1]
    r['cash_adjustments']=[{'type':'cross_truck_transfer','description':'Carryover Adjustment: Settlement #2636','amount':947.27}]
    assert reporting(r)['review_required']
    assert reporting(r)['settlement_net'] == r['net_profit']


def test_new_journal_uses_transfer_result_and_does_not_rewrite_existing_entry(db):
    from app.services.accounting_service import create_settlement_journal_entry
    from app.models.journal_entry_line import JournalEntryLine
    db.add(Truck(id=1,tenant_id=1,name='Test',vehicle_type='truck'));db.flush()
    r=records()[0]
    r.update(expenses=7953.77,net_profit=1718.23,expense_categories={'fuel':7953.77},deduction_details=None,
             cash_adjustments=[{'type':'cross_truck_transfer','description':'Carryover Adjustment: Settlement #2636','amount':-947.27}])
    saved=Settlement(**r);db.add(saved);db.flush()
    entry=create_settlement_journal_entry(db,saved,1)
    lines=db.query(JournalEntryLine).filter_by(journal_entry_id=entry.id).all()
    assert sum(line.debit for line in lines) == Decimal('770.96')
    assert sum(line.credit for line in lines) == Decimal('770.96')
    assert create_settlement_journal_entry(db,saved,1).id == entry.id
    assert db.query(JournalEntryLine).filter_by(journal_entry_id=entry.id).count() == len(lines)


def test_asset_journal_carryover_uses_clearing_without_expense_or_reimbursement(db):
    from app.models.tenant import Tenant
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.chart_of_accounts import ChartOfAccount
    from app.services.accounting_service import create_settlement_journal_entry
    db.get(Tenant,1).name='LS Logistics'
    db.add_all([Truck(id=i,tenant_id=1,name=str(i),vehicle_type='truck') for i in [1,2]])
    db.add_all([Settlement(**r) for r in records()]);db.flush()
    clearing_debit=Decimal(0);clearing_credit=Decimal(0)
    for i in [1,2]:
        entry=create_settlement_journal_entry(db,db.get(Settlement,i),1)
        lines=db.query(JournalEntryLine).filter_by(journal_entry_id=entry.id).all()
        assert sum(line.debit for line in lines) == sum(line.credit for line in lines)
        clearing=db.query(ChartOfAccount).filter_by(tenant_id=1,truck_id=i,code='2190').one()
        clearing_debit+=sum(line.debit for line in lines if line.account_id==clearing.id)
        clearing_credit+=sum(line.credit for line in lines if line.account_id==clearing.id)
        assert not db.query(ChartOfAccount).filter_by(tenant_id=1,truck_id=i,code='4100').count()
    assert clearing_debit == clearing_credit == Decimal('947.27')
