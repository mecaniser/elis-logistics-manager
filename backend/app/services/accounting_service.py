"""
Accounting service - handles journal entry creation and financial calculations
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime
from decimal import Decimal

from app.models.chart_of_accounts import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from app.models.settlement import Settlement
from app.models.repair import Repair
from app.models.truck import Truck
from app.models.tenant import Tenant
from app.utils.account_mapping import (
    get_account_code_for_expense_category,
    get_revenue_account_code,
    get_cash_account_code,
    get_accounts_receivable_code,
    get_loans_payable_code,
    get_retained_earnings_code,
)


def uses_per_asset_accounting(tenant: Tenant) -> bool:
    """
    Check if tenant uses per-asset accounting (LS Logistics).
    For LS Logistics, each truck/trailer has its own chart of accounts.
    """
    return tenant.name.lower() == "ls logistics"


def get_or_create_account(db: Session, code: str, name: str, account_type: str, tenant_id: int, parent_id: Optional[int] = None, truck_id: Optional[int] = None) -> ChartOfAccount:
    """
    Get an account by code for a tenant (and truck if per-asset accounting), or create it if it doesn't exist.
    """
    query = db.query(ChartOfAccount).filter(
        ChartOfAccount.code == code,
        ChartOfAccount.tenant_id == tenant_id
    )
    
    # For per-asset accounting, also filter by truck_id
    if truck_id is not None:
        query = query.filter(ChartOfAccount.truck_id == truck_id)
    else:
        query = query.filter(ChartOfAccount.truck_id.is_(None))
    
    account = query.first()
    if not account:
        account = ChartOfAccount(
            code=code,
            name=name,
            account_type=account_type,
            tenant_id=tenant_id,
            parent_id=parent_id,
            truck_id=truck_id,
            is_active=True
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def ensure_standard_accounts_exist(db: Session, tenant_id: int, truck_id: Optional[int] = None):
    """
    Ensure all standard chart of accounts exist for a tenant based on business type.
    For LS Logistics with truck_id, creates accounts per truck/trailer.
    Called during initialization or migration.
    """
    # Get tenant to determine business type
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")
    
    business_type = tenant.business_type or 'logistics'
    per_asset = uses_per_asset_accounting(tenant)
    
    # For LS Logistics, if truck_id is None, create accounts for all trucks/trailers
    if per_asset and truck_id is None:
        trucks = db.query(Truck).filter(Truck.tenant_id == tenant_id).all()
        for truck in trucks:
            ensure_standard_accounts_exist(db, tenant_id, truck.id)
        return
    
    # Common accounts for all business types
    # Assets
    get_or_create_account(db, "1000", "Cash", "Asset", tenant_id, truck_id=truck_id)
    get_or_create_account(db, "1100", "Accounts Receivable", "Asset", tenant_id, truck_id=truck_id)
    
    # Liabilities
    get_or_create_account(db, "2000", "Accounts Payable", "Liability", tenant_id, truck_id=truck_id)
    get_or_create_account(db, "2100", "Loans Payable", "Liability", tenant_id, truck_id=truck_id)
    get_or_create_account(db, "2200", "Accrued Expenses", "Liability", tenant_id, truck_id=truck_id)
    
    # Equity
    get_or_create_account(db, "3000", "Owner Equity", "Equity", tenant_id, truck_id=truck_id)
    get_or_create_account(db, "3100", "Retained Earnings", "Equity", tenant_id, truck_id=truck_id)
    
    # Revenue
    get_or_create_account(db, "4000", "Operating Revenue", "Revenue", tenant_id, truck_id=truck_id)
    
    # Business-type-specific accounts
    if business_type == 'logistics':
        # Logistics-specific assets
        get_or_create_account(db, "1500", "Vehicles", "Asset", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "1501", "Accumulated Depreciation - Vehicles", "Asset", tenant_id, truck_id=truck_id)
        
        # Logistics-specific expenses
        get_or_create_account(db, "6001", "Fuel Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6002", "Dispatch Fee Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6003", "Insurance Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6004", "Safety Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6005", "Prepass Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6006", "IFTA Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6007", "Driver Pay Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6008", "Payroll Fee Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6009", "Interest Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6010", "Parking Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6011", "Maintenance Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6012", "Decals Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6099", "Other Operating Expense", "Expense", tenant_id, truck_id=truck_id)
    
    elif business_type == 'tech':
        # Tech-specific assets
        get_or_create_account(db, "1500", "Equipment", "Asset", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "1501", "Accumulated Depreciation - Equipment", "Asset", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "1600", "Software Licenses", "Asset", tenant_id, truck_id=truck_id)
        
        # Tech-specific expenses
        get_or_create_account(db, "6001", "Software & Subscriptions Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6002", "Cloud Services Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6003", "Insurance Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6004", "Professional Services Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6005", "Equipment Maintenance Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6006", "Marketing & Advertising Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6007", "Salaries & Wages Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6008", "Payroll Tax Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6009", "Interest Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6010", "Office Rent Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6011", "Utilities Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6012", "Travel & Entertainment Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6099", "Other Operating Expense", "Expense", tenant_id, truck_id=truck_id)
    
    elif business_type == 'real_estate':
        # Real Estate-specific assets
        get_or_create_account(db, "1500", "Properties", "Asset", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "1501", "Accumulated Depreciation - Properties", "Asset", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "1600", "Furniture & Fixtures", "Asset", tenant_id, truck_id=truck_id)
        
        # Real Estate-specific expenses
        get_or_create_account(db, "6001", "Property Maintenance Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6002", "Property Management Fee Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6003", "Property Insurance Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6004", "Property Tax Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6005", "Utilities Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6006", "HOA Fees Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6007", "Cleaning & Turnover Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6008", "Legal & Professional Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6009", "Interest Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6010", "Marketing & Advertising Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6011", "Repairs & Improvements Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6012", "Supplies Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6099", "Other Operating Expense", "Expense", tenant_id, truck_id=truck_id)
    
    else:
        # Generic/Other business type - minimal accounts
        get_or_create_account(db, "1500", "Fixed Assets", "Asset", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "1501", "Accumulated Depreciation", "Asset", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6001", "Cost of Goods Sold", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6002", "Operating Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6003", "Insurance Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6009", "Interest Expense", "Expense", tenant_id, truck_id=truck_id)
        get_or_create_account(db, "6099", "Other Operating Expense", "Expense", tenant_id, truck_id=truck_id)


def validate_journal_entry_lines(lines: List[Dict]) -> Tuple[bool, str]:
    """
    Validate that journal entry lines balance (total debits = total credits).
    Returns (is_valid, error_message)
    """
    total_debits = sum(float(line.get("debit", 0) or 0) for line in lines)
    total_credits = sum(float(line.get("credit", 0) or 0) for line in lines)
    
    if abs(total_debits - total_credits) > 0.01:  # Allow small rounding differences
        return False, f"Journal entry does not balance: Debits ${total_debits:.2f} != Credits ${total_credits:.2f}"
    
    return True, ""


def create_settlement_journal_entry(db: Session, settlement: Settlement) -> Optional[JournalEntry]:
    """
    Create a journal entry for a settlement.
    Settlement entries:
    - Debit: Accounts Receivable (or Cash if received)
    - Credit: Operating Revenue
    - Debit: Various Expense accounts
    - Credit: Accounts Payable (or Cash if paid)
    """
    # Get truck to get tenant_id
    truck = db.query(Truck).filter(Truck.id == settlement.truck_id).first()
    if not truck:
        return None  # Truck not found
    
    tenant_id = truck.tenant_id
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return None
    
    per_asset = uses_per_asset_accounting(tenant)
    truck_id_for_accounting = settlement.truck_id if per_asset else None
    
    # Check if journal entry already exists for this settlement
    existing_query = db.query(JournalEntry).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.reference_type == "settlement",
        JournalEntry.reference_id == settlement.id
    )
    if per_asset:
        existing_query = existing_query.filter(JournalEntry.truck_id == settlement.truck_id)
    else:
        existing_query = existing_query.filter(JournalEntry.truck_id.is_(None))
    
    existing = existing_query.first()
    if existing:
        return existing  # Already created
    
    # Ensure accounts exist (per-asset for LS Logistics)
    ensure_standard_accounts_exist(db, tenant_id, truck_id_for_accounting)
    
    # Get accounts (per-asset for LS Logistics)
    revenue_account = get_or_create_account(db, get_revenue_account_code(), "Operating Revenue", "Revenue", tenant_id, truck_id=truck_id_for_accounting)
    ar_account = get_or_create_account(db, get_accounts_receivable_code(), "Accounts Receivable", "Asset", tenant_id, truck_id=truck_id_for_accounting)
    
    entry_date = settlement.settlement_date or settlement.created_at.date() if settlement.created_at else date.today()
    
    # Create journal entry (with truck_id for LS Logistics)
    journal_entry = JournalEntry(
        tenant_id=tenant_id,
        truck_id=truck_id_for_accounting,
        entry_date=entry_date,
        reference_type="settlement",
        reference_id=settlement.id,
        description=f"Settlement for truck {settlement.truck_id} on {entry_date}"
    )
    db.add(journal_entry)
    db.flush()  # Get the ID
    
    lines = []
    
    # Revenue side: Debit AR, Credit Revenue
    gross_revenue = float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
    if gross_revenue > 0:
        lines.append({
            "journal_entry_id": journal_entry.id,
            "account_id": ar_account.id,
            "debit": gross_revenue,
            "credit": 0,
            "description": "Settlement revenue",
            "truck_id": settlement.truck_id
        })
        lines.append({
            "journal_entry_id": journal_entry.id,
            "account_id": revenue_account.id,
            "debit": 0,
            "credit": gross_revenue,
            "description": "Operating revenue",
            "truck_id": settlement.truck_id
        })
    
    # Expense side: Debit Expense accounts, Credit AR (or Cash)
    if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
        for category, amount in settlement.expense_categories.items():
            # Skip reimbursements - they're credits, handled separately
            if category == "reimbursement":
                continue
            
            amount_float = float(amount) if amount else 0.0
            if amount_float > 0:
                account_code = get_account_code_for_expense_category(category)
                expense_account = get_or_create_account(
                    db, 
                    account_code,
                    f"{category.replace('_', ' ').title()} Expense",
                    "Expense",
                    tenant_id,
                    truck_id=truck_id_for_accounting
                )
                
                lines.append({
                    "journal_entry_id": journal_entry.id,
                    "account_id": expense_account.id,
                    "debit": amount_float,
                    "credit": 0,
                    "description": f"{category} expense",
                    "truck_id": settlement.truck_id
                })
                lines.append({
                    "journal_entry_id": journal_entry.id,
                    "account_id": ar_account.id,
                    "debit": 0,
                    "credit": amount_float,
                    "description": f"Payment for {category}",
                    "truck_id": settlement.truck_id
                })
    
    # Handle reimbursements (credits that reduce expenses)
    if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
        reimbursement = settlement.expense_categories.get("reimbursement", 0)
        if reimbursement:
            reimbursement_float = float(reimbursement)
            # Reimbursement: Debit AR, Credit Expense (reduces expense)
            lines.append({
                "journal_entry_id": journal_entry.id,
                "account_id": ar_account.id,
                "debit": reimbursement_float,
                "credit": 0,
                "description": "Reimbursement received",
                "truck_id": settlement.truck_id
            })
            # Credit to a reimbursement income account or reduce expenses
            reimbursement_account = get_or_create_account(db, "4100", "Reimbursement Income", "Revenue", tenant_id, truck_id=truck_id_for_accounting)
            lines.append({
                "journal_entry_id": journal_entry.id,
                "account_id": reimbursement_account.id,
                "debit": 0,
                "credit": reimbursement_float,
                "description": "Reimbursement income",
                "truck_id": settlement.truck_id
            })
    
    # Validate entry balances
    is_valid, error_msg = validate_journal_entry_lines(lines)
    if not is_valid:
        db.rollback()
        raise ValueError(f"Invalid journal entry: {error_msg}")
    
    # Create lines
    for line_data in lines:
        line = JournalEntryLine(**line_data)
        db.add(line)
    
    db.commit()
    db.refresh(journal_entry)
    return journal_entry


def create_repair_journal_entry(db: Session, repair: Repair) -> Optional[JournalEntry]:
    """
    Create a journal entry for a repair expense.
    Repair entries:
    - Debit: Maintenance Expense
    - Credit: Cash (or Accounts Payable if not paid)
    """
    # Get truck to get tenant_id
    truck = db.query(Truck).filter(Truck.id == repair.truck_id).first()
    if not truck:
        return None  # Truck not found
    
    tenant_id = truck.tenant_id
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return None
    
    per_asset = uses_per_asset_accounting(tenant)
    truck_id_for_accounting = repair.truck_id if per_asset else None
    
    # Check if journal entry already exists for this repair
    existing_query = db.query(JournalEntry).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.reference_type == "repair",
        JournalEntry.reference_id == repair.id
    )
    if per_asset:
        existing_query = existing_query.filter(JournalEntry.truck_id == repair.truck_id)
    else:
        existing_query = existing_query.filter(JournalEntry.truck_id.is_(None))
    
    existing = existing_query.first()
    if existing:
        return existing  # Already created
    
    if not repair.cost or float(repair.cost) <= 0:
        return None  # No cost, no entry
    
    # Ensure accounts exist (per-asset for LS Logistics)
    ensure_standard_accounts_exist(db, tenant_id, truck_id_for_accounting)
    
    # Get accounts (per-asset for LS Logistics)
    maintenance_account = get_or_create_account(db, "6011", "Maintenance Expense", "Expense", tenant_id, truck_id=truck_id_for_accounting)
    cash_account = get_or_create_account(db, get_cash_account_code(), "Cash", "Asset", tenant_id, truck_id=truck_id_for_accounting)
    
    entry_date = repair.repair_date or (repair.created_at.date() if repair.created_at else date.today())
    
    # Create journal entry (with truck_id for LS Logistics)
    journal_entry = JournalEntry(
        tenant_id=tenant_id,
        truck_id=truck_id_for_accounting,
        entry_date=entry_date,
        reference_type="repair",
        reference_id=repair.id,
        description=f"Repair for truck {repair.truck_id}: {repair.description or 'No description'}"
    )
    db.add(journal_entry)
    db.flush()  # Get the ID
    
    cost = float(repair.cost)
    
    # Debit Maintenance Expense, Credit Cash
    lines = [
        {
            "journal_entry_id": journal_entry.id,
            "account_id": maintenance_account.id,
            "debit": cost,
            "credit": 0,
            "description": repair.description or "Repair expense",
            "truck_id": repair.truck_id
        },
        {
            "journal_entry_id": journal_entry.id,
            "account_id": cash_account.id,
            "debit": 0,
            "credit": cost,
            "description": "Payment for repair",
            "truck_id": repair.truck_id
        }
    ]
    
    # Validate entry balances
    is_valid, error_msg = validate_journal_entry_lines(lines)
    if not is_valid:
        db.rollback()
        raise ValueError(f"Invalid journal entry: {error_msg}")
    
    # Create lines
    for line_data in lines:
        line = JournalEntryLine(**line_data)
        db.add(line)
    
    db.commit()
    db.refresh(journal_entry)
    return journal_entry


def delete_settlement_journal_entry(db: Session, settlement_id: int):
    """Delete journal entry for a settlement."""
    journal_entry = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "settlement",
        JournalEntry.reference_id == settlement_id
    ).first()
    
    if journal_entry:
        db.delete(journal_entry)
        db.commit()


def delete_repair_journal_entry(db: Session, repair_id: int):
    """Delete journal entry for a repair."""
    journal_entry = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "repair",
        JournalEntry.reference_id == repair_id
    ).first()
    
    if journal_entry:
        db.delete(journal_entry)
        db.commit()


def calculate_account_balance(db: Session, account_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None, truck_id: Optional[int] = None) -> Decimal:
    """
    Calculate account balance (debits - credits for assets/expenses, credits - debits for liabilities/equity/revenue).
    For per-asset accounts, filters by account's truck_id and journal entry's truck_id.
    Optionally filter by truck_id on journal entry lines for operational tracking.
    """
    account = db.query(ChartOfAccount).filter(ChartOfAccount.id == account_id).first()
    if not account:
        return Decimal(0)
    
    # Build query with date and truck filtering
    total_debits = db.query(func.sum(JournalEntryLine.debit)).join(JournalEntry).filter(
        JournalEntryLine.account_id == account_id
    )
    total_credits = db.query(func.sum(JournalEntryLine.credit)).join(JournalEntry).filter(
        JournalEntryLine.account_id == account_id
    )
    
    # For per-asset accounts, filter by journal entry's truck_id matching account's truck_id
    if account.truck_id is not None:
        total_debits = total_debits.filter(JournalEntry.truck_id == account.truck_id)
        total_credits = total_credits.filter(JournalEntry.truck_id == account.truck_id)
    else:
        # For shared accounts, only include entries without truck_id
        total_debits = total_debits.filter(JournalEntry.truck_id.is_(None))
        total_credits = total_credits.filter(JournalEntry.truck_id.is_(None))
    
    if start_date:
        total_debits = total_debits.filter(JournalEntry.entry_date >= start_date)
        total_credits = total_credits.filter(JournalEntry.entry_date >= start_date)
    if end_date:
        total_debits = total_debits.filter(JournalEntry.entry_date <= end_date)
        total_credits = total_credits.filter(JournalEntry.entry_date <= end_date)
    if truck_id:
        # Additional filter on journal entry lines for operational tracking
        total_debits = total_debits.filter(JournalEntryLine.truck_id == truck_id)
        total_credits = total_credits.filter(JournalEntryLine.truck_id == truck_id)
    
    debits = total_debits.scalar() or Decimal(0)
    credits = total_credits.scalar() or Decimal(0)
    
    # For assets and expenses: balance = debits - credits
    # For liabilities, equity, and revenue: balance = credits - debits
    if account.account_type in ["Asset", "Expense"]:
        return debits - credits
    else:
        return credits - debits


def generate_balance_sheet(db: Session, tenant_id: int, as_of_date: Optional[date] = None, truck_id: Optional[int] = None) -> Dict:
    """
    Generate balance sheet as of a specific date for a specific tenant.
    For LS Logistics, truck_id is required for per-asset accounting.
    """
    if not as_of_date:
        as_of_date = date.today()
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")
    
    per_asset = uses_per_asset_accounting(tenant)
    # For LS Logistics (per-asset), truck_id is required
    # For other logistics businesses, truck_id is optional (if provided, shows per-vehicle; if not, shows total)
    if per_asset and truck_id is None:
        raise ValueError("truck_id is required for LS Logistics balance sheet")
    
    # Determine the truck_id to use for account creation/querying
    # For per-asset accounting, we MUST use truck_id
    # For non-per-asset logistics with truck_id, we use shared accounts (truck_id=None) but filter data by truck_id
    account_truck_id = truck_id if per_asset else None
    
    ensure_standard_accounts_exist(db, tenant_id, account_truck_id)
    
    # Build account query filter
    account_filter = [ChartOfAccount.tenant_id == tenant_id]
    if per_asset:
        # Per-asset accounting: must filter by truck_id
        account_filter.append(ChartOfAccount.truck_id == truck_id)
    else:
        # Non-per-asset: always use shared accounts (truck_id is NULL)
        account_filter.append(ChartOfAccount.truck_id.is_(None))
    
    # Assets
    cash_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_cash_account_code()).first()
    ar_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_accounts_receivable_code()).first()
    fixed_assets_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == "1500").first()
    acc_dep_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == "1501").first()
    
    # If accounts don't exist, try to create them
    if not cash_account or not ar_account or (tenant.business_type == 'logistics' and (not fixed_assets_account or not acc_dep_account)):
        ensure_standard_accounts_exist(db, tenant_id, truck_id)
        db.commit()  # Ensure accounts are committed before querying
        cash_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_cash_account_code()).first()
        ar_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_accounts_receivable_code()).first()
        if tenant.business_type == 'logistics':
            fixed_assets_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == "1500").first()
            acc_dep_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == "1501").first()
    
    cash_balance = calculate_account_balance(db, cash_account.id, end_date=as_of_date) if cash_account else Decimal(0)
    ar_balance = calculate_account_balance(db, ar_account.id, end_date=as_of_date) if ar_account else Decimal(0)
    
    # Fixed assets: for per-asset accounting or logistics with truck_id, use specific truck's total_cost; 
    # for logistics without truck_id, sum all trucks; otherwise use account balance
    fixed_assets_balance = Decimal(0)
    if (per_asset and truck_id) or (tenant.business_type == 'logistics' and truck_id):
        # Per-vehicle view: use specific truck's cost
        truck = db.query(Truck).filter(Truck.id == truck_id, Truck.tenant_id == tenant_id).first()
        if truck and truck.total_cost:
            fixed_assets_balance = Decimal(str(truck.total_cost))
    elif tenant.business_type == 'logistics':
        # Logistics total view: sum all trucks
        trucks = db.query(Truck).filter(Truck.tenant_id == tenant_id).all()
        for truck in trucks:
            if truck.total_cost:
                fixed_assets_balance += Decimal(str(truck.total_cost))
    else:
        # Non-logistics: use account balance
        fixed_assets_balance = calculate_account_balance(db, fixed_assets_account.id, end_date=as_of_date) if fixed_assets_account else Decimal(0)
    
    # Calculate accumulated depreciation
    # First try to get from journal entries (if depreciation entries exist)
    acc_dep_balance = calculate_account_balance(db, acc_dep_account.id, end_date=as_of_date) if acc_dep_account else Decimal(0)
    
    # If no journal entries exist and we have truck data, calculate from depreciation service
    if acc_dep_balance == 0 and tenant.business_type == 'logistics':
        try:
            from app.services.depreciation_service import calculate_depreciation_for_truck
            
            if per_asset and truck_id:
                # Per-vehicle view: calculate depreciation for specific truck
                truck = db.query(Truck).filter(Truck.id == truck_id, Truck.tenant_id == tenant_id).first()
                if truck:
                    calculated_dep = calculate_depreciation_for_truck(truck, as_of_date)
                    if calculated_dep:
                        acc_dep_balance = calculated_dep
            elif tenant.business_type == 'logistics':
                # Total view: sum depreciation for all trucks
                trucks = db.query(Truck).filter(Truck.tenant_id == tenant_id).all()
                total_depreciation = Decimal(0)
                for truck in trucks:
                    if truck.purchase_date and truck.total_cost:
                        calculated_dep = calculate_depreciation_for_truck(truck, as_of_date)
                        if calculated_dep:
                            total_depreciation += calculated_dep
                if total_depreciation > 0:
                    acc_dep_balance = total_depreciation
        except Exception as e:
            # If depreciation calculation fails, log error but continue with 0 depreciation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to calculate depreciation: {str(e)}")
            # Continue with acc_dep_balance = 0 (already set above)
    net_fixed_assets = fixed_assets_balance - acc_dep_balance
    
    # Ensure all values are valid Decimals before converting to float
    fixed_assets_balance = fixed_assets_balance or Decimal(0)
    acc_dep_balance = acc_dep_balance or Decimal(0)
    net_fixed_assets = net_fixed_assets or Decimal(0)
    
    total_assets = cash_balance + ar_balance + net_fixed_assets
    
    # Liabilities
    ap_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == "2000").first()
    loans_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_loans_payable_code()).first()
    
    # If liability accounts don't exist, try to create them
    if not ap_account or not loans_account:
        ensure_standard_accounts_exist(db, tenant_id, account_truck_id)
        db.commit()  # Ensure accounts are committed before querying
        ap_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == "2000").first()
        loans_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_loans_payable_code()).first()
    
    ap_balance = calculate_account_balance(db, ap_account.id, end_date=as_of_date) if ap_account else Decimal(0)
    
    # Loans: for per-asset accounting or logistics with truck_id, use specific truck's loan balance;
    # for logistics without truck_id, sum all trucks; otherwise use account balance
    loans_balance = Decimal(0)
    if (per_asset and truck_id) or (tenant.business_type == 'logistics' and truck_id):
        # Per-vehicle view: use specific truck's loan balance
        truck = db.query(Truck).filter(Truck.id == truck_id, Truck.tenant_id == tenant_id).first()
        if truck:
            if truck.current_loan_balance:
                loans_balance = Decimal(str(truck.current_loan_balance))
            elif truck.loan_amount and truck.vehicle_type == 'truck':
                loans_balance = Decimal(str(truck.loan_amount))
    elif tenant.business_type == 'logistics':
        # Logistics total view: sum all trucks
        trucks = db.query(Truck).filter(Truck.tenant_id == tenant_id).all()
        for truck in trucks:
            if truck.current_loan_balance:
                loans_balance += Decimal(str(truck.current_loan_balance))
            elif truck.loan_amount and truck.vehicle_type == 'truck':
                loans_balance += Decimal(str(truck.loan_amount))
    else:
        # Non-logistics: use account balance
        loans_balance = calculate_account_balance(db, loans_account.id, end_date=as_of_date) if loans_account else Decimal(0)
    
    total_liabilities = ap_balance + loans_balance
    
    # Equity
    owner_equity_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == "3000").first()
    retained_earnings_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_retained_earnings_code()).first()
    
    # If equity accounts don't exist, try to create them
    if not owner_equity_account or not retained_earnings_account:
        ensure_standard_accounts_exist(db, tenant_id, account_truck_id)
        db.commit()  # Ensure accounts are committed before querying
        owner_equity_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == "3000").first()
        retained_earnings_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_retained_earnings_code()).first()
    
    owner_equity_balance = calculate_account_balance(db, owner_equity_account.id, end_date=as_of_date) if owner_equity_account else Decimal(0)
    
    # Retained earnings: for per-asset accounting, calculate from journal entries for this truck; otherwise from all trucks or account balance
    retained_earnings = Decimal(0)
    if per_asset and truck_id:
        # Calculate from journal entries for this specific truck
        retained_earnings = calculate_account_balance(db, retained_earnings_account.id, end_date=as_of_date) if retained_earnings_account else Decimal(0)
    elif tenant.business_type == 'logistics':
        # Calculate from settlements/repairs (filtered by truck_id if provided)
        settlement_query = db.query(Settlement).join(Truck).filter(
            Truck.tenant_id == tenant_id,
            Settlement.settlement_date <= as_of_date
        )
        repair_query = db.query(Repair).join(Truck).filter(
            Truck.tenant_id == tenant_id,
            Repair.repair_date <= as_of_date
        )
        if truck_id:
            settlement_query = settlement_query.filter(Settlement.truck_id == truck_id)
            repair_query = repair_query.filter(Repair.truck_id == truck_id)
        
        settlements = settlement_query.all()
        repairs = repair_query.all()
        
        total_revenue = sum(float(s.gross_revenue) if s.gross_revenue else 0 for s in settlements)
        total_expenses = sum(float(s.expenses) if s.expenses else 0 for s in settlements)
        total_repairs = sum(float(r.cost) if r.cost else 0 for r in repairs)
        
        retained_earnings = Decimal(str(total_revenue - total_expenses - total_repairs))
    else:
        # For non-logistics, calculate from retained earnings account
        retained_earnings = calculate_account_balance(db, retained_earnings_account.id, end_date=as_of_date) if retained_earnings_account else Decimal(0)
    
    total_equity = owner_equity_balance + retained_earnings
    total_liabilities_and_equity = total_liabilities + total_equity
    
    # Convert to float, ensuring no NaN values
    def safe_float(value):
        try:
            result = float(value or 0)
            return result if not (result != result) else 0.0  # Check for NaN
        except (TypeError, ValueError):
            return 0.0
    
    return {
        "as_of_date": as_of_date.isoformat(),
        "assets": {
            "cash": safe_float(cash_balance),
            "accounts_receivable": safe_float(ar_balance),
            "vehicles": safe_float(fixed_assets_balance),
            "accumulated_depreciation": safe_float(acc_dep_balance),
            "net_vehicles": safe_float(net_fixed_assets),
            "total": safe_float(total_assets)
        },
        "liabilities": {
            "accounts_payable": safe_float(ap_balance),
            "loans_payable": safe_float(loans_balance),
            "total": safe_float(total_liabilities)
        },
        "equity": {
            "owner_equity": safe_float(owner_equity_balance),
            "retained_earnings": safe_float(retained_earnings),
            "total": safe_float(total_equity)
        },
        "total_liabilities_and_equity": safe_float(total_liabilities_and_equity)
    }


def generate_income_statement(db: Session, tenant_id: int, start_date: date, end_date: date, truck_id: Optional[int] = None) -> Dict:
    """
    Generate income statement for a date range for a specific tenant.
    For LS Logistics, truck_id is required for per-asset accounting.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")
    
    per_asset = uses_per_asset_accounting(tenant)
    if per_asset and truck_id is None:
        raise ValueError("truck_id is required for LS Logistics income statement")
    
    ensure_standard_accounts_exist(db, tenant_id, truck_id)
    
    # Build account query filter
    account_filter = [
        ChartOfAccount.tenant_id == tenant_id
    ]
    if per_asset:
        if truck_id is None:
            raise ValueError("truck_id cannot be None for per-asset accounting")
        account_filter.append(ChartOfAccount.truck_id == truck_id)
    else:
        account_filter.append(ChartOfAccount.truck_id.is_(None))
    
    # Revenue
    revenue_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_revenue_account_code()).first()
    if not revenue_account:
        # If account doesn't exist, try to create it again
        ensure_standard_accounts_exist(db, tenant_id, truck_id)
        revenue_account = db.query(ChartOfAccount).filter(*account_filter, ChartOfAccount.code == get_revenue_account_code()).first()
    
    revenue_balance = calculate_account_balance(db, revenue_account.id, start_date, end_date, truck_id) if revenue_account else Decimal(0)
    
    # Expenses by category
    expense_accounts = db.query(ChartOfAccount).filter(
        *account_filter,
        ChartOfAccount.account_type == "Expense"
    ).all()
    expenses_by_category = {}
    total_expenses = Decimal(0)
    
    for account in expense_accounts:
        balance = calculate_account_balance(db, account.id, start_date, end_date, truck_id)
        if balance > 0:
            expenses_by_category[account.name] = float(balance)
            total_expenses += balance
    
    net_income = revenue_balance - total_expenses
    
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "truck_id": truck_id,
        "revenue": {
            "operating_revenue": float(revenue_balance),
            "total": float(revenue_balance)
        },
        "expenses": expenses_by_category,
        "total_expenses": float(total_expenses),
        "net_income": float(net_income)
    }

