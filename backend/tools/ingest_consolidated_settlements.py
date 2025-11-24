import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Allow running the script directly by adding backend/ to PYTHONPATH
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal, DATABASE_URL
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


def upsert_settlements(entries: List[Dict[str, Any]], db: Session, dry_run: bool, verbose: bool = False) -> Dict[str, Any]:
    stats = {
        "inserted": 0,
        "updated": 0,
        "skipped_unresolved_truck": 0,
        "skipped_no_changes": 0,
        "errors": 0,
        "error_details": []
    }
    
    unresolved_trucks = set()
    
    for idx, entry in enumerate(entries, 1):
        try:
            if not entry.get("truck_id"):
                unit = entry.get("unit_number") or "unknown"
                plate = entry.get("plate_number") or "unknown"
                unresolved_trucks.add(f"{unit} ({plate})")
                stats["skipped_unresolved_truck"] += 1
                if verbose:
                    print(f"  [{idx}/{len(entries)}] ⚠️  Skipped: No truck found for unit {unit}, plate {plate}")
                continue
            
            # Use a fresh session/transaction for each entry to avoid transaction abort issues
            try:
                existing = find_existing(db, entry)
            except Exception as e:
                # Rollback and retry
                db.rollback()
                try:
                    existing = find_existing(db, entry)
                except Exception as retry_e:
                    raise Exception(f"Failed to query existing settlement: {str(retry_e)}")
            
            if existing:
                changes = diff_settlement(existing, entry)
                if changes:
                    if not dry_run:
                        for k, v in entry.items():
                            setattr(existing, k, v)
                        db.add(existing)
                    stats["updated"] += 1
                    if verbose:
                        try:
                            truck_name = db.query(Truck).filter(Truck.id == entry["truck_id"]).first().name
                        except Exception:
                            truck_name = f"Truck ID {entry['truck_id']}"
                        print(f"  [{idx}/{len(entries)}] ✏️  Update: Truck {truck_name}, Date {entry['settlement_date']}")
                        if verbose and len(changes) <= 5:
                            for field, (old_val, new_val) in changes.items():
                                print(f"      {field}: {old_val} → {new_val}")
                else:
                    stats["skipped_no_changes"] += 1
                    if verbose:
                        try:
                            truck_name = db.query(Truck).filter(Truck.id == entry["truck_id"]).first().name
                        except Exception:
                            truck_name = f"Truck ID {entry['truck_id']}"
                        print(f"  [{idx}/{len(entries)}] ✓ No changes: Truck {truck_name}, Date {entry['settlement_date']}")
            else:
                if not dry_run:
                    db.add(Settlement(**entry))
                stats["inserted"] += 1
                if verbose:
                    try:
                        truck_name = db.query(Truck).filter(Truck.id == entry["truck_id"]).first().name
                    except Exception:
                        truck_name = f"Truck ID {entry['truck_id']}"
                    print(f"  [{idx}/{len(entries)}] ➕ Insert: Truck {truck_name}, Date {entry['settlement_date']}")
            
            # Commit in batches to avoid transaction issues (every 50 entries or at the end)
            if not dry_run and (idx % 50 == 0 or idx == len(entries)):
                try:
                    db.commit()
                except SQLAlchemyError as e:
                    db.rollback()
                    stats["errors"] += 1
                    error_msg = f"Database commit error at entry {idx}: {str(e)}"
                    stats["error_details"].append(error_msg)
                    if verbose:
                        print(f"  [{idx}/{len(entries)}] ❌ Commit error: {error_msg}")
                    
        except Exception as e:
            # Rollback on any error and continue
            try:
                db.rollback()
            except Exception:
                pass
            
            stats["errors"] += 1
            error_msg = f"Error processing entry {idx}: {str(e)}"
            stats["error_details"].append(error_msg)
            if verbose:
                print(f"  [{idx}/{len(entries)}] ❌ Error: {error_msg}")
    
    # Final commit if there are remaining changes
    if not dry_run and (stats["inserted"] > 0 or stats["updated"] > 0):
        try:
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            stats["errors"] += 1
            stats["error_details"].append(f"Final database commit error: {str(e)}")
    
    if unresolved_trucks:
        stats["unresolved_trucks"] = sorted(list(unresolved_trucks))
    
    return stats


