"""
PDF parser for Amazon Relay settlement files
"""
import pdfplumber
import re
from datetime import datetime
from typing import Dict, List

# Whitelist of valid license plates - only these plates will be accepted
# Any other plates found in PDFs will be rejected
VALID_LICENSE_PLATES = {
    'VW9327',
    'VW9328',
    'VW1503',
    'VV9952'
}


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
        "driver_name": None,  # Extract driver name from PDF
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
            
            # Calculate driver's pay and payroll fee from individual blocks
            # Each block (B-XXXXX) has a driver's pay amount - sum them all up
            # Then calculate 6.5% payroll fee on the total
            total_driver_pay_from_blocks = 0.0
            
            # Parse all block rows to extract driver's pay from each block
            lines = text.split('\n')
            for i, line in enumerate(lines):
                # Look for block rows (B-XXXXX pattern)
                if re.search(r'B-[A-Z0-9]+', line):
                    # Extract dollar amounts from this line
                    # Format: B-XXXXX ... $amount1 $amount2 ... (second amount is usually driver's pay)
                    dollar_amounts = re.findall(r'\$([\d,]+\.?\d*)', line)
                    
                    # Also check next few lines for driver's pay if not found on same line
                    driver_pay_found = False
                    if len(dollar_amounts) >= 2:
                        # Second $ amount is typically Driver's pay
                        try:
                            driver_pay = float(dollar_amounts[1].replace(",", ""))
                            # Validate it's a reasonable driver's pay amount (between $100 and $50,000)
                            if 100 <= driver_pay <= 50000:
                                total_driver_pay_from_blocks += driver_pay
                                driver_pay_found = True
                        except (ValueError, IndexError):
                            pass
                    
                    # If not found on same line, check next lines for driver's pay pattern
                    if not driver_pay_found:
                        check_idx = i + 1
                        while check_idx < len(lines) and check_idx < i + 3:  # Check up to 2 lines ahead
                            next_line = lines[check_idx]
                            # Stop if we hit another block
                            if re.search(r'B-[A-Z0-9]+', next_line):
                                break
                            
                            # Look for driver's pay pattern: "Driver's Pay $amount" or just "$amount" after block
                            driver_pay_match = re.search(r"Driver's Pay\s+\$?([\d,]+\.?\d*)", next_line, re.IGNORECASE)
                            if not driver_pay_match:
                                # Try to find dollar amount that could be driver's pay
                                dollar_amounts_next = re.findall(r'\$([\d,]+\.?\d*)', next_line)
                                if dollar_amounts_next:
                                    try:
                                        driver_pay = float(dollar_amounts_next[0].replace(",", ""))
                                        if 100 <= driver_pay <= 50000:
                                            total_driver_pay_from_blocks += driver_pay
                                            driver_pay_found = True
                                            break
                                    except ValueError:
                                        pass
                            
                            if driver_pay_match:
                                try:
                                    driver_pay = float(driver_pay_match.group(1).replace(",", ""))
                                    if 100 <= driver_pay <= 50000:
                                        total_driver_pay_from_blocks += driver_pay
                                        driver_pay_found = True
                                        break
                                except ValueError:
                                    pass
                            
                            check_idx += 1
            
            # If we found driver's pay from blocks, use that instead of summary values
            if total_driver_pay_from_blocks > 0:
                expense_categories["driver_pay"] = total_driver_pay_from_blocks
                # Calculate 6.5% payroll fee
                payroll_fee_amount = total_driver_pay_from_blocks * 0.065
                expense_categories["payroll_fee"] = payroll_fee_amount
                # Update total expenses
                total_expenses += total_driver_pay_from_blocks + payroll_fee_amount
                # Skip the summary extraction below for driver's pay
                skip_summary_driver_pay = True
            else:
                skip_summary_driver_pay = False
            
            # Special handling for settlement types that explicitly list "driver's pay" and "driver's pay fee"
            # NBM Transport LLC and 277 Logistics both have these fields explicitly listed
            # BUT: Only use summary values if we didn't find driver's pay from blocks
            settlement_type_upper = settlement_type.upper() if settlement_type else ""
            if settlement_type_upper in ["NBM TRANSPORT LLC", "277 LOGISTICS"] and not skip_summary_driver_pay:
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
                    # Skip processing driver's pay and payroll fee if we already calculated from blocks
                    if skip_summary_driver_pay:
                        if re.search(r"DRIVER'S PAY", line, re.IGNORECASE) or re.search(r"DRIVER'S PAY FEE", line, re.IGNORECASE):
                            continue
                    
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
                                # Skip this if we already calculated from blocks, or for settlement types that explicitly list them
                                settlement_type_upper = settlement_type.upper() if settlement_type else ""
                                if category == 'driver_pay' and not skip_summary_driver_pay and settlement_type_upper not in ["NBM TRANSPORT LLC", "277 LOGISTICS"]:
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
                            # Skip this if we already calculated from blocks, or for settlement types that explicitly list them
                            settlement_type_upper = settlement_type.upper() if settlement_type else ""
                            if category == 'driver_pay' and not skip_summary_driver_pay and settlement_type_upper not in ["NBM TRANSPORT LLC", "277 LOGISTICS"]:
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
                # Skip this if we already calculated from blocks, or for settlement types that explicitly list them
                settlement_type_upper = settlement_type.upper() if settlement_type else ""
                if expense_categories["driver_pay"] == 0 and not skip_summary_driver_pay and settlement_type_upper not in ["NBM TRANSPORT LLC", "277 LOGISTICS"]:
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
            
            # Extract driver name from block rows or header
            # Format: B-XXXXX Driver Name PLATE or "Driver: Name" or "Name" in block rows
            driver_names = []
            lines = text.split('\n')
            for line in lines:
                # Look for block rows with driver names
                # Pattern: B-XXXXX followed by name (capitalized words) before plate number
                block_match = re.search(r'B-[A-Z0-9]+\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+[A-Z]{2,3}\d{3,6}', line)
                if block_match:
                    driver_name = block_match.group(1).strip()
                    # Filter out common false positives (like "Driver", "Pay", etc.)
                    if driver_name and len(driver_name) > 2 and driver_name.lower() not in ['driver', 'pay', 'fee', 'fuel', 'safety', 'prepass', 'insurance', 'ifta']:
                        driver_names.append(driver_name)
                
                # Also look for explicit "Driver:" pattern in header sections
                driver_label_match = re.search(r'Driver[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', line, re.IGNORECASE)
                if driver_label_match:
                    driver_name = driver_label_match.group(1).strip()
                    if driver_name and len(driver_name) > 2 and driver_name.lower() not in ['pay', 'fee', 'id']:
                        driver_names.append(driver_name)
            
            # Use the most common driver name (if multiple blocks have same driver)
            if driver_names:
                # Count occurrences and get the most common
                from collections import Counter
                name_counts = Counter(driver_names)
                most_common_name = name_counts.most_common(1)[0][0]
                settlement_data["driver_name"] = most_common_name
            
            # If net_profit not found but we have gross_revenue and expenses, calculate it
            if settlement_data["net_profit"] is None:
                if settlement_data["gross_revenue"] is not None and settlement_data["expenses"] is not None:
                    settlement_data["net_profit"] = settlement_data["gross_revenue"] - settlement_data["expenses"]
    
    except Exception as e:
        raise Exception(f"Error parsing PDF: {str(e)}")
    
    return settlement_data


