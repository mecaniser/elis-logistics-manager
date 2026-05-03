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


def _journal_entry_supports_soft_delete() -> bool:
    return hasattr(JournalEntry, "deleted_at")


def _filter_active_journal_entries(query):
    if _journal_entry_supports_soft_delete():
        return query.filter(JournalEntry.deleted_at.is_(None))
    return query


def _delete_or_soft_delete_journal_entry(db: Session, journal_entry: JournalEntry) -> None:
    # Settlement/repair journal entries are regenerated on update, so they must be
    # removed from the uniqueness key entirely instead of being soft-deleted.
    db.delete(journal_entry)


def uses_per_asset_accounting(tenant: Tenant) -> bool:
    """
    Check if tenant uses per-asset accounting (LS Logistics).
    For LS Logistics, each truck/trailer has its own chart of accounts.
    Elis Logistics LLC uses shared accounts (truck_id = NULL).
    """
    return tenant.name.lower() == "ls logistics" and tenant.name.lower() != "elis logistics llc"


def get_or_create_account(
    db: Session,
    code: str,
    name: str,
    account_type: str,
    tenant_id: int,
    parent_id: Optional[int] = None,
    truck_id: Optional[int] = None,
    auto_commit: bool = True,
) -> ChartOfAccount:
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
        if auto_commit:
            db.commit()
            db.refresh(account)
        else:
            db.flush()
    return account


