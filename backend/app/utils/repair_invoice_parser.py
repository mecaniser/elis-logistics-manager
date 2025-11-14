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
            
            # Extract Description - prioritize table extraction for structured data
            description_parts = []
            
            # Method 1: Try to extract from table structure using pdfplumber
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        # Look for description column in table
                        # Common column names: "DESCRIPTION", "ACTIVITY DESCRIPTION", "WORK DESCRIPTION", "SERVICE DESCRIPTION"
                        header_row_idx = None
                        desc_col_idx = None
                        
                        # Find header row and description column
                        for row_idx, row in enumerate(table):
                            if row and len(row) > 0:
                                # Check if this row contains column headers
                                row_text = ' '.join([str(cell) if cell else '' for cell in row]).upper()
                                if any(keyword in row_text for keyword in ['DESCRIPTION', 'ACTIVITY', 'WORK', 'SERVICE']):
                                    header_row_idx = row_idx
                                    # Find which column contains description
                                    for col_idx, cell in enumerate(row):
                                        if cell:
                                            cell_upper = str(cell).upper()
                                            if any(keyword in cell_upper for keyword in ['DESCRIPTION', 'ACTIVITY', 'WORK', 'SERVICE']):
                                                desc_col_idx = col_idx
                                                break
                                    break
                        
                        # Extract description from description column
                        if header_row_idx is not None and desc_col_idx is not None:
                            for row_idx in range(header_row_idx + 1, len(table)):
                                row = table[row_idx]
                                if row and len(row) > desc_col_idx and row[desc_col_idx]:
                                    desc_text = str(row[desc_col_idx]).strip()
                                    # Skip if it's a header, total, or empty
                                    if desc_text and desc_text.upper() not in ['DESCRIPTION', 'TOTAL', 'SUBTOTAL', 'TAX', 'BALANCE DUE', '']:
                                        # Clean up the description
                                        desc_text = re.sub(r'\s+', ' ', desc_text)  # Normalize whitespace
                                        if len(desc_text) > 5:  # Only add meaningful descriptions
                                            description_parts.append(desc_text)
            
            # Method 2: If no table data found, try regex patterns on text
            if not description_parts:
                # Look for description after TOTAL or TAX line
                work_desc_patterns = [
                    r'(REMOVED[^\n]*(?:\n[^\n]*){0,5}?)(?=\n(?:BALANCE|TOTAL|TAX|$))',
                    r'(REPLACED[^\n]*(?:\n[^\n]*){0,5}?)(?=\n(?:BALANCE|TOTAL|TAX|$))',
                    r'(INSTALLED[^\n]*(?:\n[^\n]*){0,5}?)(?=\n(?:BALANCE|TOTAL|TAX|$))',
                    r'(REPAIRED[^\n]*(?:\n[^\n]*){0,5}?)(?=\n(?:BALANCE|TOTAL|TAX|$))',
                    r'(FIXED[^\n]*(?:\n[^\n]*){0,5}?)(?=\n(?:BALANCE|TOTAL|TAX|$))',
                    r'(SERVICED[^\n]*(?:\n[^\n]*){0,5}?)(?=\n(?:BALANCE|TOTAL|TAX|$))',
                ]
                
                for pattern in work_desc_patterns:
                    desc_match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                    if desc_match:
                        description = desc_match.group(1).strip()
                        # Clean up - remove extra whitespace and newlines
                        description = re.sub(r'\s+', ' ', description)
                        # Remove common invoice text and numbers that shouldn't be there
                        description = re.sub(r'\b(Contact|PHOTOS ATTACHED|TAX\s+\d+|TOTAL\s+\d+|SUBTOTAL|BALANCE DUE)\b', '', description, flags=re.IGNORECASE)
                        # Remove standalone numbers/decimals that are likely from invoice totals
                        description = re.sub(r'\s+\.\d+\s+', ' ', description)
                        description = re.sub(r'\s+\d+\.\d+\s+', ' ', description)
                        # Remove trailing periods and clean up
                        description = re.sub(r'\.+$', '', description)
                        description = re.sub(r'\s+\.\s+', ' ', description)  # Remove standalone periods
                        description = description.strip()
                        if len(description) > 10:  # Only use if meaningful
                            description_parts.append(description)
                            break
                
                # Method 3: Look for text in ACTIVITY DESCRIPTION column (regex fallback)
                if not description_parts:
                    desc_match = re.search(r'ACTIVITY\s+DESCRIPTION\s+([^\n]+(?:\n[^\n]+){0,3})', text, re.IGNORECASE | re.MULTILINE)
                    if desc_match:
                        description = desc_match.group(1).strip()
                        description = re.sub(r'\s+', ' ', description)
                        description = re.sub(r'\b(TOTAL|SUBTOTAL|TAX|BALANCE)\b', '', description, flags=re.IGNORECASE)
                        if len(description) > 10:
                            description_parts.append(description)
            
            # Combine all description parts
            if description_parts:
                # Join multiple descriptions with semicolons or newlines
                combined_description = '; '.join(description_parts)
                # Final cleanup
                combined_description = re.sub(r'\s+', ' ', combined_description)  # Normalize whitespace
                combined_description = re.sub(r';\s*;+', ';', combined_description)  # Remove duplicate semicolons
                combined_description = combined_description.strip('; ').strip()
                if len(combined_description) > 5:
                    repair_data["description"] = combined_description
            
            # Try to determine category from description
            if repair_data["description"]:
                desc_lower = repair_data["description"].lower()
                
                # Engine-related keywords
                engine_keywords = ['starter', 'motor', 'engine', 'crankshaft', 'piston', 'cylinder', 'head gasket', 
                                  'timing belt', 'serpentine', 'alternator', 'water pump', 'radiator', 'coolant',
                                  'thermostat', 'fan', 'turbo', 'exhaust', 'manifold', 'catalytic', 'muffler']
                
                # Tire-related keywords
                tire_keywords = ['tire', 'tyre', 'wheel', 'rim', 'lug nut', 'hub', 'bearing', 'axle', 'alignment',
                                'rotation', 'balance', 'tread', 'valve stem']
                
                # Electrical-related keywords
                electrical_keywords = ['battery', 'electrical', 'wired', 'wire', 'wiring', 'inverter', 'fuse', 'relay',
                                      'sensor', 'switch', 'light', 'bulb', 'led', 'harness', 'connector', 'ground',
                                      'starter solenoid', 'ignition', 'spark plug', 'coil']
                
                # Brake-related keywords
                brake_keywords = ['brake', 'braking', 'pad', 'rotor', 'caliper', 'line', 'fluid', 'master cylinder',
                                 'abs', 'anti-lock']
                
                # Maintenance-related keywords
                maintenance_keywords = ['oil', 'filter', 'air filter', 'fuel filter', 'maintenance', 'service',
                                       'lube', 'grease', 'fluid change', 'transmission', 'differential', 'transfer case']
                
                # Count matches for each category
                engine_matches = sum(1 for keyword in engine_keywords if keyword in desc_lower)
                tire_matches = sum(1 for keyword in tire_keywords if keyword in desc_lower)
                electrical_matches = sum(1 for keyword in electrical_keywords if keyword in desc_lower)
                brake_matches = sum(1 for keyword in brake_keywords if keyword in desc_lower)
                maintenance_matches = sum(1 for keyword in maintenance_keywords if keyword in desc_lower)
                
                # Assign category based on highest match count
                category_scores = {
                    'engine': engine_matches,
                    'tires': tire_matches,
                    'electrical': electrical_matches,
                    'brakes': brake_matches,
                    'maintenance': maintenance_matches
                }
                
                max_score = max(category_scores.values())
                if max_score > 0:
                    # Get category with highest score
                    repair_data["category"] = max(category_scores, key=category_scores.get)
                else:
                    repair_data["category"] = "other"
    
    except Exception as e:
        raise Exception(f"Error parsing repair invoice PDF: {str(e)}")
    
    return repair_data

