"""
Tenants router for multi-tenant management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter()

@router.get("", response_model=List[TenantResponse])
@router.get("/", response_model=List[TenantResponse])
def get_tenants(db: Session = Depends(get_db)):
    """Get all tenants"""
    return db.query(Tenant).order_by(Tenant.name).all()

@router.post("", response_model=TenantResponse)
@router.post("/", response_model=TenantResponse)
def create_tenant(tenant: TenantCreate, db: Session = Depends(get_db)):
    """Create a new tenant"""
    # Check for duplicate name
    existing = db.query(Tenant).filter(Tenant.name == tenant.name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Tenant with name '{tenant.name}' already exists"
        )
    
    db_tenant = Tenant(**tenant.model_dump())
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: int, db: Session = Depends(get_db)):
    """Get a specific tenant"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant

@router.put("/{tenant_id}", response_model=TenantResponse)
def update_tenant(tenant_id: int, tenant_update: TenantUpdate, db: Session = Depends(get_db)):
    """Update a tenant"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    update_data = tenant_update.model_dump(exclude_unset=True)
    if 'name' in update_data:
        # Check for duplicate name
        existing = db.query(Tenant).filter(
            Tenant.name == update_data['name'],
            Tenant.id != tenant_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Tenant with name '{update_data['name']}' already exists"
            )
    
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    db.commit()
    db.refresh(tenant)
    return tenant

@router.delete("/{tenant_id}")
def delete_tenant(tenant_id: int, db: Session = Depends(get_db)):
    """Delete a tenant and all associated data"""
    from app.models.truck import Truck
    from app.models.settlement import Settlement
    from app.models.repair import Repair
    from app.models.chart_of_accounts import ChartOfAccount
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Check if this is the last tenant
    total_tenants = db.query(Tenant).count()
    if total_tenants <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the last remaining tenant. At least one tenant must exist."
        )
    
    try:
        # Delete all related data in the correct order (respecting foreign key constraints)
        
        # 1. Delete journal entry lines first (they reference journal entries)
        journal_entries = db.query(JournalEntry).filter(JournalEntry.tenant_id == tenant_id).all()
        journal_entry_ids = [je.id for je in journal_entries]
        if journal_entry_ids:
            db.query(JournalEntryLine).filter(JournalEntryLine.journal_entry_id.in_(journal_entry_ids)).delete(synchronize_session=False)
        
        # 2. Delete journal entries
        db.query(JournalEntry).filter(JournalEntry.tenant_id == tenant_id).delete(synchronize_session=False)
        
        # 3. Delete chart of accounts
        db.query(ChartOfAccount).filter(ChartOfAccount.tenant_id == tenant_id).delete(synchronize_session=False)
        
        # 4. Get trucks for this tenant to delete related settlements and repairs
        trucks = db.query(Truck).filter(Truck.tenant_id == tenant_id).all()
        truck_ids = [truck.id for truck in trucks]
        
        # 5. Delete repairs (they reference trucks)
        if truck_ids:
            db.query(Repair).filter(Repair.truck_id.in_(truck_ids)).delete(synchronize_session=False)
        
        # 6. Delete settlements (they reference trucks)
        if truck_ids:
            db.query(Settlement).filter(Settlement.truck_id.in_(truck_ids)).delete(synchronize_session=False)
        
        # 7. Delete trucks
        db.query(Truck).filter(Truck.tenant_id == tenant_id).delete(synchronize_session=False)
        
        # 8. Finally, delete the tenant
        db.delete(tenant)
        db.commit()
        
        return {"message": f"Tenant '{tenant.name}' and all associated data deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete tenant: {str(e)}"
        )

