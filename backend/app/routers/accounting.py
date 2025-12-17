"""
Accounting router
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal

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
from app.services.depreciation_service import (
    calculate_depreciation_for_truck,
    calculate_accumulated_depreciation,
    calculate_cost_basis,
    create_depreciation_journal_entry,
)
from app.models.truck import Truck

router = APIRouter()


@router.post("/chart-of-accounts/initialize", response_model=List[ChartOfAccountResponse])
def initialize_chart_of_accounts(db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Initialize standard chart of accounts for the current tenant."""
    ensure_standard_accounts_exist(db, tenant_id)
    accounts = db.query(ChartOfAccount).filter(ChartOfAccount.tenant_id == tenant_id).all()
    return accounts


@router.delete("/chart-of-accounts/reset")
def reset_chart_of_accounts(db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """
    Reset (delete) all chart of accounts for the current tenant.
    WARNING: This will delete all accounts. Journal entries referencing these accounts will also be affected.
    Use this to re-initialize accounts with the correct business type.
    """
    # Check if there are any journal entries using these accounts
    account_ids = [acc.id for acc in db.query(ChartOfAccount).filter(ChartOfAccount.tenant_id == tenant_id).all()]
    
    if account_ids:
        # Check for journal entry lines referencing these accounts
        journal_entry_lines_count = db.query(JournalEntryLine).filter(
            JournalEntryLine.account_id.in_(account_ids)
        ).count()
        
        if journal_entry_lines_count > 0:
            # Delete journal entry lines first
            db.query(JournalEntryLine).filter(
                JournalEntryLine.account_id.in_(account_ids)
            ).delete(synchronize_session=False)
            
            # Delete journal entries for this tenant
            db.query(JournalEntry).filter(
                JournalEntry.tenant_id == tenant_id
            ).delete(synchronize_session=False)
        
        # Delete all accounts for this tenant
        db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant_id
        ).delete(synchronize_session=False)
        
        db.commit()
    
    return {"message": "All accounts have been reset. You can now re-initialize with the correct business type."}


@router.get("/chart-of-accounts", response_model=List[ChartOfAccountResponse])
def get_chart_of_accounts(
    account_type: Optional[str] = None,
    is_active: Optional[bool] = True,
    truck_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Get all chart of accounts for the current tenant, optionally filtered by type and truck_id."""
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    from app.services.accounting_service import uses_per_asset_accounting
    
    query = db.query(ChartOfAccount).filter(ChartOfAccount.tenant_id == tenant_id)
    
    # For per-asset accounting, filter by truck_id
    if uses_per_asset_accounting(tenant):
        if truck_id:
            query = query.filter(ChartOfAccount.truck_id == truck_id)
        else:
            # If no truck_id specified, return all per-asset accounts
            query = query.filter(ChartOfAccount.truck_id.isnot(None))
    else:
        # For shared accounting, only return accounts without truck_id
        query = query.filter(ChartOfAccount.truck_id.is_(None))
    
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
    # Check if code already exists for this tenant (and truck_id if per-asset)
    existing_query = db.query(ChartOfAccount).filter(
        ChartOfAccount.tenant_id == tenant_id,
        ChartOfAccount.code == account.code
    )
    if account.truck_id is not None:
        existing_query = existing_query.filter(ChartOfAccount.truck_id == account.truck_id)
    else:
        existing_query = existing_query.filter(ChartOfAccount.truck_id.is_(None))
    
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account with code {account.code} already exists")
    
    account_data = account.model_dump()
    account_data['tenant_id'] = tenant_id
    db_account = ChartOfAccount(**account_data)
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
    truck_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Get all journal entries, optionally filtered."""
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    from app.services.accounting_service import uses_per_asset_accounting
    
    query = db.query(JournalEntry).filter(JournalEntry.tenant_id == tenant_id)
    
    # For per-asset accounting, filter by truck_id
    if uses_per_asset_accounting(tenant):
        if truck_id:
            query = query.filter(JournalEntry.truck_id == truck_id)
        else:
            # If no truck_id specified, return all per-asset entries
            query = query.filter(JournalEntry.truck_id.isnot(None))
    else:
        # For shared accounting, only return entries without truck_id
        query = query.filter(JournalEntry.truck_id.is_(None))
    
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
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Create a manual journal entry."""
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    from app.services.accounting_service import uses_per_asset_accounting
    
    per_asset = uses_per_asset_accounting(tenant)
    if per_asset and not entry.truck_id:
        raise HTTPException(status_code=400, detail="truck_id is required for LS Logistics journal entries")
    
    # Validate that lines balance
    lines_data = [line.model_dump() for line in entry.lines]
    is_valid, error_msg = validate_journal_entry_lines(lines_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Create journal entry
    entry_data = entry.model_dump(exclude={"lines"})
    entry_data['tenant_id'] = tenant_id
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
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Get balance sheet as of a specific date. Always shows total for all business assets."""
    if not as_of_date:
        as_of_date = date.today()
    
    try:
        balance_sheet = generate_balance_sheet(db, tenant_id, as_of_date)
        return BalanceSheetResponse(**balance_sheet)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        error_trace = traceback.format_exc()
        logger.error(f"Balance sheet error: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to generate balance sheet: {str(e)}")


@router.get("/income-statement", response_model=IncomeStatementResponse)
def get_income_statement(
    start_date: date = Query(...),
    end_date: date = Query(...),
    truck_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Get income statement for a date range. For LS Logistics, truck_id is required."""
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    from app.services.accounting_service import uses_per_asset_accounting
    
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    
    per_asset = uses_per_asset_accounting(tenant)
    if per_asset and not truck_id:
        raise HTTPException(status_code=400, detail="truck_id is required for LS Logistics income statement")
    
    # If truck_id provided, verify it belongs to the tenant
    if truck_id:
        from app.models.truck import Truck
        truck = db.query(Truck).filter(Truck.id == truck_id, Truck.tenant_id == tenant_id).first()
        if not truck:
            raise HTTPException(status_code=404, detail="Truck not found or does not belong to this tenant")
    
    try:
        income_statement = generate_income_statement(db, tenant_id, start_date, end_date, truck_id)
        return IncomeStatementResponse(**income_statement)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

