"""
PDF parser for Amazon Relay settlement files
"""
import pdfplumber
import re
from datetime import datetime
from typing import Dict


def parse_amazon_relay_pdf(file_path: str) -> Dict:
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
                "fees": 0.0,  # Dispatch fee, safety, prepass, insurance, etc
                "ifta": 0.0,
                "driver_pay": 0.0,  # Driver's pay/compensation
                "other": 0.0  # Service on truck, parking, deductions, etc
            }
            
            if is_income_sheet_format:
                # Format 2: Expenses in parentheses like "($ 211.91)"
                expense_mappings = [
                    (r'FUEL[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'fuel'),
                    (r'IFTA[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'ifta'),
                    (r'DISPATCH FEE[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'fees'),
                    (r'SAFETY[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'fees'),
                    (r'PREPASS[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'fees'),
                    (r'INSURANCE[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'fees'),
                    (r"DRIVER'S PAY[^\n]*\(\$\s*([\d,]+\.?\d*)\)", 'driver_pay'),
                    (r'SERVICE ON THE TRUCK[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'other'),
                    (r'TRUCK PARKING[^\n]*\(\$\s*([\d,]+\.?\d*)\)', 'other'),
                ]
            else:
                # Format 1: "Expense Name $X,XXX.XX"
                expense_mappings = [
                    (r'Fuel\s+\$?([\d,]+\.?\d*)', 'fuel'),
                    (r'IFTA\s+\$?([\d,]+\.?\d*)', 'ifta'),
                    (r'Dispatch Fee\s+\$?([\d,]+\.?\d*)', 'fees'),
                    (r'Safety\s+\$?([\d,]+\.?\d*)', 'fees'),
                    (r'Prepass\s+\$?([\d,]+\.?\d*)', 'fees'),
                    (r'Insurance\s+\$?([\d,]+\.?\d*)', 'fees'),
                    (r"Driver's Pay Fee\s+\$?([\d,]+\.?\d*)", 'driver_pay'),
                    (r'Deductions\s+\$?([\d,]+\.?\d*)', 'other'),
                ]
            
            for pattern, category in expense_mappings:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    amount = float(match.group(1).replace(",", ""))
                    expense_categories[category] += amount
                    total_expenses += amount
            
            # Format 1: Also check for Driver's Pay separately
            if not is_income_sheet_format:
                drivers_pay_match = re.search(r"Driver's Pay\s+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
                if drivers_pay_match:
                    amount = float(drivers_pay_match.group(1).replace(",", ""))
                    expense_categories["driver_pay"] += amount
                    total_expenses += amount
            
            if total_expenses > 0:
                settlement_data["expenses"] = total_expenses
                settlement_data["expense_categories"] = expense_categories
            
            # Count blocks delivered
            if is_income_sheet_format:
                # Format 2: Use STOPS count as blocks
                # Look in table row: "12/27-12/29/2024 TFC9-CLT2 CLT5 7 795.0"
                # Pattern: date range, route codes, then stops number
                table_row_match = re.search(r'\d{1,2}/\d{1,2}-\d{1,2}/\d{1,2}/\d{4}[^\n]*?([A-Z0-9-]+)\s+([A-Z0-9]+)\s+(\d+)', text, re.IGNORECASE)
                if table_row_match:
                    # Third group is stops count
                    settlement_data["blocks_delivered"] = int(table_row_match.group(3))
                else:
                    # Fallback: look for "STOPS 7" pattern
                    stops_match = re.search(r'STOPS\s+(\d+)', text, re.IGNORECASE)
                    if stops_match:
                        settlement_data["blocks_delivered"] = int(stops_match.group(1))
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