def ensure_standard_accounts_exist(
    db: Session,
    tenant_id: int,
    truck_id: Optional[int] = None,
    auto_commit: bool = True,
):
    """
    Ensure all standard chart of accounts exist for a tenant based on business type.
    For LS Logistics with truck_id, creates accounts per truck/trailer.
    For Elis Logistics (non-per-asset), ensures minimal accounts exist.
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
    
    # For Elis Logistics (non-per-asset), ensure minimal accounts exist
    # This is called when creating journal entries, so we need to ensure accounts exist
    # but we don't want to create all the logistics accounts - just the ones that might be needed
    if not per_asset and business_type == 'logistics' and truck_id is None:
        # Ensure minimal accounts exist - these are the ones used by Elis Logistics
        get_or_create_account(db, "1000", "Cash", "Asset", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "4000", "Settlement Income", "Revenue", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "4100", "Trailer Rental Income", "Revenue", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "5100", "Maintenance & Repairs", "Expense", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "5200", "Trailer Expenses", "Expense", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "5300", "Interest Expense", "Expense", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "5400", "Depreciation Expense", "Expense", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "5500", "Section 179 Deduction", "Expense", tenant_id, truck_id=None, auto_commit=auto_commit)
        # Also ensure common accounts exist
        get_or_create_account(db, "1500", "Vehicles & Equipment", "Asset", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "1600", "Accumulated Depreciation - Vehicles", "Asset", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "2100", "Loans Payable", "Liability", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "3000", "Owner Equity", "Equity", tenant_id, truck_id=None, auto_commit=auto_commit)
        get_or_create_account(db, "3100", "Retained Earnings", "Equity", tenant_id, truck_id=None, auto_commit=auto_commit)
        return
    
    # Common accounts for all business types
    # Assets
    get_or_create_account(db, "1000", "Cash", "Asset", tenant_id, truck_id=truck_id, auto_commit=auto_commit)
    get_or_create_account(db, "1100", "Accounts Receivable", "Asset", tenant_id, truck_id=truck_id, auto_commit=auto_commit)
    
    # Liabilities
    get_or_create_account(db, "2000", "Accounts Payable", "Liability", tenant_id, truck_id=truck_id, auto_commit=auto_commit)
    get_or_create_account(db, "2100", "Loans Payable", "Liability", tenant_id, truck_id=truck_id, auto_commit=auto_commit)
    get_or_create_account(db, "2200", "Accrued Expenses", "Liability", tenant_id, truck_id=truck_id, auto_commit=auto_commit)


def initialize_minimal_logistics_accounts(db: Session, tenant_id: int) -> list[ChartOfAccount]:
    """
    Initialize minimal Logistics Chart of Accounts for Elis Logistics.
    Simplified to only include accounts actually needed:
    - Settlement income (net profit from truck leases)
    - Trailer rental income
    - Maintenance & repairs (truck repairs you pay)
    - Trailer expenses (parking, repairs)
    - Interest expense (loan interest)
    - Depreciation and Section 179
    
    All accounts are shared (truck_id = NULL) - no per-asset accounting.
    Returns list of created accounts.
    Raises ValueError if accounts already exist.
    """
    # Check if accounts already exist (only check for accounts without truck_id)
    existing_count = db.query(ChartOfAccount).filter(
        ChartOfAccount.tenant_id == tenant_id,
        ChartOfAccount.truck_id.is_(None)
    ).count()
    if existing_count > 0:
        raise ValueError("Chart already initialized. Use reset if needed.")
    
    accounts = []
    
    # ASSET accounts
    accounts.append(get_or_create_account(db, "1000", "Cash", "Asset", tenant_id, parent_id=None, truck_id=None))
    accounts.append(get_or_create_account(db, "1500", "Vehicles & Equipment", "Asset", tenant_id, parent_id=None, truck_id=None))
    accounts.append(get_or_create_account(db, "1600", "Accumulated Depreciation - Vehicles", "Asset", tenant_id, parent_id=None, truck_id=None))
    
    # LIABILITY accounts
    accounts.append(get_or_create_account(db, "2100", "Loans Payable", "Liability", tenant_id, parent_id=None, truck_id=None))
    accounts.append(get_or_create_account(db, "2200", "Taxes Payable", "Liability", tenant_id, parent_id=None, truck_id=None))
    
    # EQUITY accounts
    accounts.append(get_or_create_account(db, "3000", "Owner Equity", "Equity", tenant_id, parent_id=None, truck_id=None))
    accounts.append(get_or_create_account(db, "3100", "Retained Earnings", "Equity", tenant_id, parent_id=None, truck_id=None))
    
    # REVENUE accounts
    accounts.append(get_or_create_account(db, "4000", "Settlement Income", "Revenue", tenant_id, parent_id=None, truck_id=None))
    accounts.append(get_or_create_account(db, "4100", "Trailer Rental Income", "Revenue", tenant_id, parent_id=None, truck_id=None))
    
    # EXPENSE accounts
    accounts.append(get_or_create_account(db, "5100", "Maintenance & Repairs", "Expense", tenant_id, parent_id=None, truck_id=None))
    accounts.append(get_or_create_account(db, "5200", "Trailer Expenses", "Expense", tenant_id, parent_id=None, truck_id=None))
    accounts.append(get_or_create_account(db, "5300", "Interest Expense", "Expense", tenant_id, parent_id=None, truck_id=None))
    accounts.append(get_or_create_account(db, "5400", "Depreciation Expense", "Expense", tenant_id, parent_id=None, truck_id=None))
    accounts.append(get_or_create_account(db, "5500", "Section 179 Deduction", "Expense", tenant_id, parent_id=None, truck_id=None))
    
    return accounts
    
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


def validate_journal_entry_lines(lines: List[Dict], tenant_id: int, db: Session, entry_tenant_id: Optional[int] = None) -> Tuple[bool, str]:
    """
    Validate journal entry lines with all required rules:
    1. Total debits must equal total credits
    2. Each line must have exactly one side: (debit > 0 XOR credit > 0)
    3. All accounts must belong to the same tenant_id
    4. All lines must share the same tenant_id as entry (if provided)
    
    Returns (is_valid, error_message)
    """
    if not lines:
        return False, "Journal entry must have at least one line"
    
    # Use entry_tenant_id if provided, otherwise use tenant_id parameter
    expected_tenant_id = entry_tenant_id if entry_tenant_id is not None else tenant_id
    
    total_debits = Decimal(0)
    total_credits = Decimal(0)
    account_ids = []
    
    for idx, line in enumerate(lines):
        debit = Decimal(str(line.get("debit", 0) or 0))
        credit = Decimal(str(line.get("credit", 0) or 0))
        account_id = line.get("account_id")
        line_tenant_id = line.get("tenant_id")
        
        # Rule 2: XOR validation - exactly one side must be > 0
        if debit > 0 and credit > 0:
            return False, f"Line {idx + 1}: Cannot have both debit and credit > 0. Each line must have exactly one side."
        if debit == 0 and credit == 0:
            return False, f"Line {idx + 1}: Must have either debit > 0 or credit > 0 (not both zero)."
        
        # Rule 4: All lines must share same tenant_id as entry
        if line_tenant_id is not None and line_tenant_id != expected_tenant_id:
            return False, f"Line {idx + 1}: tenant_id ({line_tenant_id}) does not match entry tenant_id ({expected_tenant_id})"
        
        # Collect account IDs for tenant validation
        if account_id:
            account_ids.append(account_id)
        
        total_debits += debit
        total_credits += credit
    
    # Rule 1: Debits must equal credits
    if abs(total_debits - total_credits) > Decimal("0.01"):  # Allow small rounding differences
        return False, f"Journal entry does not balance: Debits ${total_debits:.2f} != Credits ${total_credits:.2f}"
    
    # Rule 3: All accounts must belong to same tenant
    if account_ids:
        accounts = db.query(ChartOfAccount).filter(ChartOfAccount.id.in_(account_ids)).all()
        if len(accounts) != len(account_ids):
            missing_ids = set(account_ids) - {acc.id for acc in accounts}
            return False, f"One or more accounts not found: {missing_ids}"
        
        for account in accounts:
            if account.tenant_id != expected_tenant_id:
                return False, f"Account {account.code} ({account.name}) belongs to tenant {account.tenant_id}, but entry is for tenant {expected_tenant_id}"
    
    return True, ""


def create_settlement_journal_entry(
    db: Session,
    settlement: Settlement,
    auto_commit: bool = True,
) -> Optional[JournalEntry]:
    """
    Create a journal entry for a settlement.
    
    For Elis Logistics: Simple entry since they receive clean profit (net_profit):
    - Debit: Cash = net_profit
    - Credit: Settlement Income (4000) = net_profit
    
    For LS Logistics (per-asset): Full entry with revenue and expenses:
    - Debit: Accounts Receivable = gross_revenue
    - Credit: Operating Revenue = gross_revenue
    - Debit: Various Expense accounts
    - Credit: Accounts Payable (or Cash)
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
    existing_query = _filter_active_journal_entries(existing_query)
    if per_asset:
        existing_query = existing_query.filter(JournalEntry.truck_id == settlement.truck_id)
    else:
        existing_query = existing_query.filter(JournalEntry.truck_id.is_(None))
    
    existing = existing_query.first()
    if existing:
        return existing  # Already created
    
    # Ensure accounts exist
    ensure_standard_accounts_exist(db, tenant_id, truck_id_for_accounting, auto_commit=auto_commit)

    gross_revenue = Decimal(str(settlement.gross_revenue)) if settlement.gross_revenue else Decimal(0)
    net_profit = Decimal(str(settlement.net_profit)) if settlement.net_profit else Decimal(0)
    has_positive_expenses = False
    has_reimbursement = False
    if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
        for category, amount in settlement.expense_categories.items():
            amount_dec = Decimal(str(amount)) if amount else Decimal(0)
            if category == "reimbursement":
                if amount_dec > 0:
                    has_reimbursement = True
                continue
            if amount_dec > 0:
                has_positive_expenses = True

    # Skip accounting side effects when a settlement produces nothing valid to post.
    if not per_asset and net_profit <= 0:
        return None
    if per_asset and gross_revenue <= 0 and not has_positive_expenses and not has_reimbursement:
        return None
    
    entry_date = settlement.settlement_date or settlement.created_at.date() if settlement.created_at else date.today()
    
    # Create journal entry
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
    
    # For Elis Logistics: Simple entry with net_profit only
    if not per_asset:
        # Elis Logistics receives clean profit - simple entry
        if net_profit > 0:
            cash_account = get_or_create_account(db, get_cash_account_code(), "Cash", "Asset", tenant_id, truck_id=None, auto_commit=auto_commit)
            revenue_account = get_or_create_account(db, "4000", "Settlement Income", "Revenue", tenant_id, truck_id=None, auto_commit=auto_commit)
            
            lines.append({
                "journal_entry_id": journal_entry.id,
                "account_id": cash_account.id,
                "debit": net_profit,
                "credit": 0,
                "description": "Settlement net profit received",
                "tenant_id": tenant_id
            })
            lines.append({
                "journal_entry_id": journal_entry.id,
                "account_id": revenue_account.id,
                "debit": 0,
                "credit": net_profit,
                "description": "Settlement income",
                "tenant_id": tenant_id
            })
    else:
        # LS Logistics: Full entry with revenue and expenses
        revenue_account = get_or_create_account(db, get_revenue_account_code(), "Operating Revenue", "Revenue", tenant_id, truck_id=truck_id_for_accounting, auto_commit=auto_commit)
        ar_account = get_or_create_account(db, get_accounts_receivable_code(), "Accounts Receivable", "Asset", tenant_id, truck_id=truck_id_for_accounting, auto_commit=auto_commit)
        
        # Revenue side: Debit AR, Credit Revenue
        if gross_revenue > 0:
            lines.append({
                "journal_entry_id": journal_entry.id,
                "account_id": ar_account.id,
                "debit": gross_revenue,
                "credit": 0,
                "description": "Settlement revenue",
                "truck_id": settlement.truck_id,
                "tenant_id": tenant_id
            })
            lines.append({
                "journal_entry_id": journal_entry.id,
                "account_id": revenue_account.id,
                "debit": 0,
                "credit": gross_revenue,
                "description": "Operating revenue",
                "truck_id": settlement.truck_id,
                "tenant_id": tenant_id
            })
        
        # Expense side: Debit Expense accounts, Credit AR (or Cash)
        if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
            for category, amount in settlement.expense_categories.items():
                # Skip reimbursements - they're credits, handled separately
                if category == "reimbursement":
                    continue
                
                amount_dec = Decimal(str(amount)) if amount else Decimal(0)
                if amount_dec > 0:
                    account_code = get_account_code_for_expense_category(category)
                    expense_account = get_or_create_account(
                        db, 
                        account_code,
                        f"{category.replace('_', ' ').title()} Expense",
                        "Expense",
                        tenant_id,
                        truck_id=truck_id_for_accounting,
                        auto_commit=auto_commit,
                    )
                    
                    lines.append({
                        "journal_entry_id": journal_entry.id,
                        "account_id": expense_account.id,
                        "debit": amount_dec,
                        "credit": 0,
                        "description": f"{category} expense",
                        "truck_id": settlement.truck_id,
                        "tenant_id": tenant_id
                    })
                    lines.append({
                        "journal_entry_id": journal_entry.id,
                        "account_id": ar_account.id,
                        "debit": 0,
                        "credit": amount_dec,
                        "description": f"Payment for {category}",
                        "truck_id": settlement.truck_id,
                        "tenant_id": tenant_id
                    })
        
        # Handle reimbursements (credits that reduce expenses)
        if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
            reimbursement = settlement.expense_categories.get("reimbursement", 0)
            if reimbursement:
                reimbursement_float = Decimal(str(reimbursement))
                # Reimbursement: Debit AR, Credit Expense (reduces expense)
                lines.append({
                    "journal_entry_id": journal_entry.id,
                    "account_id": ar_account.id,
                    "debit": reimbursement_float,
                    "credit": 0,
                    "description": "Reimbursement received",
                    "truck_id": settlement.truck_id,
                    "tenant_id": tenant_id
                })
                # Credit to a reimbursement income account or reduce expenses
                reimbursement_account = get_or_create_account(db, "4100", "Reimbursement Income", "Revenue", tenant_id, truck_id=truck_id_for_accounting, auto_commit=auto_commit)
                lines.append({
                    "journal_entry_id": journal_entry.id,
                    "account_id": reimbursement_account.id,
                    "debit": 0,
                    "credit": reimbursement_float,
                    "description": "Reimbursement income",
                    "truck_id": settlement.truck_id,
                    "tenant_id": tenant_id
                })
    
    # Ensure all lines have tenant_id
    for line_data in lines:
        if "tenant_id" not in line_data:
            line_data["tenant_id"] = tenant_id
    
    # Validate entry balances with enhanced validation
    is_valid, error_msg = validate_journal_entry_lines(lines, tenant_id, db, entry_tenant_id=tenant_id)
    if not is_valid:
        if auto_commit:
            db.rollback()
        raise ValueError(f"Invalid journal entry: {error_msg}")
    
    # Create lines
    for line_data in lines:
        line = JournalEntryLine(**line_data)
        db.add(line)
    
    if auto_commit:
        db.commit()
        db.refresh(journal_entry)
    else:
        db.flush()
    return journal_entry