def verify_trucks_exist(db: Session, entries: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Verify all trucks referenced in entries exist in database."""
    truck_ids = {e.get("truck_id") for e in entries if e.get("truck_id")}
    missing_trucks = []
    
    for truck_id in truck_ids:
        truck = db.query(Truck).filter(Truck.id == truck_id).first()
        if not truck:
            missing_trucks.append(f"Truck ID {truck_id}")
    
    return len(missing_trucks) == 0, missing_trucks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest consolidated settlement JSON files into the DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (test without writing)
  python ingest_consolidated_settlements.py --dry-run backend/417_consolidated_settlement.json
  
  # Import files
  python ingest_consolidated_settlements.py backend/417_consolidated_settlement.json backend/418_consolidated_settlement.json
  
  # Verbose output
  python ingest_consolidated_settlements.py --verbose backend/417_consolidated_settlement.json
        """
    )
    parser.add_argument("files", nargs="+", help="Paths to consolidated settlement JSON files.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB; just report what would be done.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed progress.")
    parser.add_argument("--skip-truck-check", action="store_true", help="Skip verification that trucks exist.")
    args = parser.parse_args()

    # Show database connection info
    db_type = "PostgreSQL (Production)" if "postgresql" in DATABASE_URL.lower() else "SQLite (Local)"
    print(f"📊 Database: {db_type}")
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be written to database\n")
    
    db = SessionLocal()
    try:
        # Verify database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        
        all_entries: List[Dict[str, Any]] = []
        file_stats = {}
        
        # Load entries from all files
        for file_path in args.files:
            path = Path(file_path)
            if not path.exists():
                print(f"❌ Error: File not found: {file_path}")
                sys.exit(1)
            
            if args.verbose:
                print(f"📄 Loading: {file_path}")
            
            try:
                entries = load_entries(path, db)
                all_entries.extend(entries)
                file_stats[str(path)] = len(entries)
                if args.verbose:
                    print(f"   Found {len(entries)} settlement entries\n")
            except Exception as e:
                print(f"❌ Error loading {file_path}: {e}")
                sys.exit(1)
        
        if not all_entries:
            print("⚠️  No settlement entries found in any file.")
            sys.exit(0)
        
        print(f"📦 Total entries to process: {len(all_entries)}\n")
        
        # Verify trucks exist
        if not args.skip_truck_check:
            all_exist, missing = verify_trucks_exist(db, all_entries)
            if not all_exist:
                print("❌ Error: Some trucks referenced in settlements do not exist in database:")
                for truck in missing:
                    print(f"   - {truck}")
                print("\n💡 Tip: Create trucks first or use --skip-truck-check to proceed anyway")
                sys.exit(1)
            if args.verbose:
                print("✓ All trucks verified\n")
        
        # Process settlements
        if args.verbose:
            print("🔄 Processing settlements...\n")
        
        stats = upsert_settlements(all_entries, db, dry_run=args.dry_run, verbose=args.verbose)
        
        # Print summary
        print("\n" + "="*60)
        print("📊 IMPORT SUMMARY")
        print("="*60)
        print(f"Files processed: {len(args.files)}")
        for file_path, count in file_stats.items():
            print(f"  - {file_path}: {count} entries")
        print(f"\nTotal entries: {len(all_entries)}")
        print(f"✅ Inserted: {stats['inserted']}")
        print(f"✏️  Updated: {stats['updated']}")
        print(f"⏭️  Skipped (no changes): {stats.get('skipped_no_changes', 0)}")
        print(f"⚠️  Skipped (unresolved truck): {stats['skipped_unresolved_truck']}")
        if stats.get('errors', 0) > 0:
            print(f"❌ Errors: {stats['errors']}")
            for error in stats.get('error_details', []):
                print(f"   - {error}")
        
        if stats.get('unresolved_trucks'):
            print(f"\n⚠️  Unresolved trucks (need to be created in database):")
            for truck in stats['unresolved_trucks']:
                print(f"   - {truck}")
        
        print("="*60)
        
        # Return JSON output for scripting
        if not args.verbose:
            print(json.dumps({
                "files": args.files,
                "file_stats": file_stats,
                "counts": stats,
                "total_entries": len(all_entries)
            }, indent=2))
        
        # Exit with error code if there were issues
        if stats.get('errors', 0) > 0:
            sys.exit(1)
            
    except SQLAlchemyError as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
