"""
Accounting router
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import date, datetime

from app.database import get_db
from app.dependencies import get_tenant_id
from app.models.chart_of_accounts import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from app.schemas.accounting import (
    ChartOfAccountCreate,
    ChartOfAccountResponse,
    JournalEntryCreate,
    JournalEntryResponse,
    GeneralLedgerResponse,
    GeneralLedgerEntry,
    BalanceSheetResponse,
    IncomeStatementResponse,
)
from app.services.accounting_service import (
    ensure_standard_accounts_exist,
    create_settlement_journal_entry,
    create_repair_journal_entry,
    calculate_account_balance,
    generate_balance_sheet,
    generate_income_statement,
    validate_journal_entry_lines,
)

router = APIRouter()


@router.post("/chart-of-accounts/initialize", response_model=List[ChartOfAccountResponse])
def initialize_chart_of_accounts(db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Initialize standard chart of accounts for the current tenant."""
    ensure_standard_accounts_exist(db, tenant_id)
    accounts = db.query(ChartOfAccount).filter(ChartOfAccount.tenant_id == tenant_id).all()
    return accounts


@router.get("/chart-of-accounts", response_model=List[ChartOfAccountResponse])
def get_chart_of_accounts(
    account_type: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Get all chart of accounts for the current tenant, optionally filtered by type."""
    query = db.query(ChartOfAccount).filter(ChartOfAccount.tenant_id == tenant_id)
    
    if account_type:
        query = query.filter(ChartOfAccount.account_type == account_type)
    if is_active is not None:
        query = query.filter(ChartOfAccount.is_active == is_active)
    
    return query.order_by(ChartOfAccount.code).all()


@router.post("/chart-of-accounts", response_model=ChartOfAccountResponse)
def create_chart_of_account(
    account: ChartOfAccountCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Create a new chart of account."""
    # Check if code already exists for this tenant
    existing = db.query(ChartOfAccount).filter(
        ChartOfAccount.tenant_id == tenant_id,
        ChartOfAccount.code == account.code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account with code {account.code} already exists")
    
    db_account = ChartOfAccount(**account.model_dump())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account


@router.get("/chart-of-accounts/{account_id}", response_model=ChartOfAccountResponse)
def get_chart_of_account(account_id: int, db: Session = Depends(get_db)):
    """Get a specific chart of account."""
    account = db.query(ChartOfAccount).filter(ChartOfAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("/journal-entries", response_model=List[JournalEntryResponse])
def get_journal_entries(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get all journal entries, optionally filtered."""
    query = db.query(JournalEntry)
    
    if start_date:
        query = query.filter(JournalEntry.entry_date >= start_date)
    if end_date:
        query = query.filter(JournalEntry.entry_date <= end_date)
    if reference_type:
        query = query.filter(JournalEntry.reference_type == reference_type)
    if reference_id:
        query = query.filter(JournalEntry.reference_id == reference_id)
    
    return query.order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc()).all()


@router.post("/journal-entries", response_model=JournalEntryResponse)
def create_journal_entry(
    entry: JournalEntryCreate,
    db: Session = Depends(get_db)
):
    """Create a manual journal entry."""
    # Validate that lines balance
    lines_data = [line.model_dump() for line in entry.lines]
    is_valid, error_msg = validate_journal_entry_lines(lines_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Create journal entry
    entry_data = entry.model_dump(exclude={"lines"})
    db_entry = JournalEntry(**entry_data)
    db.add(db_entry)
    db.flush()  # Get the ID
    
    # Create lines
    for line in entry.lines:
        line_data = line.model_dump()
        line_data["journal_entry_id"] = db_entry.id
        db_line = JournalEntryLine(**line_data)
        db.add(db_line)
    
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.get("/journal-entries/{entry_id}", response_model=JournalEntryResponse)
def get_journal_entry(entry_id: int, db: Session = Depends(get_db)):
    """Get a specific journal entry."""
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


@router.get("/general-ledger", response_model=GeneralLedgerResponse)
def get_general_ledger(
    account_id: int,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """Get general ledger for a specific account."""
    account = db.query(ChartOfAccount).filter(ChartOfAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Calculate start balance (before start_date)
    start_balance = 0.0
    if start_date:
        start_balance = float(calculate_account_balance(db, account_id, end_date=date.fromordinal(start_date.toordinal() - 1)))
    else:
        # Get earliest entry date
        earliest_entry = db.query(JournalEntry).join(JournalEntryLine).filter(
            JournalEntryLine.account_id == account_id
        ).order_by(JournalEntry.entry_date.asc()).first()
        if earliest_entry:
            start_balance = float(calculate_account_balance(db, account_id, end_date=date.fromordinal(earliest_entry.entry_date.toordinal() - 1)))
    
    # Get entries
    query = db.query(JournalEntryLine).join(JournalEntry).filter(
        JournalEntryLine.account_id == account_id
    )
    
    if start_date:
        query = query.filter(JournalEntry.entry_date >= start_date)
    if end_date:
        query = query.filter(JournalEntry.entry_date <= end_date)
    
    lines = query.order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc()).all()
    
    # Build entries with running balance
    entries = []
    running_balance = start_balance
    
    for line in lines:
        if account.account_type in ["Asset", "Expense"]:
            running_balance += float(line.debit) - float(line.credit)
        else:
            running_balance += float(line.credit) - float(line.debit)
        
        entries.append(GeneralLedgerEntry(
            entry_date=line.journal_entry.entry_date,
            journal_entry_id=line.journal_entry_id,
            account_code=account.code,
            account_name=account.name,
            description=line.description,
            debit=float(line.debit),
            credit=float(line.credit),
            running_balance=running_balance
        ))
    
    end_balance = running_balance
    
    return GeneralLedgerResponse(
        account_id=account.id,
        account_code=account.code,
        account_name=account.name,
        account_type=account.account_type,
        start_balance=start_balance,
        end_balance=end_balance,
        entries=entries
    )


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
def get_balance_sheet(
    as_of_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """Get balance sheet as of a specific date."""
    if not as_of_date:
        as_of_date = date.today()
    
    balance_sheet = generate_balance_sheet(db, as_of_date)
    return BalanceSheetResponse(**balance_sheet)


@router.get("/income-statement", response_model=IncomeStatementResponse)
def get_income_statement(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db)
):
    """Get income statement for a date range."""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    
    income_statement = generate_income_statement(db, start_date, end_date)
    return IncomeStatementResponse(**income_statement)