def create_repair_journal_entry(
    db: Session,
    repair: Repair,
    auto_commit: bool = True,
) -> Optional[JournalEntry]:
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
    existing_query = _filter_active_journal_entries(existing_query)
    if per_asset:
        existing_query = existing_query.filter(JournalEntry.truck_id == repair.truck_id)
    else:
        existing_query = existing_query.filter(JournalEntry.truck_id.is_(None))
    
    existing = existing_query.first()
    if existing:
        return existing  # Already created
    
    if not repair.cost or Decimal(str(repair.cost)) <= 0:
        return None  # No cost, no entry
    
    # Ensure accounts exist
    ensure_standard_accounts_exist(db, tenant_id, truck_id_for_accounting, auto_commit=auto_commit)
    
    # Get accounts - use 5100 for Elis Logistics, 6011 for LS Logistics
    if per_asset:
        maintenance_account = get_or_create_account(db, "6011", "Maintenance Expense", "Expense", tenant_id, truck_id=truck_id_for_accounting, auto_commit=auto_commit)
    else:
        maintenance_account = get_or_create_account(db, "5100", "Maintenance & Repairs", "Expense", tenant_id, truck_id=None, auto_commit=auto_commit)
    cash_account = get_or_create_account(db, get_cash_account_code(), "Cash", "Asset", tenant_id, truck_id=truck_id_for_accounting, auto_commit=auto_commit)
    
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
    
    cost = Decimal(str(repair.cost))
    
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
    
    # Ensure all lines have tenant_id
    for line_data in lines:
        if "tenant_id" not in line_data:
            line_data["tenant_id"] = tenant_id
    
    # Validate entry balances with enhanced validation
    is_valid, error_msg = validate_journal_entry_lines(lines, tenant_id, db, entry_tenant_id=tenant_id)
    if not is_valid:
        if auto_commit:
            db.rollback()
        raise ValueError(f"Invalid journal entry: {error_msg}")
    
    # Create lines
    for line_data in lines:
        line = JournalEntryLine(**line_data)
        db.add(line)
    
    if auto_commit:
        db.commit()
        db.refresh(journal_entry)
    else:
        db.flush()
    return journal_entry


