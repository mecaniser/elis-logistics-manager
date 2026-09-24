from datetime import date
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.models.finance import FinanceEvent, FinancePosting
from app.models.tenant import Tenant
from app.services.payment_accounts import PaymentAccountInput, add_account, list_accounts, get_account
from app.services.repair_confirmation import save_confirmation
from app.services.repair_history import repair_history
from tests.test_repair_confirmation import payload
from tests.test_repair_history import repair
from tests.test_finance import truck


def card(db):
    return add_account(db, 1, PaymentAccountInput(name='Personal card', account_type='card', ownership='personal', last4='1234'))


def test_directory_is_idempotent_scoped_and_nonfinancial(db):
    first = card(db); db.commit()
    assert card(db) == first
    assert len(list_accounts(db, 1)) == 1
    assert list_accounts(db, 2) == []
    with pytest.raises(HTTPException): get_account(db, 2, first['id'])
    assert db.query(FinanceEvent).count() == db.query(FinancePosting).count() == 0


def test_selected_card_persists_without_duplicate_expense(db, truck):
    repair(db, truck); account = card(db)
    request = payload(db).model_copy(update={'method': 'credit_card', 'source': 'personal', 'payment_account_id': account['id']})
    first = save_confirmation(db, 1, request); db.commit()
    assert save_confirmation(db, 1, request) == first
    c = repair_history(db, 1, date.today())['rows'][0]['confirmation']
    assert c['payment_account']['last4'] == '1234'
    assert c['payment_account_id'] == account['id']
    assert db.query(FinancePosting).count() == 0
    for change in ({'source':'business'}, {'method':'cash'}, {'status':'unpaid'}):
        with pytest.raises(HTTPException): save_confirmation(db, 1, request.model_copy(update=change))


def test_other_business_account_cannot_be_used(db, truck):
    repair(db, truck)
    db.add(Tenant(id=2, name='Other', business_type='logistics')); db.commit()
    account = add_account(db, 2, PaymentAccountInput(name='Other card', account_type='card', ownership='personal'))
    request = payload(db).model_copy(update={'method':'credit_card', 'source':'personal', 'payment_account_id':account['id']})
    with pytest.raises(HTTPException): save_confirmation(db, 1, request)


def test_account_validation_and_routes(db, client, monkeypatch):
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS', '1')
    monkeypatch.setenv('APP_AUTH_TENANT_IDS', '1')
    data = {'name':'Business checking', 'account_type':'bank', 'ownership':'business', 'last4':'5678'}
    headers = {'X-Tenant-ID':'1'}
    response = client.post('/api/v1/accounting/payment-accounts', json=data, headers=headers)
    assert response.status_code == 200
    assert client.get('/api/v1/accounting/payment-accounts', headers=headers).json()['items'][0]['name'] == data['name']
    assert client.get('/api/v1/accounting/payment-accounts', headers={'X-Tenant-ID':'2'}).status_code == 404
    for change in ({'last4':'1234567890123456'}, {'name':'  '}, {'ownership':'mixed'}):
        with pytest.raises(ValidationError): PaymentAccountInput(**{**data, **change})