def parse_amazon_relay_pdf_multi_truck(file_path: str, settlement_type: str = None, 
                                       return_validation: bool = False) -> List[Dict]:
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
            
            # Extract Net Pay from PDF (for validation - this is the total net profit after all deductions)
            pdf_net_pay = None
            net_pay_match = re.search(r'Net Pay\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if net_pay_match:
                try:
                    pdf_net_pay = float(net_pay_match.group(1).replace(",", ""))
                except ValueError:
                    pass
            
            # Find license plates from "Plate#:" line
            plate_line_match = re.search(r'Plate#:\s*([^\n]+)', text, re.IGNORECASE)
            license_plates = set()
            header_plates = []  # Store header plates in order for reference
            
            if plate_line_match:
                plate_text = plate_line_match.group(1).strip()
                # Extract all license plates from the plate line (e.g., "VV9952 VW1503")
                plate_matches = re.findall(r'\b([A-Z]{2,3}\d{3,6})\b', plate_text, re.IGNORECASE)
                for plate in plate_matches:
                    normalized_plate = plate.upper()
                    license_plates.add(normalized_plate)
                    header_plates.append(normalized_plate)  # Keep order for matching
            
            # Also search for plates in block rows (B-XXXXX rows)
            # Handle cases where plate might be concatenated with driver name (e.g., "VereenVW1503", "LeeNVV9952")
            # Pattern allows for one letter before the plate prefix (e.g., "NVV9952" -> "VV9952")
            block_plate_matches = re.findall(r'B-[A-Z0-9]+\s+[^\n]*?([A-Z]?[A-Z]{2,3}\d{3,6})\b', text, re.IGNORECASE)
            for plate in block_plate_matches:
                # Remove leading letter if present (e.g., "NVV9952" -> "VV9952")
                normalized_plate = plate.upper()
                # Check if it starts with a valid plate prefix after removing first char
                if len(normalized_plate) > 6 and normalized_plate[0] not in ['V']:
                    # Might have extra letter, try without first char
                    if normalized_plate[1:3] in ['VW', 'VV']:
                        normalized_plate = normalized_plate[1:]
                license_plates.add(normalized_plate)
            
            # Also search for plates that might be concatenated (no space before plate)
            # Pattern: letters followed immediately by plate pattern
            concatenated_plates = re.findall(r'([A-Z][a-z]+)([A-Z]{2,3}\d{3,6})', text)
            for _, plate in concatenated_plates:
                license_plates.add(plate.upper())
            
            # Filter out invalid plates and ensure we have distinct plates
            valid_plates = {p.upper().strip() for p in license_plates if len(p.strip()) >= 5}
            
            # Remove known invalid plates (OCR errors)
            # VW9237 is an invalid plate - likely OCR error for VW9327
            # NVW9328 is corrupted OCR text (from "NaVpWpe9r327") - should be VW9327
            invalid_plates = {'VW9237', 'NVW9328'}  # Add other invalid plates here as needed
            valid_plates = {p for p in valid_plates if p not in invalid_plates}
            
            # CRITICAL: Only accept plates that are on the whitelist
            # Reject any plates that don't belong to the user's trucks
            valid_plates = {p for p in valid_plates if p in VALID_LICENSE_PLATES}
            
            # Map invalid plates to correct ones (for OCR error correction)
            plate_corrections = {
                'VW9237': 'VW9327',   # VW9237 -> VW9327 (OCR error)
                'NVW9328': 'VW9327',   # NVW9328 -> VW9327 (corrupted OCR "NaVpWpe9r327")
                'VV4342': 'VV9952'     # VV4342 -> VV9952 (wrong plate, should be VV9952)
            }
            
            if len(valid_plates) < 2:
                # If we don't find multiple DISTINCT plates, fallback to single truck parsing
                single_settlement = parse_amazon_relay_pdf(file_path, settlement_type)
                return [single_settlement]
            
            # Use the valid plates for processing
            license_plates = valid_plates
            num_trucks = len(license_plates)
            
            # Extract shared expenses (to be divided by number of trucks)
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
            
            # Extract deductions/custom expenses (common deductions that apply to the whole settlement)
            # These will be applied to the first truck since it's a common settlement expense
            deductions_match = re.search(r'Deductions\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            deductions_total = float(deductions_match.group(1).replace(",", "")) if deductions_match else 0.0
            
            # Also check for other common deduction patterns
            if deductions_total == 0:
                # Try alternative patterns for deductions
                other_deduction_patterns = [
                    r'Other Deductions\s+\$?([\d,]+\.?\d*)',
                    r'Additional Deductions\s+\$?([\d,]+\.?\d*)',
                    r'Total Deductions\s+\$?([\d,]+\.?\d*)',
                ]
                for pattern in other_deduction_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        deductions_total = float(match.group(1).replace(",", ""))
                        break
            
            # Extract total fuel from PDF (for validation - some PDFs may have fuel totals)
            # Look for "Fuel" or "Total Fuel" line
            fuel_total_from_pdf = None
            fuel_total_match = re.search(r'(?:Total\s+)?Fuel\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
            if fuel_total_match:
                try:
                    fuel_total_from_pdf = float(fuel_total_match.group(1).replace(",", ""))
                except ValueError:
                    pass
            
            # Extract total reimbursement from summary section (if available)
            reimbursement_total = 0.0
            # Try various patterns for reimbursement (with/without space, with typo)
            reimb_patterns = [
                r'Reimbursement\s+\$?([\d,]+\.?\d*)',  # "Reimbursement $100.00"
                r'Reimbursement\$\s*([\d,]+\.?\d*)',  # "Reimbursement$100.00"
                r'Reimbursment\s+\$?([\d,]+\.?\d*)',  # "Reimbursment $100.00" (typo)
                r'Reimbursment\$\s*([\d,]+\.?\d*)',  # "Reimbursment$100.00" (typo)
            ]
            for pattern in reimb_patterns:
                reimb_match = re.search(pattern, text, re.IGNORECASE)
                if reimb_match:
                    try:
                        reimbursement_total = float(reimb_match.group(1).replace(",", ""))
                        break
                    except ValueError:
                        pass
            
            # Parse block rows to get per-truck data
            # Format: B-XXXXX Driver Name PLATE Pay Amount Driver's pay Fuel amount Reimb Bonus Deduct
            # Group blocks by license plate
            plate_data = {}
            for plate in license_plates:
                plate_data[plate] = {
                    "gross_revenue": 0.0,
                    "driver_pay": 0.0,
                    "fuel": 0.0,
                    "reimbursement": 0.0,  # Track reimbursements per plate
                    "blocks": 0,
                    "driver_name": None  # Extract driver name per plate
                }
            
            # Parse each block row - need to handle multi-line fuel entries
            lines = text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i]
                # Look for block rows (B-XXXXX pattern)
                if re.search(r'B-[A-Z0-9]+', line):
                    # Extract license plate and driver name from this line
                    plate_match = None
                    driver_name = None
                    
                    # Method 1: Try pattern with space: B-XXXXX Driver Name PLATE
                    name_match = re.search(r'B-[A-Z0-9]+\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+([A-Z]{2,3}\d{3,6})', line)
                    if name_match:
                        driver_name = name_match.group(1).strip()
                        # Filter out false positives
                        if driver_name.lower() in ['driver', 'pay', 'fee', 'fuel', 'safety', 'prepass', 'insurance', 'ifta']:
                            driver_name = None
                        # Create a mock match object for plate
                        plate_match = type('obj', (object,), {'group': lambda self, n: name_match.group(2)})()
                    else:
                        # Method 2: Try to find plate by matching against header plates first
                        # This is more reliable when columns are close together
                        matched_plate = None
                        if header_plates:  # Only if we have header plates
                            for header_plate in header_plates:
                                # Look for the plate pattern in the line (may be concatenated with name)
                                # Handle both clean plates and corrupted OCR like "NaVpWpe9r327" -> "VW9327"
                                
                                # First try: exact pattern match (e.g., "VW9327" or "VW 9327")
                                plate_pattern = header_plate[:2] + r'\s*' + header_plate[2:]  # e.g., "VW\s*9327"
                                plate_found = re.search(plate_pattern, line, re.IGNORECASE)
                                
                                # Second try: handle corrupted OCR where letters/digits are mixed
                                # Pattern: "NaVpWpe9r327" should match "VW9327"
                                # Also handles "VereenVW1503" for VW1503 and similar patterns for VV9952
                                # The plate number might have letters mixed in (e.g., "9r327" instead of "9327")
                                if not plate_found and len(header_plate) >= 5:
                                    plate_prefix = header_plate[:2]  # e.g., "VW", "VV"
                                    plate_number = header_plate[2:]  # e.g., "9327", "1503", "9952"
                                    
                                    # For 4-digit plates (VW9327, VW1503, VV9952), use first digit + last two
                                    if len(plate_number) >= 4:
                                        first_digit = plate_number[0]  # "9", "1", "9"
                                        last_two = plate_number[-2:]  # "27", "03", "52"
                                        
                                        # Try to find pattern: first_digit + (any chars, possibly corrupted) + last_two
                                        # e.g., "9r327" matches "9327", "1503" matches "1503", "9952" matches "9952"
                                        pattern = first_digit + r'[0-9a-z]{0,3}' + last_two  # Allow 0-3 chars between
                                        ocr_match = re.search(pattern, line, re.IGNORECASE)
                                        if ocr_match:
                                            # Check if plate prefix (VW or VV) appears before this pattern (may be corrupted)
                                            # Handle cases like "NaVpWpe" (VW) or "VereenVW" (VW) or "NameVV" (VV)
                                            match_start = ocr_match.start()
                                            before_match = line[max(0, match_start-20):match_start]  # Check more characters back
                                            
                                            # Look for plate prefix pattern (VW or VV) with possible OCR corruption
                                            # Pattern: V + (0-3 chars) + W or V, e.g., "VpW", "VW", "NaVpWp", "VV", "VereenVW", "NVV" (from "LeeNVV9952")
                                            # Allow one extra letter before the prefix (common when name concatenates with plate)
                                            if plate_prefix == "VW":
                                                # VW: allow "VW", "VpW", "NaVpWp", or one letter before like "NVW", "eVW" (from "VereeVW")
                                                prefix_match = re.search(r'[A-Z]?[Vv][a-zA-Z]{0,3}[Ww]', before_match, re.IGNORECASE)
                                            elif plate_prefix == "VV":
                                                # VV: allow "VV", or one letter before like "NVV" (from "LeeNVV9952")
                                                prefix_match = re.search(r'[A-Z]?[Vv][a-zA-Z]{0,3}[Vv]', before_match, re.IGNORECASE)
                                            else:
                                                # For other prefixes, try exact match with optional leading letter
                                                prefix_match = re.search(r'[A-Z]?' + plate_prefix[0] + r'[a-zA-Z]{0,3}' + plate_prefix[1], before_match, re.IGNORECASE)
                                            
                                            if prefix_match:
                                                # Check context to avoid dates
                                                context_start = max(0, match_start - 3)
                                                context_end = min(len(line), ocr_match.end() + 3)
                                                context = line[context_start:context_end]
                                                # Skip if it looks like a date
                                                if '/' not in context and '-' not in context:
                                                    # Create a mock match object pointing to where the number would be
                                                    plate_found = type('obj', (object,), {
                                                        'start': lambda self: match_start,
                                                        'group': lambda self, n: plate_number
                                                    })()
                                    # Also try the original method for cleaner cases
                                    if not plate_found:
                                        all_numbers = list(re.finditer(r'(\d{4})', line))
                                        for number_match in all_numbers:
                                            if number_match.group(1) == plate_number:
                                                num_start = number_match.start()
                                                context_start = max(0, num_start - 3)
                                                context_end = min(len(line), number_match.end() + 3)
                                                context = line[context_start:context_end]
                                                if '/' not in context and '-' not in context:
                                                    before_number = line[max(0, num_start-15):num_start]
                                                    # Check for plate prefix (VW or VV) before the number
                                                    if plate_prefix == "VW":
                                                        prefix_match = re.search(r'[Vv][Ww]', before_number, re.IGNORECASE)
                                                    elif plate_prefix == "VV":
                                                        prefix_match = re.search(r'[Vv][Vv]', before_number, re.IGNORECASE)
                                                    else:
                                                        # For other prefixes, try exact match
                                                        prefix_match = re.search(plate_prefix[0] + plate_prefix[1], before_number, re.IGNORECASE)
                                                    if prefix_match:
                                                        plate_found = number_match
                                                        break
                                
                                if plate_found:
                                    matched_plate = header_plate
                                    # Extract name - everything before the plate
                                    # For corrupted OCR, plate_found points to the number, but we need to go back further
                                    plate_start = plate_found.start()
                                    # If this was a corrupted match, look for where the corruption starts (before plate prefix)
                                    if not re.search(plate_pattern, line, re.IGNORECASE):
                                        # This was a corrupted match - find where plate prefix (VW or VV) pattern starts
                                        before_number = line[max(0, plate_start-15):plate_start]
                                        # Check for plate prefix (VW or VV) before the number
                                        # Allow one extra letter before prefix (e.g., "NVV" from "LeeNVV9952")
                                        if plate_prefix == "VW":
                                            prefix_match = re.search(r'[A-Z]?[Vv][Ww]', before_number, re.IGNORECASE)
                                        elif plate_prefix == "VV":
                                            prefix_match = re.search(r'[A-Z]?[Vv][Vv]', before_number, re.IGNORECASE)
                                        else:
                                            # For other prefixes, try exact match with optional leading letter
                                            prefix_match = re.search(r'[A-Z]?' + plate_prefix[0] + plate_prefix[1], before_number, re.IGNORECASE)
                                        if prefix_match:
                                            # Adjust plate_start to where prefix starts (beginning of corrupted pattern)
                                            prefix_start_in_before = prefix_match.start()
                                            plate_start = plate_start - len(before_number) + prefix_start_in_before
                                    
                                    # Simplified driver name extraction - only extract if clearly separated from plate
                                    # Skip name extraction if plate is concatenated (focus on plate accuracy)
                                    # Only extract name if there's a clear space before the plate
                                    name_text = line[:plate_start].strip()
                                    # Only try to extract name if plate_start is far enough from block ID
                                    # and there's a clear separation (space) before the plate
                                    if plate_start > 20 and ' ' in name_text[-10:]:  # At least some space before plate
                                        # Find capitalized words (driver name) - simple extraction
                                        name_words = re.findall(r'\b([A-Z][a-z]{2,})\b', name_text)  # At least 3 chars
                                        if name_words:
                                            # Filter out common false positives
                                            filtered_names = [n for n in name_words 
                                                            if n.lower() not in ['driver', 'pay', 'fee', 'fuel', 'safety', 
                                                                                'prepass', 'insurance', 'ifta', 'b', 'block']]
                                            if filtered_names:
                                                # Take last 2 words as driver name (first + last name)
                                                driver_name = ' '.join(filtered_names[-2:]) if len(filtered_names) >= 2 else filtered_names[-1]
                                    # If name extraction failed or was skipped, driver_name remains None
                                    # This is fine - plate detection is the priority
                                    break
                        
                        # If no match with header plates, try concatenated pattern
                        if not matched_plate:
                            # Pattern: (Name)(Plate) where Name ends and Plate starts immediately
                            # Look for capitalized word(s) followed immediately by plate pattern
                            concat_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)([A-Z]{2,3}\d{3,6})', line)
                            if concat_match:
                                potential_name = concat_match.group(1).strip()
                                potential_plate = concat_match.group(2).upper()
                                
                                # Check if this plate matches any header plate
                                if potential_plate in license_plates:
                                    matched_plate = potential_plate
                                    # Extract name - everything before the plate
                                    name_end_pos = concat_match.start(2)
                                    name_text = line[:name_end_pos]
                                    name_words = re.findall(r'([A-Z][a-z]+)', name_text)
                                    if name_words:
                                        driver_name = ' '.join(name_words[-2:]) if len(name_words) >= 2 else name_words[-1]
                                else:
                                    # Plate not in header, but might be valid
                                    if len(potential_plate) >= 5 and potential_plate[:2].isalpha() and potential_plate[2:].isdigit():
                                        matched_plate = potential_plate
                                        name_end_pos = concat_match.start(2)
                                        name_text = line[:name_end_pos]
                                        name_words = re.findall(r'([A-Z][a-z]+)', name_text)
                                        if name_words:
                                            driver_name = ' '.join(name_words[-2:]) if len(name_words) >= 2 else name_words[-1]
                        
                        if matched_plate:
                            plate_match = type('obj', (object,), {'group': lambda self, n: matched_plate})()
                        
                        # Method 3: Try to find plate directly (standalone pattern)
                        if not plate_match:
                            plate_match = re.search(r'\b([A-Z]{2,3}\d{3,6})\b', line, re.IGNORECASE)
                            
                            # If no plate found, try to extract from corrupted OCR text
                            # Pattern: "NaVpWpe9r327" -> extract "VW9327"
                            if not plate_match:
                                # Look for corrupted patterns like "NaVpWpe9r327" (should be "VW9327")
                                # Try to find "VW" followed by digits, even if there's garbage before it
                                corrupted_match = re.search(r'[Vv][Ww]\s*(\d{4})', line)
                                if corrupted_match:
                                    plate_number = corrupted_match.group(1)
                                    reconstructed_plate = f"VW{plate_number}"
                                    # Check if this matches a header plate
                                    if reconstructed_plate in license_plates:
                                        plate_match = type('obj', (object,), {'group': lambda self, n: reconstructed_plate})()
                                    # Also try to extract name before the corrupted plate
                                    # Find text before the corrupted pattern
                                    corrupted_start = corrupted_match.start()
                                    name_text = line[:corrupted_start]
                                    name_words = re.findall(r'([A-Z][a-z]+)', name_text)
                                    if name_words:
                                        driver_name = ' '.join(name_words[-2:]) if len(name_words) >= 2 else name_words[-1]
                    
                    if plate_match:
                        plate = plate_match.group(1).upper()
                        
                        # Normalize plate - remove leading letter if present (e.g., "NVV9952" -> "VV9952")
                        # This handles cases where driver name is concatenated with plate
                        if len(plate) > 6 and plate[0] not in ['V']:
                            # Check if removing first char gives us a valid plate prefix
                            if plate[1:3] in ['VW', 'VV'] and plate[1:] in VALID_LICENSE_PLATES:
                                plate = plate[1:]  # Remove leading letter
                        
                        # Apply plate corrections for known OCR errors BEFORE whitelist check
                        # This ensures wrong plates (like VV4342) get mapped to correct ones (VV9952)
                        if plate in plate_corrections:
                            plate = plate_corrections[plate]
                        
                        # CRITICAL: Only process plates that are on the whitelist
                        # Reject any plates that don't belong to the user's trucks
                        if plate not in VALID_LICENSE_PLATES:
                            # Skip this block - it belongs to a plate we don't recognize
                            i += 1
                            continue
                        
                        # Handle OCR errors: similar plates (one digit difference)
                        # Works for VW plates (VW9327, VW1503) and VV plates (VV9952)
                        if plate not in plate_data and len(plate) == 6 and (plate.startswith('VW') or plate.startswith('VV')):
                            # Check if there's a similar plate (e.g., VW9237 vs VW9327, VV9952 vs VV9953)
                            plate_prefix = plate[:2]  # "VW" or "VV"
                            for existing_plate in plate_data.keys():
                                if len(existing_plate) == 6 and existing_plate.startswith(plate_prefix):
                                    # Check if only one digit differs
                                    diff_count = sum(1 for a, b in zip(plate, existing_plate) if a != b)
                                    if diff_count == 1:
                                        # Use the existing plate instead (likely the correct one)
                                        plate = existing_plate
                                        break
                        
                        if plate in plate_data:
                            # Store driver name if found and not already set
                            if driver_name and len(driver_name) > 2:
                                if not plate_data[plate]["driver_name"]:
                                    plate_data[plate]["driver_name"] = driver_name
                            
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
                                    fuel_found = True
                                    break
                                
                                # Also check for standalone dollar amount (might be fuel)
                                next_fuel_match = re.search(r'\$([\d,]+\.?\d*)', next_line)
                                if next_fuel_match and not fuel_found:
                                    fuel_amount = float(next_fuel_match.group(1).replace(",", ""))
                                    # Only add if it's a reasonable fuel amount (less than $10,000)
                                    if fuel_amount < 10000 and fuel_amount > 0:
                                        plate_data[plate]["fuel"] += fuel_amount
                                        fuel_found = True
                                        break
                                
                                check_idx += 1
                            
                            # Update i if we skipped fuel lines
                            if check_idx > i + 1:
                                i = check_idx - 1  # Will be incremented at end of loop
                    else:
                        # No plate found - try to infer from driver name or assign to first plate
                        # This handles cases where OCR completely corrupted the plate
                        # Extract dollar amounts anyway
                        dollar_amounts = re.findall(r'\$([\d,]+\.?\d*)', line)
                        if len(dollar_amounts) >= 1 and len(license_plates) > 0:
                            # Try to match by driver name first
                            assigned_plate = None
                            if driver_name and len(driver_name) > 2:
                                # Look for existing plate with same driver name
                                for plate_key, plate_info in plate_data.items():
                                    if plate_info.get("driver_name") and driver_name.lower() in plate_info["driver_name"].lower():
                                        assigned_plate = plate_key
                                        break
                            
                            # If no match by driver name, assign to first plate
                            if not assigned_plate:
                                assigned_plate = list(license_plates)[0]
                            
                            if assigned_plate in plate_data:
                                pay_amount = float(dollar_amounts[0].replace(",", ""))
                                plate_data[assigned_plate]["gross_revenue"] += pay_amount
                                plate_data[assigned_plate]["blocks"] += 1
                                
                                if len(dollar_amounts) >= 2:
                                    # Second $ amount is Driver's pay
                                    driver_pay = float(dollar_amounts[1].replace(",", ""))
                                    plate_data[assigned_plate]["driver_pay"] += driver_pay
                                
                                # Store driver name if found
                                if driver_name and len(driver_name) > 2:
                                    if not plate_data[assigned_plate]["driver_name"]:
                                        plate_data[assigned_plate]["driver_name"] = driver_name
                                
                                # Extract fuel amount - look for pattern: date time $amount
                                # Fuel can be on same line after date/time or on next line(s)
                                fuel_found = False
                                
                                # Check for fuel on same line (after date/time pattern)
                                fuel_on_line = re.search(r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+\$([\d,]+\.?\d*)', line)
                                if fuel_on_line:
                                    fuel_amount = float(fuel_on_line.group(1).replace(",", ""))
                                    plate_data[assigned_plate]["fuel"] += fuel_amount
                                    fuel_found = True
                                
                                # If no fuel found with date/time pattern, check if 4th dollar amount is fuel
                                # (Some blocks have: Pay Amount, Driver's pay, Miles, Fuel)
                                if not fuel_found and len(dollar_amounts) >= 4:
                                    # The 4th amount might be fuel (skip the 3rd which is usually miles)
                                    fuel_amount = float(dollar_amounts[3].replace(",", ""))
                                    # Only add if it's a reasonable fuel amount (less than $10,000)
                                    if fuel_amount < 10000:
                                        plate_data[assigned_plate]["fuel"] += fuel_amount
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
                                        plate_data[assigned_plate]["fuel"] += fuel_amount
                                        fuel_found = True
                                        break
                                    
                                    # Also check for standalone dollar amount (might be fuel)
                                    next_fuel_match = re.search(r'\$([\d,]+\.?\d*)', next_line)
                                    if next_fuel_match and not fuel_found:
                                        fuel_amount = float(next_fuel_match.group(1).replace(",", ""))
                                        # Only add if it's a reasonable fuel amount (less than $10,000)
                                        if fuel_amount < 10000 and fuel_amount > 0:
                                            plate_data[assigned_plate]["fuel"] += fuel_amount
                                            fuel_found = True
                                            break
                                    
                                    check_idx += 1
                i += 1
            
            # Calculate payroll fee as 6.5% of driver's pay for each truck
            # We already summed driver's pay from blocks, now calculate 6.5% fee for each truck
            total_driver_pay = sum(data["driver_pay"] for data in plate_data.values())
            
            # Parse data for each license plate
            settlements = []
            
            # Create settlement for each license plate using parsed block data
            is_first_truck = True
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
                    "driver_name": data.get("driver_name"),
                    "license_plate": license_plate,
                }
                
                # Initialize expense categories
                # Fixed expenses (insurance, safety, prepass, IFTA) are always split 50/50 between trucks
                # Fuel is calculated separately per license plate (already in data["fuel"])
                # Deductions/custom expenses are applied to the first truck (common settlement expense)
                expense_categories = {
                    "fuel": data["fuel"],  # Already calculated per plate from block rows
                    "dispatch_fee": 0.0,
                    "insurance": shared_expenses["insurance"] / 2.0,  # Always 50% per truck
                    "safety": shared_expenses["safety"] / 2.0,  # Always 50% per truck
                    "prepass": shared_expenses["prepass"] / 2.0,  # Always 50% per truck
                    "ifta": ifta_total / 2.0,  # Always 50% per truck
                    "driver_pay": data["driver_pay"],
                    "payroll_fee": 0.0,
                    "truck_parking": 0.0,
                    "service_on_truck": 0.0,
                    "custom": deductions_total if is_first_truck else 0.0  # Apply deductions to first truck
                }
                
                # Calculate dispatch fee proportionally by gross revenue
                total_gross = sum(pd["gross_revenue"] for pd in plate_data.values())
                if total_gross > 0:
                    expense_categories["dispatch_fee"] = (dispatch_fee_total * data["gross_revenue"]) / total_gross
                
                # Calculate payroll fee as 6.5% of driver's pay (summed from blocks)
                expense_categories["payroll_fee"] = data["driver_pay"] * 0.065
                
                # Calculate total expenses
                total_expenses = sum(expense_categories.values())
                
                # Get reimbursement for this plate (if extracted from blocks)
                # If not found in blocks but we have a total, distribute proportionally
                plate_reimbursement = data.get("reimbursement", 0.0)
                if plate_reimbursement == 0.0 and reimbursement_total > 0 and len(plate_data) > 0:
                    # Distribute total reimbursement proportionally by gross revenue
                    total_gross_all = sum(pd["gross_revenue"] for pd in plate_data.values())
                    if total_gross_all > 0:
                        plate_reimbursement = (reimbursement_total * data["gross_revenue"]) / total_gross_all
                
                # Calculate net profit
                # Reimbursements are added to net profit (they increase profit)
                plate_settlement["net_profit"] = data["gross_revenue"] - total_expenses + plate_reimbursement
                
                # Store reimbursement in expense categories (as a negative expense, or track separately)
                expense_categories["reimbursement"] = plate_reimbursement
                plate_settlement["expenses"] = total_expenses
                plate_settlement["expense_categories"] = expense_categories
                
                settlements.append(plate_settlement)
                is_first_truck = False  # Mark that we've processed the first truck
            
            # Validate/adjust fuel totals FIRST (before net profit adjustment)
            # This ensures fuel adjustments are accounted for in net profit calculations
            if fuel_total_from_pdf is not None and len(settlements) > 0:
                calculated_total_fuel = sum(s.get("expense_categories", {}).get("fuel", 0) for s in settlements)
                fuel_difference = fuel_total_from_pdf - calculated_total_fuel
                
                # If there's a significant difference, fuel might be missing from some blocks
                if abs(fuel_difference) > 0.01:
                    # Distribute the missing fuel proportionally by gross revenue
                    total_gross = sum(s["gross_revenue"] for s in settlements)
                    if total_gross > 0:
                        for settlement in settlements:
                            proportion = settlement["gross_revenue"] / total_gross
                            fuel_adjustment = fuel_difference * proportion
                            settlement["expense_categories"]["fuel"] += fuel_adjustment
                            settlement["expenses"] += fuel_adjustment
                            # Recalculate net profit after fuel adjustment (include reimbursement)
                            reimbursement = settlement.get("expense_categories", {}).get("reimbursement", 0.0)
                            settlement["net_profit"] = settlement["gross_revenue"] - settlement["expenses"] + reimbursement
            
            # After calculating all settlements, validate/adjust net profit if PDF shows different total
            # The PDF's Net Pay is the final amount after ALL expenses including deductions
            # NOTE: PDF's Net Pay may or may not include reimbursement - we need to check
            # This happens AFTER fuel adjustment so fuel is accounted for
            if pdf_net_pay is not None and len(settlements) > 0:
                calculated_total_net = sum(s["net_profit"] for s in settlements)
                total_reimbursement = sum(s.get("expense_categories", {}).get("reimbursement", 0.0) for s in settlements)
                
                # Check if PDF Net Pay already includes reimbursement
                # If calculated net (with reimbursement) matches PDF, then PDF includes reimbursement
                # If calculated net (without reimbursement) matches PDF, then PDF doesn't include reimbursement
                calculated_net_without_reimb = calculated_total_net - total_reimbursement
                
                # Determine if PDF Net Pay includes reimbursement by comparing both scenarios
                diff_with_reimb = abs(calculated_total_net - pdf_net_pay)
                diff_without_reimb = abs(calculated_net_without_reimb - pdf_net_pay)
                
                # Use the scenario that's closer (within $1 tolerance)
                if diff_without_reimb < diff_with_reimb and diff_without_reimb < 1.0:
                    # PDF Net Pay does NOT include reimbursement - we need to subtract it from our calculation
                    # Adjust net profit to match PDF (which doesn't include reimbursement)
                    difference = calculated_total_net - pdf_net_pay
                    # Remove reimbursement from net profit to match PDF
                    for settlement in settlements:
                        reimb = settlement.get("expense_categories", {}).get("reimbursement", 0.0)
                        settlement["net_profit"] -= reimb
                else:
                    # PDF Net Pay likely includes reimbursement (or reimbursement is already accounted for)
                    difference = calculated_total_net - pdf_net_pay
                
                # If there's a significant difference and we have deductions, adjust
                # This handles cases where deductions might not be properly extracted or applied
                if abs(difference) > 0.01 and deductions_total > 0:
                    # Check if the difference is close to deductions amount
                    # If so, deductions might not have been properly subtracted
                    if abs(abs(difference) - deductions_total) < 10.0:  # Allow small rounding differences
                        # Adjust: subtract the difference from the first truck's net profit
                        # (since deductions are applied to first truck)
                        if settlements:
                            settlements[0]["expenses"] += difference
                            settlements[0]["expense_categories"]["custom"] += difference
                            # Recalculate net profit (include reimbursement)
                            reimbursement = settlements[0].get("expense_categories", {}).get("reimbursement", 0.0)
                            settlements[0]["net_profit"] = settlements[0]["gross_revenue"] - settlements[0]["expenses"] + reimbursement
                    # If difference doesn't match deductions, but is significant, still adjust
                    # This handles cases where deductions might be missing or incorrect
                    elif abs(difference) > 0.01:
                        # Adjust net profit to match PDF
                        if settlements:
                            settlements[0]["expenses"] += difference
                            # Update custom category if it exists, otherwise add to it
                            if "custom" in settlements[0]["expense_categories"]:
                                settlements[0]["expense_categories"]["custom"] += difference
                            else:
                                settlements[0]["expense_categories"]["custom"] = difference
                            # Recalculate net profit (include reimbursement)
                            reimbursement = settlements[0].get("expense_categories", {}).get("reimbursement", 0.0)
                            settlements[0]["net_profit"] = settlements[0]["gross_revenue"] - settlements[0]["expenses"] + reimbursement
            
            # If no settlements found, fallback to single truck parsing
            if not settlements:
                single_settlement = parse_amazon_relay_pdf(file_path, settlement_type)
                if return_validation:
                    return {
                        "settlements": [single_settlement],
                        "validation": {
                            "is_valid": True,
                            "errors": [],
                            "warnings": [{
                                "level": "warning",
                                "category": "detection",
                                "message": "Multi-truck PDF detected but only one settlement extracted",
                                "details": {}
                            }],
                            "summary": {
                                "total_settlements": 1,
                                "error_count": 0,
                                "warning_count": 1
                            }
                        }
                    }
                return [single_settlement]
            
            # Run validation if requested
            if return_validation:
                from app.utils.validation import validate_multi_truck_extraction
                
                # Extract expected totals from PDF text (if available)
                expected_totals = {}
                
                # Try to extract total gross revenue from PDF
                gross_pay_match = re.search(r'Gross Pay\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
                if gross_pay_match:
                    expected_totals["gross_revenue"] = float(gross_pay_match.group(1).replace(",", ""))
                
                # Try to extract total expenses
                total_expenses_match = re.search(r'Total Expenses\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
                if total_expenses_match:
                    expected_totals["expenses"] = float(total_expenses_match.group(1).replace(",", ""))
                
                # Prepare shared expenses for validation
                shared_expenses_dict = {
                    "insurance": shared_expenses["insurance"],
                    "safety": shared_expenses["safety"],
                    "prepass": shared_expenses["prepass"],
                    "ifta": ifta_total
                }
                
                # Run validation
                validation_result = validate_multi_truck_extraction(
                    settlements,
                    expected_totals if expected_totals else None,
                    shared_expenses_dict
                )
                
                return {
                    "settlements": settlements,
                    "validation": validation_result
                }
            
            return settlements
            
    except Exception as e:
        if return_validation:
            return {
                "settlements": [],
                "validation": {
                    "is_valid": False,
                    "errors": [{
                        "level": "error",
                        "category": "parsing",
                        "message": f"Error parsing multi-truck PDF: {str(e)}",
                        "details": {"error": str(e)}
                    }],
                    "warnings": [],
                    "summary": {
                        "total_settlements": 0,
                        "error_count": 1,
                        "warning_count": 0
                    }
                }
            }
        raise Exception(f"Error parsing multi-truck PDF: {str(e)}")