def delete_settlement_journal_entry(db: Session, settlement_id: int, auto_commit: bool = True):
    """Soft-delete journal entry for a settlement."""
    journal_entry_query = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "settlement",
        JournalEntry.reference_id == settlement_id,
    )
    journal_entry = _filter_active_journal_entries(journal_entry_query).first()

    if journal_entry:
        _delete_or_soft_delete_journal_entry(db, journal_entry)
        if auto_commit:
            db.commit()
        else:
            db.flush()


def delete_repair_journal_entry(db: Session, repair_id: int, auto_commit: bool = True):
    """Soft-delete journal entry for a repair."""
    journal_entry_query = db.query(JournalEntry).filter(
        JournalEntry.reference_type == "repair",
        JournalEntry.reference_id == repair_id,
    )
    journal_entry = _filter_active_journal_entries(journal_entry_query).first()

    if journal_entry:
        _delete_or_soft_delete_journal_entry(db, journal_entry)
        if auto_commit:
            db.commit()
        else:
            db.flush()


def calculate_account_balance(
    db: Session,
    account_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    truck_id: Optional[int] = None,
    reference_types: Optional[list[str]] = None,
    exclude_reference_types: Optional[list[str]] = None,
) -> Decimal:
    """
    Calculate account balance (debits - credits for assets/expenses, credits - debits for liabilities/equity/revenue).
    For per-asset accounts, filters by account's truck_id and journal entry's truck_id.
    Optionally filter by truck_id on journal entry lines for operational tracking.
    """
    account = db.query(ChartOfAccount).filter(ChartOfAccount.id == account_id).first()
    if not account:
        return Decimal(0)
    
    # Build query with date and truck filtering (exclude soft-deleted)
    total_debits = db.query(func.sum(JournalEntryLine.debit)).join(JournalEntry).filter(
        JournalEntryLine.account_id == account_id,
    )
    total_debits = _filter_active_journal_entries(total_debits)
    total_credits = db.query(func.sum(JournalEntryLine.credit)).join(JournalEntry).filter(
        JournalEntryLine.account_id == account_id,
    )
    total_credits = _filter_active_journal_entries(total_credits)
    
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
    if reference_types:
        total_debits = total_debits.filter(JournalEntry.reference_type.in_(reference_types))
        total_credits = total_credits.filter(JournalEntry.reference_type.in_(reference_types))
    if exclude_reference_types:
        total_debits = total_debits.filter(~JournalEntry.reference_type.in_(exclude_reference_types))
        total_credits = total_credits.filter(~JournalEntry.reference_type.in_(exclude_reference_types))
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


