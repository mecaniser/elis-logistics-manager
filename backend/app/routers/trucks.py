"""
Trucks router
"""
import logging
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional

from app.database import get_db
from app.dependencies import get_tenant_id
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.models.vehicle_document import VehicleDocument
from app.services.loan_balance_service import sync_current_loan_balance
from app.services.reserve_service import sync_repair_reserve_ledger
from app.schemas.truck import TruckCreate, TruckResponse, TruckUpdate
from app.schemas.vehicle_document import VehicleDocumentResponse
from app.utils.cloudinary import delete_uploaded_file, upload_image, upload_pdf
from app.utils.reserve_regime import RESERVE_REGIME_START_DATE

router = APIRouter()

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_VEHICLE_DOCUMENT_TYPES = {"title", "inspection", "registration", "insurance", "permit", "other"}
ALLOWED_VEHICLE_DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
MAX_VEHICLE_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024


def get_tenant_truck_or_404(db: Session, truck_id: int, tenant_id: int) -> Truck:
    truck = (
        db.query(Truck)
        .options(selectinload(Truck.vehicle_documents))
        .filter(Truck.id == truck_id, Truck.tenant_id == tenant_id)
        .first()
    )
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    return truck


def normalize_vehicle_document_type(document_type: str) -> str:
    normalized = (document_type or "other").strip().lower()
    if normalized not in ALLOWED_VEHICLE_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"document_type must be one of: {', '.join(sorted(ALLOWED_VEHICLE_DOCUMENT_TYPES))}",
        )
    return normalized


def store_vehicle_document(file_content: bytes, original_filename: str, content_type: Optional[str]) -> tuple[str, Optional[str]]:
    extension = Path(original_filename).suffix.lower()
    unique_name = f"vehicle_document_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{extension}"
    mime_type = content_type or mimetypes.guess_type(original_filename)[0]

    if extension == ".pdf":
        uploaded_path = upload_pdf(file_content, unique_name, folder="vehicle_documents")
    else:
        uploaded_path = upload_image(file_content, unique_name, folder="vehicle_documents")

    if uploaded_path:
        return uploaded_path, mime_type

    local_path = UPLOAD_DIR / unique_name
    with open(local_path, "wb") as buffer:
        buffer.write(file_content)
    return unique_name, mime_type


def cleanup_vehicle_document_file(file_path: Optional[str]) -> None:
    if not file_path:
        return

    if file_path.startswith("http://") or file_path.startswith("https://"):
        delete_uploaded_file(file_path)
        return

    local_path = UPLOAD_DIR / file_path
    if local_path.exists():
        local_path.unlink()


def validate_default_trailer_split(
    db: Session,
    tenant_id: int,
    vehicle_type: str,
    default_trailer_id: Optional[int],
    default_trailer_income_split_amount: Optional[float],
) -> tuple[Optional[int], Optional[float]]:
    """Validate stored default trailer split settings for a truck."""
    normalized_trailer_id = int(default_trailer_id) if default_trailer_id else None
    normalized_amount = (
        round(float(default_trailer_income_split_amount), 2)
        if default_trailer_income_split_amount is not None
        else None
    )

    if normalized_amount is not None and normalized_amount < 0:
        raise HTTPException(status_code=400, detail="Default trailer split amount cannot be negative.")

    if vehicle_type != "truck":
        if normalized_trailer_id or normalized_amount:
            raise HTTPException(
                status_code=400,
                detail="Default trailer split settings can only be saved on trucks.",
            )
        return None, None

    if not normalized_trailer_id and normalized_amount in (None, 0):
        return None, None

    if not normalized_trailer_id or normalized_amount is None or normalized_amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Default trailer split requires both a trailer and a positive weekly split amount.",
        )

    trailer = (
        db.query(Truck)
        .filter(
            Truck.id == normalized_trailer_id,
            Truck.tenant_id == tenant_id,
            Truck.vehicle_type == "trailer",
        )
        .first()
    )
    if not trailer:
        raise HTTPException(status_code=400, detail=f"Trailer with ID {normalized_trailer_id} not found.")

    return normalized_trailer_id, normalized_amount


