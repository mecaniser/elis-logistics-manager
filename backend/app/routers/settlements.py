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
from app.utils.pdf_parser import parse_amazon_relay_pdf, parse_amazon_relay_pdf_multi_truck
from app.utils.settlement_extractor import SettlementExtractor
import os
import json
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
    extract_only: Optional[bool] = Form(False),  # If True, extract to JSON and don't store PDF
    db: Session = Depends(get_db)
):
    """
    Upload and parse Amazon Relay settlement PDF.
    
    If extract_only=True, extracts data to JSON format and imports to database
    without storing the PDF file.
    """
    # Save uploaded file temporarily
    timestamp = datetime.now().timestamp()
    file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # If extract_only mode, use JSON extraction workflow
    if extract_only:
        try:
            extractor = SettlementExtractor()
            extracted_data = extractor.extract_from_pdf(file_path, settlement_type)
            
            # Convert to JSON string and import
            json_data = json.dumps(extracted_data)
            created_settlements = upload_settlement_json(json_data, db)
            
            # Clean up temporary PDF file
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            
            # Return first settlement (or only one)
            return created_settlements[0] if created_settlements else None
            
        except Exception as e:
            # Clean up temporary file on error
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            raise HTTPException(status_code=400, detail=f"Failed to extract and import: {str(e)}")
    
    # Parse PDF
    try:
        # Use multi-truck parser ONLY for NBM Transport LLC settlements (multiple trucks per PDF)
        # All other settlement types (e.g., "277 Logistics") have one truck per PDF - use single-truck parser
        if settlement_type and settlement_type.upper() == "NBM TRANSPORT LLC":
            settlements_data = parse_amazon_relay_pdf_multi_truck(file_path, settlement_type)
        else:
            # Single-truck parser for all other settlement types (277 Logistics, etc.)
            settlements_data = [parse_amazon_relay_pdf(file_path, settlement_type)]
        
        created_settlements = []
        
        for settlement_data in settlements_data:
            # Determine truck_id - use provided, or auto-detect from license plate
            if truck_id:
                settlement_data["truck_id"] = truck_id
            else:
                # Auto-detect truck from license plate (check both current and historic plates)
                license_plate = settlement_data.get("license_plate")
                if license_plate:
                    license_plate_upper = license_plate.upper()
                    # Try to find truck by current license plate
                    truck = db.query(Truck).filter(Truck.license_plate.ilike(license_plate_upper)).first()
                    if not truck:
                        # Try to find in license plate history
                        trucks = db.query(Truck).all()
                        for t in trucks:
                            # Check current plate (case insensitive)
                            if t.license_plate and t.license_plate.upper() == license_plate_upper:
                                truck = t
                                break
                            # Check historic plates
                            if t.license_plate_history:
                                if isinstance(t.license_plate_history, list):
                                    if any(plate.upper() == license_plate_upper for plate in t.license_plate_history if plate):
                                        truck = t
                                        break
                                elif isinstance(t.license_plate_history, dict):
                                    # Handle dict format if needed
                                    pass
                    
                    if truck:
                        settlement_data["truck_id"] = truck.id
                    else:
                        # For multi-truck PDFs, skip trucks we can't match instead of failing
                        if len(settlements_data) > 1:
                            continue
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Could not find truck with license plate '{license_plate}'. Please select a truck manually."
                        )
                else:
                    # For multi-truck PDFs, skip settlements without license plate
                    if len(settlements_data) > 1:
                        continue
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
                # For multi-truck PDFs, skip duplicates instead of failing
                if len(settlements_data) > 1:
                    continue
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
            created_settlements.append(db_settlement)
        
        if not created_settlements:
            raise HTTPException(
                status_code=400,
                detail="No valid settlements could be created from this PDF. Check that trucks exist and settlements aren't duplicates."
            )
        
        db.commit()
        
        # Refresh all created settlements
        for settlement in created_settlements:
            db.refresh(settlement)
        
        # Return the first settlement (or only one if single truck)
        return created_settlements[0]
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
            
            # Parse PDF - use multi-truck parser ONLY for NBM Transport LLC settlements (multiple trucks per PDF)
            # All other settlement types (e.g., "277 Logistics") have one truck per PDF - use single-truck parser
            if settlement_type and settlement_type.upper() == "NBM TRANSPORT LLC":
                settlements_data = parse_amazon_relay_pdf_multi_truck(file_path, settlement_type)
            else:
                # Single-truck parser for all other settlement types (277 Logistics, etc.)
                settlements_data = [parse_amazon_relay_pdf(file_path, settlement_type)]
            
            file_successful = 0
            file_failed = 0
            
            for settlement_data in settlements_data:
                try:
                    # Determine truck_id - use provided, or auto-detect from license plate
                    if truck_id:
                        settlement_data["truck_id"] = truck_id
                    else:
                        # Auto-detect truck from license plate (check both current and historic plates)
                        license_plate = settlement_data.get("license_plate")
                        if license_plate:
                            license_plate_upper = license_plate.upper()
                            # Try to find truck by current license plate
                            truck = db.query(Truck).filter(Truck.license_plate.ilike(license_plate_upper)).first()
                            if not truck:
                                # Try to find in license plate history
                                trucks = db.query(Truck).all()
                                for t in trucks:
                                    # Check current plate (case insensitive)
                                    if t.license_plate and t.license_plate.upper() == license_plate_upper:
                                        truck = t
                                        break
                                    # Check historic plates
                                    if t.license_plate_history:
                                        if isinstance(t.license_plate_history, list):
                                            if any(plate.upper() == license_plate_upper for plate in t.license_plate_history if plate):
                                                truck = t
                                                break
                                        elif isinstance(t.license_plate_history, dict):
                                            # Handle dict format if needed
                                            pass
                            
                            if truck:
                                settlement_data["truck_id"] = truck.id
                            else:
                                # For multi-truck PDFs, skip trucks we can't match
                                if len(settlements_data) > 1:
                                    file_failed += 1
                                    continue
                                results.append({
                                    "filename": file.filename,
                                    "success": False,
                                    "error": f"Could not find truck with license plate '{license_plate}'. Please select a truck manually."
                                })
                                file_failed += 1
                                continue
                        else:
                            # For multi-truck PDFs, skip settlements without license plate
                            if len(settlements_data) > 1:
                                file_failed += 1
                                continue
                            results.append({
                                "filename": file.filename,
                                "success": False,
                                "error": "Could not extract license plate from PDF. Please select a truck manually."
                            })
                            file_failed += 1
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
                        # For multi-truck PDFs, skip duplicates
                        if len(settlements_data) > 1:
                            file_failed += 1
                            continue
                        # Clean up uploaded file
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        results.append({
                            "filename": file.filename,
                            "success": False,
                            "error": f"Settlement for truck ID {settlement_data['truck_id']} on {settlement_data.get('settlement_date')} already exists"
                        })
                        file_failed += 1
                        continue
                    
                    # Create settlement
                    db_settlement = Settlement(**settlement_data)
                    db.add(db_settlement)
                    file_successful += 1
                except Exception as e:
                    file_failed += 1
                    if len(settlements_data) == 1:
                        results.append({
                            "filename": file.filename,
                            "success": False,
                            "error": str(e)
                        })
            
            # Commit all settlements for this file
            if file_successful > 0:
                db.commit()
                successful += file_successful
                if len(settlements_data) > 1:
                    results.append({
                        "filename": file.filename,
                        "success": True,
                        "settlements_created": file_successful,
                        "settlements_skipped": file_failed
                    })
                else:
                    results.append({
                        "filename": file.filename,
                        "success": True
                    })
            else:
                failed += file_failed
                if not any(r.get("filename") == file.filename and not r.get("success", True) for r in results):
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "error": "No valid settlements could be created from this PDF."
                    })
            
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

