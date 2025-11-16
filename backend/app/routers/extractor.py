"""
Settlement Extractor Router
Provides endpoints for extracting settlement data from PDFs to JSON format
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime
from app.utils.settlement_extractor import SettlementExtractor

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/extract-data")
async def extract_settlement_data(
    file: UploadFile = File(...),
    settlement_type: Optional[str] = Form(None)
):
    """
    Extract settlement data from PDF and return as JSON (for UI display).
    Keeps the PDF file temporarily so it can be viewed for comparison.
    """
    import time
    timestamp = time.time()
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        extractor = SettlementExtractor()
        extracted_data = extractor.extract_from_pdf(file_path, settlement_type)
        
        if not extracted_data.get("settlements"):
            # Clean up PDF if extraction failed
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            raise HTTPException(status_code=400, detail="No settlements found in PDF")
        
        # Add PDF filename to response so frontend can display it
        extracted_data["pdf_filename"] = filename
        
        # Return JSON data for UI display (PDF kept for viewing)
        return JSONResponse(content=extracted_data)
        
    except HTTPException:
        raise
    except Exception as e:
        # Clean up temporary file on error
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(status_code=400, detail=f"Failed to extract PDF: {str(e)}")

@router.post("/extract")
async def extract_settlement_pdf(
    file: UploadFile = File(...),
    settlement_type: Optional[str] = Form(None),
    individual_files: bool = Form(False)  # If True, return one JSON per settlement
):
    """
    Extract settlement data from PDF and return as JSON.
    If individual_files=True, returns a ZIP file with one JSON per settlement.
    Otherwise, returns a single JSON file with all settlements.
    """
    # Save uploaded file temporarily
    timestamp = os.path.getmtime if hasattr(os.path, 'getmtime') else lambda x: 0
    import time
    timestamp = time.time()
    file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        extractor = SettlementExtractor()
        extracted_data = extractor.extract_from_pdf(file_path, settlement_type)
        
        if not extracted_data.get("settlements"):
            raise HTTPException(status_code=400, detail="No settlements found in PDF")
        
        # Clean up temporary PDF
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        if individual_files and len(extracted_data["settlements"]) > 1:
            # Create individual JSON files and return as ZIP
            import zipfile
            import io
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for idx, settlement in enumerate(extracted_data["settlements"]):
                    # Create individual settlement JSON
                    settlement_json = {
                        "source_file": extracted_data["source_file"],
                        "extraction_date": extracted_data["extraction_date"],
                        "settlement_type": extracted_data["settlement_type"],
                        "settlement": settlement
                    }
                    
                    # Generate filename
                    license_plate = settlement.get("metadata", {}).get("license_plate", "")
                    settlement_date = settlement.get("metadata", {}).get("settlement_date", "")
                    if license_plate and settlement_date:
                        filename = f"{Path(file.filename).stem}_{license_plate}_{settlement_date.replace('-', '')}.json"
                    else:
                        filename = f"{Path(file.filename).stem}_settlement_{idx + 1}.json"
                    
                    json_str = json.dumps(settlement_json, indent=2, ensure_ascii=False)
                    zip_file.writestr(filename, json_str.encode('utf-8'))
            
            zip_buffer.seek(0)
            # Save to temporary file
            temp_zip = tempfile.NamedTemporaryFile(mode='wb', suffix='.zip', delete=False)
            temp_zip.write(zip_buffer.getvalue())
            temp_zip.close()
            
            return FileResponse(
                path=temp_zip.name,
                filename=f"{Path(file.filename).stem}_extracted.zip",
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={Path(file.filename).stem}_extracted.zip"}
            )
        else:
            # Return single JSON file (always individual format)
            settlement = extracted_data["settlements"][0]
            settlement_json = {
                "source_file": extracted_data["source_file"],
                "extraction_date": extracted_data["extraction_date"],
                "settlement_type": extracted_data["settlement_type"],
                "settlement": settlement
            }
            
            json_str = json.dumps(settlement_json, indent=2, ensure_ascii=False)
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
            temp_file.write(json_str)
            temp_file.close()
            
            # Generate filename with license plate and date
            filename = Path(file.filename).stem
            license_plate = settlement.get("metadata", {}).get("license_plate", "")
            settlement_date = settlement.get("metadata", {}).get("settlement_date", "")
            if license_plate and settlement_date:
                filename = f"{filename}_{license_plate}_{settlement_date.replace('-', '')}"
            
            return FileResponse(
                path=temp_file.name,
                filename=f"{filename}.json",
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}.json"}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        # Clean up temporary file on error
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(status_code=400, detail=f"Failed to extract PDF: {str(e)}")

@router.post("/extract-bulk-data")
async def extract_settlement_pdfs_bulk_data(
    files: List[UploadFile] = File(...),
    settlement_type: Optional[str] = Form(None)
):
    """
    Extract multiple PDFs and return JSON data (for UI display).
    Keeps PDF files temporarily so they can be viewed for comparison.
    """
    import time
    extractor = SettlementExtractor()
    all_extracted_data = []
    processed_count = 0
    error_count = 0
    
    for file in files:
        try:
            # Save uploaded file temporarily
            timestamp = time.time()
            filename = f"{timestamp}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, filename)
            
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Extract data
            extracted_data = extractor.extract_from_pdf(file_path, settlement_type)
            
            if extracted_data.get("settlements"):
                # Add PDF filename to response
                extracted_data["pdf_filename"] = filename
                all_extracted_data.append(extracted_data)
                processed_count += len(extracted_data["settlements"])
            else:
                # Clean up PDF if extraction failed
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
                error_count += 1
                
        except Exception as e:
            error_count += 1
            continue
    
    if processed_count == 0:
        raise HTTPException(status_code=400, detail="No settlements could be extracted from any PDF files")
    
    return JSONResponse(content={
        "total_files": len(files),
        "processed_settlements": processed_count,
        "failed_files": error_count,
        "extracted_data": all_extracted_data
    })

@router.post("/extract-bulk")
async def extract_settlement_pdfs_bulk(
    files: List[UploadFile] = File(...),
    settlement_type: Optional[str] = Form(None),
    individual_files: bool = Form(True),  # If True, return ZIP with individual files; If False, return consolidated JSON
    consolidated: bool = Form(False)  # If True, return single consolidated JSON file with all settlements
):
    """
    Extract multiple PDFs and return as ZIP file with individual JSON files OR a single consolidated JSON file.
    - If consolidated=True: Returns a single JSON file with all settlements from all PDFs (ready for database import)
    - If consolidated=False and individual_files=True: Returns ZIP with individual JSON files (one per settlement)
    - If consolidated=False and individual_files=False: Returns single JSON with first settlement only
    """
    import zipfile
    import io
    import time
    
    extractor = SettlementExtractor()
    processed_count = 0
    error_count = 0
    all_settlements = []  # List of (settlement, source_file, extraction_date, settlement_type) tuples
    
    try:
        # Extract all settlements from all PDFs
        for file in files:
            try:
                # Save uploaded file temporarily
                timestamp = time.time()
                file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")
                
                with open(file_path, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)
                
                # Extract data
                extracted_data = extractor.extract_from_pdf(file_path, settlement_type)
                
                # Clean up temporary PDF
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
                
                if not extracted_data.get("settlements"):
                    error_count += 1
                    continue
                
                # Collect all settlements with their metadata
                source_file = extracted_data.get("source_file", file.filename)
                extraction_date = extracted_data.get("extraction_date", datetime.now().isoformat())
                settlement_type_from_data = extracted_data.get("settlement_type", settlement_type)
                
                for settlement in extracted_data["settlements"]:
                    all_settlements.append((settlement, source_file, extraction_date, settlement_type_from_data))
                    processed_count += 1
                    
            except Exception as e:
                error_count += 1
                continue
        
        if processed_count == 0:
            raise HTTPException(status_code=400, detail="No settlements could be extracted from any PDF files")
        
        # If consolidated mode, return single JSON file with all settlements
        if consolidated:
            # Extract just the settlement objects for consolidated format
            settlements_only = [settlement for settlement, _, _, _ in all_settlements]
            consolidated_json = {
                "settlements": settlements_only,
                "total_settlements": len(settlements_only),
                "source_files": list(set([source_file for _, source_file, _, _ in all_settlements])),
                "extraction_date": datetime.now().isoformat(),
                "settlement_type": settlement_type
            }
            
            json_str = json.dumps(consolidated_json, indent=2, ensure_ascii=False)
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
            temp_file.write(json_str)
            temp_file.close()
            
            return FileResponse(
                path=temp_file.name,
                filename="settlements_consolidated.json",
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=settlements_consolidated.json"}
            )
        
        # Otherwise, create ZIP with individual files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Create individual JSON files for each settlement
            for idx, (settlement, source_file, extraction_date, settlement_type_from_data) in enumerate(all_settlements):
                settlement_json = {
                    "source_file": source_file,
                    "extraction_date": extraction_date,
                    "settlement_type": settlement_type_from_data,
                    "settlement": settlement
                }
                
                # Generate filename
                license_plate = settlement.get("metadata", {}).get("license_plate", "")
                settlement_date = settlement.get("metadata", {}).get("settlement_date", "")
                
                if license_plate and settlement_date:
                    filename = f"{Path(source_file).stem}_{license_plate}_{settlement_date.replace('-', '')}.json"
                else:
                    filename = f"{Path(source_file).stem}_settlement_{idx + 1}.json"
                
                json_str = json.dumps(settlement_json, indent=2, ensure_ascii=False)
                zip_file.writestr(filename, json_str.encode('utf-8'))
        
        zip_buffer.seek(0)
        
        # Save to temporary file
        temp_zip = tempfile.NamedTemporaryFile(mode='wb', suffix='.zip', delete=False)
        temp_zip.write(zip_buffer.getvalue())
        temp_zip.close()
        
        return FileResponse(
            path=temp_zip.name,
            filename="settlements_extracted.zip",
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=settlements_extracted.zip"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract PDFs: {str(e)}")

