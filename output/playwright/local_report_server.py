"""Synthetic-only browser QA server. Real analytics; read-only HTTP; no production startup."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from app.main import app as unused_application  # register model metadata, do not run startup
from app.database import Base, get_db
from app.dependencies import get_tenant_id
from app.models.tenant import Tenant
from app.models.truck import Truck
from app.models.settlement import Settlement
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.routers import analytics, trucks, repair_reserves
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from datetime import date
engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
Base.metadata.create_all(engine)
Session=sessionmaker(bind=engine)
analytics.get_historical_diesel_price=lambda *args: None
names=['October synthetic','Unpaid synthetic','Partial synthetic','Non-reserve synthetic','Negative reserve synthetic']
with Session() as db:
 for tenant_id,name in enumerate(names,1):
  db.add(Tenant(id=tenant_id,name=name,business_type='logistics'));db.flush()
  truck=Truck(tenant_id=tenant_id,name='QA 609',vehicle_type='truck')
  trailer=Truck(tenant_id=tenant_id,name='QA trailer',vehicle_type='trailer')
  db.add_all([truck,trailer]);db.flush()
  # Exact October-like combined saved totals; categories include support/custom already charged.
  db.add(Settlement(truck_id=truck.id,settlement_date=date(2026,10,5),week_start=date(2026,9,28),week_end=date(2026,10,4),gross_revenue=52296,expenses=44817.22,net_profit=7478.78,repair_reserve_amount=3200,trailer_income_split_amount=3200,miles_driven=10000,expense_categories={'fuel':44517.22 if tenant_id==4 else 44317.22,'fleet_manager_support':400,'custom':-100 if tenant_id==4 else 100}))
  db.add(Settlement(truck_id=trailer.id,settlement_date=date(2026,10,5),week_start=date(2026,9,28),week_end=date(2026,10,4),gross_revenue=3200,expenses=321.32,net_profit=2878.68,expense_categories={'loan_interest':321.32}))
  db.add(Repair(truck_id=truck.id,repair_date=date(2026,10,20),cost=8056.76,description=name+' invoice',paid_from_reserve=False))
  deposit=11970.08 if tenant_id==1 else 3200
  payment={1:8056.76,2:0,3:200,4:0,5:4000}[tenant_id]
  db.add(RepairReserveLedger(tenant_id=tenant_id,truck_id=truck.id,entry_date=date(2026,10,1),entry_type='deposit',amount=deposit,source_type='settlement',source_id=tenant_id))
  if payment:db.add(RepairReserveLedger(tenant_id=tenant_id,truck_id=truck.id,entry_date=date(2026,10,21),entry_type='withdrawal',amount=payment,source_type='dbn_payment',source_id=tenant_id))
 db.commit()
def get_synthetic_db():
 with Session() as db:yield db
app=FastAPI()
app.dependency_overrides[get_db]=get_synthetic_db
app.include_router(analytics.router,prefix='/api/analytics')
app.include_router(trucks.router,prefix='/api/trucks')
app.include_router(repair_reserves.router,prefix='/api/repair-reserves')
@app.middleware('http')
async def read_only(request,call_next):
 if request.method not in ['GET','HEAD']:return JSONResponse({'error':'QA server forbids writes'},status_code=405)
 return await call_next(request)
@app.get('/api/auth/me')
def auth():return {'username':'Synthetic QA'}
@app.get('/api/tenants')
@app.get('/api/tenants/')
def tenants():return [{'id':i,'name':n,'business_type':'logistics'} for i,n in enumerate(names,1)]
@app.get('/api/reserve-balances')
def reserves(request:Request):
 with Session() as db:return repair_reserves.get_reserve_balances(db,int(request.headers.get('X-Tenant-ID','1')))
@app.get('/api/qa/invariants')
def invariants():
 with Session() as db:return {'settlements':db.query(Settlement).count(),'repairs':db.query(Repair).count(),'ledger_entries':db.query(RepairReserveLedger).count()}
dist=Path(__file__).resolve().parents[2]/'frontend/dist'
app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
@app.get('/{path:path}')
def frontend(path:str):
 if path.startswith('api/'):return JSONResponse({'unhandled':path},status_code=404)
 return FileResponse(dist/'index.html')
