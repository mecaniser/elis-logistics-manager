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
    """Delete a tenant"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # TODO: Check if tenant has any data (trucks, settlements, etc.) before deletion
    # For now, allow deletion but warn about cascading
    
    db.delete(tenant)
    db.commit()
    return {"message": "Tenant deleted successfully"}

