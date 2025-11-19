"""
Repairs router
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, FileResponse
import httpx
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
from app.utils.cloudinary import upload_image, upload_pdf, delete_image, download_file_content, CLOUDINARY_CONFIGURED

router = APIRouter()

# Upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("", response_model=List[RepairResponse])
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
async def create_repair(
    repair_json: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    """Create a new repair expense"""
    # Parse repair data from JSON string (for FormData) or use RepairCreate directly
    if repair_json:
        repair_data = json.loads(repair_json)
    else:
        raise HTTPException(status_code=400, detail="Repair data is required")
    
    # Upload image files to Cloudinary or save locally
    image_paths = []
    if images:
        for img in images:
            img_content = await img.read()
            img_timestamp = datetime.now().timestamp()
            img_filename = f"{img_timestamp}_{img.filename}"
            
            # Try Cloudinary upload first
            cloudinary_url = upload_image(img_content, img_filename, folder="repairs")
            
            if cloudinary_url:
                # Store Cloudinary URL
                image_paths.append(cloudinary_url)
            else:
                # Fallback to local storage if Cloudinary not configured
                img_path = os.path.join(UPLOAD_DIR, img_filename)
                with open(img_path, "wb") as img_buffer:
                    img_buffer.write(img_content)
                image_paths.append(img_filename)
    
    # Validate required fields
    if not repair_data.get("truck_id"):
        raise HTTPException(status_code=400, detail="Truck ID is required")
    
    # Handle date conversion if provided as string
    repair_date = repair_data.get("repair_date")
    if repair_date and isinstance(repair_date, str):
        try:
            from datetime import datetime as dt
            repair_date = dt.fromisoformat(repair_date.replace('Z', '+00:00')).date()
        except (ValueError, AttributeError):
            try:
                repair_date = datetime.strptime(repair_date, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                repair_date = None
    
    # Handle cost conversion
    cost = repair_data.get("cost")
    if cost is not None:
        try:
            cost = float(cost)
        except (ValueError, TypeError):
            cost = None
    
    db_repair = Repair(
        truck_id=repair_data.get("truck_id"),
        repair_date=repair_date,
        title=repair_data.get("title") or None,
        details=repair_data.get("details") or None,
        description=repair_data.get("description") or None,
        category=repair_data.get("category") or None,
        cost=cost,
        receipt_path=repair_data.get("receipt_path") or None,
        invoice_number=repair_data.get("invoice_number") or None,
        image_paths=image_paths if image_paths else None
    )
    
    try:
        db.add(db_repair)
        db.commit()
        db.refresh(db_repair)
        return db_repair
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create repair: {str(e)}")

@router.get("/{repair_id}/invoice")
async def get_repair_invoice(repair_id: int, db: Session = Depends(get_db)):
    """Proxy repair invoice PDF from Cloudinary with inline display headers"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        repair = db.query(Repair).filter(Repair.id == repair_id).first()
        if not repair:
            raise HTTPException(status_code=404, detail="Repair not found")
        
        if not repair.receipt_path:
            raise HTTPException(status_code=404, detail="No invoice found for this repair")
        
        logger.info(f"Fetching invoice for repair {repair_id}, receipt_path: {repair.receipt_path[:50]}...")
        
        # If it's a Cloudinary URL, proxy it through our backend with correct headers
        if repair.receipt_path.startswith('http://') or repair.receipt_path.startswith('https://'):
            try:
                # Try downloading via Cloudinary API first (uses API credentials)
                if "res.cloudinary.com" in repair.receipt_path:
                    logger.info(f"Attempting to download PDF via Cloudinary API: {repair.receipt_path[:100]}...")
                    file_content = await download_file_content(repair.receipt_path)
                    
                    if file_content:
                        logger.info(f"Successfully downloaded PDF via API, size: {len(file_content)} bytes")
                        # Verify it's a PDF
                        if not file_content.startswith(b"%PDF"):
                            logger.warning(f"Downloaded content doesn't start with PDF magic bytes")
                        
                        # Return PDF with Content-Disposition: inline header
                        return Response(
                            content=file_content,
                            media_type="application/pdf",
                            headers={
                                "Content-Disposition": "inline; filename=invoice.pdf",
                                "Cache-Control": "public, max-age=3600"
                            }
                        )
                    else:
                        logger.warning(f"API download failed, trying direct HTTP...")
                
                # Fallback: Try direct HTTP fetch
                fetch_url = repair.receipt_path
                logger.info(f"Fetching PDF from Cloudinary using direct HTTP: {fetch_url[:100]}...")
                
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    # Fetch PDF from Cloudinary
                    response = await client.get(fetch_url, timeout=30.0)
                    
                    if response.status_code != 200:
                        logger.error(f"Cloudinary returned status {response.status_code}")
                        raise HTTPException(
                            status_code=response.status_code, 
                            detail=f"Failed to fetch invoice from Cloudinary: HTTP {response.status_code}"
                        )
                    
                    # Verify content type and content
                    if not response.content:
                        logger.error("Empty response content from Cloudinary")
                        raise HTTPException(status_code=500, detail="Empty response from Cloudinary")
                    
                    content_type = response.headers.get("content-type", "application/pdf")
                    logger.info(f"Content type from Cloudinary: {content_type}, content length: {len(response.content)}")
                    
                    # Check if it's a PDF by content type or magic bytes
                    is_pdf = "pdf" in content_type.lower() or response.content.startswith(b"%PDF")
                    if not is_pdf:
                        logger.warning(f"Unexpected content type: {content_type}, first bytes: {response.content[:20]}")
                        # Still try to serve it, might be a PDF with wrong content-type header
                    
                    # Return PDF with Content-Disposition: inline header to force display instead of download
                    logger.info(f"Returning PDF response, size: {len(response.content)} bytes")
                    return Response(
                        content=response.content,
                        media_type="application/pdf",
                        headers={
                            "Content-Disposition": "inline; filename=invoice.pdf",
                            "Cache-Control": "public, max-age=3600"
                        }
                    )
            except httpx.RequestError as e:
                logger.error(f"httpx.RequestError fetching invoice: {type(e).__name__}: {str(e)}", exc_info=True)
                error_msg = str(e) if str(e) else f"{type(e).__name__}"
                raise HTTPException(status_code=500, detail=f"Failed to fetch invoice: {error_msg}")
            except HTTPException:
                # Re-raise HTTP exceptions as-is
                raise
            except Exception as e:
                logger.error(f"Unexpected error fetching invoice: {type(e).__name__}: {str(e)}", exc_info=True)
                error_msg = str(e) if str(e) else f"{type(e).__name__}"
                raise HTTPException(status_code=500, detail=f"Unexpected error: {type(e).__name__}: {error_msg}")
        else:
            # Local file - serve directly
            local_file_path = os.path.join(UPLOAD_DIR, repair.receipt_path)
            if os.path.exists(local_file_path):
                return FileResponse(
                    local_file_path,
                    media_type="application/pdf",
                    headers={"Content-Disposition": "inline; filename=invoice.pdf"}
                )
            else:
                raise HTTPException(status_code=404, detail="Invoice file not found")
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_repair_invoice: {type(e).__name__}: {str(e)}", exc_info=True)
        error_msg = str(e) if str(e) else f"{type(e).__name__}"
        raise HTTPException(status_code=500, detail=f"Unexpected error: {type(e).__name__}: {error_msg}")

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
    
    # Upload new image files to Cloudinary or save locally, and add to existing images
    if images:
        existing_images = repair.image_paths if repair.image_paths else []
        new_image_paths = []
        
        for img in images:
            img_content = await img.read()
            img_timestamp = datetime.now().timestamp()
            img_filename = f"{img_timestamp}_{img.filename}"
            
            # Try Cloudinary upload first
            cloudinary_url = upload_image(img_content, img_filename, folder="repairs")
            
            if cloudinary_url:
                # Store Cloudinary URL
                new_image_paths.append(cloudinary_url)
            else:
                # Fallback to local storage if Cloudinary not configured
                img_path = os.path.join(UPLOAD_DIR, img_filename)
                with open(img_path, "wb") as img_buffer:
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
    truck_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload and parse repair invoice PDF. Truck is automatically identified by VIN if available, otherwise truck_id must be provided."""
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
    truck = None
    vin_found = bool(vin)
    
    if vin:
        # Find truck by VIN (case-insensitive)
        truck = db.query(Truck).filter(Truck.vin.ilike(vin)).first()
        if not truck:
            # VIN found but no matching truck - clean up file and return info so frontend can show truck selection
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            return RepairUploadResponse(
                repair=None,  # Will be created after truck selection on re-upload
                warning=f"VIN {vin} found in invoice but no matching truck found in database. Please select the correct truck from the dropdown and upload the file again. If this VIN belongs to an existing truck, you may need to update that truck's VIN in the Trucks page.",
                vin_found=True,
                vin=vin,
                requires_truck_selection=True
            )
    
    # If no VIN found, require truck_id to be provided
    if not vin and not truck_id:
        # Clean up uploaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(
            status_code=400,
            detail="Could not extract VIN number from invoice. Please select a truck manually."
        )
    
    # If truck_id provided but no VIN found, use truck_id
    if not truck and truck_id:
        truck = db.query(Truck).filter(Truck.id == truck_id).first()
        if not truck:
            # Clean up uploaded file
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            raise HTTPException(
                status_code=404,
                detail=f"No truck found with ID {truck_id}."
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
    
    # Upload image files to Cloudinary or save locally
    image_paths = []
    if images:
        for img in images:
            img_content = await img.read()
            img_timestamp = datetime.now().timestamp()
            img_filename = f"{img_timestamp}_{img.filename}"
            
            # Try Cloudinary upload first
            cloudinary_url = upload_image(img_content, img_filename, folder="repairs")
            
            if cloudinary_url:
                # Store Cloudinary URL
                image_paths.append(cloudinary_url)
            else:
                # Fallback to local storage if Cloudinary not configured
                img_path = os.path.join(UPLOAD_DIR, img_filename)
                with open(img_path, "wb") as img_buffer:
                    img_buffer.write(img_content)
                # Store relative path without "uploads/" prefix
                image_paths.append(img_filename)
    
    # Upload PDF receipt to Cloudinary or save locally
    receipt_path = None
    if os.path.exists(file_path):
        with open(file_path, "rb") as pdf_file:
            pdf_content = pdf_file.read()
            pdf_filename = os.path.basename(file_path)
            
            # Try Cloudinary upload first
            cloudinary_pdf_url = upload_pdf(pdf_content, pdf_filename, folder="repairs/receipts")
            
            if cloudinary_pdf_url:
                # Store Cloudinary URL
                receipt_path = cloudinary_pdf_url
            else:
                # Fallback to local storage if Cloudinary not configured
                receipt_path = os.path.basename(file_path)  # Store just filename, frontend adds /uploads/ prefix
    
    # Create repair record
    try:
        db_repair = Repair(
            truck_id=truck.id,
            repair_date=repair_data.get("repair_date"),
            title=repair_data.get("title"),
            details=repair_data.get("details"),
            description=repair_data.get("description"),
            category=repair_data.get("category"),
            cost=repair_data.get("cost"),
            receipt_path=receipt_path,
            invoice_number=repair_data.get("invoice_number"),
            image_paths=image_paths if image_paths else None
        )
        db.add(db_repair)
        db.commit()
        db.refresh(db_repair)
        
        warning_parts = []
        if not repair_data.get("repair_date"):
            warning_parts.append("Repair date could not be extracted from invoice. Please update manually.")
        if not repair_data.get("cost"):
            warning_parts.append("Cost could not be extracted from invoice. Please update manually.")
        if not repair_data.get("description"):
            warning_parts.append("Description could not be extracted from invoice. Please update manually.")
        
        warning = " ".join(warning_parts) if warning_parts else None
        
        return RepairUploadResponse(
            repair=db_repair, 
            warning=warning,
            vin_found=vin_found,
            vin=vin,
            requires_truck_selection=False
        )
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

@router.delete("/{repair_id}/images/{image_index}")
async def delete_repair_image(
    repair_id: int,
    image_index: int,
    db: Session = Depends(get_db)
):
    """Delete a specific image from a repair"""
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    
    if not repair.image_paths or not isinstance(repair.image_paths, list):
        raise HTTPException(status_code=400, detail="No images found for this repair")
    
    if image_index < 0 or image_index >= len(repair.image_paths):
        raise HTTPException(status_code=400, detail="Invalid image index")
    
    # Get the image URL/path to delete
    image_path = repair.image_paths[image_index]
    
    # Delete from Cloudinary if it's a Cloudinary URL, otherwise delete local file
    if "res.cloudinary.com" in image_path:
        delete_image(image_path)
    else:
        # Delete local file if it exists
        local_file_path = os.path.join(UPLOAD_DIR, image_path)
        if os.path.exists(local_file_path):
            try:
                os.remove(local_file_path)
            except Exception as e:
                # Log error but continue - file might already be deleted
                pass
    
    # Remove image from the list
    updated_images = [img for i, img in enumerate(repair.image_paths) if i != image_index]
    repair.image_paths = updated_images if updated_images else None
    
    db.commit()
    db.refresh(repair)
    return {"message": "Image deleted successfully", "repair": repair}

@router.delete("/{repair_id}")
def delete_repair(repair_id: int, db: Session = Depends(get_db)):
    """Delete a repair"""
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    db.delete(repair)
    db.commit()
    return {"message": "Repair deleted successfully"}

