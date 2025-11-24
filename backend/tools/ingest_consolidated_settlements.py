import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

# Allow running the script directly by adding backend/ to PYTHONPATH
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal
from app.models import Settlement, Truck
from app.utils.loan_interest import calculate_weekly_loan_interest


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        parts = [int(p) for p in value.split("-")]
        if len(parts) == 3:
            return date(parts[0], parts[1], parts[2])
    except Exception:
        return None
    return None


def map_truck(db: Session, unit_number: Optional[str], plate_number: Optional[str]) -> Optional[int]:
    """Resolve truck_id using plate or unit number (truck name).
    
    Tries multiple matching strategies:
    1. Exact license plate match
    2. Exact name match (e.g., "417")
    3. "Volvo {number}" format (e.g., "Volvo 417")
    4. License plate history (if plate_number provided)
    """
    # Try license plate first (most reliable)
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
    
    # Try unit number matching
    if unit_number:
        # Exact match
        truck = db.query(Truck).filter(Truck.name == unit_number).first()
        if truck:
            return truck.id
        
        # Try "Volvo {number}" format
        truck = db.query(Truck).filter(Truck.name == f"Volvo {unit_number}").first()
        if truck:
            return truck.id
    
    return None


def normalize_expense_categories(totals: Dict[str, Any]) -> Tuple[Dict[str, float], float]:
    """Build expense_categories and total_expenses from statement_totals.
    
    Note: Reimbursements reduce expenses (they're credits), so we subtract them
    from total expenses rather than adding them.
    """
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
    # Reimbursements reduce expenses (they're credits)
    reimbursement = totals.get("reimbursment", 0) or totals.get("reimbursement", 0) or 0
    
    # Remove zero/None categories to keep payload small
    expense_categories = {k: float(v) for k, v in cat_map.items() if v}
    # Store reimbursement separately for tracking (as positive value)
    if reimbursement:
        expense_categories["reimbursement"] = float(reimbursement)
    
    # Calculate total expenses: sum of expense categories MINUS reimbursement
    # (since reimbursement reduces expenses, we subtract it from the total)
    total_expenses = sum(v for k, v in expense_categories.items() if k != "reimbursement") - float(reimbursement)
    
    return expense_categories, total_expenses


def normalize_entry(entry: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
    totals = entry.get("statement_totals") or {}
    statement = entry.get("statement") or {}

    gross_revenue = totals.get("gross_revenue")
    net_profit = totals.get("net_to_owner")
    if gross_revenue is None and net_profit is None:
        return None  # skip invalid rows

    truck_id = map_truck(db, entry.get("unit_number"), entry.get("plate_number"))
    settlement_date = parse_date(statement.get("period_end"))
    week_start = parse_date(statement.get("period_start"))
    week_end = parse_date(statement.get("period_end"))  # Use period_end as week_end

    expense_categories, calculated_expenses = normalize_expense_categories(totals)

    # Calculate and add loan interest if truck has a loan
    weekly_interest = 0.0
    if truck_id:
        truck = db.query(Truck).filter(Truck.id == truck_id).first()
        if truck and truck.vehicle_type == 'truck':
            # Use current_loan_balance if available, otherwise use loan_amount
            current_balance = float(truck.current_loan_balance) if truck.current_loan_balance is not None else (float(truck.loan_amount) if truck.loan_amount else None)
            interest_rate = float(truck.interest_rate) if truck.interest_rate else 0.07
            
            if current_balance and current_balance > 0:
                weekly_interest = calculate_weekly_loan_interest(current_balance, interest_rate)
                
                # Add loan interest to expense categories
                expense_categories["loan_interest"] = weekly_interest

    # Map additional fields
    blocks_delivered = entry.get("blocks_count")
    block_ids = entry.get("block_ids")  # Extract block IDs array
    miles_driven = totals.get("gross_miles")
    license_plate = entry.get("plate_number")
    pdf_file_path = statement.get("source_file")

    # Use net_to_owner from JSON as the source of truth for net profit
    # Calculate expenses from net_to_owner to ensure consistency: expenses = revenue - net_profit
    if net_profit is not None:
        # Base expenses from JSON's net_to_owner (before loan interest)
        base_expenses = float(gross_revenue or 0) - float(net_profit)
        # Add loan interest to expenses
        final_expenses = base_expenses + weekly_interest
        # Net profit with loan interest subtracted
        final_net_profit = float(net_profit) - weekly_interest
    else:
        # Fallback: use calculated expenses if net_to_owner not available
        final_expenses = calculated_expenses + weekly_interest
        final_net_profit = float(gross_revenue or 0) - final_expenses

    return {
        "truck_id": truck_id,
        "settlement_date": settlement_date,
        "week_start": week_start,
        "week_end": week_end,
        "miles_driven": float(miles_driven) if miles_driven is not None else None,
        "blocks_delivered": int(blocks_delivered) if blocks_delivered is not None else None,
        "block_ids": block_ids if block_ids else None,  # Store block IDs array
        "gross_revenue": float(gross_revenue or 0),
        "expenses": float(final_expenses),
        "expense_categories": expense_categories,
        "net_profit": final_net_profit,
        "pdf_file_path": pdf_file_path,
        "license_plate": license_plate,
    }


def load_entries(path: Path, db: Session) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text())
    entries: List[Dict[str, Any]] = []
    for item in data:
        if "statement_totals" in item:
            norm = normalize_entry(item, db)
            if norm:
                entries.append(norm)
        elif "statements" in item:
            for st in item.get("statements", []):
                merged = {
                    "unit_number": item.get("unit_number"),
                    "plate_number": item.get("plate_number"),
                    "statement": st.get("statement"),
                    "statement_totals": st.get("statement_totals"),
                    "blocks_count": st.get("blocks_count"),  # Include blocks_count from nested structure
                    "block_ids": st.get("block_ids"),  # Include block_ids from nested structure
                }
                norm = normalize_entry(merged, db)
                if norm:
                    entries.append(norm)
    return entries


