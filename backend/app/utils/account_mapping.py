"""
Account mapping utility - maps operational categories to chart of accounts
"""
from typing import Dict, Optional

# Mapping of operational expense categories to account codes
# These codes will be used to find/create accounts in the chart of accounts
EXPENSE_CATEGORY_TO_ACCOUNT_CODE: Dict[str, str] = {
    "fuel": "6001",  # Fuel Expense
    "dispatch_fee": "6002",  # Dispatch Fee Expense
    "tolls": "6013",  # Tolls Expense
    "insurance": "6003",  # Insurance Expense
    "safety": "6004",  # Safety Expense
    "prepass": "6005",  # Prepass Expense
    "ifta": "6006",  # IFTA Expense
    "driver_pay": "6007",  # Driver Pay Expense
    "payroll_fee": "6008",  # Payroll Fee Expense
    "loan_interest": "6009",  # Interest Expense
    "truck_parking": "6010",  # Parking Expense
    "service_on_truck": "6011",  # Maintenance Expense
    "repairs": "6011",  # Maintenance Expense (same as service_on_truck)
    "custom": "6099",  # Other Operating Expense
    "decals": "6012",  # Decals Expense
    "deduct": "6099",  # Other Operating Expense (deductions)
}

# Revenue account code
REVENUE_ACCOUNT_CODE = "4000"  # Operating Revenue

# Asset account codes
CASH_ACCOUNT_CODE = "1000"  # Cash
ACCOUNTS_RECEIVABLE_CODE = "1100"  # Accounts Receivable
VEHICLES_ASSET_CODE = "1500"  # Vehicles (Trucks/Trailers)
ACCUMULATED_DEPRECIATION_CODE = "1501"  # Accumulated Depreciation - Vehicles

# Liability account codes
ACCOUNTS_PAYABLE_CODE = "2000"  # Accounts Payable
LOANS_PAYABLE_CODE = "2100"  # Loans Payable
ACCRUED_EXPENSES_CODE = "2200"  # Accrued Expenses

# Equity account codes
OWNER_EQUITY_CODE = "3000"  # Owner Equity
RETAINED_EARNINGS_CODE = "3100"  # Retained Earnings

def get_account_code_for_expense_category(category: str) -> str:
    """
    Get the account code for an expense category.
    Returns the account code, or 6099 (Other Operating Expense) if not found.
    """
    return EXPENSE_CATEGORY_TO_ACCOUNT_CODE.get(category, "6099")

def get_revenue_account_code() -> str:
    """Get the account code for revenue."""
    return REVENUE_ACCOUNT_CODE

def get_cash_account_code() -> str:
    """Get the account code for cash."""
    return CASH_ACCOUNT_CODE

def get_accounts_receivable_code() -> str:
    """Get the account code for accounts receivable."""
    return ACCOUNTS_RECEIVABLE_CODE

def get_vehicles_asset_code() -> str:
    """Get the account code for vehicles asset."""
    return VEHICLES_ASSET_CODE

def get_loans_payable_code() -> str:
    """Get the account code for loans payable."""
    return LOANS_PAYABLE_CODE

def get_retained_earnings_code() -> str:
    """Get the account code for retained earnings."""
    return RETAINED_EARNINGS_CODE
