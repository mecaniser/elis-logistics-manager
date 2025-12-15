"""
Settlements router
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.database import get_db
from app.dependencies import get_tenant_id
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.models.repair import Repair
from app.schemas.settlement import SettlementCreate, SettlementResponse, SettlementUpdate
from app.utils.pdf_parser import parse_amazon_relay_pdf, parse_amazon_relay_pdf_multi_truck
from app.utils.settlement_extractor import SettlementExtractor
from app.utils.cloudinary import upload_pdf
from app.utils.loan_interest import calculate_weekly_loan_interest, calculate_principal_payment
from app.utils.block_id_validator import validate_block_ids
from app.services.accounting_service import create_settlement_journal_entry, delete_settlement_journal_entry
import os
import json
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def update_loan_balance_after_settlement(truck_id: int, db: Session):
    """
    Update current_loan_balance after a settlement is created.
    Principal payments only apply after cash investment is 100% recovered.
    """
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck or truck.vehicle_type != 'truck':
        return
    
    cash_investment = float(truck.cash_investment) if truck.cash_investment else None
    if not cash_investment or cash_investment <= 0:
        return
    
    # Get current loan balance (use loan_amount if current_loan_balance is None)
    current_balance = float(truck.current_loan_balance) if truck.current_loan_balance is not None else (float(truck.loan_amount) if truck.loan_amount else None)
    if not current_balance or current_balance <= 0:
        return
    
    # Calculate cumulative net profit
    settlements = db.query(Settlement).filter(Settlement.truck_id == truck_id)
    repairs = db.query(Repair).filter(Repair.truck_id == truck_id)
    
    revenue = settlements.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    settlement_expenses = settlements.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    repair_costs = repairs.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    cumulative_net_profit = float(revenue) - float(settlement_expenses) - float(repair_costs)
    
    # Calculate principal payment
    principal_payment, new_loan_balance = calculate_principal_payment(
        cumulative_net_profit,
        cash_investment,
        current_balance
    )
    
    # Update truck's current_loan_balance
    if principal_payment > 0:
        truck.current_loan_balance = new_loan_balance
        db.commit()

@router.get("/duplicate-block-ids")
def get_duplicate_block_ids(db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """
    Find all duplicate block IDs across settlements.
    Returns a report of which block IDs appear in multiple settlements.
    """
    from app.utils.block_id_validator import extract_block_ids
    from collections import defaultdict
    
    # Get all settlements with block_ids for current tenant
    settlements = db.query(Settlement).join(Truck).filter(
        Truck.tenant_id == tenant_id,
        Settlement.block_ids.isnot(None)
    ).all()
    
    # Map block_id -> list of settlements containing it
    block_id_to_settlements = defaultdict(list)
    
    for settlement in settlements:
        block_ids = extract_block_ids(settlement.block_ids)
        for block_id in block_ids:
            block_id_to_settlements[block_id].append({
                "settlement_id": settlement.id,
                "truck_id": settlement.truck_id,
                "settlement_date": str(settlement.settlement_date) if settlement.settlement_date else None,
            })
    
    # Filter to only duplicates (appearing in 2+ settlements)
    duplicates = {
        block_id: settlements_list
        for block_id, settlements_list in block_id_to_settlements.items()
        if len(settlements_list) > 1
    }
    
    return {
        "total_duplicate_block_ids": len(duplicates),
        "duplicates": duplicates
    }

@router.get("", response_model=List[SettlementResponse])
@router.get("/", response_model=List[SettlementResponse])
def get_settlements(
    truck_id: Optional[int] = None,
    skip: Optional[int] = 0,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Get all settlements for the current tenant, optionally filtered by truck, with pagination support"""
    try:
        # Filter settlements through trucks by tenant_id
        query = db.query(Settlement).join(Truck).filter(Truck.tenant_id == tenant_id)
        if truck_id:
            # Also verify truck belongs to tenant
            truck = db.query(Truck).filter(Truck.id == truck_id, Truck.tenant_id == tenant_id).first()
            if not truck:
                raise HTTPException(status_code=404, detail="Truck not found")
            query = query.filter(Settlement.truck_id == truck_id)
        query = query.order_by(Settlement.settlement_date.desc())
        
        # Apply pagination
        if skip:
            query = query.offset(skip)
        if limit:
            query = query.limit(limit)
        
        settlements = query.all()
        return settlements
    except Exception as e:
        import traceback
        error_detail = f"Error fetching settlements: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

