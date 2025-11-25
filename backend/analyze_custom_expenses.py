#!/usr/bin/env python3
"""
Analyze and report all custom expenses in the database.

This script queries all settlements and identifies expenses that are categorized
as "custom" (i.e., not in the standard expense categories list).
"""
import sys
from pathlib import Path
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Any, Optional
import json

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal, engine
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.database import Base

# Standard expense categories (NOT custom)
STANDARD_CATEGORIES = [
    "fuel",
    "dispatch_fee",
    "insurance",
    "safety",
    "prepass",
    "ifta",
    "driver_pay",
    "payroll_fee",
    "loan_interest",
    "truck_parking",
    "service_on_truck",
    "repairs",  # Repairs are tracked separately but not in expense_categories
]


def format_currency(amount: Optional[float]) -> str:
    """Format amount as currency."""
    if amount is None:
        return "$0.00"
    return f"${float(amount):,.2f}"


def is_custom_category(category: str) -> bool:
    """Check if a category is considered custom."""
    if category in STANDARD_CATEGORIES:
        return False
    if category == "custom":
        return True
    if category.startswith("custom_"):
        return True
    if category in ["fees", "other"]:
        return True
    return True  # Any other category not in standard list


def extract_custom_description(category_key: str) -> str:
    """Extract human-readable description from custom category key."""
    if category_key.startswith("custom_"):
        desc = category_key.replace("custom_", "")
        return " ".join(word.capitalize() for word in desc.split("_"))
    return category_key.replace("_", " ").title()


def analyze_custom_expenses(db) -> Dict[str, Any]:
    """Analyze all custom expenses from settlements."""
    settlements = db.query(Settlement).order_by(Settlement.settlement_date.desc()).all()
    
    # Statistics
    total_custom_expenses = 0.0
    settlements_with_custom = 0
    custom_category_totals = defaultdict(float)
    custom_category_counts = defaultdict(int)
    custom_category_examples = defaultdict(list)  # Store example settlements
    
    # Track by truck
    truck_custom_totals = defaultdict(float)
    
    # Track by date range
    date_range_totals = defaultdict(float)
    
    # Process each settlement
    for settlement in settlements:
        has_custom = False
        settlement_custom_total = 0.0
        
        if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
            for category, amount in settlement.expense_categories.items():
                try:
                    amount_float = float(amount) if amount is not None else 0.0
                    
                    # Skip reimbursement (it's a credit, not an expense)
                    if category == "reimbursement":
                        continue
                    
                    # Check if this is a custom category
                    if is_custom_category(category):
                        has_custom = True
                        settlement_custom_total += amount_float
                        total_custom_expenses += amount_float
                        
                        # Track by category
                        custom_category_totals[category] += amount_float
                        custom_category_counts[category] += 1
                        
                        # Store example (limit to 5 per category)
                        if len(custom_category_examples[category]) < 5:
                            truck_name = settlement.truck.name if settlement.truck else "Unknown"
                            custom_category_examples[category].append({
                                "settlement_id": settlement.id,
                                "truck_name": truck_name,
                                "truck_id": settlement.truck_id,
                                "date": str(settlement.settlement_date),
                                "amount": amount_float,
                                "license_plate": settlement.license_plate,
                            })
                        
                        # Track by truck
                        if settlement.truck_id:
                            truck_name = settlement.truck.name if settlement.truck else f"Truck {settlement.truck_id}"
                            truck_custom_totals[truck_name] += amount_float
                        
                        # Track by year-month
                        if settlement.settlement_date:
                            year_month = settlement.settlement_date.strftime("%Y-%m")
                            date_range_totals[year_month] += amount_float
                
                except (ValueError, TypeError) as e:
                    continue
        
        if has_custom:
            settlements_with_custom += 1
    
    return {
        "total_custom_expenses": total_custom_expenses,
        "settlements_with_custom": settlements_with_custom,
        "total_settlements": len(settlements),
        "custom_category_totals": dict(custom_category_totals),
        "custom_category_counts": dict(custom_category_counts),
        "custom_category_examples": dict(custom_category_examples),
        "truck_custom_totals": dict(truck_custom_totals),
        "date_range_totals": dict(date_range_totals),
    }


