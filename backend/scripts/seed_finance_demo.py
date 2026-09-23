"""Disposable local demonstration only. Never runs against a business database."""
import os
if not os.environ.get('DATABASE_URL', '').startswith('sqlite:////tmp/elis-finance-demo'):
    raise SystemExit('Use a new /tmp/elis-finance-demo*.db SQLite database.')
from app.main import app
from app.database import SessionLocal
from app.models.tenant import Tenant
from app.models.truck import Truck
from app.services import finance as f
from tests.test_finance import doc, cmd, policy_setup

with SessionLocal() as db:
    if db.query(Tenant).count(): raise SystemExit('Demo database already populated.')
    db.add(Tenant(id=1, name='ELIS · Synthetic preview', business_type='logistics'));db.commit()
    units=[Truck(name='603 · demo', tenant_id=1, vehicle_type='truck'),Truck(name='609 · demo', tenant_id=1, vehicle_type='truck'),Truck(name='T1003142 · demo',tenant_id=1,vehicle_type='trailer'),Truck(name='T1003130 · demo',tenant_id=1,vehicle_type='trailer')]
    db.add_all(units);db.commit()
    d=policy_setup(db)
    for i in range(2): cmd(db,'assignment',when='2026-01-01',truck_id=units[i].id,trailer_id=units[i+2].id)
    for i,g,c,driver,fuel,toll,support,net in [(0,'11800.00','1416.00','3540.00','2811.94','54.72','0.00','3677.34'),(1,'11900.00','1428.00','3570.00','4032.89','209.53','200.00','2159.58')]:
        cmd(db,'settlement',evidence_id=d,source_ref=f'demo-settlement-{i}',asset_id=units[i].id,trailer_id=units[i+2].id,period_start='2026-09-14',period_end='2026-09-21',freight_gross=g,carrier_retention=c,deductions={'driver_pay':driver,'fuel':fuel,'insurance':'300.00','tolls':toll,'support':support},reported_payout=net)
    account=cmd(db,'account',when='2026-01-01',name='Synthetic checking',account_type='bank')
    mapping=cmd(db,'csv_mapping',when='2026-01-01',name='Demo mapping',date_column='Date',amount_column='Amount',description_column='Description',id_column='ID',approved_for_matching=True)
    csvdoc=doc(db,b'Date,Amount,Description,ID\n2026-09-21,3677.34,demo-settlement-0,deposit603\n2026-09-21,2159.58,demo-settlement-1,deposit609\n')
    cmd(db,'statement',when='2026-09-23',account_id=account.id,mapping_id=mapping.id,evidence_id=csvdoc,start='2026-09-01',end='2026-09-23',opening='10000.00',closing='15836.92')
    f.auto_reconcile(db,1);db.commit()
    for i in range(2):
        cmd(db,'reserve',when='2026-09-23',pair_id=units[i].id,purpose='repair',amount='1000.00',opening=True,note='Synthetic confirmed allocation',evidence_id=d)
        cmd(db,'reserve',when='2026-09-23',pair_id=units[i].id,asset_id=units[i].id,purpose='capital',amount='1500.00',opening=True,note='Synthetic confirmed capital',evidence_id=d)
        cmd(db,'asset_plan',asset_id=units[i].id,acquired='2025-01-01',acquisition_cost='50000.00',expected_resale='20000.00',planned_sale='2028-01-01',evidence_id=d)
    print('Synthetic preview seeded; available cash is an illustrative value, not live business data.')
