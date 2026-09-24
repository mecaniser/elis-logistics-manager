from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from app.models.bank_monitor import BankMonitorConfig, BankMonitorRun
from app.models.finance import FinanceEvent, FinancePosting
from app.services.payment_accounts import add_account, PaymentAccountInput
from app.services.payment_account_links import sources, link_account, account_balances, AccountLinkInput
from tests.test_finance import bank


def identity(db, ownership='business', typ='bank', name='Checking'):
    return add_account(db,1,PaymentAccountInput(name=name,ownership=ownership,account_type=typ,last4='1234'))


def test_business_statement_link_no_new_cash_or_duplicate_identity(db):
    account=identity(db); a,s=bank(db)
    before=db.query(FinanceEvent).count()
    request=AccountLinkInput(provider='ledger',source_id=a.id)
    first=link_account(db,1,account['id'],request);db.commit()
    assert link_account(db,1,account['id'],request)==first
    balance=account_balances(db,1,account['id'])[0]
    assert balance['source']['balance']=='10000.00'
    assert balance['source']['basis']=='reconciled_statement'
    assert db.query(FinanceEvent).count()==before
    other=identity(db,name='Other checking')
    with pytest.raises(HTTPException):link_account(db,1,other['id'],request)
    with pytest.raises(HTTPException):account_balances(db,2,account['id'])


def test_personal_balance_is_observed_not_business_cash(db):
    account=identity(db,ownership='personal',typ='card')
    db.add(BankMonitorConfig(tenant_id=1,enabled=False,updated_at=datetime.now(timezone.utc),rules={'sources':[{'nickname':'Personal card','last4':'1234','kind':'credit'}]}))
    db.add(BankMonitorRun(tenant_id=1,scheduled_date=datetime.now().date(),started_at=datetime.now(timezone.utc),status='completed',result={'observed_at':'2026-09-23T10:00:00Z','credit_accounts':[{'nickname':'Personal card','last4':'1234','outstanding_cents':90000}]}));db.commit()
    assert sources(db,1)==[]
    request=AccountLinkInput(provider='monitor',source_id='sources:1234')
    with pytest.raises(HTTPException):link_account(db,1,account['id'],request)
    link_account(db,1,account['id'],request,True);db.commit()
    linked=account_balances(db,1,account['id'],True)[0]
    assert linked['source']['balance']=='900.00'
    assert linked['source']['basis']=='observed_not_reconciled'
    assert linked['source']['as_of']=='2026-09-23T10:00:00Z'
    assert db.query(FinancePosting).count()==db.query(FinanceEvent).count()==0
    assert account_balances(db,1,account['id'],False)[0]['source'] is None
    config=db.get(BankMonitorConfig,1);config.rules={'sources':[{'nickname':'Different card','last4':'1234','kind':'credit'}]};db.commit()
    assert account_balances(db,1,account['id'],True)[0]['status']=='review_required'


def test_personal_cannot_link_business_statement(db):
    account=identity(db,ownership='personal'); a,s=bank(db)
    with pytest.raises(HTTPException):link_account(db,1,account['id'],AccountLinkInput(provider='ledger',source_id=a.id))