def print_report(analysis: Dict[str, Any]):
    """Print a formatted report of custom expenses."""
    print("=" * 80)
    print("CUSTOM EXPENSES ANALYSIS REPORT")
    print("=" * 80)
    print()
    
    # Summary
    print("SUMMARY")
    print("-" * 80)
    print(f"Total Settlements Analyzed: {analysis['total_settlements']}")
    print(f"Settlements with Custom Expenses: {analysis['settlements_with_custom']}")
    print(f"Total Custom Expenses: {format_currency(analysis['total_custom_expenses'])}")
    if analysis['total_settlements'] > 0:
        percentage = (analysis['settlements_with_custom'] / analysis['total_settlements']) * 100
        print(f"Percentage with Custom Expenses: {percentage:.1f}%")
    print()
    
    # Custom categories breakdown
    if analysis['custom_category_totals']:
        print("CUSTOM EXPENSE CATEGORIES BREAKDOWN")
        print("-" * 80)
        
        # Sort by total amount (descending)
        sorted_categories = sorted(
            analysis['custom_category_totals'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for category, total in sorted_categories:
            count = analysis['custom_category_counts'].get(category, 0)
            description = extract_custom_description(category)
            percentage = (total / analysis['total_custom_expenses'] * 100) if analysis['total_custom_expenses'] > 0 else 0
            
            print(f"\n{description} ({category})")
            print(f"  Total Amount: {format_currency(total)}")
            print(f"  Occurrences: {count} settlements")
            print(f"  Percentage of Custom Expenses: {percentage:.1f}%")
            print(f"  Average per Settlement: {format_currency(total / count if count > 0 else 0)}")
            
            # Show examples
            if category in analysis['custom_category_examples']:
                examples = analysis['custom_category_examples'][category]
                if examples:
                    print(f"  Examples:")
                    for ex in examples[:3]:  # Show first 3 examples
                        print(f"    - {ex['truck_name']} ({ex['date']}): {format_currency(ex['amount'])}")
    else:
        print("No custom expenses found in database.")
    print()
    
    # Top trucks by custom expenses
    if analysis['truck_custom_totals']:
        print("TOP TRUCKS BY CUSTOM EXPENSES")
        print("-" * 80)
        sorted_trucks = sorted(
            analysis['truck_custom_totals'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for i, (truck_name, total) in enumerate(sorted_trucks[:10], 1):  # Top 10
            percentage = (total / analysis['total_custom_expenses'] * 100) if analysis['total_custom_expenses'] > 0 else 0
            print(f"{i:2d}. {truck_name:30s} {format_currency(total):>15s} ({percentage:5.1f}%)")
    print()
    
    # Custom expenses by month
    if analysis['date_range_totals']:
        print("CUSTOM EXPENSES BY MONTH")
        print("-" * 80)
        sorted_months = sorted(analysis['date_range_totals'].items())
        
        for year_month, total in sorted_months:
            percentage = (total / analysis['total_custom_expenses'] * 100) if analysis['total_custom_expenses'] > 0 else 0
            print(f"{year_month}: {format_currency(total):>15s} ({percentage:5.1f}%)")
    print()
    
    # Category details
    print("DETAILED CATEGORY INFORMATION")
    print("-" * 80)
    print("\nStandard Categories (NOT custom):")
    for cat in STANDARD_CATEGORIES:
        print(f"  - {cat}")
    
    print("\nCustom Categories Found:")
    if analysis['custom_category_totals']:
        for category in sorted(analysis['custom_category_totals'].keys()):
            print(f"  - {category}")
    else:
        print("  (none)")
    print()
    
    print("=" * 80)


def export_to_json(analysis: Dict[str, Any], output_file: str):
    """Export analysis results to JSON file."""
    # Convert Decimal and other types to JSON-serializable formats
    export_data = {
        "summary": {
            "total_settlements": analysis['total_settlements'],
            "settlements_with_custom": analysis['settlements_with_custom'],
            "total_custom_expenses": float(analysis['total_custom_expenses']),
            "percentage_with_custom": (
                (analysis['settlements_with_custom'] / analysis['total_settlements'] * 100)
                if analysis['total_settlements'] > 0 else 0
            ),
        },
        "categories": {
            category: {
                "total": float(total),
                "count": analysis['custom_category_counts'].get(category, 0),
                "description": extract_custom_description(category),
                "average": float(total / analysis['custom_category_counts'].get(category, 1)),
                "percentage": float(
                    (total / analysis['total_custom_expenses'] * 100)
                    if analysis['total_custom_expenses'] > 0 else 0
                ),
                "examples": analysis['custom_category_examples'].get(category, []),
            }
            for category, total in analysis['custom_category_totals'].items()
        },
        "by_truck": {
            truck: float(total) for truck, total in analysis['truck_custom_totals'].items()
        },
        "by_month": {
            month: float(total) for month, total in analysis['date_range_totals'].items()
        },
        "standard_categories": STANDARD_CATEGORIES,
    }
    
    with open(output_file, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
    
    print(f"\n✓ Analysis exported to: {output_file}")


def main():
    """Main function to run the analysis."""
    print("Connecting to database...")
    
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        print("Analyzing custom expenses...")
        print()
        
        analysis = analyze_custom_expenses(db)
        
        # Print report
        print_report(analysis)
        
        # Export to JSON
        output_file = BASE_DIR / "custom_expenses_analysis.json"
        export_to_json(analysis, str(output_file))
        
        print("\n✓ Analysis complete!")
        
    except Exception as e:
        print(f"\n✗ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