def validate_default_repair_reserve(
    vehicle_type: str,
    default_repair_reserve_amount: Optional[float],
) -> Optional[float]:
    """Validate the default weekly repair reserve stored on a vehicle."""
    if default_repair_reserve_amount is None:
        return None

    normalized_amount = round(float(default_repair_reserve_amount), 2)
    if normalized_amount < 0:
        raise HTTPException(status_code=400, detail="Default repair reserve amount cannot be negative.")

    if vehicle_type != "truck":
        if normalized_amount > 0:
            raise HTTPException(
                status_code=400,
                detail="Default repair reserve settings can only be saved on trucks.",
            )
        return None

    return normalized_amount or None


def validate_fuel_estimation_settings(
    vehicle_type: str,
    estimated_mpg: Optional[float],
    fuel_card_discount_per_gallon: Optional[float],
) -> tuple[Optional[float], Optional[float]]:
    """Validate truck-level settings used to estimate miles from fuel spend."""
    normalized_mpg = None if estimated_mpg is None else round(float(estimated_mpg), 2)
    normalized_discount = None if fuel_card_discount_per_gallon is None else round(float(fuel_card_discount_per_gallon), 3)

    if vehicle_type != "truck":
        if (normalized_mpg or 0) > 0 or (normalized_discount or 0) > 0:
            raise HTTPException(
                status_code=400,
                detail="Fuel estimation settings can only be saved on trucks.",
            )
        return None, None

    if normalized_mpg is None:
        normalized_mpg = 6.5
    if normalized_mpg <= 0:
        raise HTTPException(status_code=400, detail="Estimated MPG must be greater than 0.")

    if normalized_discount is None:
        normalized_discount = 0.0
    if normalized_discount < 0:
        raise HTTPException(status_code=400, detail="Fuel-card discount per gallon cannot be negative.")

    return normalized_mpg, normalized_discount


def normalize_interest_rate(interest_rate: Optional[float]) -> Optional[float]:
    """Normalize user-entered interest rates to decimal form.

    Examples:
    - 0.07 stays 0.07
    - 6.5 becomes 0.065
    """
    if interest_rate is None:
        return None

    normalized_rate = float(interest_rate)
    if normalized_rate < 0:
        raise HTTPException(status_code=400, detail="Interest rate cannot be negative.")

    if normalized_rate > 1:
        if normalized_rate > 100:
            raise HTTPException(status_code=400, detail="Interest rate cannot exceed 100%.")
        normalized_rate = normalized_rate / 100.0

    return round(normalized_rate, 4)


def resync_truck_default_repair_reserve(
    db: Session,
    truck: Truck,
    new_default_repair_reserve_amount: Optional[float],
) -> int:
    """Rewrite 2026+ source settlements to the new truck default reserve amount."""
    settlements = (
        db.query(Settlement)
        .filter(
            Settlement.truck_id == truck.id,
            Settlement.source_settlement_id.is_(None),
            Settlement.settlement_date >= RESERVE_REGIME_START_DATE,
        )
        .order_by(Settlement.id.asc())
        .all()
    )

    rewritten_count = 0
    normalized_new_amount = round(float(new_default_repair_reserve_amount or 0.0), 2)

    for settlement in settlements:
        existing_reserve_amount = round(float(settlement.repair_reserve_amount or 0.0), 2)
        if existing_reserve_amount == normalized_new_amount:
            sync_repair_reserve_ledger(db, settlement)
            continue

        settlement.gross_revenue = round(float(settlement.gross_revenue or 0.0) + existing_reserve_amount - normalized_new_amount, 2)
        settlement.net_profit = round(float(settlement.net_profit or 0.0) + existing_reserve_amount - normalized_new_amount, 2)
        settlement.repair_reserve_amount = normalized_new_amount or None
        db.add(settlement)
        sync_repair_reserve_ledger(db, settlement)
        rewritten_count += 1

    return rewritten_count

