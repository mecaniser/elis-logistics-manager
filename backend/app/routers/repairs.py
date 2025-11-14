"""
Repairs router
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import json
from datetime import datetime
from app.database import get_db
from app.models.repair import Repair
from app.models.truck import Truck
from app.schemas.repair import RepairCreate, RepairResponse, RepairUploadResponse, RepairUpdate
from app.utils.repair_invoice_parser import parse_repair_invoice_pdf

router = APIRouter()

# Upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/", response_model=List[RepairResponse])
def get_repairs(
    truck_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get all repairs, optionally filtered by truck"""
    query = db.query(Repair)
    if truck_id:
        query = query.filter(Repair.truck_id == truck_id)
    return query.order_by(Repair.repair_date.desc()).all()

@router.post("/", response_model=RepairResponse)
def create_repair(repair: RepairCreate, db: Session = Depends(get_db)):
    """Create a new repair expense"""
    db_repair = Repair(**repair.dict())
    db.add(db_repair)
    db.commit()
    db.refresh(db_repair)
    return db_repair

@router.get("/{repair_id}", response_model=RepairResponse)
def get_repair(repair_id: int, db: Session = Depends(get_db)):
    """Get a specific repair"""
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    return repair

@router.put("/{repair_id}", response_model=RepairResponse)
async def update_repair(
    repair_id: int,
    repair_update_json: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    """Update a repair, optionally adding new images"""
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    
    # Parse JSON data from form
    update_data = {}
    if repair_update_json:
        try:
            repair_data = json.loads(repair_update_json)
            # Create RepairUpdate object to validate
            repair_update = RepairUpdate(**repair_data)
            update_data = repair_update.model_dump(exclude_unset=True)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid repair data: {str(e)}")
    
    # Save new image files and add to existing images
    if images:
        existing_images = repair.image_paths if repair.image_paths else []
        new_image_paths = []
        
        for img in images:
            img_timestamp = datetime.now().timestamp()
            img_filename = f"{img_timestamp}_{img.filename}"
            img_path = os.path.join(UPLOAD_DIR, img_filename)
            with open(img_path, "wb") as img_buffer:
                img_content = await img.read()
                img_buffer.write(img_content)
            # Store relative path without "uploads/" prefix
            new_image_paths.append(img_filename)
        
        # Merge existing and new images
        update_data["image_paths"] = list(existing_images) + new_image_paths
    
    # Update only provided fields
    for field, value in update_data.items():
        setattr(repair, field, value)
    
    db.commit()
    db.refresh(repair)
    return repair

@router.post("/upload", response_model=RepairUploadResponse)
async def upload_repair_invoice(
    file: UploadFile = File(...),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    """Upload and parse repair invoice PDF. Truck is automatically identified by VIN."""
    # Save uploaded PDF file
    timestamp = datetime.now().timestamp()
    file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Parse PDF to extract repair data and VIN
    try:
        repair_data = parse_repair_invoice_pdf(file_path)
    except Exception as e:
        # Clean up uploaded file on error
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    
    # Extract VIN and find matching truck
    vin = repair_data.get("vin")
    if not vin:
        # Clean up uploaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(
            status_code=400,
            detail="Could not extract VIN number from invoice. Please ensure the invoice contains a VIN."
        )
    
    # Find truck by VIN (case-insensitive)
    truck = db.query(Truck).filter(Truck.vin.ilike(vin)).first()
    if not truck:
        # Clean up uploaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(
            status_code=404,
            detail=f"No truck found with VIN {vin}. Please ensure the truck is registered in the system."
        )
    
    # Check for duplicates before creating repair
    invoice_number = repair_data.get("invoice_number")
    repair_date = repair_data.get("repair_date")
    cost = repair_data.get("cost")
    
    # Method 1: Check by invoice number (most reliable if available)
    if invoice_number:
        existing_by_invoice = db.query(Repair).filter(
            Repair.truck_id == truck.id,
            Repair.invoice_number == invoice_number
        ).first()
        if existing_by_invoice:
            # Clean up uploaded file
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            raise HTTPException(
                status_code=400,
                detail=f"Repair with invoice number {invoice_number} for {truck.name} already exists (ID: {existing_by_invoice.id})."
            )
    
    # Method 2: Check by truck + date + cost (more reliable - exact match)
    # This catches duplicates even if invoice number wasn't extracted or differs
    if repair_date and cost:
        existing_by_details = db.query(Repair).filter(
            Repair.truck_id == truck.id,
            Repair.repair_date == repair_date,
            Repair.cost == cost
        ).first()
        if existing_by_details:
            # Clean up uploaded file
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            existing_date_str = existing_by_details.repair_date.strftime("%Y-%m-%d") if existing_by_details.repair_date else "unknown date"
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate repair detected: A repair for {truck.name} on {existing_date_str} with cost ${float(cost):.2f} already exists (ID: {existing_by_details.id})."
            )
    
    # Save image files
    image_paths = []
    if images:
        for img in images:
            img_timestamp = datetime.now().timestamp()
            img_filename = f"{img_timestamp}_{img.filename}"
            img_path = os.path.join(UPLOAD_DIR, img_filename)
            with open(img_path, "wb") as img_buffer:
                img_content = await img.read()
                img_buffer.write(img_content)
            # Store relative path without "uploads/" prefix (matches how settlements store paths)
            image_paths.append(img_filename)
    
    # Create repair record
    try:
        db_repair = Repair(
            truck_id=truck.id,
            repair_date=repair_data.get("repair_date"),
            description=repair_data.get("description"),
            category=repair_data.get("category"),
            cost=repair_data.get("cost"),
            receipt_path=os.path.basename(file_path),  # Store just filename, frontend adds /uploads/ prefix
            invoice_number=repair_data.get("invoice_number"),
            image_paths=image_paths if image_paths else None
        )
        db.add(db_repair)
        db.commit()
        db.refresh(db_repair)
        
        warning = None
        if not repair_data.get("repair_date"):
            warning = "Repair date could not be extracted from invoice. Please update manually."
        elif not repair_data.get("description"):
            warning = "Description could not be extracted from invoice. Please update manually."
        
        return RepairUploadResponse(repair=db_repair, warning=warning)
    except Exception as e:
        db.rollback()
        # Clean up uploaded files on error
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        for img_path in image_paths:
            full_path = os.path.join(os.path.dirname(UPLOAD_DIR), img_path)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except:
                    pass
        raise HTTPException(status_code=400, detail=f"Failed to create repair: {str(e)}")

@router.delete("/{repair_id}")
def delete_repair(repair_id: int, db: Session = Depends(get_db)):
    """Delete a repair"""
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    db.delete(repair)
    db.commit()
    return {"message": "Repair deleted successfully"}

