"""
Standalone Settlement PDF Extraction Tool
Extracts all important information from settlement PDFs and converts to JSON structure
"""
import pdfplumber
import re
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class SettlementExtractor:
    """
    Extracts structured data from settlement PDFs and outputs JSON.
    This tool can be used independently to process PDFs and generate JSON files
    that can then be imported into the database.
    """
    
    def __init__(self):
        self.settlement_types = [
            "Owner Operator Income Sheet",
            "277 Logistics",
            "NBM Transport LLC"
        ]
    
    def extract_from_pdf(self, pdf_path: str, settlement_type: Optional[str] = None, 
                         return_validation: bool = False) -> Dict:
        """
        Extract all settlement data from PDF and return as structured dictionary.
        
        Args:
            pdf_path: Path to the PDF file
            settlement_type: Optional settlement type hint
            return_validation: If True, include validation results (for multi-truck PDFs)
            
        Returns:
            Dictionary with all extracted settlement data. If return_validation=True and
            PDF is multi-truck, includes 'validation' key with validation results.
        """
        from app.utils.pdf_parser import parse_amazon_relay_pdf, parse_amazon_relay_pdf_multi_truck
        
        # Detect settlement type if not provided
        if not settlement_type:
            settlement_type = self._detect_settlement_type(pdf_path)
        
        # Check if PDF contains multiple trucks by detecting multiple license plates
        # This works for any settlement type, not just NBM
        has_multiple_trucks = self._detect_multiple_trucks(pdf_path)
        
        # Use appropriate parser
        validation_result = None
        if has_multiple_trucks:
            # Multi-truck parser returns list or dict with validation
            if return_validation:
                parser_result = parse_amazon_relay_pdf_multi_truck(pdf_path, settlement_type, return_validation=True)
                if isinstance(parser_result, dict) and "validation" in parser_result:
                    settlements_data = parser_result.get("settlements", [])
                    validation_result = parser_result.get("validation")
                else:
                    settlements_data = parser_result if isinstance(parser_result, list) else [parser_result]
            else:
                settlements_data = parse_amazon_relay_pdf_multi_truck(pdf_path, settlement_type)
        elif settlement_type and settlement_type.upper() == "NBM TRANSPORT LLC":
            # NBM Transport LLC always uses multi-truck parser (even if only one truck found)
            if return_validation:
                parser_result = parse_amazon_relay_pdf_multi_truck(pdf_path, settlement_type, return_validation=True)
                if isinstance(parser_result, dict) and "validation" in parser_result:
                    settlements_data = parser_result.get("settlements", [])
                    validation_result = parser_result.get("validation")
                else:
                    settlements_data = parser_result if isinstance(parser_result, list) else [parser_result]
            else:
                settlements_data = parse_amazon_relay_pdf_multi_truck(pdf_path, settlement_type)
        else:
            # Single-truck parser returns dict, wrap in list
            settlement_data = parse_amazon_relay_pdf(pdf_path, settlement_type)
            settlements_data = [settlement_data]
        
        # Enhance with metadata
        result = {
            "source_file": Path(pdf_path).name,
            "extraction_date": datetime.now().isoformat(),
            "settlement_type": settlement_type,
            "settlements": []
        }
        
        for settlement_data in settlements_data:
            # Clean and structure the data
            structured_settlement = {
                "metadata": {
                    "settlement_date": settlement_data.get("settlement_date").isoformat() if settlement_data.get("settlement_date") else None,
                    "week_start": settlement_data.get("week_start").isoformat() if settlement_data.get("week_start") else None,
                    "week_end": settlement_data.get("week_end").isoformat() if settlement_data.get("week_end") else None,
                    "settlement_type": settlement_data.get("settlement_type") or settlement_type,
                    "license_plate": settlement_data.get("license_plate"),
                    "driver_id": settlement_data.get("driver_id"),
                    "driver_name": settlement_data.get("driver_name")
                },
                "revenue": {
                    "gross_revenue": float(settlement_data.get("gross_revenue") or 0),
                    "net_profit": float(settlement_data.get("net_profit") or 0)
                },
                "expenses": {
                    "total_expenses": float(settlement_data.get("expenses") or 0),
                    "categories": self._normalize_expense_categories(settlement_data.get("expense_categories", {}))
                },
                "metrics": {
                    "miles_driven": float(settlement_data.get("miles_driven") or 0),
                    "blocks_delivered": int(settlement_data.get("blocks_delivered") or 0)
                },
                "driver_pay": {
                    "driver_pay": float(settlement_data.get("expense_categories", {}).get("driver_pay", 0) or 0),
                    "payroll_fee": float(settlement_data.get("expense_categories", {}).get("payroll_fee", 0) or 0)
                },
                "raw_data": {
                    # Keep original extracted values for reference
                    "expense_categories_raw": settlement_data.get("expense_categories")
                }
            }
            
            result["settlements"].append(structured_settlement)
        
        # Add validation result if available
        if validation_result:
            result["validation"] = validation_result
        
        return result
    
    def _detect_settlement_type(self, pdf_path: str) -> Optional[str]:
        """Detect settlement type from PDF content"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                
                if "NBM TRANSPORT" in text.upper() or "NBM TRANSPORT LLC" in text.upper():
                    return "NBM Transport LLC"
                elif "277 LOGISTICS" in text.upper():
                    return "277 Logistics"
                elif "OWNER OPERATOR INCOME SHEET" in text.upper() or "INCOME SHEET" in text.upper():
                    return "Owner Operator Income Sheet"
        except Exception:
            pass
        return None
    
    def _detect_multiple_trucks(self, pdf_path: str) -> bool:
        """
        Detect if PDF contains multiple trucks by finding multiple DISTINCT license plates.
        Uses comprehensive detection: checks header, block rows, and all text patterns.
        More robust than relying solely on header, as some PDFs may have incomplete headers.
        """
        try:
            import re
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                
                license_plates = set()
                
                # Method 1: Find license plates from "Plate#:" line (header) - MOST RELIABLE
                # If header shows multiple plates, trust it even if block rows are corrupted
                plate_line_match = re.search(r'Plate#:\s*([^\n]+)', text, re.IGNORECASE)
                header_plates = set()
                if plate_line_match:
                    plate_text = plate_line_match.group(1).strip()
                    # Extract all license plates from the plate line (e.g., "VV9952 VW1503" or "VW9327 VW9328")
                    plate_matches = re.findall(r'\b([A-Z]{2,3}\d{3,6})\b', plate_text, re.IGNORECASE)
                    for plate in plate_matches:
                        normalized_plate = plate.upper().strip()
                        if len(normalized_plate) >= 5:  # Valid plate should be at least 5 chars
                            header_plates.add(normalized_plate)
                            license_plates.add(normalized_plate)
                    
                    # If header shows 2+ plates, that's definitive - return immediately
                    if len(header_plates) >= 2:
                        return True
                
                # Method 2: Always check block rows (B-XXXXX rows) - most reliable source
                # Format: B-XXXXX Driver Name PLATE Pay Amount Driver's pay Fuel amount
                # Handle OCR errors where plates might be corrupted (e.g., "NaVpWpe9r327" -> "VW9327")
                block_plate_matches = re.findall(r'B-[A-Z0-9]+\s+[^\n]*?([A-Z]{2,3}\d{3,6})\b', text, re.IGNORECASE)
                for plate in block_plate_matches:
                    normalized_plate = plate.upper().strip()
                    if len(normalized_plate) >= 5:
                        license_plates.add(normalized_plate)
                
                # Method 2b: Handle corrupted OCR text in block rows
                # Look for patterns like "NaVpWpe9r327" where VW9327 is embedded
                # The corrupted text has mixed case, so we need to find VW followed by 4 digits
                # Pattern: Find VW (case insensitive) followed by exactly 4 digits, possibly with lowercase letters in between
                corrupted_block_lines = re.findall(r'B-[A-Z0-9]+\s+[^\n]*', text, re.IGNORECASE)
                for line in corrupted_block_lines:
                    # Look for VW followed by 4 digits, handling OCR corruption
                    # Pattern: V (or v) followed by W (or w) followed by exactly 4 digits
                    corrupted_plate_match = re.search(r'[Vv][Ww]\s*(\d{4})', line)
                    if corrupted_plate_match:
                        # Reconstruct the plate: VW + 4 digits
                        plate_number = corrupted_plate_match.group(1)
                        reconstructed_plate = f"VW{plate_number}"
                        if len(reconstructed_plate) == 6:  # VW9327 format
                            license_plates.add(reconstructed_plate.upper())
                
                # Method 3: Check for concatenated patterns (e.g., "VereenVW1503")
                # Pattern: letters followed immediately by plate pattern
                concatenated_plates = re.findall(r'([A-Z][a-z]+)([A-Z]{2,3}\d{3,6})', text)
                for _, plate in concatenated_plates:
                    normalized_plate = plate.upper().strip()
                    if len(normalized_plate) >= 5:
                        license_plates.add(normalized_plate)
                
                # Method 4: Look for plates near block identifiers (more reliable than standalone)
                # Find plates that appear on lines with block IDs but weren't caught by Method 2
                block_lines = re.findall(r'B-[A-Z0-9]+[^\n]*', text, re.IGNORECASE)
                for block_line in block_lines:
                    # Extract any plate patterns from this block line
                    line_plates = re.findall(r'\b([A-Z]{2,3}\d{3,6})\b', block_line, re.IGNORECASE)
                    for plate in line_plates:
                        normalized_plate = plate.upper().strip()
                        if len(normalized_plate) >= 5 and len(normalized_plate) <= 8:
                            license_plates.add(normalized_plate)
                
                # Filter and validate plates
                # Remove common false positives
                false_positives = {'IFTA', 'PREPASS', 'SAFETY', 'INSURANCE', 'DISPATCH', 'PAYROLL'}
                valid_plates = {p for p in license_plates 
                               if len(p) >= 5 
                               and len(p) <= 8
                               and p not in false_positives
                               and not p.startswith('#')}  # Skip truck numbers like "#418"
                
                # CRITICAL: Only accept plates that are on the whitelist
                # Import the whitelist from pdf_parser
                from app.utils.pdf_parser import VALID_LICENSE_PLATES
                valid_plates = {p for p in valid_plates if p in VALID_LICENSE_PLATES}
                
                # If we found 2+ DISTINCT valid plates, it's multi-truck
                return len(valid_plates) >= 2
                
        except Exception as e:
            # Log error but don't fail - return False to use single-truck parser
            print(f"Error detecting multiple trucks: {e}")
            return False
    
    def _normalize_expense_categories(self, categories: Dict) -> Dict[str, float]:
        """Normalize expense categories to standard format"""
        if not categories:
            return {}
        
        normalized = {}
        for key, value in categories.items():
            try:
                normalized[key] = float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                normalized[key] = 0.0
        
        return normalized
    
    def extract_to_json_file(self, pdf_path: str, output_path: Optional[str] = None, 
                           settlement_type: Optional[str] = None, individual_files: bool = False) -> List[str]:
        """
        Extract data from PDF and save to JSON file(s).
        
        Args:
            pdf_path: Path to input PDF
            output_path: Optional output JSON file path (defaults to PDF name with .json extension)
            settlement_type: Optional settlement type hint
            individual_files: If True, create one JSON file per settlement
            
        Returns:
            List of paths to created JSON file(s)
        """
        # Extract data
        data = self.extract_from_pdf(pdf_path, settlement_type)
        
        if individual_files and len(data["settlements"]) > 1:
            # Create one JSON file per settlement
            pdf_file = Path(pdf_path)
            output_dir = Path(output_path).parent if output_path else pdf_file.parent
            output_files = []
            
            for idx, settlement in enumerate(data["settlements"]):
                # Create individual settlement JSON
                settlement_json = {
                    "source_file": data["source_file"],
                    "extraction_date": data["extraction_date"],
                    "settlement_type": data["settlement_type"],
                    "settlement": settlement  # Single settlement, not array
                }
                
                # Generate filename with settlement index and license plate
                license_plate = settlement.get("metadata", {}).get("license_plate", "")
                settlement_date = settlement.get("metadata", {}).get("settlement_date", "")
                if license_plate and settlement_date:
                    filename = f"{pdf_file.stem}_{license_plate}_{settlement_date.replace('-', '')}.json"
                else:
                    filename = f"{pdf_file.stem}_settlement_{idx + 1}.json"
                
                file_path = output_dir / filename
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(settlement_json, f, indent=2, ensure_ascii=False)
                output_files.append(str(file_path))
            
            return output_files
        else:
            # Single JSON file with all settlements
            if not output_path:
                pdf_file = Path(pdf_path)
                output_path = pdf_file.parent / f"{pdf_file.stem}_extracted.json"
            
            # Write JSON file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return [str(output_path)]
    
    def batch_extract(self, pdf_directory: str, output_directory: Optional[str] = None) -> List[Dict]:
        """
        Extract data from all PDFs in a directory.
        
        Args:
            pdf_directory: Directory containing PDF files
            output_directory: Optional directory for JSON output (defaults to same as PDF directory)
            
        Returns:
            List of extraction results with status
        """
        pdf_dir = Path(pdf_directory)
        output_dir = Path(output_directory) if output_directory else pdf_dir
        
        results = []
        
        for pdf_file in pdf_dir.glob("*.pdf"):
            try:
                json_path = output_dir / f"{pdf_file.stem}_extracted.json"
                self.extract_to_json_file(str(pdf_file), str(json_path))
                results.append({
                    "pdf_file": pdf_file.name,
                    "json_file": json_path.name,
                    "status": "success"
                })
            except Exception as e:
                results.append({
                    "pdf_file": pdf_file.name,
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    def extract_single_truck_pdfs(self, pdf_directory: str, output_directory: Optional[str] = None) -> Dict:
        """
        Identify and process only single-truck PDFs from a directory.
        This is Phase 1 of the two-phase extraction process.
        
        Args:
            pdf_directory: Directory containing PDF files
            output_directory: Optional directory for JSON output (defaults to same as PDF directory)
            
        Returns:
            Dictionary with:
            - single_truck_pdfs: List of PDFs identified as single-truck
            - multi_truck_pdfs: List of PDFs identified as multi-truck
            - results: List of extraction results with status
            - consolidated_data: Combined JSON data from all single-truck PDFs
        """
        pdf_dir = Path(pdf_directory)
        output_dir = Path(output_directory) if output_directory else pdf_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        single_truck_pdfs = []
        multi_truck_pdfs = []
        results = []
        all_settlements = []
        
        # First pass: identify single-truck vs multi-truck PDFs
        for pdf_file in sorted(pdf_dir.glob("*.pdf")):
            try:
                is_multi_truck = self._detect_multiple_trucks(str(pdf_file))
                if is_multi_truck:
                    multi_truck_pdfs.append(pdf_file.name)
                else:
                    single_truck_pdfs.append(pdf_file.name)
            except Exception as e:
                # If detection fails, treat as multi-truck to be safe
                multi_truck_pdfs.append(pdf_file.name)
        
        # Second pass: process only single-truck PDFs
        for pdf_file in sorted(pdf_dir.glob("*.pdf")):
            if pdf_file.name in single_truck_pdfs:
                try:
                    json_path = output_dir / f"{pdf_file.stem}_extracted.json"
                    json_files = self.extract_to_json_file(str(pdf_file), str(json_path))
                    
                    # Load the extracted data and add to consolidated list
                    with open(json_files[0], 'r', encoding='utf-8') as f:
                        extracted_data = json.load(f)
                        # Add each settlement to the consolidated list
                        for settlement in extracted_data.get("settlements", []):
                            settlement_entry = {
                                "source_file": extracted_data["source_file"],
                                "extraction_date": extracted_data["extraction_date"],
                                "settlement_type": extracted_data["settlement_type"],
                                "settlement": settlement
                            }
                            all_settlements.append(settlement_entry)
                    
                    results.append({
                        "pdf_file": pdf_file.name,
                        "json_file": json_path.name,
                        "status": "success",
                        "type": "single_truck"
                    })
                except Exception as e:
                    results.append({
                        "pdf_file": pdf_file.name,
                        "status": "error",
                        "error": str(e),
                        "type": "single_truck"
                    })
        
        # Create consolidated data structure
        consolidated_data = {
            "consolidation_date": datetime.now().isoformat(),
            "source": "phase1_single_truck_extraction",
            "total_settlements": len(all_settlements),
            "settlements": all_settlements
        }
        
        return {
            "single_truck_pdfs": single_truck_pdfs,
            "multi_truck_pdfs": multi_truck_pdfs,
            "results": results,
            "consolidated_data": consolidated_data
        }


def main():
    """CLI interface for the extraction tool"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract settlement data from PDFs to JSON")
    parser.add_argument("pdf_path", help="Path to PDF file or directory")
    parser.add_argument("-o", "--output", help="Output JSON file path (for single file)")
    parser.add_argument("-t", "--type", help="Settlement type (277 Logistics, NBM Transport LLC, etc.)")
    parser.add_argument("-b", "--batch", action="store_true", help="Process directory of PDFs")
    
    args = parser.parse_args()
    
    extractor = SettlementExtractor()
    
    if args.batch:
        # Batch processing
        results = extractor.batch_extract(args.pdf_path, args.output)
        print(f"\nProcessed {len(results)} files:")
        for result in results:
            if result["status"] == "success":
                print(f"  ✓ {result['pdf_file']} -> {result['json_file']}")
            else:
                print(f"  ✗ {result['pdf_file']}: {result.get('error', 'Unknown error')}")
    else:
        # Single file processing
        json_path = extractor.extract_to_json_file(args.pdf_path, args.output, args.type)
        print(f"Extracted data saved to: {json_path}")


if __name__ == "__main__":
    main()