@router.get("", response_model=List[TruckResponse])
@router.get("/", response_model=List[TruckResponse])
def get_trucks(
    vehicle_type: Optional[str] = None,  # Filter by 'truck', 'trailer', or 'suv'
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Get all trucks, trailers, and SUVs for the current tenant, optionally filtered by vehicle_type"""
    query = db.query(Truck).options(selectinload(Truck.vehicle_documents)).filter(Truck.tenant_id == tenant_id)
    if vehicle_type:
        vehicle_type_lower = vehicle_type.lower()
        if vehicle_type_lower in ['truck', 'trailer', 'suv']:
            query = query.filter(Truck.vehicle_type == vehicle_type_lower)
    return query.order_by(Truck.vehicle_type, Truck.name).all()

@router.post("", response_model=TruckResponse)
@router.post("/", response_model=TruckResponse)
def create_truck(truck: TruckCreate, db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Create a new truck or trailer"""
    # Validate vehicle_type
    vehicle_type = truck.vehicle_type.lower()
    if vehicle_type not in ['truck', 'trailer', 'suv']:
        raise HTTPException(
            status_code=400,
            detail="vehicle_type must be 'truck', 'trailer', or 'suv'"
        )
    
    # Validate: trucks and SUVs should have license_plate, trailers should have tag_number
    if vehicle_type in ['truck', 'suv'] and not truck.license_plate:
        # License plate is optional but recommended for trucks and SUVs
        pass
    elif vehicle_type == 'trailer' and not truck.tag_number:
        # Tag number is recommended for trailers
        pass
    
    # Calculate additional expenses total
    additional_expenses_total = 0.0
    if truck.additional_expenses:
        for expense in truck.additional_expenses:
            if isinstance(expense, dict) and 'amount' in expense:
                additional_expenses_total += float(expense['amount'])
    
    # Validate investment fields
    if vehicle_type == 'trailer':
        # Trailers should not have loans
        if truck.loan_amount and truck.loan_amount > 0:
            raise HTTPException(
                status_code=400,
                detail="Trailers cannot have loan amounts. Set loan_amount to 0 or null."
            )
        # For trailers, total_cost should equal cash_investment + registration_fee + additional_expenses (if provided)
        if truck.cash_investment is not None and truck.total_cost is not None:
            cash = float(truck.cash_investment)
            total = float(truck.total_cost)
            registration = float(truck.registration_fee) if truck.registration_fee else 0.0
            expected_total = cash + registration + additional_expenses_total
            
            if abs(total - expected_total) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"For trailers, total_cost ({total}) must equal cash_investment ({cash}) + registration_fee ({registration}) + additional_expenses ({additional_expenses_total})"
                )
    elif vehicle_type in ['truck', 'suv']:
        # For trucks and SUVs, validate total_cost = cash_investment + loan_amount + registration_fee + additional_expenses (if all provided)
        if truck.cash_investment is not None and truck.total_cost is not None:
            cash = float(truck.cash_investment)
            total = float(truck.total_cost)
            loan = float(truck.loan_amount) if truck.loan_amount else 0.0
            registration = float(truck.registration_fee) if truck.registration_fee else 0.0
            
            expected_total = cash + loan + registration + additional_expenses_total
            if abs(total - expected_total) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"total_cost ({total}) must equal cash_investment ({cash}) + loan_amount ({loan}) + registration_fee ({registration}) + additional_expenses ({additional_expenses_total})"
                )
    
    # Check for duplicate name within same vehicle type and tenant
    existing = db.query(Truck).filter(
        Truck.tenant_id == tenant_id,
        Truck.name == truck.name,
        Truck.vehicle_type == vehicle_type
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A {vehicle_type} with name '{truck.name}' already exists"
        )

    default_trailer_id, default_trailer_amount = validate_default_trailer_split(
        db,
        tenant_id,
        vehicle_type,
        truck.default_trailer_id,
        truck.default_trailer_income_split_amount,
    )
    default_repair_reserve_amount = validate_default_repair_reserve(
        vehicle_type,
        truck.default_repair_reserve_amount,
    )
    estimated_mpg, fuel_card_discount_per_gallon = validate_fuel_estimation_settings(
        vehicle_type,
        truck.estimated_mpg,
        truck.fuel_card_discount_per_gallon,
    )

    truck_dict = truck.model_dump()
    truck_dict['tenant_id'] = tenant_id
    truck_dict['vehicle_type'] = vehicle_type  # Ensure lowercase
    truck_dict['default_trailer_id'] = default_trailer_id
    truck_dict['default_trailer_income_split_amount'] = default_trailer_amount
    truck_dict['default_repair_reserve_amount'] = default_repair_reserve_amount
    truck_dict['estimated_mpg'] = estimated_mpg
    truck_dict['fuel_card_discount_per_gallon'] = fuel_card_discount_per_gallon
    # Set default interest_rate if not provided
    if 'interest_rate' not in truck_dict or truck_dict['interest_rate'] is None:
        truck_dict['interest_rate'] = 0.07  # Default 7%
    else:
        truck_dict['interest_rate'] = normalize_interest_rate(truck_dict['interest_rate'])
    # Initialize current_loan_balance = loan_amount for trucks and SUVs
    if vehicle_type in ['truck', 'suv'] and truck_dict.get('loan_amount'):
        if 'current_loan_balance' not in truck_dict or truck_dict['current_loan_balance'] is None:
            truck_dict['current_loan_balance'] = truck_dict['loan_amount']
    db_truck = Truck(**truck_dict)
    db.add(db_truck)
    db.commit()
    db.refresh(db_truck)
    return db_truck