@router.post("/upload-json", response_model=List[SettlementResponse])
def upload_settlement_json(
    json_data: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Upload settlement data from JSON structure (extracted from PDFs).
    This allows importing pre-extracted JSON data without storing PDFs.
    
    JSON format should match the schema defined in settlement_json_schema.json
    """
    try:
        # Parse JSON
        data = json.loads(json_data)
        
        if "settlements" not in data:
            raise HTTPException(status_code=400, detail="JSON must contain 'settlements' array")
        
        created_settlements = []
        
        for settlement_json in data["settlements"]:
            # Convert JSON structure to database format
            metadata = settlement_json.get("metadata", {})
            revenue = settlement_json.get("revenue", {})
            expenses = settlement_json.get("expenses", {})
            metrics = settlement_json.get("metrics", {})
            driver_pay = settlement_json.get("driver_pay", {})
            
            # Parse dates
            settlement_date = None
            week_start = None
            week_end = None
            
            if metadata.get("settlement_date"):
                settlement_date = datetime.fromisoformat(metadata["settlement_date"]).date()
            if metadata.get("week_start"):
                week_start = datetime.fromisoformat(metadata["week_start"]).date()
            if metadata.get("week_end"):
                week_end = datetime.fromisoformat(metadata["week_end"]).date()
            
            # Determine truck_id from license plate
            license_plate = metadata.get("license_plate")
            truck_id = None
            
            if license_plate:
                # Try exact match first
                truck = db.query(Truck).filter(Truck.license_plate == license_plate).first()
                
                # If not found, check license plate history (stored as JSON array)
                if not truck:
                    trucks = db.query(Truck).all()
                    for t in trucks:
                        history = t.license_plate_history
                        if isinstance(history, str):
                            try:
                                import json
                                history = json.loads(history)
                            except:
                                history = []
                        elif history is None:
                            history = []
                        
                        if license_plate in history or license_plate == t.license_plate:
                            truck = t
                            break
                
                if truck:
                    truck_id = truck.id
            
            if not truck_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not find truck with license plate '{license_plate}'. Please ensure truck exists."
                )
            
            # Build expense categories
            expense_categories = expenses.get("categories", {})
            if driver_pay.get("driver_pay"):
                expense_categories["driver_pay"] = driver_pay["driver_pay"]
            if driver_pay.get("payroll_fee"):
                expense_categories["payroll_fee"] = driver_pay["payroll_fee"]
            
            # Check for duplicates
            if settlement_date:
                existing = db.query(Settlement).filter(
                    Settlement.truck_id == truck_id,
                    Settlement.settlement_date == settlement_date
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Settlement for truck ID {truck_id} on {settlement_date} already exists"
                    )
            
            # Create settlement record (without PDF file path)
            settlement_data = {
                "truck_id": truck_id,
                "driver_id": metadata.get("driver_id"),
                "settlement_date": settlement_date,
                "week_start": week_start,
                "week_end": week_end,
                "miles_driven": metrics.get("miles_driven"),
                "blocks_delivered": metrics.get("blocks_delivered"),
                "gross_revenue": revenue.get("gross_revenue"),
                "expenses": expenses.get("total_expenses"),
                "expense_categories": expense_categories,
                "net_profit": revenue.get("net_profit"),
                "license_plate": license_plate,
                "settlement_type": metadata.get("settlement_type") or data.get("settlement_type"),
                "pdf_file_path": None  # No PDF stored
            }
            
            db_settlement = Settlement(**settlement_data)
            db.add(db_settlement)
            created_settlements.append(db_settlement)
        
        db.commit()
        
        # Refresh all created settlements
        for settlement in created_settlements:
            db.refresh(settlement)
        
        return created_settlements
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process JSON: {str(e)}")

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

