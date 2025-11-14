"""
PDF parser for repair invoice files
"""
import pdfplumber
import re
from datetime import datetime
from typing import Dict, Optional


def parse_repair_invoice_pdf(file_path: str) -> Dict:
    """
    Parse repair invoice PDF and extract structured data.
    
    Expected PDF format (CaroMeck Diesel PM LLC):
    - Invoice #: XXXX
    - DATE: MM/DD/YYYY
    - TOTAL: $X,XXX.XX
    - BALANCE DUE: $X,XXX.XX
    - DESCRIPTION: Text description of work done
    - VIN NUMBER: XXXXXXXXXXXXXXXX
    - Year, Make, & Model: YYYY MAKE MODEL
    """
    repair_data = {
        "repair_date": None,
        "description": None,
        "cost": None,
        "category": None,
        "vin": None,
        "invoice_number": None,
    }
    
    try:
        with pdfplumber.open(file_path) as pdf:
            # Extract text from all pages
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            
            # Extract Invoice Date
            # Format in header: "3528 10/30/2025 $798.54 11/08/2025"
            # Look for date pattern after invoice number or in header row
            # Try to find date in the invoice header line
            header_date_match = re.search(r'(\d{4})\s+(\d{1,2}/\d{1,2}/\d{4})\s+\$', text, re.IGNORECASE)
            if header_date_match:
                try:
                    repair_data["repair_date"] = datetime.strptime(
                        header_date_match.group(2), "%m/%d/%Y"
                    ).date()
                except ValueError:
                    pass
            
            # Fallback: look for any date pattern
            if not repair_data["repair_date"]:
                date_match = re.search(r'DATE\s+(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
                if date_match:
                    try:
                        repair_data["repair_date"] = datetime.strptime(
                            date_match.group(1), "%m/%d/%Y"
                        ).date()
                    except ValueError:
                        pass
            
            # Extract Total/Balance Due
            # Prefer "BALANCE DUE" as it's the final amount, then "TOTAL" (not SUBTOTAL)
            balance_match = re.search(r'BALANCE DUE\s*\$?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
            if balance_match:
                repair_data["cost"] = float(
                    balance_match.group(1).replace(",", "")
                )
            else:
                # Look for TOTAL (but not SUBTOTAL)
                total_match = re.search(r'(?<!SUB)TOTAL\s*:?\s*\$?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
                if total_match:
                    repair_data["cost"] = float(
                        total_match.group(1).replace(",", "")
                    )
            
            # Extract Invoice Number
            # Format: "3528 10/30/2025" - number before date in header
            invoice_match = re.search(r'(\d{4})\s+\d{1,2}/\d{1,2}/\d{4}\s+\$', text, re.IGNORECASE)
            if invoice_match:
                repair_data["invoice_number"] = invoice_match.group(1)
            else:
                # Fallback: look for "INVOICE # 3528"
                invoice_match = re.search(r'INVOICE\s*#\s+(\d+)', text, re.IGNORECASE)
                if invoice_match:
                    repair_data["invoice_number"] = invoice_match.group(1)
            
            # Extract VIN Number
            # Format: "VIN NUMBER 4V4WC9EG2LN250024" (17 characters)
            # Look for 17-character alphanumeric sequence after "VIN NUMBER"
            vin_match = re.search(r'VIN\s*NUMBER\s+([A-Z0-9]{17})', text, re.IGNORECASE)
            if vin_match:
                repair_data["vin"] = vin_match.group(1).upper()
            else:
                # Fallback: look for VIN pattern in the line with VIN NUMBER
                vin_line_match = re.search(r'VIN\s*NUMBER[^\n]*\n[^\n]*([A-Z0-9]{17})', text, re.IGNORECASE | re.MULTILINE)
                if vin_line_match:
                    repair_data["vin"] = vin_line_match.group(1).upper()
                else:
                    # Last resort: find any 17-character alphanumeric sequence
                    vin_match = re.search(r'\b([A-Z0-9]{17})\b', text)
                    if vin_match:
                        repair_data["vin"] = vin_match.group(1).upper()
            
            # Extract Description
            # Look for work description text - usually appears after the table
            # Pattern: Look for sentences describing work done (all caps, after SUBTOTAL/TAX)
            # Example: "REMOVED AND REPLACED STARTER MOTOR. WIRED INVERTER TO BATTERY..."
            
            # First, try to find description after TOTAL or TAX line
            # Look for text that starts with action words and continues
            work_desc_patterns = [
                r'(REMOVED[^\n]*(?:\n[^\n]*){0,3}?)(?=\n(?:BALANCE|$))',
                r'(REPLACED[^\n]*(?:\n[^\n]*){0,3}?)(?=\n(?:BALANCE|$))',
                r'(INSTALLED[^\n]*(?:\n[^\n]*){0,3}?)(?=\n(?:BALANCE|$))',
            ]
            
            for pattern in work_desc_patterns:
                desc_match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if desc_match:
                    description = desc_match.group(1).strip()
                    # Clean up - remove extra whitespace and newlines
                    description = re.sub(r'\s+', ' ', description)
                    # Remove common invoice text and numbers that shouldn't be there
                    description = re.sub(r'\b(Contact|PHOTOS ATTACHED|TAX\s+\d+|TOTAL\s+\d+)\b', '', description, flags=re.IGNORECASE)
                    # Remove standalone numbers/decimals that are likely from invoice totals
                    description = re.sub(r'\s+\.\d+\s+', ' ', description)
                    description = re.sub(r'\s+\d+\.\d+\s+', ' ', description)
                    # Remove trailing periods and clean up
                    description = re.sub(r'\.+$', '', description)
                    description = re.sub(r'\s+\.\s+', ' ', description)  # Remove standalone periods
                    description = description.strip()
                    if len(description) > 10:  # Only use if meaningful
                        repair_data["description"] = description
                        break
            
            # Fallback: Look for text in ACTIVITY DESCRIPTION column
            if not repair_data["description"]:
                # Try to extract from table row
                desc_match = re.search(r'ACTIVITY DESCRIPTION\s+([^\n]+)', text, re.IGNORECASE)
                if desc_match:
                    repair_data["description"] = desc_match.group(1).strip()
            
            # Try to determine category from description
            if repair_data["description"]:
                desc_lower = repair_data["description"].lower()
                if any(word in desc_lower for word in ['starter', 'motor', 'engine']):
                    repair_data["category"] = "engine"
                elif any(word in desc_lower for word in ['tire', 'wheel', 'rim']):
                    repair_data["category"] = "tires"
                elif any(word in desc_lower for word in ['battery', 'electrical', 'wired', 'inverter']):
                    repair_data["category"] = "electrical"
                elif any(word in desc_lower for word in ['brake', 'braking']):
                    repair_data["category"] = "brakes"
                elif any(word in desc_lower for word in ['oil', 'filter', 'maintenance']):
                    repair_data["category"] = "maintenance"
                else:
                    repair_data["category"] = "other"
    
    except Exception as e:
        raise Exception(f"Error parsing repair invoice PDF: {str(e)}")
    
    return repair_data