def generate_balance_sheet(db: Session, tenant_id: int, as_of_date: Optional[date] = None) -> Dict:
    """
    Generate balance sheet as of a specific date for a specific tenant.
    Always aggregates all assets (trucks, trailers, SUV) for the business.
    """
    if not as_of_date:
        as_of_date = date.today()
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")
    
    per_asset = uses_per_asset_accounting(tenant)
    
    # Ensure accounts exist - for per-asset, ensure all vehicles have accounts
    if per_asset:
        ensure_standard_accounts_exist(db, tenant_id, None)  # Creates accounts for all vehicles
    else:
        ensure_standard_accounts_exist(db, tenant_id, None)  # Creates shared accounts
    
    # Assets - Cash and AR
    if per_asset:
        # Aggregate across all vehicle accounts
        cash_accounts = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == get_cash_account_code(),
            ChartOfAccount.truck_id.isnot(None)
        ).all()
        ar_accounts = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == get_accounts_receivable_code(),
            ChartOfAccount.truck_id.isnot(None)
        ).all()
        cash_balance = sum(calculate_account_balance(db, acc.id, end_date=as_of_date) for acc in cash_accounts)
        ar_balance = sum(calculate_account_balance(db, acc.id, end_date=as_of_date) for acc in ar_accounts)
    else:
        # Use shared accounts
        cash_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == get_cash_account_code(),
            ChartOfAccount.truck_id.is_(None)
        ).first()
        ar_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == get_accounts_receivable_code(),
            ChartOfAccount.truck_id.is_(None)
        ).first()
        cash_balance = calculate_account_balance(db, cash_account.id, end_date=as_of_date) if cash_account else Decimal(0)
        ar_balance = calculate_account_balance(db, ar_account.id, end_date=as_of_date) if ar_account else Decimal(0)
    
    # Fixed assets: always sum all vehicles for logistics businesses
    fixed_assets_balance = Decimal(0)
    if tenant.business_type == 'logistics':
        trucks = db.query(Truck).filter(Truck.tenant_id == tenant_id).all()
        for truck in trucks:
            if truck.total_cost:
                fixed_assets_balance += Decimal(str(truck.total_cost))
    else:
        # Non-logistics: use account balance
        fixed_assets_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == "1500",
            ChartOfAccount.truck_id.is_(None)
        ).first()
        fixed_assets_balance = calculate_account_balance(db, fixed_assets_account.id, end_date=as_of_date) if fixed_assets_account else Decimal(0)
    
    # Accumulated depreciation
    acc_dep_balance = Decimal(0)
    if per_asset:
        # Aggregate depreciation accounts across all vehicles
        acc_dep_accounts = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == "1501",
            ChartOfAccount.truck_id.isnot(None)
        ).all()
        acc_dep_balance = sum(calculate_account_balance(db, acc.id, end_date=as_of_date) for acc in acc_dep_accounts)
    else:
        acc_dep_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == "1501",
            ChartOfAccount.truck_id.is_(None)
        ).first()
        acc_dep_balance = calculate_account_balance(db, acc_dep_account.id, end_date=as_of_date) if acc_dep_account else Decimal(0)
    
    # If no journal entries exist, calculate from depreciation service
    if acc_dep_balance == 0 and tenant.business_type == 'logistics':
        try:
            from app.services.depreciation_service import calculate_depreciation_for_truck
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
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to calculate depreciation: {str(e)}")
    
    net_fixed_assets = fixed_assets_balance - acc_dep_balance
    fixed_assets_balance = fixed_assets_balance or Decimal(0)
    acc_dep_balance = acc_dep_balance or Decimal(0)
    net_fixed_assets = net_fixed_assets or Decimal(0)
    
    total_assets = cash_balance + ar_balance + net_fixed_assets
    
    # Liabilities
    if per_asset:
        # Aggregate across all vehicle accounts
        ap_accounts = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == "2000",
            ChartOfAccount.truck_id.isnot(None)
        ).all()
        loans_accounts = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == get_loans_payable_code(),
            ChartOfAccount.truck_id.isnot(None)
        ).all()
        ap_balance = sum(calculate_account_balance(db, acc.id, end_date=as_of_date) for acc in ap_accounts)
        loans_balance = sum(calculate_account_balance(db, acc.id, end_date=as_of_date) for acc in loans_accounts)
    else:
        ap_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == "2000",
            ChartOfAccount.truck_id.is_(None)
        ).first()
        loans_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == get_loans_payable_code(),
            ChartOfAccount.truck_id.is_(None)
        ).first()
        ap_balance = calculate_account_balance(db, ap_account.id, end_date=as_of_date) if ap_account else Decimal(0)
        loans_balance = calculate_account_balance(db, loans_account.id, end_date=as_of_date) if loans_account else Decimal(0)
    
    # For logistics businesses, also sum loans from truck records
    if tenant.business_type == 'logistics':
        trucks = db.query(Truck).filter(Truck.tenant_id == tenant_id).all()
        truck_loans = Decimal(0)
        for truck in trucks:
            if truck.current_loan_balance:
                truck_loans += Decimal(str(truck.current_loan_balance))
            elif truck.loan_amount and truck.vehicle_type == 'truck':
                truck_loans += Decimal(str(truck.loan_amount))
        if truck_loans > 0:
            loans_balance = truck_loans
    
    total_liabilities = ap_balance + loans_balance
    
    # Equity
    if per_asset:
        # Aggregate across all vehicle accounts
        owner_equity_accounts = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == "3000",
            ChartOfAccount.truck_id.isnot(None)
        ).all()
        retained_earnings_accounts = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == get_retained_earnings_code(),
            ChartOfAccount.truck_id.isnot(None)
        ).all()
        owner_equity_balance = sum(calculate_account_balance(db, acc.id, end_date=as_of_date) for acc in owner_equity_accounts)
        retained_earnings = sum(calculate_account_balance(db, acc.id, end_date=as_of_date) for acc in retained_earnings_accounts)
    else:
        owner_equity_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == "3000",
            ChartOfAccount.truck_id.is_(None)
        ).first()
        retained_earnings_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id,
            ChartOfAccount.code == get_retained_earnings_code(),
            ChartOfAccount.truck_id.is_(None)
        ).first()
        owner_equity_balance = calculate_account_balance(db, owner_equity_account.id, end_date=as_of_date) if owner_equity_account else Decimal(0)
        retained_earnings = calculate_account_balance(db, retained_earnings_account.id, end_date=as_of_date) if retained_earnings_account else Decimal(0)
    
    # For logistics businesses, calculate retained earnings from settlements/repairs
    if tenant.business_type == 'logistics':
        settlements = db.query(Settlement).join(Truck).filter(
            Truck.tenant_id == tenant_id,
            Settlement.settlement_date <= as_of_date
        ).all()
        repairs = db.query(Repair).join(Truck).filter(
            Truck.tenant_id == tenant_id,
            Repair.repair_date <= as_of_date
        ).all()
        
        total_revenue = sum((Decimal(str(s.gross_revenue)) if s.gross_revenue else Decimal(0) for s in settlements), Decimal(0))
        total_expenses = sum((Decimal(str(s.expenses)) if s.expenses else Decimal(0) for s in settlements), Decimal(0))
        total_repairs = sum((Decimal(str(r.cost)) if r.cost else Decimal(0) for r in repairs), Decimal(0))

        retained_earnings = total_revenue - total_expenses - total_repairs
    
    total_equity = owner_equity_balance + retained_earnings
    total_liabilities_and_equity = total_liabilities + total_equity
    
    def safe_dec(value) -> float:
        try:
            d = Decimal(str(value or 0))
            return float(d.quantize(Decimal("0.01")))
        except Exception:
            return 0.0

    return {
        "as_of_date": as_of_date.isoformat(),
        "assets": {
            "cash": safe_dec(cash_balance),
            "accounts_receivable": safe_dec(ar_balance),
            "vehicles": safe_dec(fixed_assets_balance),
            "accumulated_depreciation": safe_dec(acc_dep_balance),
            "net_vehicles": safe_dec(net_fixed_assets),
            "total": safe_dec(total_assets)
        },
        "liabilities": {
            "accounts_payable": safe_dec(ap_balance),
            "loans_payable": safe_dec(loans_balance),
            "total": safe_dec(total_liabilities)
        },
        "equity": {
            "owner_equity": safe_dec(owner_equity_balance),
            "retained_earnings": safe_dec(retained_earnings),
            "total": safe_dec(total_equity)
        },
        "total_liabilities_and_equity": safe_dec(total_liabilities_and_equity)
    }


