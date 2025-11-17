#!/usr/bin/env python3
"""
Utility script to manually add/edit custom expense categories in settlement JSON files.
This is useful when deductions exist in the PDF but weren't captured by the parser.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List


def load_json_file(file_path: str) -> Dict:
    """Load JSON file and return parsed data"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(file_path: str, data: Dict):
    """Save data to JSON file with proper formatting"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_custom_expense_to_settlement(settlement: Dict, amount: float, category_name: str = "custom"):
    """
    Add a custom expense to a settlement and recalculate totals.
    
    Args:
        settlement: Settlement dictionary
        amount: Amount to add (positive for expenses, negative for credits)
        category_name: Category name (default: "custom")
    """
    # Ensure expense categories exist
    if "expenses" not in settlement:
        settlement["expenses"] = {"total_expenses": 0.0, "categories": {}}
    
    if "categories" not in settlement["expenses"]:
        settlement["expenses"]["categories"] = {}
    
    # Add or update the custom category
    current_custom = settlement["expenses"]["categories"].get(category_name, 0.0)
    settlement["expenses"]["categories"][category_name] = current_custom + amount
    
    # Recalculate total expenses
    total_expenses = sum(settlement["expenses"]["categories"].values())
    settlement["expenses"]["total_expenses"] = total_expenses
    
    # Recalculate net profit
    if "revenue" in settlement:
        gross_revenue = settlement["revenue"].get("gross_revenue", 0.0)
        settlement["revenue"]["net_profit"] = gross_revenue - total_expenses


def find_settlement_by_plate(data: Dict, license_plate: str) -> List[Dict]:
    """Find all settlements matching a license plate"""
    settlements = []
    
    if "settlements" in data:
        for settlement in data["settlements"]:
            if settlement.get("metadata", {}).get("license_plate") == license_plate:
                settlements.append(settlement)
    
    return settlements


def find_settlement_by_date(data: Dict, settlement_date: str) -> List[Dict]:
    """Find all settlements matching a settlement date"""
    settlements = []
    
    if "settlements" in data:
        for settlement in data["settlements"]:
            if settlement.get("metadata", {}).get("settlement_date") == settlement_date:
                settlements.append(settlement)
    
    return settlements


def add_custom_to_all_settlements_in_pdf(data: Dict, amount: float, category_name: str = "custom"):
    """
    Add custom expense to all settlements in a PDF (useful for multi-truck settlements).
    Applies to the first settlement only (as per parser logic).
    """
    if "settlements" not in data or not data["settlements"]:
        print("No settlements found in data")
        return
    
    # Apply to first settlement only (as per parser logic)
    add_custom_expense_to_settlement(data["settlements"][0], amount, category_name)
    print(f"Added ${amount:,.2f} to '{category_name}' category for first settlement")


def interactive_edit(file_path: str):
    """Interactive mode to edit JSON file"""
    print(f"\nEditing: {file_path}")
    data = load_json_file(file_path)
    
    if "settlements" not in data:
        print("Error: File doesn't contain settlements array")
        return
    
    print(f"\nFound {len(data['settlements'])} settlement(s)")
    
    # Show first few settlements for reference
    print("\nFirst few settlements:")
    for i, settlement in enumerate(data["settlements"][:3]):
        metadata = settlement.get("metadata", {})
        plate = metadata.get("license_plate", "N/A")
        date = metadata.get("settlement_date", "N/A")
        net_profit = settlement.get("revenue", {}).get("net_profit", 0)
        print(f"  {i+1}. Plate: {plate}, Date: {date}, Net Profit: ${net_profit:,.2f}")
    
    print("\nOptions:")
    print("1. Add custom expense to first settlement (for multi-truck PDFs)")
    print("2. Add custom expense to specific settlement by index")
    print("3. Add custom expense to all settlements with matching date")
    print("4. Exit without saving")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        amount = float(input("Enter amount (positive for expense, negative for credit): "))
        category = input("Enter category name (default: 'custom'): ").strip() or "custom"
        add_custom_to_all_settlements_in_pdf(data, amount, category)
        save_json_file(file_path, data)
        print("✓ Saved!")
    
    elif choice == "2":
        index = int(input(f"Enter settlement index (0-{len(data['settlements'])-1}): "))
        if 0 <= index < len(data["settlements"]):
            amount = float(input("Enter amount (positive for expense, negative for credit): "))
            category = input("Enter category name (default: 'custom'): ").strip() or "custom"
            add_custom_expense_to_settlement(data["settlements"][index], amount, category)
            save_json_file(file_path, data)
            print("✓ Saved!")
        else:
            print("Invalid index")
    
    elif choice == "3":
        date = input("Enter settlement date (YYYY-MM-DD): ").strip()
        settlements = find_settlement_by_date(data, date)
        if settlements:
            amount = float(input("Enter amount (positive for expense, negative for credit): "))
            category = input("Enter category name (default: 'custom'): ").strip() or "custom"
            for settlement in settlements:
                add_custom_expense_to_settlement(settlement, amount, category)
            save_json_file(file_path, data)
            print(f"✓ Updated {len(settlements)} settlement(s)!")
        else:
            print(f"No settlements found with date {date}")
    
    elif choice == "4":
        print("Exiting without saving")
    else:
        print("Invalid choice")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python edit_settlement_json.py <json_file> [amount] [category]")
        print("\nExamples:")
        print("  python edit_settlement_json.py settlements_consolidated.json")
        print("  python edit_settlement_json.py settlements_consolidated.json 150.50")
        print("  python edit_settlement_json.py settlements_consolidated.json 150.50 'deduction'")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    # If amount provided, non-interactive mode
    if len(sys.argv) >= 3:
        amount = float(sys.argv[2])
        category = sys.argv[3] if len(sys.argv) >= 4 else "custom"
        
        data = load_json_file(file_path)
        add_custom_to_all_settlements_in_pdf(data, amount, category)
        save_json_file(file_path, data)
        print(f"✓ Added ${amount:,.2f} to '{category}' category and saved!")
    else:
        # Interactive mode
        interactive_edit(file_path)


if __name__ == "__main__":
    main()

