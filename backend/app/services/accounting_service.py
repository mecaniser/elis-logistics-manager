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
from app.utils.account_mapping import (
    get_account_code_for_expense_category,
    get_revenue_account_code,
    get_cash_account_code,
    get_accounts_receivable_code,
    get_loans_payable_code,
    get_retained_earnings_code,
)


def get_or_create_account(db: Session, code: str, name: str, account_type: str, tenant_id: int, parent_id: Optional[int] = None) -> ChartOfAccount:
    """
    Get an account by code for a tenant, or create it if it doesn't exist.
    """
    account = db.query(ChartOfAccount).filter(
        ChartOfAccount.code == code,
        ChartOfAccount.tenant_id == tenant_id
    ).first()
    if not account:
        account = ChartOfAccount(
            code=code,
            name=name,
            account_type=account_type,
            tenant_id=tenant_id,
            parent_id=parent_id,
            is_active=True
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def ensure_standard_accounts_exist(db: Session, tenant_id: int):
    """
    Ensure all standard chart of accounts exist for a tenant.
    Called during initialization or migration.
    """
    # Assets
    get_or_create_account(db, "1000", "Cash", "Asset", tenant_id)
    get_or_create_account(db, "1100", "Accounts Receivable", "Asset", tenant_id)
    get_or_create_account(db, "1500", "Vehicles", "Asset", tenant_id)
    get_or_create_account(db, "1501", "Accumulated Depreciation - Vehicles", "Asset", tenant_id)
    
    # Liabilities
    get_or_create_account(db, "2000", "Accounts Payable", "Liability", tenant_id)
    get_or_create_account(db, "2100", "Loans Payable", "Liability", tenant_id)
    get_or_create_account(db, "2200", "Accrued Expenses", "Liability", tenant_id)
    
    # Equity
    get_or_create_account(db, "3000", "Owner Equity", "Equity", tenant_id)
    get_or_create_account(db, "3100", "Retained Earnings", "Equity", tenant_id)
    
    # Revenue
    get_or_create_account(db, "4000", "Operating Revenue", "Revenue", tenant_id)
    
    # Expenses
    get_or_create_account(db, "6001", "Fuel Expense", "Expense", tenant_id)
    get_or_create_account(db, "6002", "Dispatch Fee Expense", "Expense", tenant_id)
    get_or_create_account(db, "6003", "Insurance Expense", "Expense", tenant_id)
    get_or_create_account(db, "6004", "Safety Expense", "Expense", tenant_id)
    get_or_create_account(db, "6005", "Prepass Expense", "Expense", tenant_id)
    get_or_create_account(db, "6006", "IFTA Expense", "Expense", tenant_id)
    get_or_create_account(db, "6007", "Driver Pay Expense", "Expense", tenant_id)
    get_or_create_account(db, "6008", "Payroll Fee Expense", "Expense", tenant_id)
    get_or_create_account(db, "6009", "Interest Expense", "Expense", tenant_id)
    get_or_create_account(db, "6010", "Parking Expense", "Expense", tenant_id)
    get_or_create_account(db, "6011", "Maintenance Expense", "Expense", tenant_id)
    get_or_create_account(db, "6012", "Decals Expense", "Expense", tenant_id)
    get_or_create_account(db, "6099", "Other Operating Expense", "Expense", tenant_id)


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
    
    # Check if journal entry already exists for this settlement
    existing = db.query(JournalEntry).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.reference_type == "settlement",
        JournalEntry.reference_id == settlement.id
    ).first()
    
    if existing:
        return existing  # Already created
    
    # Ensure accounts exist
    ensure_standard_accounts_exist(db, tenant_id)
    
    # Get accounts
    revenue_account = get_or_create_account(db, get_revenue_account_code(), "Operating Revenue", "Revenue", tenant_id)
    ar_account = get_or_create_account(db, get_accounts_receivable_code(), "Accounts Receivable", "Asset", tenant_id)
    
    entry_date = settlement.settlement_date or settlement.created_at.date() if settlement.created_at else date.today()
    
    # Create journal entry
    journal_entry = JournalEntry(
        tenant_id=tenant_id,
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
                    tenant_id
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
            reimbursement_account = get_or_create_account(db, "4100", "Reimbursement Income", "Revenue", tenant_id)
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
    
    # Check if journal entry already exists for this repair
    existing = db.query(JournalEntry).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.reference_type == "repair",
        JournalEntry.reference_id == repair.id
    ).first()
    
    if existing:
        return existing  # Already created
    
    if not repair.cost or float(repair.cost) <= 0:
        return None  # No cost, no entry
    
    # Ensure accounts exist
    ensure_standard_accounts_exist(db, tenant_id)
    
    # Get accounts
    maintenance_account = get_or_create_account(db, "6011", "Maintenance Expense", "Expense", tenant_id)
    cash_account = get_or_create_account(db, get_cash_account_code(), "Cash", "Asset", tenant_id)
    
    entry_date = repair.repair_date or (repair.created_at.date() if repair.created_at else date.today())
    
    # Create journal entry
    journal_entry = JournalEntry(
        tenant_id=tenant_id,
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


def calculate_account_balance(db: Session, account_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None) -> Decimal:
    """
    Calculate account balance (debits - credits for assets/expenses, credits - debits for liabilities/equity/revenue).
    """
    account = db.query(ChartOfAccount).filter(ChartOfAccount.id == account_id).first()
    if not account:
        return Decimal(0)
    
    # Build query with date filtering
    total_debits = db.query(func.sum(JournalEntryLine.debit)).join(JournalEntry).filter(
        JournalEntryLine.account_id == account_id
    )
    total_credits = db.query(func.sum(JournalEntryLine.credit)).join(JournalEntry).filter(
        JournalEntryLine.account_id == account_id
    )
    
    if start_date:
        total_debits = total_debits.filter(JournalEntry.entry_date >= start_date)
        total_credits = total_credits.filter(JournalEntry.entry_date >= start_date)
    if end_date:
        total_debits = total_debits.filter(JournalEntry.entry_date <= end_date)
        total_credits = total_credits.filter(JournalEntry.entry_date <= end_date)
    
    debits = total_debits.scalar() or Decimal(0)
    credits = total_credits.scalar() or Decimal(0)
    
    # For assets and expenses: balance = debits - credits
    # For liabilities, equity, and revenue: balance = credits - debits
    if account.account_type in ["Asset", "Expense"]:
        return debits - credits
    else:
        return credits - debits


def generate_balance_sheet(db: Session, as_of_date: Optional[date] = None) -> Dict:
    """
    Generate balance sheet as of a specific date.
    """
    if not as_of_date:
        as_of_date = date.today()
    
    ensure_standard_accounts_exist(db)
    
    # Assets
    cash_account = db.query(ChartOfAccount).filter(ChartOfAccount.code == get_cash_account_code()).first()
    ar_account = db.query(ChartOfAccount).filter(ChartOfAccount.code == get_accounts_receivable_code()).first()
    vehicles_account = db.query(ChartOfAccount).filter(ChartOfAccount.code == "1500").first()
    acc_dep_account = db.query(ChartOfAccount).filter(ChartOfAccount.code == "1501").first()
    
    cash_balance = calculate_account_balance(db, cash_account.id, end_date=as_of_date) if cash_account else Decimal(0)
    ar_balance = calculate_account_balance(db, ar_account.id, end_date=as_of_date) if ar_account else Decimal(0)
    
    # Vehicles: sum of truck total_cost
    vehicles_balance = Decimal(0)
    trucks = db.query(Truck).all()
    for truck in trucks:
        if truck.total_cost:
            vehicles_balance += Decimal(str(truck.total_cost))
    
    acc_dep_balance = calculate_account_balance(db, acc_dep_account.id, end_date=as_of_date) if acc_dep_account else Decimal(0)
    net_vehicles = vehicles_balance - acc_dep_balance
    
    total_assets = cash_balance + ar_balance + net_vehicles
    
    # Liabilities
    ap_account = db.query(ChartOfAccount).filter(ChartOfAccount.code == "2000").first()
    loans_account = db.query(ChartOfAccount).filter(ChartOfAccount.code == get_loans_payable_code()).first()
    
    ap_balance = calculate_account_balance(db, ap_account.id, end_date=as_of_date) if ap_account else Decimal(0)
    
    # Loans: sum of current_loan_balance from trucks
    loans_balance = Decimal(0)
    for truck in trucks:
        if truck.current_loan_balance:
            loans_balance += Decimal(str(truck.current_loan_balance))
        elif truck.loan_amount and truck.vehicle_type == 'truck':
            loans_balance += Decimal(str(truck.loan_amount))
    
    total_liabilities = ap_balance + loans_balance
    
    # Equity
    owner_equity_account = db.query(ChartOfAccount).filter(ChartOfAccount.code == "3000").first()
    retained_earnings_account = db.query(ChartOfAccount).filter(ChartOfAccount.code == get_retained_earnings_code()).first()
    
    owner_equity_balance = calculate_account_balance(db, owner_equity_account.id, end_date=as_of_date) if owner_equity_account else Decimal(0)
    
    # Retained earnings = cumulative net profit
    settlements = db.query(Settlement).filter(Settlement.settlement_date <= as_of_date).all()
    repairs = db.query(Repair).filter(Repair.repair_date <= as_of_date).all() if as_of_date else db.query(Repair).all()
    
    total_revenue = sum(float(s.gross_revenue) if s.gross_revenue else 0 for s in settlements)
    total_expenses = sum(float(s.expenses) if s.expenses else 0 for s in settlements)
    total_repairs = sum(float(r.cost) if r.cost else 0 for r in repairs)
    
    retained_earnings = Decimal(str(total_revenue - total_expenses - total_repairs))
    
    total_equity = owner_equity_balance + retained_earnings
    total_liabilities_and_equity = total_liabilities + total_equity
    
    return {
        "as_of_date": as_of_date.isoformat(),
        "assets": {
            "cash": float(cash_balance),
            "accounts_receivable": float(ar_balance),
            "vehicles": float(vehicles_balance),
            "accumulated_depreciation": float(acc_dep_balance),
            "net_vehicles": float(net_vehicles),
            "total": float(total_assets)
        },
        "liabilities": {
            "accounts_payable": float(ap_balance),
            "loans_payable": float(loans_balance),
            "total": float(total_liabilities)
        },
        "equity": {
            "owner_equity": float(owner_equity_balance),
            "retained_earnings": float(retained_earnings),
            "total": float(total_equity)
        },
        "total_liabilities_and_equity": float(total_liabilities_and_equity)
    }


def generate_income_statement(db: Session, start_date: date, end_date: date) -> Dict:
    """
    Generate income statement for a date range.
    """
    ensure_standard_accounts_exist(db)
    
    # Revenue
    revenue_account = db.query(ChartOfAccount).filter(ChartOfAccount.code == get_revenue_account_code()).first()
    revenue_balance = calculate_account_balance(db, revenue_account.id, start_date, end_date) if revenue_account else Decimal(0)
    
    # Expenses by category
    expense_accounts = db.query(ChartOfAccount).filter(ChartOfAccount.account_type == "Expense").all()
    expenses_by_category = {}
    total_expenses = Decimal(0)
    
    for account in expense_accounts:
        balance = calculate_account_balance(db, account.id, start_date, end_date)
        if balance > 0:
            expenses_by_category[account.name] = float(balance)
            total_expenses += balance
    
    net_income = revenue_balance - total_expenses
    
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "revenue": {
            "operating_revenue": float(revenue_balance),
            "total": float(revenue_balance)
        },
        "expenses": expenses_by_category,
        "total_expenses": float(total_expenses),
        "net_income": float(net_income)
    }