def generate_income_statement(
    db: Session,
    tenant_id: int,
    start_date: date,
    end_date: date,
    truck_id: Optional[int] = None,
    reference_types: Optional[list[str]] = None,
    exclude_reference_types: Optional[list[str]] = None,
) -> Dict:
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
    
    # Revenue - aggregate all revenue accounts (Settlement Income, Trailer Rental Income, etc.)
    revenue_accounts = db.query(ChartOfAccount).filter(
        *account_filter,
        ChartOfAccount.account_type == "Revenue"
    ).all()
    
    if not revenue_accounts:
        # If accounts don't exist, try to create them
        ensure_standard_accounts_exist(db, tenant_id, truck_id)
        revenue_accounts = db.query(ChartOfAccount).filter(
            *account_filter,
            ChartOfAccount.account_type == "Revenue"
        ).all()
    
    revenue_by_category = {}
    revenue_balance = Decimal(0)
    for account in revenue_accounts:
        balance = calculate_account_balance(db, account.id, start_date, end_date, truck_id, reference_types, exclude_reference_types)
        if balance > 0:
            revenue_by_category[account.name] = float(Decimal(str(balance)).quantize(Decimal("0.01")))
            revenue_balance += balance

    expense_accounts = db.query(ChartOfAccount).filter(
        *account_filter,
        ChartOfAccount.account_type == "Expense"
    ).all()
    expenses_by_category = {}
    total_expenses = Decimal(0)

    for account in expense_accounts:
        balance = calculate_account_balance(db, account.id, start_date, end_date, truck_id, reference_types, exclude_reference_types)
        if balance > 0:
            expenses_by_category[account.name] = float(Decimal(str(balance)).quantize(Decimal("0.01")))
            total_expenses += balance

    net_income = revenue_balance - total_expenses

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "truck_id": truck_id,
        "revenue": revenue_by_category if revenue_by_category else {"operating_revenue": float(revenue_balance.quantize(Decimal("0.01")))},
        "total_revenue": float(revenue_balance.quantize(Decimal("0.01"))),
        "expenses": expenses_by_category,
        "total_expenses": float(total_expenses.quantize(Decimal("0.01"))),
        "net_income": float(net_income.quantize(Decimal("0.01")))
    }
