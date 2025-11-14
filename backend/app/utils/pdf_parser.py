"""
PDF parser for Amazon Relay settlement files
"""
import pdfplumber
import re
from datetime import datetime
from typing import Dict, List


def parse_amazon_relay_pdf(file_path: str, settlement_type: str = None) -> Dict:
    """
    Parse Amazon Relay settlement PDF and extract structured data.
    
    Supports two PDF formats:
    1. Paystub format:
       - Pay Period: MM/DD/YYYY (week_end/settlement_date)
       - Gross Pay: $X,XXX.XX
       - Net Pay: $X,XXX.XX
       - Block IDs: B-XXXXX
    
    2. Owner Operator Income Sheet format:
       - Date Period: MM/DD-MM/DD/YYYY
       - SUMMARY GROSS: ($ X,XXX.XX) - amounts in parentheses
       - PAID TO DRIVER: ($ X,XXX.XX)
       - LOAD MILES: XXX.X
       - STOPS: X
    """
    settlement_data = {
        "settlement_date": None,
        "week_start": None,
        "week_end": None,
        "miles_driven": None,
        "blocks_delivered": None,
        "gross_revenue": None,
        "expenses": None,
        "net_profit": None,
        "driver_id": None,
        "license_plate": None  # Extract from PDF for truck matching
    }
    
    try:
        with pdfplumber.open(file_path) as pdf:
            # Extract text from all pages
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            
            # Detect PDF format
            is_income_sheet_format = "OWNER OPERATOR INCOME SHEET" in text or "INCOME SHEET" in text
            
            # Extract Pay Period (Format 1: Paystub) or Date Period (Format 2: Income Sheet)
            if is_income_sheet_format:
                # Format 2: "Date Period : 12/22-12/28/2024"
                date_period_match = re.search(r'Date Period\s*:\s*(\d{1,2}/\d{1,2})-(\d{1,2}/\d{1,2})/(\d{4})', text, re.IGNORECASE)
                if date_period_match:
                    try:
                        week_start_str = f"{date_period_match.group(1)}/{date_period_match.group(3)}"
                        week_end_str = f"{date_period_match.group(2)}/{date_period_match.group(3)}"
                        settlement_data["week_start"] = datetime.strptime(week_start_str, "%m/%d/%Y").date()
                        settlement_data["week_end"] = datetime.strptime(week_end_str, "%m/%d/%Y").date()
                        settlement_data["settlement_date"] = settlement_data["week_end"]
                    except ValueError:
                        pass
            else:
                # Format 1: "Pay Period: MM/DD/YYYY"
                pay_period_match = re.search(r'Pay Period:\s*(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
                if pay_period_match:
                    try:
                        settlement_data["settlement_date"] = datetime.strptime(
                            pay_period_match.group(1), "%m/%d/%Y"
                        ).date()
                        settlement_data["week_end"] = settlement_data["settlement_date"]
                    except ValueError:
                        pass
            
            # Extract Generated on date (Format 1 only)
            generated_match = re.search(r'Generated on:\s*(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
            
            # Extract License Plate(s) from PDF
            # Format 1: "Plate#: VW9327 VW9328" or "Plate#: 418 VW9328"
            # Format 2: "VW1503 #418" or "TRUCK#: 418"
            if is_income_sheet_format:
                # Format 2: Look for patterns like "VW1503 #418" or "TRUCK#: 418"
                # Try to find truck number pattern
                truck_match = re.search(r'TRUCK#\s*:\s*(\d+)', text, re.IGNORECASE)
                if truck_match:
                    truck_num = truck_match.group(1)
                    # Also try to find plate like VW1503
                    plate_match = re.search(r'\b([A-Z]{1,3}\d{3,6})\b', text)
                    if plate_match:
                        settlement_data["license_plate"] = plate_match.group(1).upper()
                    else:
                        # Use truck number as plate
                        settlement_data["license_plate"] = f"#{truck_num}"
                else:
                    # Look for pattern like "VW1503 #418"
                    plate_combo_match = re.search(r'\b([A-Z]{1,3}\d{3,6})\s*#(\d+)', text)
                    if plate_combo_match:
                        settlement_data["license_plate"] = plate_combo_match.group(1).upper()
                    else:
                        # Just look for any plate pattern
                        plate_match = re.search(r'\b([A-Z]{1,3}\d{3,6})\b', text)
                        if plate_match:
                            settlement_data["license_plate"] = plate_match.group(1).upper()
            else:
                # Format 1: "Plate#: VW9327 VW9328"
                plate_match = re.search(r'Plate#:\s*([^\n]+)', text, re.IGNORECASE)
                if plate_match:
                    plate_text = plate_match.group(1).strip()
                    plates = re.findall(r'\b([A-Z]{1,3}\d{3,6})\b', plate_text)
                    if plates:
                        settlement_data["license_plate"] = plates[-1].upper()
                    else:
                        fallback_plates = re.findall(r'\b([A-Z0-9]{4,8})\b', plate_text)
                        if fallback_plates:
                            settlement_data["license_plate"] = fallback_plates[-1].upper()
            
            # Extract Gross Pay (gross_revenue)
            if is_income_sheet_format:
                # Format 2: "SUMMARY GROSS 795.0 ($ 2,119.07) ($ 600.00) ($ 517.94)"
                # First amount in parentheses is the gross revenue
                gross_match = re.search(r'SUMMARY GROSS[^\n]*?\(\$\s*([\d,]+\.?\d*)\)', text, re.IGNORECASE)
                if gross_match:
                    settlement_data["gross_revenue"] = float(
                        gross_match.group(1).replace(",", "")
                    )
                else:
                    # Fallback: look for any number after SUMMARY GROSS
                    gross_match = re.search(r'SUMMARY GROSS[^\n]*\$\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
                    if gross_match:
                        settlement_data["gross_revenue"] = float(
                            gross_match.group(1).replace(",", "")
                        )
            else:
                # Format 1: "Gross Pay $X,XXX.XX"
                gross_pay_match = re.search(r'Gross Pay\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
                if gross_pay_match:
                    settlement_data["gross_revenue"] = float(
                        gross_pay_match.group(1).replace(",", "")
                    )
            
            # Extract Net Pay (net_profit)
            if is_income_sheet_format:
                # Format 2: "PAID TO DRIVER ($ 295.22)" - amount in parentheses
                net_match = re.search(r'PAID TO DRIVER[^\n]*\(\$\s*([\d,]+\.?\d*)\)', text, re.IGNORECASE)
                if net_match:
                    settlement_data["net_profit"] = float(
                        net_match.group(1).replace(",", "")
                    )
                else:
                    # Fallback: look for any number after PAID TO DRIVER
                    net_match = re.search(r'PAID TO DRIVER[^\n]*\$\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
                    if net_match:
                        settlement_data["net_profit"] = float(
                            net_match.group(1).replace(",", "")
                        )
            else:
                # Format 1: "Net Pay $X,XXX.XX"
                net_pay_match = re.search(r'Net Pay\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
                if net_pay_match:
                    settlement_data["net_profit"] = float(
                        net_pay_match.group(1).replace(",", "")
                    )
            
            # Calculate total expenses and categorize them
            total_expenses = 0.0
            expense_categories = {
                "fuel": 0.0,
                "dispatch_fee": 0.0,
                "insurance": 0.0,
                "safety": 0.0,
                "prepass": 0.0,
                "ifta": 0.0,
                "driver_pay": 0.0,
                "payroll_fee": 0.0,
                "truck_parking": 0.0,
                "service_on_truck": 0.0,
                "custom": 0.0
            }
            
            if is_income_sheet_format:
                # Format 2: Expenses in parentheses like "($ 211.91)"
                # Process line by line to avoid false matches
                expense_mappings = [
                    # DISPATCH FEE line is actually PAYROLL FEE - may have percentage and amount, take the fee amount (last one)
                    (r'^DISPATCH[^\n]*FEE[^\n]*%\s*\(\$\s*([\d,]+\.?\d*)\)[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'payroll_fee', 2),  # Two amounts, take second (the fee)
                    (r'^DISPATCH[^\n]*FEE[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'payroll_fee', 1),  # Single amount
                    # FUEL - standalone line with FUEL keyword
                    (r'^FUEL[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'fuel', 1),  # Single amount on FUEL line
                    (r'IFTA[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'ifta', 1),
                    (r'SAFETY[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'safety', 1),
                    (r'PREPASS[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'prepass', 1),
                    (r'INSURANCE[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'insurance', 1),
                    # DRIVER'S PAY in PDF - treat as base driver's pay (before payroll fee)
                    # Payroll fee will be calculated as percentage of this base amount
                    (r"DRIVER'S PAY[^\n]*\(\$\s*([\d,]+\.?\d*)\)", 'driver_pay', 1),
                    (r'PAYROLL[^\n]*FEE[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'payroll_fee', 1),
                    (r'SERVICE ON THE TRUCK[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'service_on_truck', 1),
                    (r'TRUCK PARKING[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'truck_parking', 1),
                ]
            else:
                # Format 1: "Expense Name $X,XXX.XX"
                expense_mappings = [
                    (r'Fuel\s+\$?([\d,]+\.?\d*)', 'fuel'),
                    (r'IFTA\s+\$?([\d,]+\.?\d*)', 'ifta'),
                    (r'Dispatch Fee\s+\$?([\d,]+\.?\d*)', 'dispatch_fee'),
                    (r'Safety\s+\$?([\d,]+\.?\d*)', 'safety'),
                    (r'Prepass\s+\$?([\d,]+\.?\d*)', 'prepass'),
                    (r'Insurance\s+\$?([\d,]+\.?\d*)', 'insurance'),
                    (r"Driver's Pay\s+\$?([\d,]+\.?\d*)", 'driver_pay'),
                    (r"Driver's Pay Fee\s+\$?([\d,]+\.?\d*)", 'driver_pay'),
                    (r'Payroll Fee\s+\$?([\d,]+\.?\d*)', 'payroll_fee'),
                    (r'Payroll\s+\$?([\d,]+\.?\d*)', 'payroll_fee'),
                    (r'Service on Truck\s+\$?([\d,]+\.?\d*)', 'service_on_truck'),
                    (r'Truck Parking\s+\$?([\d,]+\.?\d*)', 'truck_parking'),
                    (r'Deductions\s+\$?([\d,]+\.?\d*)', 'custom'),
                ]
            
            # Special handling for settlement types that explicitly list "driver's pay" and "driver's pay fee"
            # NBM Transport LLC and 277 Logistics both have these fields explicitly listed
            settlement_type_upper = settlement_type.upper() if settlement_type else ""
            if settlement_type_upper in ["NBM TRANSPORT LLC", "277 LOGISTICS"]:
                # Look for "DRIVER'S PAY" and "DRIVER'S PAY FEE" rows specifically
                # Format 2 (income sheet): amounts in parentheses like "($ 1,234.56)"
                drivers_pay_match = re.search(r"DRIVER'S PAY[^\n]*\(\$\s*([\d,]+\.?\d*)\)", text, re.IGNORECASE)
                drivers_pay_fee_match = re.search(r"DRIVER'S PAY FEE[^\n]*\(\$\s*([\d,]+\.?\d*)\)", text, re.IGNORECASE)
                
                # Format 1 (paystub): amounts like "$1,234.56" or "1,234.56"
                if not drivers_pay_match:
                    drivers_pay_match = re.search(r"Driver's Pay\s+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
                if not drivers_pay_fee_match:
                    drivers_pay_fee_match = re.search(r"Driver's Pay Fee\s+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
                
                if drivers_pay_match:
                    driver_pay_amount = float(drivers_pay_match.group(1).replace(",", ""))
                    expense_categories["driver_pay"] = driver_pay_amount
                    total_expenses += driver_pay_amount
                
                if drivers_pay_fee_match:
                    payroll_fee_amount = float(drivers_pay_fee_match.group(1).replace(",", ""))
                    expense_categories["payroll_fee"] = payroll_fee_amount
                    total_expenses += payroll_fee_amount
            
            # Process line by line for income sheet format to avoid false matches
            if is_income_sheet_format:
                lines = text.split('\n')
                for line in lines:
                    # Skip processing driver's pay and payroll fee for settlement types that explicitly list them
                    settlement_type_upper = settlement_type.upper() if settlement_type else ""
                    if settlement_type_upper in ["NBM TRANSPORT LLC", "277 LOGISTICS"]:
                        if re.search(r"DRIVER'S PAY", line, re.IGNORECASE) or re.search(r"DRIVER'S PAY FEE", line, re.IGNORECASE):
                            continue
                    
                    for mapping in expense_mappings:
                        if len(mapping) == 3:
                            pattern, category, group_num = mapping
                        else:
                            # Backward compatibility
                            pattern, category = mapping
                            group_num = 1
                        
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            # Only update if category is still 0 (avoid double counting)
                            if category in expense_categories and expense_categories[category] == 0:
                                amount_str = match.group(group_num).replace(",", "")
                                amount = float(amount_str)
                                
                                # Special handling: if driver's pay is found, treat as gross and calculate base + payroll fee
                                # Skip this for settlement types that explicitly list driver's pay and payroll fee
                                settlement_type_upper = settlement_type.upper() if settlement_type else ""
                                if category == 'driver_pay' and settlement_type_upper not in ["NBM TRANSPORT LLC", "277 LOGISTICS"]:
                                    driver_pay_gross = amount
                                    # Check if payroll fee was already found (e.g., from DISPATCH FEE line)
                                    if expense_categories["payroll_fee"] > 0:
                                        # Use found payroll fee and calculate base driver's pay
                                        payroll_fee_amount = expense_categories["payroll_fee"]
                                        base_driver_pay = driver_pay_gross - payroll_fee_amount
                                    else:
                                        # Calculate base driver's pay and payroll fee
                                        # If gross = base + (base * 6.5%), then base = gross / (1 + 6.5%)
                                        base_driver_pay = driver_pay_gross / 1.065
                                        payroll_fee_amount = base_driver_pay * 0.065
                                        expense_categories["payroll_fee"] = payroll_fee_amount
                                        total_expenses += payroll_fee_amount
                                    
                                    expense_categories["driver_pay"] = base_driver_pay
                                    total_expenses += base_driver_pay
                                else:
                                    expense_categories[category] = amount
                                    total_expenses += amount
                                break  # Found this category, move to next line
            
            if not is_income_sheet_format:
                # Format 1: Search entire text
                for mapping in expense_mappings:
                    if len(mapping) == 3:
                        pattern, category, group_num = mapping
                    else:
                        # Backward compatibility
                        pattern, category = mapping
                        group_num = 1
                    
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        # Only update if category is still 0 (avoid double counting)
                        if category in expense_categories and expense_categories[category] == 0:
                            amount_str = match.group(group_num).replace(",", "")
                            amount = float(amount_str)
                            
                            # Special handling: if driver's pay is found, treat as gross and calculate base + payroll fee
                            # Skip this for settlement types that explicitly list driver's pay and payroll fee
                            settlement_type_upper = settlement_type.upper() if settlement_type else ""
                            if category == 'driver_pay' and settlement_type_upper not in ["NBM TRANSPORT LLC", "277 LOGISTICS"]:
                                driver_pay_gross = amount
                                # Check if payroll fee was already found
                                if expense_categories["payroll_fee"] > 0:
                                    # Use found payroll fee and calculate base driver's pay
                                    payroll_fee_amount = expense_categories["payroll_fee"]
                                    base_driver_pay = driver_pay_gross - payroll_fee_amount
                                else:
                                    # Calculate base driver's pay and payroll fee
                                    base_driver_pay = driver_pay_gross / 1.065
                                    payroll_fee_amount = base_driver_pay * 0.065
                                    expense_categories["payroll_fee"] = payroll_fee_amount
                                    total_expenses += payroll_fee_amount
                                
                                expense_categories["driver_pay"] = base_driver_pay
                                total_expenses += base_driver_pay
                            else:
                                expense_categories[category] = amount
                                total_expenses += amount
                
                # Format 1: Also check for Driver's Pay separately (in case it wasn't caught above)
                # Skip this for settlement types that explicitly list driver's pay and payroll fee
                settlement_type_upper = settlement_type.upper() if settlement_type else ""
                if expense_categories["driver_pay"] == 0 and settlement_type_upper not in ["NBM TRANSPORT LLC", "277 LOGISTICS"]:
                    drivers_pay_match = re.search(r"Driver's Pay\s+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
                    if drivers_pay_match:
                        driver_pay_gross = float(drivers_pay_match.group(1).replace(",", ""))
                        # Check if payroll fee was already found
                        if expense_categories["payroll_fee"] > 0:
                            # Use found payroll fee and calculate base driver's pay
                            payroll_fee_amount = expense_categories["payroll_fee"]
                            base_driver_pay = driver_pay_gross - payroll_fee_amount
                        else:
                            # Calculate base driver's pay and payroll fee
                            base_driver_pay = driver_pay_gross / 1.065
                            payroll_fee_amount = base_driver_pay * 0.065
                            expense_categories["payroll_fee"] = payroll_fee_amount
                            total_expenses += payroll_fee_amount
                        
                        expense_categories["driver_pay"] = base_driver_pay
                        total_expenses += base_driver_pay
            
            # Check for Payroll Fee separately (may appear as "Payroll Fee" or "Payroll" or percentage-based)
            # Note: "DISPATCH FEE" line is already mapped to payroll_fee above, this is for explicit "PAYROLL FEE" lines
            payroll_fee_match = re.search(r'Payroll\s+Fee\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if payroll_fee_match and expense_categories["payroll_fee"] == 0:
                amount = float(payroll_fee_match.group(1).replace(",", ""))
                expense_categories["payroll_fee"] += amount
                total_expenses += amount
            
            # Extract dispatch fee from PDF if explicitly shown
            # Note: the "DISPATCH FEE" line in PDFs is actually payroll fee, so we look for dispatch fee separately
            # Only extract if explicitly found in PDF - no automatic calculation
            if expense_categories["dispatch_fee"] == 0 and settlement_data["gross_revenue"]:
                # Look for dispatch fee percentage in text and extract the first amount from "DISPATCH FEE X% ($ amount1) ($ amount2)"
                # The first amount is the dispatch fee, the second is payroll fee (already captured above)
                dispatch_line_match = re.search(r'DISPATCH[^\n]*FEE[^\n]*%\s*\(\$\s*([\d,]+\.?\d*)\)', text, re.IGNORECASE)
                if dispatch_line_match:
                    # Use the first amount (the calculated percentage amount) as dispatch fee
                    dispatch_amount = float(dispatch_line_match.group(1).replace(",", ""))
                    expense_categories["dispatch_fee"] = dispatch_amount
                    total_expenses += dispatch_amount
            
            # Always set expense_categories, even if empty (so frontend can display all categories)
            settlement_data["expense_categories"] = expense_categories
            
            # Set total expenses if we found any, or calculate from gross - net if available
            if total_expenses > 0:
                settlement_data["expenses"] = total_expenses
            elif settlement_data["gross_revenue"] and settlement_data["net_profit"]:
                # Calculate expenses from gross - net if not found explicitly
                calculated_expenses = settlement_data["gross_revenue"] - settlement_data["net_profit"]
                settlement_data["expenses"] = calculated_expenses
                # Put calculated expenses in "custom" if no categories were found
                if total_expenses == 0:
                    expense_categories["custom"] = calculated_expenses
                    settlement_data["expense_categories"] = expense_categories
            
            # Count blocks delivered
            if is_income_sheet_format:
                # Format 2: Count unique P/L column values (route codes or date ranges)
                # P/L column contains values like "VDF2-CLT5", "18BV-GSP1", or "06/04-06/06/2025"
                # Each unique P/L value = 1 block/delivery
                blocks_found = False
                pl_values = set()
                
                try:
                    # Try to find tables in the PDF
                    for page in pdf.pages:
                        tables = page.extract_tables()
                        for table in tables:
                            # Look for P/L column header
                            for row_idx, row in enumerate(table):
                                if row and any(cell and 'P/L' in str(cell).upper() for cell in row):
                                    # Found P/L header, get the column index
                                    header_row = row
                                    pl_col_idx = None
                                    for col_idx, cell in enumerate(header_row):
                                        if cell and 'P/L' in str(cell).upper():
                                            pl_col_idx = col_idx
                                            break
                                    
                                    if pl_col_idx is not None:
                                        # Collect all P/L values from data rows
                                        for data_row in table[row_idx + 1:]:
                                            if data_row and len(data_row) > pl_col_idx:
                                                pl_value = data_row[pl_col_idx]
                                                if pl_value:
                                                    pl_str = str(pl_value).strip()
                                                    # Check if it's a route code (e.g., "VDF2-CLT5") or date range (e.g., "06/04-06/06/2025")
                                                    if pl_str and (re.match(r'[A-Z0-9]+-[A-Z0-9]+', pl_str) or re.match(r'\d{1,2}/\d{1,2}-\d{1,2}/\d{1,2}/\d{4}', pl_str)):
                                                        pl_values.add(pl_str)
                                        
                                        if pl_values:
                                            settlement_data["blocks_delivered"] = len(pl_values)
                                            blocks_found = True
                                            break
                                    if blocks_found:
                                        break
                                if blocks_found:
                                    break
                            if blocks_found:
                                break
                except Exception:
                    pass
                
                # Fallback: Count unique P/L values from text using regex (more strict)
                if not blocks_found:
                    # Find route codes (e.g., "VDF2-CLT5", "18BV-GSP1") - must have letters and numbers
                    # Pattern: 2-4 uppercase letters/numbers, dash, 2-4 uppercase letters/numbers
                    route_codes = re.findall(r'\b([A-Z0-9]{2,4}-[A-Z0-9]{2,4})\b', text)
                    # Filter out false positives (like "23-02" which are just numbers)
                    # Route codes should have at least one letter
                    route_codes = [rc for rc in route_codes if re.search(r'[A-Z]', rc)]
                    
                    # Find date ranges (e.g., "06/04-06/06/2025") - must be full date format
                    date_ranges = re.findall(r'\b(\d{1,2}/\d{1,2}-\d{1,2}/\d{1,2}/\d{4})\b', text)
                    
                    # Combine and count unique values
                    pl_values = set(route_codes + date_ranges)
                    
                    if pl_values:
                        settlement_data["blocks_delivered"] = len(pl_values)
                    else:
                        # Alternative: Count number of driver pay entries (each driver pay = 1 block)
                        # Look for multiple "DRIVER'S PAY" entries or individual pay amounts
                        drivers_pay_pattern = r"DRIVER'S PAY[^\n]*\(\$\s*([\d,]+\.?\d*)\)"
                        drivers_pay_matches = re.findall(drivers_pay_pattern, text, re.IGNORECASE)
                        if drivers_pay_matches:
                            settlement_data["blocks_delivered"] = len(drivers_pay_matches)
                        # If still not found, leave as None so user can enter manually
            else:
                # Format 1: Count Block IDs (B-XXXXX)
                block_ids = re.findall(r'B-[A-Z0-9]+', text)
                if block_ids:
                    settlement_data["blocks_delivered"] = len(block_ids)
            
            # Extract week_start from "Start of Load" dates in the table (Format 1 only)
            # For Format 2, week_start is already extracted from Date Period above
            if not is_income_sheet_format and not settlement_data.get("week_start"):
                # Look for dates in the format MM/DD/YYYY that appear after "Start of Load"
                start_dates = re.findall(r'(\d{1,2}/\d{1,2}/\d{4})', text)
                if start_dates:
                    try:
                        # Find the earliest date (likely the week_start)
                        parsed_dates = []
                        for date_str in start_dates:
                            try:
                                parsed_dates.append(
                                    datetime.strptime(date_str, "%m/%d/%Y").date()
                                )
                            except ValueError:
                                continue
                        
                        if parsed_dates:
                            # The earliest date is likely week_start
                            # But we need to be careful - the pay period date might be included
                            # Filter out dates that are after the settlement_date
                            if settlement_data["settlement_date"]:
                                valid_dates = [
                                    d for d in parsed_dates
                                    if d <= settlement_data["settlement_date"]
                                ]
                                if valid_dates:
                                    settlement_data["week_start"] = min(valid_dates)
                            else:
                                settlement_data["week_start"] = min(parsed_dates)
                    except Exception:
                        pass
            
            # Extract miles driven
            if is_income_sheet_format:
                # Format 2: Look in table row: "12/27-12/29/2024 TFC9-CLT2 CLT5 7 795.0 ($ 2,119.07)"
                # Pattern: date range, then route, then stops, then miles
                # Find row with date range and extract miles (number before dollar amount)
                table_row_match = re.search(r'\d{1,2}/\d{1,2}-\d{1,2}/\d{1,2}/\d{4}[^\n]*?\s+(\d+\.?\d*)\s+\(\$', text, re.IGNORECASE)
                if table_row_match:
                    settlement_data["miles_driven"] = float(table_row_match.group(1))
                else:
                    # Fallback: look for "LOAD MILES" in summary
                    miles_match = re.search(r'LOAD MILES\s+([\d,]+\.?\d*)', text, re.IGNORECASE)
                    if miles_match:
                        settlement_data["miles_driven"] = float(
                            miles_match.group(1).replace(",", "")
                        )
            # Format 1: Miles driven is not typically in paystubs
            # Leave as None for Format 1
            
            # If net_profit not found but we have gross_revenue and expenses, calculate it
            if settlement_data["net_profit"] is None:
                if settlement_data["gross_revenue"] is not None and settlement_data["expenses"] is not None:
                    settlement_data["net_profit"] = settlement_data["gross_revenue"] - settlement_data["expenses"]
    
    except Exception as e:
        raise Exception(f"Error parsing PDF: {str(e)}")
    
    return settlement_data


def parse_amazon_relay_pdf_multi_truck(file_path: str, settlement_type: str = None) -> List[Dict]:
    """
    Parse Amazon Relay settlement PDF that contains multiple trucks (e.g., NBM with vv9952 and vw1503).
    Returns a list of settlement data dictionaries, one for each truck/license plate.
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            # Extract text from all pages
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            
            # Extract common date information
            settlement_date = None
            week_start = None
            week_end = None
            
            # Extract Pay Period date
            pay_period_match = re.search(r'Pay Period:\s*(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
            if pay_period_match:
                try:
                    settlement_date = datetime.strptime(pay_period_match.group(1), "%m/%d/%Y").date()
                    week_end = settlement_date
                except ValueError:
                    pass
            
            # Find license plates from "Plate#:" line
            plate_line_match = re.search(r'Plate#:\s*([^\n]+)', text, re.IGNORECASE)
            license_plates = set()
            
            if plate_line_match:
                plate_text = plate_line_match.group(1).strip()
                # Extract all license plates from the plate line (e.g., "VV9952 VW1503")
                plate_matches = re.findall(r'\b([A-Z]{2,3}\d{3,6})\b', plate_text, re.IGNORECASE)
                for plate in plate_matches:
                    license_plates.add(plate.upper())
            
            # Also search for plates in block rows (B-XXXXX rows)
            # Handle cases where plate might be concatenated with driver name (e.g., "VereenVW1503")
            block_plate_matches = re.findall(r'B-[A-Z0-9]+\s+[^\n]*?([A-Z]{2,3}\d{3,6})\b', text, re.IGNORECASE)
            for plate in block_plate_matches:
                license_plates.add(plate.upper())
            
            # Also search for plates that might be concatenated (no space before plate)
            # Pattern: letters followed immediately by plate pattern
            concatenated_plates = re.findall(r'([A-Z][a-z]+)([A-Z]{2,3}\d{3,6})', text)
            for _, plate in concatenated_plates:
                license_plates.add(plate.upper())
            
            if len(license_plates) < 2:
                # If we don't find multiple plates, fallback to single truck parsing
                single_settlement = parse_amazon_relay_pdf(file_path, settlement_type)
                return [single_settlement]
            
            # Extract shared expenses (to be divided by 2)
            shared_expenses = {
                "safety": 0.0,
                "prepass": 0.0,
                "insurance": 0.0
            }
            
            # Extract shared expenses from summary section
            safety_match = re.search(r'Safety\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if safety_match:
                shared_expenses["safety"] = float(safety_match.group(1).replace(",", ""))
            
            prepass_match = re.search(r'Prepass\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if prepass_match:
                shared_expenses["prepass"] = float(prepass_match.group(1).replace(",", ""))
            
            insurance_match = re.search(r'Insurance\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if insurance_match:
                shared_expenses["insurance"] = float(insurance_match.group(1).replace(",", ""))
            
            # Extract other shared expenses
            ifta_match = re.search(r'IFTA\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            ifta_total = float(ifta_match.group(1).replace(",", "")) if ifta_match else 0.0
            
            dispatch_fee_match = re.search(r'Dispatch Fee\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            dispatch_fee_total = float(dispatch_fee_match.group(1).replace(",", "")) if dispatch_fee_match else 0.0
            
            # Parse block rows to get per-truck data
            # Format: B-XXXXX Driver Name PLATE Pay Amount Driver's pay Fuel amount
            # Group blocks by license plate
            plate_data = {}
            for plate in license_plates:
                plate_data[plate] = {
                    "gross_revenue": 0.0,
                    "driver_pay": 0.0,
                    "fuel": 0.0,
                    "blocks": 0
                }
            
            # Parse each block row - need to handle multi-line fuel entries
            lines = text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i]
                # Look for block rows (B-XXXXX pattern)
                if re.search(r'B-[A-Z0-9]+', line):
                    # Extract license plate from this line (handle concatenated cases)
                    plate_match = None
                    # Try normal pattern first
                    plate_match = re.search(r'\b([A-Z]{2,3}\d{3,6})\b', line, re.IGNORECASE)
                    if not plate_match:
                        # Try concatenated pattern (e.g., "VereenVW1503")
                        concat_match = re.search(r'([A-Z][a-z]+)([A-Z]{2,3}\d{3,6})', line)
                        if concat_match:
                            plate_match = type('obj', (object,), {'group': lambda self, n: concat_match.group(2)})()
                    
                    if plate_match:
                        plate = plate_match.group(1).upper()
                        if plate in plate_data:
                            # Extract all dollar amounts from this line
                            dollar_amounts = re.findall(r'\$([\d,]+\.?\d*)', line)
                            
                            if len(dollar_amounts) >= 1:
                                # First $ amount is Pay Amount
                                pay_amount = float(dollar_amounts[0].replace(",", ""))
                                plate_data[plate]["gross_revenue"] += pay_amount
                                plate_data[plate]["blocks"] += 1
                            
                            if len(dollar_amounts) >= 2:
                                # Second $ amount is Driver's pay
                                driver_pay = float(dollar_amounts[1].replace(",", ""))
                                plate_data[plate]["driver_pay"] += driver_pay
                            
                            # Extract fuel amount - look for pattern: date time $amount
                            # Fuel can be on same line after date/time or on next line(s)
                            fuel_found = False
                            
                            # Check for fuel on same line (after date/time pattern)
                            fuel_on_line = re.search(r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+\$([\d,]+\.?\d*)', line)
                            if fuel_on_line:
                                fuel_amount = float(fuel_on_line.group(1).replace(",", ""))
                                plate_data[plate]["fuel"] += fuel_amount
                                fuel_found = True
                            
                            # If no fuel found with date/time pattern, check if 4th dollar amount is fuel
                            # (Some blocks have: Pay Amount, Driver's pay, Miles, Fuel)
                            if not fuel_found and len(dollar_amounts) >= 4:
                                # The 4th amount might be fuel (skip the 3rd which is usually miles)
                                fuel_amount = float(dollar_amounts[3].replace(",", ""))
                                # Only add if it's a reasonable fuel amount (less than $10,000)
                                if fuel_amount < 10000:
                                    plate_data[plate]["fuel"] += fuel_amount
                                    fuel_found = True
                            
                            # Check next line(s) for fuel amount (common pattern)
                            # Keep checking until we hit another block or summary section
                            check_idx = i + 1
                            while check_idx < len(lines) and check_idx < i + 5:  # Check up to 4 lines ahead
                                next_line = lines[check_idx]
                                
                                # Stop if we hit another block or summary section
                                if re.search(r'B-[A-Z0-9]+', next_line) or re.search(r'^(Gross Pay|Driver|Fuel|Safety|Prepass|Insurance|IFTA|Dispatch)', next_line, re.IGNORECASE):
                                    break
                                
                                # Look for fuel pattern: date time $amount
                                fuel_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+\$([\d,]+\.?\d*)', next_line)
                                if fuel_match:
                                    fuel_amount = float(fuel_match.group(1).replace(",", ""))
                                    plate_data[plate]["fuel"] += fuel_amount
                                    check_idx += 1
                                else:
                                    check_idx += 1
                            
                            # Update i if we skipped fuel lines
                            if check_idx > i + 1:
                                i = check_idx - 1  # Will be incremented at end of loop
                i += 1
            
            # Extract Driver's Pay Fee from summary (divide proportionally by driver pay)
            drivers_pay_fee_match = re.search(r"Driver's Pay Fee\s+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
            drivers_pay_fee_total = float(drivers_pay_fee_match.group(1).replace(",", "")) if drivers_pay_fee_match else 0.0
            
            # Calculate total driver pay for proportional division
            total_driver_pay = sum(data["driver_pay"] for data in plate_data.values())
            
            # Parse data for each license plate
            settlements = []
            
            # Create settlement for each license plate using parsed block data
            for license_plate in license_plates:
                if license_plate not in plate_data or plate_data[license_plate]["gross_revenue"] == 0:
                    continue
                
                data = plate_data[license_plate]
                
                # Create base settlement data
                plate_settlement = {
                    "settlement_date": settlement_date,
                    "week_start": week_start,
                    "week_end": week_end,
                    "miles_driven": None,
                    "blocks_delivered": data["blocks"],
                    "gross_revenue": data["gross_revenue"],
                    "expenses": None,
                    "net_profit": None,
                    "driver_id": None,
                    "license_plate": license_plate,
                }
                
                # Initialize expense categories
                expense_categories = {
                    "fuel": data["fuel"],
                    "dispatch_fee": 0.0,
                    "insurance": shared_expenses["insurance"] / 2.0,  # Divide by 2
                    "safety": shared_expenses["safety"] / 2.0,  # Divide by 2
                    "prepass": shared_expenses["prepass"] / 2.0,  # Divide by 2
                    "ifta": ifta_total / 2.0,  # Divide by 2
                    "driver_pay": data["driver_pay"],
                    "payroll_fee": 0.0,
                    "truck_parking": 0.0,
                    "service_on_truck": 0.0,
                    "custom": 0.0
                }
                
                # Calculate dispatch fee proportionally by gross revenue
                total_gross = sum(pd["gross_revenue"] for pd in plate_data.values())
                if total_gross > 0:
                    expense_categories["dispatch_fee"] = (dispatch_fee_total * data["gross_revenue"]) / total_gross
                
                # Calculate payroll fee proportionally by driver pay
                if total_driver_pay > 0:
                    expense_categories["payroll_fee"] = (drivers_pay_fee_total * data["driver_pay"]) / total_driver_pay
                
                # Calculate total expenses
                total_expenses = sum(expense_categories.values())
                
                # Calculate net profit
                plate_settlement["net_profit"] = data["gross_revenue"] - total_expenses
                plate_settlement["expenses"] = total_expenses
                plate_settlement["expense_categories"] = expense_categories
                
                settlements.append(plate_settlement)
            
            # If no settlements found, fallback to single truck parsing
            if not settlements:
                single_settlement = parse_amazon_relay_pdf(file_path, settlement_type)
                return [single_settlement]
            
            return settlements
            
    except Exception as e:
        raise Exception(f"Error parsing multi-truck PDF: {str(e)}")