@router.get("/{truck_id}/documents", response_model=List[VehicleDocumentResponse])
def get_vehicle_documents(
    truck_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    """Get all documents for a specific vehicle."""
    get_tenant_truck_or_404(db, truck_id, tenant_id)
    return (
        db.query(VehicleDocument)
        .filter(VehicleDocument.truck_id == truck_id)
        .order_by(VehicleDocument.uploaded_at.desc(), VehicleDocument.id.desc())
        .all()
    )


@router.post("/{truck_id}/documents", response_model=VehicleDocumentResponse)
async def upload_vehicle_document(
    truck_id: int,
    file: UploadFile = File(...),
    document_type: str = Form("other"),
    title: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    """Upload a document for a specific vehicle."""
    get_tenant_truck_or_404(db, truck_id, tenant_id)

    normalized_document_type = normalize_vehicle_document_type(document_type)
    original_filename = (file.filename or "").strip()
    if not original_filename:
        raise HTTPException(status_code=400, detail="A file name is required")

    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_VEHICLE_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, PNG, JPG, JPEG, and WEBP files are supported",
        )

    file_content = await file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(file_content) > MAX_VEHICLE_DOCUMENT_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File must be 10 MB or smaller")

    stored_path = None
    try:
        stored_path, mime_type = store_vehicle_document(file_content, original_filename, file.content_type)
        document = VehicleDocument(
            truck_id=truck_id,
            document_type=normalized_document_type,
            title=title.strip() if title and title.strip() else None,
            notes=notes.strip() if notes and notes.strip() else None,
            original_filename=original_filename,
            file_path=stored_path,
            mime_type=mime_type,
            file_size=len(file_content),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    except HTTPException:
        if stored_path:
            cleanup_vehicle_document_file(stored_path)
        raise
    except Exception as exc:
        db.rollback()
        if stored_path:
            cleanup_vehicle_document_file(stored_path)
        logger.exception("Failed to upload vehicle document")
        raise HTTPException(status_code=400, detail=f"Failed to upload vehicle document: {str(exc)}")

@router.get("/{truck_id}", response_model=TruckResponse)
def get_truck(truck_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Get a specific truck"""
    return get_tenant_truck_or_404(db, truck_id, tenant_id)


@router.delete("/{truck_id}/documents/{document_id}")
def delete_vehicle_document(
    truck_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    """Delete a document from a specific vehicle."""
    get_tenant_truck_or_404(db, truck_id, tenant_id)
    document = (
        db.query(VehicleDocument)
        .filter(VehicleDocument.id == document_id, VehicleDocument.truck_id == truck_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Vehicle document not found")

    stored_path = document.file_path
    db.delete(document)
    db.commit()
    cleanup_vehicle_document_file(stored_path)
    return {"message": "Vehicle document deleted successfully"}

@router.put("/{truck_id}", response_model=TruckResponse)
def update_truck(truck_id: int, truck_update: TruckUpdate, db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Update a truck or trailer"""
    truck = get_tenant_truck_or_404(db, truck_id, tenant_id)
    previous_default_repair_reserve_amount = round(float(truck.default_repair_reserve_amount or 0.0), 2)
    
    # Update only provided fields
    update_data = truck_update.model_dump(exclude_unset=True)
    # Ensure vehicle_type is lowercase if provided
    if 'vehicle_type' in update_data:
        update_data['vehicle_type'] = update_data['vehicle_type'].lower()
        vehicle_type = update_data['vehicle_type']
    else:
        vehicle_type = truck.vehicle_type

    if any(field in update_data for field in ['default_trailer_id', 'default_trailer_income_split_amount', 'vehicle_type']):
        default_trailer_id, default_trailer_amount = validate_default_trailer_split(
            db,
            tenant_id,
            vehicle_type,
            update_data.get('default_trailer_id', truck.default_trailer_id),
            update_data.get('default_trailer_income_split_amount', truck.default_trailer_income_split_amount),
        )
        update_data['default_trailer_id'] = default_trailer_id
        update_data['default_trailer_income_split_amount'] = default_trailer_amount
    if any(field in update_data for field in ['default_repair_reserve_amount', 'vehicle_type']):
        update_data['default_repair_reserve_amount'] = validate_default_repair_reserve(
            vehicle_type,
            update_data.get('default_repair_reserve_amount', truck.default_repair_reserve_amount),
        )
    if any(field in update_data for field in ['estimated_mpg', 'fuel_card_discount_per_gallon', 'vehicle_type']):
        estimated_mpg, fuel_card_discount_per_gallon = validate_fuel_estimation_settings(
            vehicle_type,
            update_data.get('estimated_mpg', truck.estimated_mpg),
            update_data.get('fuel_card_discount_per_gallon', truck.fuel_card_discount_per_gallon),
        )
        update_data['estimated_mpg'] = estimated_mpg
        update_data['fuel_card_discount_per_gallon'] = fuel_card_discount_per_gallon
    if 'interest_rate' in update_data:
        update_data['interest_rate'] = normalize_interest_rate(update_data['interest_rate'])
    
    # Calculate additional expenses total
    additional_expenses_total = 0.0
    if 'additional_expenses' in update_data and update_data.get('additional_expenses'):
        for expense in update_data['additional_expenses']:
            if isinstance(expense, dict) and 'amount' in expense:
                additional_expenses_total += float(expense['amount'])
    elif truck.additional_expenses:
        for expense in truck.additional_expenses:
            if isinstance(expense, dict) and 'amount' in expense:
                additional_expenses_total += float(expense['amount'])
    
    # Validate investment fields if being updated
    if 'loan_amount' in update_data or 'cash_investment' in update_data or 'total_cost' in update_data or 'registration_fee' in update_data or 'additional_expenses' in update_data:
        cash_investment = update_data.get('cash_investment', truck.cash_investment)
        loan_amount = update_data.get('loan_amount', truck.loan_amount)
        total_cost = update_data.get('total_cost', truck.total_cost)
        registration_fee = update_data.get('registration_fee', truck.registration_fee)
        
        if vehicle_type == 'trailer':
            # Trailers should not have loans
            if loan_amount and float(loan_amount) > 0:
                raise HTTPException(
                    status_code=400,
                    detail="Trailers cannot have loan amounts. Set loan_amount to 0 or null."
                )
            # For trailers, total_cost should equal cash_investment + registration_fee + additional_expenses (if provided)
            if cash_investment is not None and total_cost is not None:
                cash = float(cash_investment)
                total = float(total_cost)
                registration = float(registration_fee) if registration_fee else 0.0
                expected_total = cash + registration + additional_expenses_total
                
                if abs(total - expected_total) > 0.01:
                    raise HTTPException(
                        status_code=400,
                        detail=f"For trailers, total_cost ({total}) must equal cash_investment ({cash}) + registration_fee ({registration}) + additional_expenses ({additional_expenses_total})"
                    )
        elif vehicle_type in ['truck', 'suv']:
            # For trucks and SUVs, validate total_cost = cash_investment + loan_amount + registration_fee + additional_expenses (if all provided)
            if cash_investment is not None and total_cost is not None:
                cash = float(cash_investment)
                total = float(total_cost)
                loan = float(loan_amount) if loan_amount else 0.0
                registration = float(registration_fee) if registration_fee else 0.0
                
                expected_total = cash + loan + registration + additional_expenses_total
                if abs(total - expected_total) > 0.01:
                    raise HTTPException(
                        status_code=400,
                        detail=f"total_cost ({total}) must equal cash_investment ({cash}) + loan_amount ({loan}) + registration_fee ({registration}) + additional_expenses ({additional_expenses_total})"
                    )
    
    # Update current_loan_balance if loan_amount is being updated
    if 'loan_amount' in update_data:
        new_loan_amount = update_data['loan_amount']
        if vehicle_type in ['truck', 'suv'] and new_loan_amount:
            # If loan_amount is updated, reset current_loan_balance to new loan_amount
            # (unless it's being explicitly set in update_data)
            if 'current_loan_balance' not in update_data:
                update_data['current_loan_balance'] = new_loan_amount
        elif vehicle_type == 'trailer':
            # Trailers shouldn't have loan balances
            update_data['current_loan_balance'] = None
    
    for field, value in update_data.items():
        setattr(truck, field, value)

    should_resync_loan_balance = (
        vehicle_type == 'truck'
        and 'current_loan_balance' not in update_data
        and any(field in update_data for field in ['loan_amount', 'cash_investment', 'total_cost', 'registration_fee', 'additional_expenses'])
    )
    if should_resync_loan_balance:
        sync_current_loan_balance(db, truck)

    next_default_repair_reserve_amount = round(float(truck.default_repair_reserve_amount or 0.0), 2)
    should_resync_default_reserve = (
        vehicle_type == 'truck'
        and previous_default_repair_reserve_amount != next_default_repair_reserve_amount
    )
    if should_resync_default_reserve:
        resync_truck_default_repair_reserve(db, truck, truck.default_repair_reserve_amount)
    
    db.commit()
    db.refresh(truck)
    return truck

@router.delete("/{truck_id}")
def delete_truck(truck_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Delete a truck or trailer"""
    truck = get_tenant_truck_or_404(db, truck_id, tenant_id)

    document_paths = [document.file_path for document in truck.vehicle_documents]
    db.delete(truck)
    db.commit()

    for file_path in document_paths:
        cleanup_vehicle_document_file(file_path)

    return {"message": "Vehicle deleted successfully"}
