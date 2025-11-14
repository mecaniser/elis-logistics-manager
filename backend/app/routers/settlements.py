"""
Settlements router
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.schemas.settlement import SettlementCreate, SettlementResponse, SettlementUpdate
from app.utils.pdf_parser import parse_amazon_relay_pdf
import os
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/", response_model=List[SettlementResponse])
def get_settlements(
    truck_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get all settlements, optionally filtered by truck"""
    query = db.query(Settlement)
    if truck_id:
        query = query.filter(Settlement.truck_id == truck_id)
    return query.order_by(Settlement.settlement_date.desc()).all()

@router.post("/upload", response_model=SettlementResponse)
async def upload_settlement_pdf(
    file: UploadFile = File(...),
    truck_id: Optional[int] = Form(None),
    settlement_type: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload and parse Amazon Relay settlement PDF"""
    # Save uploaded file
    timestamp = datetime.now().timestamp()
    file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Parse PDF
    try:
        settlement_data = parse_amazon_relay_pdf(file_path, settlement_type)
        
        # Determine truck_id - use provided, or auto-detect from license plate
        if truck_id:
            settlement_data["truck_id"] = truck_id
        else:
            # Auto-detect truck from license plate
            license_plate = settlement_data.get("license_plate")
            if license_plate:
                # Try to find truck by current license plate
                truck = db.query(Truck).filter(Truck.license_plate == license_plate).first()
                if not truck and hasattr(Truck, 'license_plate_history'):
                    # Try to find in license plate history (if JSON column exists)
                    trucks = db.query(Truck).all()
                    for t in trucks:
                        if t.license_plate_history and license_plate in t.license_plate_history:
                            truck = t
                            break
                
                if truck:
                    settlement_data["truck_id"] = truck.id
                else:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Could not find truck with license plate '{license_plate}'. Please select a truck manually."
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract license plate from PDF. Please select a truck manually."
                )
        
        settlement_data["pdf_file_path"] = file_path
        if settlement_type:
            settlement_data["settlement_type"] = settlement_type
        
        # Check for duplicates
        existing = db.query(Settlement).filter(
            Settlement.truck_id == settlement_data["truck_id"],
            Settlement.settlement_date == settlement_data.get("settlement_date")
        ).first()
        
        if existing:
            # Clean up uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=400,
                detail=f"Settlement for truck ID {settlement_data['truck_id']} on {settlement_data.get('settlement_date')} already exists"
            )
        
        # Create settlement
        db_settlement = Settlement(**settlement_data)
        db.add(db_settlement)
        db.commit()
        db.refresh(db_settlement)
        return db_settlement
    except HTTPException:
        raise
    except Exception as e:
        # Clean up uploaded file on error
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")

@router.post("/upload-bulk")
async def upload_settlement_pdf_bulk(
    files: List[UploadFile] = File(...),
    truck_id: Optional[int] = Form(None),
    settlement_type: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload and parse multiple Amazon Relay settlement PDFs"""
    results = []
    successful = 0
    failed = 0
    
    for file in files:
        try:
            # Save uploaded file
            timestamp = datetime.now().timestamp()
            file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Parse PDF
            settlement_data = parse_amazon_relay_pdf(file_path, settlement_type)
            
            # Determine truck_id - use provided, or auto-detect from license plate
            if truck_id:
                settlement_data["truck_id"] = truck_id
            else:
                # Auto-detect truck from license plate
                license_plate = settlement_data.get("license_plate")
                if license_plate:
                    # Try to find truck by current license plate
                    truck = db.query(Truck).filter(Truck.license_plate == license_plate).first()
                    if not truck and hasattr(Truck, 'license_plate_history'):
                        # Try to find in license plate history
                        trucks = db.query(Truck).all()
                        for t in trucks:
                            if t.license_plate_history and license_plate in t.license_plate_history:
                                truck = t
                                break
                    
                    if truck:
                        settlement_data["truck_id"] = truck.id
                    else:
                        results.append({
                            "filename": file.filename,
                            "success": False,
                            "error": f"Could not find truck with license plate '{license_plate}'. Please select a truck manually."
                        })
                        failed += 1
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        continue
                else:
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "error": "Could not extract license plate from PDF. Please select a truck manually."
                    })
                    failed += 1
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    continue
            
            settlement_data["pdf_file_path"] = file_path
            if settlement_type:
                settlement_data["settlement_type"] = settlement_type
            
            # Check for duplicates
            existing = db.query(Settlement).filter(
                Settlement.truck_id == settlement_data["truck_id"],
                Settlement.settlement_date == settlement_data.get("settlement_date")
            ).first()
            
            if existing:
                # Clean up uploaded file
                if os.path.exists(file_path):
                    os.remove(file_path)
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": f"Settlement for truck ID {settlement_data['truck_id']} on {settlement_data.get('settlement_date')} already exists"
                })
                failed += 1
                continue
            
            # Create settlement
            db_settlement = Settlement(**settlement_data)
            db.add(db_settlement)
            db.commit()
            db.refresh(db_settlement)
            
            results.append({
                "filename": file.filename,
                "success": True,
                "settlement": db_settlement
            })
            successful += 1
            
        except HTTPException as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": e.detail
            })
            failed += 1
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": f"Failed to parse PDF: {str(e)}"
            })
            failed += 1
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
    
    return {
        "total": len(files),
        "successful": successful,
        "failed": failed,
        "results": results
    }

@router.post("/", response_model=SettlementResponse)
def create_settlement(settlement: SettlementCreate, db: Session = Depends(get_db)):
    """Manually create a settlement"""
    db_settlement = Settlement(**settlement.dict())
    db.add(db_settlement)
    db.commit()
    db.refresh(db_settlement)
    return db_settlement

@router.get("/{settlement_id}", response_model=SettlementResponse)
def get_settlement(settlement_id: int, db: Session = Depends(get_db)):
    """Get a specific settlement"""
    settlement = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    return settlement

@router.put("/{settlement_id}", response_model=SettlementResponse)
def update_settlement(
    settlement_id: int,
    settlement_update: SettlementUpdate,
    db: Session = Depends(get_db)
):
    """Update a settlement"""
    settlement = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    
    # Update settlement fields
    update_data = settlement_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settlement, field, value)
    
    db.commit()
    db.refresh(settlement)
    return settlement

@router.delete("/{settlement_id}")
def delete_settlement(settlement_id: int, db: Session = Depends(get_db)):
    """Delete a settlement"""
    settlement = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    
    # Delete PDF file if it exists
    if settlement.pdf_file_path and os.path.exists(settlement.pdf_file_path):
        try:
            os.remove(settlement.pdf_file_path)
        except Exception:
            pass  # Don't fail if file deletion fails
    
    db.delete(settlement)
    db.commit()
    return {"message": "Settlement deleted successfully"}