@router.post("/upload", response_model=SettlementResponse)
async def upload_settlement_pdf(
    file: UploadFile = File(...),
    truck_id: Optional[int] = Form(None),
    settlement_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Upload and parse Amazon Relay settlement PDF.
    Always extracts data, stores PDF in Cloudinary, and creates settlement records.
    """
    # Save uploaded file temporarily
    timestamp = datetime.now().timestamp()
    file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
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
            
            # Upload PDF to Cloudinary or keep local path
            pdf_path = None
            if os.path.exists(file_path):
                with open(file_path, "rb") as pdf_file:
                    pdf_content = pdf_file.read()
                    pdf_filename = os.path.basename(file_path)
                    
                    # Try Cloudinary upload first
                    cloudinary_pdf_url = upload_pdf(pdf_content, pdf_filename, folder="settlements")
                    
                    if cloudinary_pdf_url:
                        # Store Cloudinary URL
                        pdf_path = cloudinary_pdf_url
                        # Keep local file for now (will be cleaned up after commit)
                    else:
                        # Fallback to local storage if Cloudinary not configured
                        pdf_path = file_path
            
            settlement_data["pdf_file_path"] = pdf_path
            if settlement_type:
                settlement_data["settlement_type"] = settlement_type
            
            # Remove driver_name if present (not a valid Settlement field)
            settlement_data.pop("driver_name", None)
            
            # Calculate and add loan interest to expense_categories
            truck = db.query(Truck).filter(Truck.id == settlement_data["truck_id"]).first()
            if truck and truck.vehicle_type == 'truck':
                # Use current_loan_balance if available, otherwise use loan_amount
                current_balance = float(truck.current_loan_balance) if truck.current_loan_balance is not None else (float(truck.loan_amount) if truck.loan_amount else None)
                interest_rate = float(truck.interest_rate) if truck.interest_rate else 0.07
                
                if current_balance and current_balance > 0:
                    weekly_interest = calculate_weekly_loan_interest(current_balance, interest_rate)
                    
                    # Initialize expense_categories if not present
                    if "expense_categories" not in settlement_data or not settlement_data["expense_categories"]:
                        settlement_data["expense_categories"] = {}
                    
                    # Ensure expense_categories is a dict
                    if not isinstance(settlement_data["expense_categories"], dict):
                        settlement_data["expense_categories"] = {}
                    
                    # Add loan interest to expense categories
                    settlement_data["expense_categories"]["loan_interest"] = weekly_interest
                    
                    # Update total expenses to include interest
                    current_expenses = float(settlement_data.get("expenses", 0) or 0)
                    settlement_data["expenses"] = current_expenses + weekly_interest
                    
                    # Recalculate net profit
                    revenue = float(settlement_data.get("gross_revenue", 0) or 0)
                    settlement_data["net_profit"] = revenue - settlement_data["expenses"]
            
            # Check for duplicate settlement (same truck + date)
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
            
            # Check for duplicate block IDs (flag but don't reject)
            has_duplicates, warning_msg, duplicates = validate_block_ids(
                settlement_data.get("block_ids"),
                db
            )
            
            # Store duplicate warning if found
            if has_duplicates:
                duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
                settlement_data["duplicate_block_ids_warning"] = {
                    "has_duplicates": True,
                    "duplicate_block_ids": duplicate_block_ids,
                    "conflicting_settlements": duplicates,
                    "warning_message": warning_msg
                }
            else:
                settlement_data["duplicate_block_ids_warning"] = None
            
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
        
        # Create accounting journal entries for settlements
        for settlement in created_settlements:
            try:
                create_settlement_journal_entry(db, settlement)
            except Exception as e:
                # Log error but don't fail settlement creation
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create journal entry for settlement {settlement.id}: {str(e)}")
        
        # Clean up local PDF file if it was uploaded to Cloudinary
        # (Only delete if all settlements were created successfully and PDF is in Cloudinary)
        if os.path.exists(file_path):
            # Check if PDF was uploaded to Cloudinary (URL starts with http/https)
            first_settlement = created_settlements[0]
            if first_settlement.pdf_file_path and (first_settlement.pdf_file_path.startswith("http://") or first_settlement.pdf_file_path.startswith("https://")):
                try:
                    os.remove(file_path)
                except:
                    pass
        
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
            file_settlements = []  # Track settlements created for this file
            
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
                    
                    # Upload PDF to Cloudinary or keep local path
                    pdf_path = None
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as pdf_file:
                            pdf_content = pdf_file.read()
                            pdf_filename = os.path.basename(file_path)
                            
                            # Try Cloudinary upload first
                            cloudinary_pdf_url = upload_pdf(pdf_content, pdf_filename, folder="settlements")
                            
                            if cloudinary_pdf_url:
                                # Store Cloudinary URL
                                pdf_path = cloudinary_pdf_url
                            else:
                                # Fallback to local storage if Cloudinary not configured
                                pdf_path = file_path
                    
                    settlement_data["pdf_file_path"] = pdf_path
                    if settlement_type:
                        settlement_data["settlement_type"] = settlement_type
                    
                    # Remove driver_name if present (not a valid Settlement field)
                    settlement_data.pop("driver_name", None)
                    
                    # Calculate and add loan interest to expense_categories
                    truck = db.query(Truck).filter(Truck.id == settlement_data["truck_id"]).first()
                    if truck and truck.vehicle_type == 'truck':
                        # Use current_loan_balance if available, otherwise use loan_amount
                        current_balance = float(truck.current_loan_balance) if truck.current_loan_balance is not None else (float(truck.loan_amount) if truck.loan_amount else None)
                        interest_rate = float(truck.interest_rate) if truck.interest_rate else 0.07
                        
                        if current_balance and current_balance > 0:
                            weekly_interest = calculate_weekly_loan_interest(current_balance, interest_rate)
                            
                            # Initialize expense_categories if not present
                            if "expense_categories" not in settlement_data or not settlement_data["expense_categories"]:
                                settlement_data["expense_categories"] = {}
                            
                            # Ensure expense_categories is a dict
                            if not isinstance(settlement_data["expense_categories"], dict):
                                settlement_data["expense_categories"] = {}
                            
                            # Add loan interest to expense categories
                            settlement_data["expense_categories"]["loan_interest"] = weekly_interest
                            
                            # Update total expenses to include interest
                            current_expenses = float(settlement_data.get("expenses", 0) or 0)
                            settlement_data["expenses"] = current_expenses + weekly_interest
                            
                            # Recalculate net profit
                            revenue = float(settlement_data.get("gross_revenue", 0) or 0)
                            settlement_data["net_profit"] = revenue - settlement_data["expenses"]
                    
                    # Check for duplicate settlement (same truck + date)
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
                    
                    # Check for duplicate block IDs (flag but don't reject)
                    has_duplicates, warning_msg, duplicates = validate_block_ids(
                        settlement_data.get("block_ids"),
                        db
                    )
                    
                    # Store duplicate warning if found
                    if has_duplicates:
                        duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
                        settlement_data["duplicate_block_ids_warning"] = {
                            "has_duplicates": True,
                            "duplicate_block_ids": duplicate_block_ids,
                            "conflicting_settlements": duplicates,
                            "warning_message": warning_msg
                        }
                    else:
                        settlement_data["duplicate_block_ids_warning"] = None
                    
                    # Create settlement
                    db_settlement = Settlement(**settlement_data)
                    db.add(db_settlement)
                    file_settlements.append(db_settlement)  # Track for loan balance update
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
                # Refresh settlements to get IDs
                for settlement in file_settlements:
                    db.refresh(settlement)
                # Create accounting journal entries
                for settlement in file_settlements:
                    try:
                        create_settlement_journal_entry(db, settlement)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to create journal entry for settlement {settlement.id}: {str(e)}")
                # Update loan balances for trucks after settlements are created
                truck_ids_updated = set()
                for settlement in file_settlements:
                    if settlement.truck_id not in truck_ids_updated:
                        update_loan_balance_after_settlement(settlement.truck_id, db)
                        truck_ids_updated.add(settlement.truck_id)
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

@router.post("", response_model=SettlementResponse)
@router.post("/", response_model=SettlementResponse)
def create_settlement(settlement: SettlementCreate, db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Manually create a settlement"""
    try:
        # Check if truck exists and belongs to tenant
        from app.models.truck import Truck
        truck = db.query(Truck).filter(Truck.id == settlement.truck_id, Truck.tenant_id == tenant_id).first()
        if not truck:
            raise HTTPException(status_code=400, detail=f"Truck with ID {settlement.truck_id} not found")
        
        # Check for duplicate settlement
        existing = db.query(Settlement).filter(
            Settlement.truck_id == settlement.truck_id,
            Settlement.settlement_date == settlement.settlement_date
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Settlement for truck ID {settlement.truck_id} on {settlement.settlement_date} already exists"
            )
        
        # Check for duplicate block IDs (flag but don't reject)
        has_duplicates, warning_msg, duplicates = validate_block_ids(
            settlement.block_ids,
            db
        )
        
        # Use model_dump() for Pydantic v2
        settlement_dict = settlement.model_dump()
        
        # Store duplicate warning if found
        if has_duplicates:
            duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
            settlement_dict["duplicate_block_ids_warning"] = {
                "has_duplicates": True,
                "duplicate_block_ids": duplicate_block_ids,
                "conflicting_settlements": duplicates,
                "warning_message": warning_msg
            }
        else:
            settlement_dict["duplicate_block_ids_warning"] = None
        
        # Calculate and add loan interest to expense_categories
        if truck.vehicle_type == 'truck':
            # Use current_loan_balance if available, otherwise use loan_amount
            current_balance = float(truck.current_loan_balance) if truck.current_loan_balance is not None else (float(truck.loan_amount) if truck.loan_amount else None)
            interest_rate = float(truck.interest_rate) if truck.interest_rate else 0.07
            
            if current_balance and current_balance > 0:
                weekly_interest = calculate_weekly_loan_interest(current_balance, interest_rate)
                
                # Initialize expense_categories if not present
                if "expense_categories" not in settlement_dict or not settlement_dict["expense_categories"]:
                    settlement_dict["expense_categories"] = {}
                
                # Ensure expense_categories is a dict
                if not isinstance(settlement_dict["expense_categories"], dict):
                    settlement_dict["expense_categories"] = {}
                
                # Add loan interest to expense categories
                settlement_dict["expense_categories"]["loan_interest"] = weekly_interest
                
                # Update total expenses to include interest
                current_expenses = float(settlement_dict.get("expenses", 0) or 0)
                settlement_dict["expenses"] = current_expenses + weekly_interest
                
                # Recalculate net profit
                revenue = float(settlement_dict.get("gross_revenue", 0) or 0)
                settlement_dict["net_profit"] = revenue - settlement_dict["expenses"]
        
        db_settlement = Settlement(**settlement_dict)
        db.add(db_settlement)
        db.commit()
        
        # Update loan balance if cash investment is recovered
        update_loan_balance_after_settlement(truck.id, db)
        
        # Create accounting journal entry
        try:
            create_settlement_journal_entry(db, db_settlement)
        except Exception as e:
            # Log error but don't fail settlement creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create journal entry for settlement {db_settlement.id}: {str(e)}")
        
        db.refresh(db_settlement)
        return db_settlement
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create settlement: {str(e)}")

@router.get("/{settlement_id}", response_model=SettlementResponse)
def get_settlement(settlement_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Get a specific settlement"""
    settlement = db.query(Settlement).join(Truck).filter(
        Settlement.id == settlement_id,
        Truck.tenant_id == tenant_id
    ).first()
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    return settlement

@router.put("/{settlement_id}", response_model=SettlementResponse)
async def update_settlement(
    settlement_id: int,
    settlement_update: Optional[SettlementUpdate] = None,
    settlement_update_json: Optional[str] = Form(None),
    pdf_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Update a settlement with optional PDF file upload.
    Accepts either JSON body (settlement_update) or Form data with JSON string (settlement_update_json).
    When uploading a PDF file, use Form data with settlement_update_json.
    """
    settlement = db.query(Settlement).join(Truck).filter(
        Settlement.id == settlement_id,
        Truck.tenant_id == tenant_id
    ).first()
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    
    # Parse settlement update data
    update_data = {}
    if settlement_update_json:
        # Parse JSON from Form field (used when file is uploaded)
        try:
            settlement_data = json.loads(settlement_update_json)
            settlement_update_obj = SettlementUpdate(**settlement_data)
            update_data = settlement_update_obj.model_dump(exclude_unset=True)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid settlement data: {str(e)}")
    elif settlement_update:
        # Use Pydantic model directly (used when no file is uploaded)
        update_data = settlement_update.model_dump(exclude_unset=True)
    # If both are None but pdf_file is provided, that's okay - we'll just update the PDF
    # If all are None, that's also okay - endpoint will just return the settlement unchanged
    
    # Handle PDF file upload if provided
    if pdf_file:
        # Save uploaded file temporarily
        timestamp = datetime.now().timestamp()
        file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{pdf_file.filename}")
        with open(file_path, "wb") as buffer:
            content = await pdf_file.read()
            buffer.write(content)
        
        # Upload PDF to Cloudinary or keep local path
        pdf_path = None
        if os.path.exists(file_path):
            with open(file_path, "rb") as pdf_file_handle:
                pdf_content = pdf_file_handle.read()
                pdf_filename = os.path.basename(file_path)
                
                # Try Cloudinary upload first
                cloudinary_pdf_url = upload_pdf(pdf_content, pdf_filename, folder="settlements")
                
                if cloudinary_pdf_url:
                    # Store Cloudinary URL
                    pdf_path = cloudinary_pdf_url
                else:
                    # Fallback to local storage if Cloudinary not configured
                    pdf_path = file_path
        
        # Update pdf_file_path in settlement
        if pdf_path:
            update_data["pdf_file_path"] = pdf_path
    
    # Check for duplicate block IDs if block_ids are being updated (flag but don't reject)
    if "block_ids" in update_data:
        has_duplicates, warning_msg, duplicates = validate_block_ids(
            update_data["block_ids"],
            db,
            exclude_settlement_id=settlement.id
        )
        
        # Store duplicate warning if found
        if has_duplicates:
            duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
            update_data["duplicate_block_ids_warning"] = {
                "has_duplicates": True,
                "duplicate_block_ids": duplicate_block_ids,
                "conflicting_settlements": duplicates,
                "warning_message": warning_msg
            }
        else:
            update_data["duplicate_block_ids_warning"] = None
    
    # Update settlement fields
    for field, value in update_data.items():
        setattr(settlement, field, value)
    
    db.commit()
    db.refresh(settlement)
    
    # Update accounting journal entry (delete old, create new)
    try:
        delete_settlement_journal_entry(db, settlement.id)
        create_settlement_journal_entry(db, settlement)
    except Exception as e:
        # Log error but don't fail settlement update
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to update journal entry for settlement {settlement.id}: {str(e)}")
    
    return settlement

@router.post("/upload-consolidated")
def upload_consolidated_settlements(
    json_data: str = Form(...),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db)
):
    """
    Upload consolidated settlement JSON files (format used by ingest_consolidated_settlements.py).
    
    This endpoint accepts the consolidated JSON format where each entry can have:
    - A single "statement" object, OR
    - A "statements" array
    
    Each statement includes block_ids with delivery_date information.
    
    Format example:
    [
      {
        "unit_number": "418",
        "plate_number": "VW1503",
        "statement": { ... },
        "block_ids": [{"block_id": "ABC-123", "delivery_date": "2024-12-27"}],
        "statement_totals": { ... }
      },
      {
        "unit_number": "418",
        "plate_number": "VW1503",
        "statements": [
          {
            "statement": { ... },
            "block_ids": [{"block_id": "XYZ-456", "delivery_date": "2024-12-28"}],
            "statement_totals": { ... }
          }
        ]
      }
    ]
    """
    try:
        from app.utils.loan_interest import calculate_weekly_loan_interest
        from datetime import date
        
        # Parse JSON
        data = json.loads(json_data)
        
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="JSON must be an array of settlement entries")
        
        created_settlements = []
        updated_settlements = []
        would_create_count = 0
        would_update_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        
        def parse_date(value):
            """Parse date string to date object"""
            if not value:
                return None
            try:
                parts = [int(p) for p in value.split("-")]
                if len(parts) == 3:
                    return date(parts[0], parts[1], parts[2])
            except Exception:
                return None
            return None
        
        def map_truck(unit_number, plate_number):
            """Resolve truck_id using plate or unit number"""
            if plate_number:
                truck = db.query(Truck).filter(Truck.license_plate == plate_number).first()
                if truck:
                    return truck.id
                
                # Check license plate history
                trucks = db.query(Truck).filter(Truck.license_plate_history.isnot(None)).all()
                for truck in trucks:
                    history = truck.license_plate_history or []
                    if plate_number in history:
                        return truck.id
            
            if unit_number:
                truck = db.query(Truck).filter(Truck.name == unit_number).first()
                if truck:
                    return truck.id
                
                truck = db.query(Truck).filter(Truck.name == f"Volvo {unit_number}").first()
                if truck:
                    return truck.id
            
            return None
        
        def normalize_expense_categories(totals):
            """Build expense_categories from statement_totals"""
            cat_map = {
                "driver_pay": totals.get("total_driver_pay", 0) or 0,
                "fuel": totals.get("fuel", totals.get("total_fuel", 0)) or 0,
                "dispatch_fee": totals.get("dispatch_fee_total", 0) or 0,
                "payroll_fee": totals.get("driver_payroll_fee", 0) or 0,
                "ifta": totals.get("ifta", 0) or 0,
                "safety": totals.get("safety", 0) or 0,
                "prepass": totals.get("prepass", 0) or 0,
                "insurance": totals.get("insurance", 0) or 0,
                "service_on_truck": totals.get("service_on_truck", 0) or 0,
                "truck_parking": totals.get("truck_parking", 0) or 0,
                "decals": totals.get("decals", 0) or 0,
                "deduct": totals.get("deductions", 0) or 0,
            }
            reimbursement = totals.get("reimbursment", 0) or totals.get("reimbursement", 0) or 0
            
            expense_categories = {k: float(v) for k, v in cat_map.items() if v}
            if reimbursement:
                expense_categories["reimbursement"] = float(reimbursement)
            
            total_expenses = sum(v for k, v in expense_categories.items() if k != "reimbursement") - float(reimbursement)
            return expense_categories, total_expenses
        
        def process_entry(entry):
            """Process a single settlement entry"""
            totals = entry.get("statement_totals") or {}
            statement = entry.get("statement") or {}
            
            gross_revenue = totals.get("gross_revenue")
            net_profit = totals.get("net_to_owner")
            if gross_revenue is None and net_profit is None:
                return None
            
            truck_id = map_truck(entry.get("unit_number"), entry.get("plate_number"))
            if not truck_id:
                return {"error": f"Could not find truck for unit {entry.get('unit_number')}, plate {entry.get('plate_number')}"}
            
            settlement_date = parse_date(statement.get("period_end"))
            week_start = parse_date(statement.get("period_start"))
            week_end = parse_date(statement.get("period_end"))
            
            expense_categories, calculated_expenses = normalize_expense_categories(totals)
            
            # Calculate loan interest
            weekly_interest = 0.0
            truck = db.query(Truck).filter(Truck.id == truck_id).first()
            if truck and truck.vehicle_type == 'truck':
                current_balance = float(truck.current_loan_balance) if truck.current_loan_balance is not None else (float(truck.loan_amount) if truck.loan_amount else None)
                interest_rate = float(truck.interest_rate) if truck.interest_rate else 0.07
                
                if current_balance and current_balance > 0:
                    weekly_interest = calculate_weekly_loan_interest(current_balance, interest_rate)
                    expense_categories["loan_interest"] = weekly_interest
            
            # Extract block_ids (already in correct format with delivery_date)
            block_ids = entry.get("block_ids")
            blocks_delivered = entry.get("blocks_count")
            miles_driven = totals.get("gross_miles")
            license_plate = entry.get("plate_number")
            pdf_file_path = statement.get("source_file")
            
            # Calculate expenses and net profit
            if net_profit is not None:
                base_expenses = float(gross_revenue or 0) - float(net_profit)
                final_expenses = base_expenses + weekly_interest
                final_net_profit = float(net_profit) - weekly_interest
            else:
                final_expenses = calculated_expenses + weekly_interest
                final_net_profit = float(gross_revenue or 0) - final_expenses
            
            return {
                "truck_id": truck_id,
                "settlement_date": settlement_date,
                "week_start": week_start,
                "week_end": week_end,
                "miles_driven": float(miles_driven) if miles_driven is not None else None,
                "blocks_delivered": int(blocks_delivered) if blocks_delivered is not None else None,
                "block_ids": block_ids if block_ids else None,
                "gross_revenue": float(gross_revenue or 0),
                "expenses": float(final_expenses),
                "expense_categories": expense_categories,
                "net_profit": final_net_profit,
                "pdf_file_path": pdf_file_path,
                "license_plate": license_plate,
            }
        
        # Process all entries
        for idx, item in enumerate(data, 1):
            try:
                # Handle flat structure (single statement)
                if "statement_totals" in item:
                    entry_data = process_entry(item)
                    if entry_data and "error" in entry_data:
                        error_count += 1
                        errors.append(f"Entry {idx}: {entry_data['error']}")
                        continue
                    if not entry_data:
                        skipped_count += 1
                        continue
                    
                    # Check for duplicate settlement (same truck + date)
                    existing = db.query(Settlement).filter(
                        Settlement.truck_id == entry_data["truck_id"],
                        Settlement.settlement_date == entry_data["settlement_date"]
                    ).first()
                    
                    if existing:
                        if not dry_run:
                            # Check for duplicate block IDs (flag but don't reject)
                            has_duplicates, warning_msg, duplicates = validate_block_ids(
                                entry_data.get("block_ids"),
                                db,
                                exclude_settlement_id=existing.id
                            )
                            
                            # Store duplicate warning if found
                            if has_duplicates:
                                duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
                                entry_data["duplicate_block_ids_warning"] = {
                                    "has_duplicates": True,
                                    "duplicate_block_ids": duplicate_block_ids,
                                    "conflicting_settlements": duplicates,
                                    "warning_message": warning_msg
                                }
                            else:
                                entry_data["duplicate_block_ids_warning"] = None
                            
                            # Update existing
                            for k, v in entry_data.items():
                                setattr(existing, k, v)
                            db.add(existing)
                            updated_settlements.append(existing)
                        else:
                            would_update_count += 1
                    else:
                        # Check for duplicate block IDs (flag but don't reject)
                        has_duplicates, warning_msg, duplicates = validate_block_ids(
                            entry_data.get("block_ids"),
                            db
                        )
                        
                        # Store duplicate warning if found
                        if has_duplicates:
                            duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
                            entry_data["duplicate_block_ids_warning"] = {
                                "has_duplicates": True,
                                "duplicate_block_ids": duplicate_block_ids,
                                "conflicting_settlements": duplicates,
                                "warning_message": warning_msg
                            }
                        else:
                            entry_data["duplicate_block_ids_warning"] = None
                        
                        if not dry_run:
                            db_settlement = Settlement(**entry_data)
                            db.add(db_settlement)
                            created_settlements.append(db_settlement)
                        else:
                            would_create_count += 1
                
                # Handle nested structure (statements array)
                elif "statements" in item:
                    for st in item.get("statements", []):
                        merged = {
                            "unit_number": item.get("unit_number"),
                            "plate_number": item.get("plate_number"),
                            "statement": st.get("statement"),
                            "statement_totals": st.get("statement_totals"),
                            "blocks_count": st.get("blocks_count"),
                            "block_ids": st.get("block_ids"),
                        }
                        entry_data = process_entry(merged)
                        if entry_data and "error" in entry_data:
                            error_count += 1
                            errors.append(f"Entry {idx}: {entry_data['error']}")
                            continue
                        if not entry_data:
                            skipped_count += 1
                            continue
                        
                        # Check for duplicate settlement (same truck + date)
                        existing = db.query(Settlement).filter(
                            Settlement.truck_id == entry_data["truck_id"],
                            Settlement.settlement_date == entry_data["settlement_date"]
                        ).first()
                        
                        if existing:
                            if not dry_run:
                                # Check for duplicate block IDs (flag but don't reject)
                                has_duplicates, warning_msg, duplicates = validate_block_ids(
                                    entry_data.get("block_ids"),
                                    db,
                                    exclude_settlement_id=existing.id
                                )
                                
                                # Store duplicate warning if found
                                if has_duplicates:
                                    duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
                                    entry_data["duplicate_block_ids_warning"] = {
                                        "has_duplicates": True,
                                        "duplicate_block_ids": duplicate_block_ids,
                                        "conflicting_settlements": duplicates,
                                        "warning_message": warning_msg
                                    }
                                else:
                                    entry_data["duplicate_block_ids_warning"] = None
                                
                                for k, v in entry_data.items():
                                    setattr(existing, k, v)
                                db.add(existing)
                                updated_settlements.append(existing)
                            else:
                                would_update_count += 1
                        else:
                            # Check for duplicate block IDs (flag but don't reject)
                            has_duplicates, warning_msg, duplicates = validate_block_ids(
                                entry_data.get("block_ids"),
                                db
                            )
                            
                            # Store duplicate warning if found
                            if has_duplicates:
                                duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
                                entry_data["duplicate_block_ids_warning"] = {
                                    "has_duplicates": True,
                                    "duplicate_block_ids": duplicate_block_ids,
                                    "conflicting_settlements": duplicates,
                                    "warning_message": warning_msg
                                }
                            else:
                                entry_data["duplicate_block_ids_warning"] = None
                            
                            if not dry_run:
                                db_settlement = Settlement(**entry_data)
                                db.add(db_settlement)
                                created_settlements.append(db_settlement)
                            else:
                                would_create_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Entry {idx}: {str(e)}")
                continue
        
        if not dry_run and (created_settlements or updated_settlements):
            db.commit()
            
            # Refresh all settlements
            for settlement in all_settlements:
                db.refresh(settlement)
            
            # Create/update accounting journal entries
            for settlement in created_settlements:
                try:
                    create_settlement_journal_entry(db, settlement)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to create journal entry for settlement {settlement.id}: {str(e)}")
            
            for settlement in updated_settlements:
                try:
                    delete_settlement_journal_entry(db, settlement.id)
                    create_settlement_journal_entry(db, settlement)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to update journal entry for settlement {settlement.id}: {str(e)}")
            
            # Update loan balances
            truck_ids_updated = set()
            all_settlements = created_settlements + updated_settlements
            for settlement in all_settlements:
                if settlement.truck_id not in truck_ids_updated:
                    update_loan_balance_after_settlement(settlement.truck_id, db)
                    truck_ids_updated.add(settlement.truck_id)
        
        # Return settlements list if not dry run, otherwise return summary only
        if not dry_run:
            all_settlements = created_settlements + updated_settlements
            return {
                "settlements": all_settlements,
                "summary": {
                    "total_entries": len(data),
                    "created": len(created_settlements),
                    "updated": len(updated_settlements),
                    "skipped": skipped_count,
                    "errors": error_count,
                    "error_details": errors if errors else None
                }
            }
        else:
            return {
                "summary": {
                    "total_entries": len(data),
                    "would_create": would_create_count,
                    "would_update": would_update_count,
                    "would_skip": skipped_count,
                    "errors": error_count,
                    "error_details": errors if errors else None,
                    "dry_run": True
                }
            }
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=400, detail=f"Failed to process consolidated JSON: {str(e)}\n{traceback.format_exc()}")

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
                        # Check current plate (case insensitive)
                        if t.license_plate and t.license_plate.upper() == license_plate.upper():
                            truck = t
                            break
                        
                        # Check historic plates
                        history = t.license_plate_history
                        if history:
                            # Parse history if it's a JSON string
                            if isinstance(history, str):
                                try:
                                    history_list = json.loads(history)
                                    if isinstance(history_list, list) and any(
                                        plate and plate.upper() == license_plate.upper() 
                                        for plate in history_list
                                    ):
                                        truck = t
                                        break
                                except (json.JSONDecodeError, TypeError):
                                    pass
                            elif isinstance(history, list) and any(
                                plate and plate.upper() == license_plate.upper() 
                                for plate in history
                            ):
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
            
            # Calculate and add loan interest
            truck = db.query(Truck).filter(Truck.id == truck_id).first()
            if truck and truck.vehicle_type == 'truck':
                # Use current_loan_balance if available, otherwise use loan_amount
                current_balance = float(truck.current_loan_balance) if truck.current_loan_balance is not None else (float(truck.loan_amount) if truck.loan_amount else None)
                interest_rate = float(truck.interest_rate) if truck.interest_rate else 0.07
                
                if current_balance and current_balance > 0:
                    weekly_interest = calculate_weekly_loan_interest(current_balance, interest_rate)
                    expense_categories["loan_interest"] = weekly_interest
            
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
            
            # Extract block_ids from metrics if available
            block_ids = metrics.get("block_ids")
            
            # Check for duplicate block IDs (flag but don't reject)
            has_duplicates, warning_msg, duplicates = validate_block_ids(
                block_ids,
                db
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
                "block_ids": block_ids,
                "gross_revenue": revenue.get("gross_revenue"),
                "expenses": expenses.get("total_expenses") + (expense_categories.get("loan_interest", 0) if expense_categories.get("loan_interest") else 0),
                "expense_categories": expense_categories,
                "net_profit": revenue.get("gross_revenue", 0) - (expenses.get("total_expenses", 0) + (expense_categories.get("loan_interest", 0) if expense_categories.get("loan_interest") else 0)),
                "license_plate": license_plate,
                "settlement_type": metadata.get("settlement_type") or data.get("settlement_type"),
                "pdf_file_path": None  # No PDF stored
            }
            
            # Store duplicate warning if found
            if has_duplicates:
                duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
                settlement_data["duplicate_block_ids_warning"] = {
                    "has_duplicates": True,
                    "duplicate_block_ids": duplicate_block_ids,
                    "conflicting_settlements": duplicates,
                    "warning_message": warning_msg
                }
            else:
                settlement_data["duplicate_block_ids_warning"] = None
            
            db_settlement = Settlement(**settlement_data)
            db.add(db_settlement)
            created_settlements.append(db_settlement)
        
        db.commit()
        
        # Refresh all created settlements
        for settlement in created_settlements:
            db.refresh(settlement)
        
        # Create accounting journal entries
        for settlement in created_settlements:
            try:
                create_settlement_journal_entry(db, settlement)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create journal entry for settlement {settlement.id}: {str(e)}")
        
        # Update loan balances for trucks after settlements are created
        truck_ids_updated = set()
        for settlement in created_settlements:
            if settlement.truck_id not in truck_ids_updated:
                update_loan_balance_after_settlement(settlement.truck_id, db)
                truck_ids_updated.add(settlement.truck_id)
        
        return created_settlements
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process JSON: {str(e)}")

@router.delete("/{settlement_id}")
def delete_settlement(settlement_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Delete a settlement"""
    settlement = db.query(Settlement).join(Truck).filter(
        Settlement.id == settlement_id,
        Truck.tenant_id == tenant_id
    ).first()
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    
    # Delete accounting journal entry
    try:
        delete_settlement_journal_entry(db, settlement_id)
    except Exception as e:
        # Log error but don't fail settlement deletion
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to delete journal entry for settlement {settlement_id}: {str(e)}")
    
    # Delete PDF file if it exists
    if settlement.pdf_file_path and os.path.exists(settlement.pdf_file_path):
        try:
            os.remove(settlement.pdf_file_path)
        except Exception:
            pass  # Don't fail if file deletion fails
    
    db.delete(settlement)
    db.commit()
    return {"message": "Settlement deleted successfully"}

