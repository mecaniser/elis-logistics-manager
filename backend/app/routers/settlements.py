"""
Settlements router
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.settlement import Settlement
from app.schemas.settlement import SettlementCreate, SettlementResponse
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
    truck_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and parse Amazon Relay settlement PDF"""
    # Save uploaded file
    file_path = os.path.join(UPLOAD_DIR, f"{truck_id}_{datetime.now().timestamp()}_{file.filename}")
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Parse PDF
    try:
        settlement_data = parse_amazon_relay_pdf(file_path)
        settlement_data["truck_id"] = truck_id
        settlement_data["pdf_file_path"] = file_path
        
        # Create settlement
        db_settlement = Settlement(**settlement_data)
        db.add(db_settlement)
        db.commit()
        db.refresh(db_settlement)
        return db_settlement
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")

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