def find_existing(db: Session, entry: Dict[str, Any]) -> Optional[Settlement]:
    """Find existing settlement by truck_id and settlement_date."""
    if entry.get("truck_id") and entry.get("settlement_date"):
        return (
            db.query(Settlement)
            .filter(
                Settlement.truck_id == entry["truck_id"],
                Settlement.settlement_date == entry["settlement_date"],
            )
            .first()
        )
    return None


def diff_settlement(existing: Settlement, entry: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    """Compare settlement fields and return differences."""
    diffs: Dict[str, Tuple[Any, Any]] = {}
    fields = [
        "gross_revenue", "expenses", "net_profit", "expense_categories",
        "miles_driven", "blocks_delivered", "block_ids", "week_start", "week_end",
        "pdf_file_path", "license_plate"
    ]
    for f in fields:
        new_val = entry.get(f)
        old_val = getattr(existing, f, None)
        # Handle numeric comparison (convert to float for comparison)
        if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            if abs(float(old_val) - float(new_val)) > 0.01:  # Allow small floating point differences
                diffs[f] = (old_val, new_val)
        elif old_val != new_val:
            diffs[f] = (old_val, new_val)
    return diffs


def upsert_settlements(entries: List[Dict[str, Any]], db: Session, dry_run: bool) -> Dict[str, int]:
    stats = {"inserted": 0, "updated": 0, "skipped_unresolved_truck": 0}
    for entry in entries:
        if not entry.get("truck_id"):
            stats["skipped_unresolved_truck"] += 1
            continue
        existing = find_existing(db, entry)
        if existing:
            changes = diff_settlement(existing, entry)
            if changes and not dry_run:
                for k, v in entry.items():
                    setattr(existing, k, v)
                db.add(existing)
                stats["updated"] += 1
        else:
            if not dry_run:
                db.add(Settlement(**entry))
            stats["inserted"] += 1
    if not dry_run:
        db.commit()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest consolidated settlement JSON files into the DB.")
    parser.add_argument("files", nargs="+", help="Paths to consolidated settlement JSON files.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB; just report.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        all_entries: List[Dict[str, Any]] = []
        for file_path in args.files:
            entries = load_entries(Path(file_path), db)
            all_entries.extend(entries)
        stats = upsert_settlements(all_entries, db, dry_run=args.dry_run)
        print(json.dumps({"files": args.files, "counts": stats, "total_entries": len(all_entries)}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
