"""
Accounting router
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
import io

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
from app.models.tenant import Tenant
from app.utils.export_utils import export_to_csv, export_to_excel, export_to_pdf, format_currency, format_date

router = APIRouter()


@router.post("/chart-of-accounts/initialize", response_model=List[ChartOfAccountResponse])
def initialize_chart_of_accounts(db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """
    Initialize minimal standard chart of accounts for LOGISTICS business type.
    Returns 409 if accounts already exist.
    """
    from app.models.tenant import Tenant
    from app.services.accounting_service_minimal import initialize_minimal_logistics_accounts
    
    # Verify tenant exists and is LOGISTICS type
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
    
    if tenant.business_type.lower() != 'logistics':
        raise HTTPException(status_code=400, detail=f"This endpoint is for LOGISTICS business type. Tenant '{tenant.name}' has type '{tenant.business_type}'")
    
    try:
        accounts = initialize_minimal_logistics_accounts(db, tenant_id)
        return accounts
    except ValueError as e:
        if "already initialized" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


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
    
    # Create journal entry first to get ID
    entry_data = entry.model_dump(exclude={"lines"})
    entry_data['tenant_id'] = tenant_id
    db_entry = JournalEntry(**entry_data)
    db.add(db_entry)
    db.flush()  # Get the ID
    
    # Prepare lines data with tenant_id
    lines_data = []
    for line in entry.lines:
        line_dict = line.model_dump()
        line_dict["tenant_id"] = tenant_id  # Ensure tenant_id is set
        lines_data.append(line_dict)
    
    # Validate lines with enhanced validation
    is_valid, error_msg = validate_journal_entry_lines(lines_data, tenant_id, db, entry_tenant_id=tenant_id)
    if not is_valid:
        db.rollback()
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Create lines
    for line_data in lines_data:
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


# Export endpoints
@router.get("/export/journal-entries")
def export_journal_entries(
    format: str = Query("csv", regex="^(csv|excel)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    reference_type: Optional[str] = None,
    truck_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Export journal entries as CSV or Excel."""
    from app.services.accounting_service import uses_per_asset_accounting
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    query = db.query(JournalEntry).filter(JournalEntry.tenant_id == tenant_id)
    
    if uses_per_asset_accounting(tenant):
        if truck_id:
            query = query.filter(JournalEntry.truck_id == truck_id)
        else:
            query = query.filter(JournalEntry.truck_id.isnot(None))
    else:
        query = query.filter(JournalEntry.truck_id.is_(None))
    
    if start_date:
        query = query.filter(JournalEntry.entry_date >= start_date)
    if end_date:
        query = query.filter(JournalEntry.entry_date <= end_date)
    if reference_type:
        query = query.filter(JournalEntry.reference_type == reference_type)
    
    entries = query.order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc()).all()
    
    # Prepare data
    data = []
    for entry in entries:
        for line in entry.lines:
            account = db.query(ChartOfAccount).filter(ChartOfAccount.id == line.account_id).first()
            data.append({
                "Entry ID": entry.id,
                "Date": format_date(entry.entry_date),
                "Reference Type": entry.reference_type or "",
                "Reference ID": entry.reference_id or "",
                "Description": entry.description or "",
                "Account Code": account.code if account else "",
                "Account Name": account.name if account else "",
                "Debit": float(line.debit),
                "Credit": float(line.credit),
                "Line Description": line.description or "",
            })
    
    headers = ["Entry ID", "Date", "Reference Type", "Reference ID", "Description", "Account Code", "Account Name", "Debit", "Credit", "Line Description"]
    tenant_name = tenant.name if tenant else "Business"
    filename = f"{tenant_name}_journal_entries_{date.today().strftime('%Y%m%d')}"
    
    if format == "excel":
        file_buffer = export_to_excel(data, headers, filename, f"Journal Entries - {tenant_name}")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file_ext = "xlsx"
    else:
        file_buffer = export_to_csv(data, headers, filename)
        media_type = "text/csv"
        file_ext = "csv"
    
    return StreamingResponse(
        io.BytesIO(file_buffer.read()),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{file_ext}"'}
    )


@router.get("/export/general-ledger")
def export_general_ledger(
    account_id: int,
    format: str = Query("csv", regex="^(csv|excel)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Export general ledger as CSV or Excel."""
    account = db.query(ChartOfAccount).filter(ChartOfAccount.id == account_id, ChartOfAccount.tenant_id == tenant_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Get general ledger data
    start_balance = 0.0
    if start_date:
        start_balance = float(calculate_account_balance(db, account_id, end_date=date.fromordinal(start_date.toordinal() - 1)))
    
    query = db.query(JournalEntryLine).join(JournalEntry).filter(
        JournalEntryLine.account_id == account_id,
        JournalEntry.tenant_id == tenant_id
    )
    
    if start_date:
        query = query.filter(JournalEntry.entry_date >= start_date)
    if end_date:
        query = query.filter(JournalEntry.entry_date <= end_date)
    
    lines = query.order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc()).all()
    
    data = []
    running_balance = start_balance
    for line in lines:
        if account.account_type in ["Asset", "Expense"]:
            running_balance += float(line.debit) - float(line.credit)
        else:
            running_balance += float(line.credit) - float(line.debit)
        
        data.append({
            "Date": format_date(line.journal_entry.entry_date),
            "Entry ID": line.journal_entry_id,
            "Description": line.description or "",
            "Debit": float(line.debit),
            "Credit": float(line.credit),
            "Running Balance": running_balance,
        })
    
    headers = ["Date", "Entry ID", "Description", "Debit", "Credit", "Running Balance"]
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    tenant_name = tenant.name if tenant else "Business"
    filename = f"{tenant_name}_general_ledger_{account.code}_{date.today().strftime('%Y%m%d')}"
    
    if format == "excel":
        file_buffer = export_to_excel(data, headers, filename, f"General Ledger - {account.name} ({account.code})")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file_ext = "xlsx"
    else:
        file_buffer = export_to_csv(data, headers, filename)
        media_type = "text/csv"
        file_ext = "csv"
    
    return StreamingResponse(
        io.BytesIO(file_buffer.read()),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{file_ext}"'}
    )


@router.get("/export/balance-sheet")
def export_balance_sheet(
    format: str = Query("pdf", regex="^(pdf|excel)$"),
    as_of_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Export balance sheet as PDF or Excel."""
    if not as_of_date:
        as_of_date = date.today()
    
    balance_sheet = generate_balance_sheet(db, tenant_id, as_of_date)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    tenant_name = tenant.name if tenant else "Business"
    
    # Prepare data
    data = []
    data.append({"Account": "ASSETS", "Amount": ""})
    data.append({"Account": "  Cash", "Amount": format_currency(balance_sheet["assets"]["cash"])})
    data.append({"Account": "  Accounts Receivable", "Amount": format_currency(balance_sheet["assets"]["accounts_receivable"])})
    data.append({"Account": "  Vehicles", "Amount": format_currency(balance_sheet["assets"]["vehicles"])})
    data.append({"Account": "  Less: Accumulated Depreciation", "Amount": f"({format_currency(abs(balance_sheet['assets']['accumulated_depreciation']))})"})
    data.append({"Account": "  Net Vehicles", "Amount": format_currency(balance_sheet["assets"]["net_vehicles"])})
    data.append({"Account": "Total Assets", "Amount": format_currency(balance_sheet["assets"]["total"])})
    data.append({"Account": "", "Amount": ""})
    data.append({"Account": "LIABILITIES", "Amount": ""})
    data.append({"Account": "  Accounts Payable", "Amount": format_currency(balance_sheet["liabilities"]["accounts_payable"])})
    data.append({"Account": "  Loans Payable", "Amount": format_currency(balance_sheet["liabilities"]["loans_payable"])})
    data.append({"Account": "Total Liabilities", "Amount": format_currency(balance_sheet["liabilities"]["total"])})
    data.append({"Account": "", "Amount": ""})
    data.append({"Account": "EQUITY", "Amount": ""})
    data.append({"Account": "  Owner Equity", "Amount": format_currency(balance_sheet["equity"]["owner_equity"])})
    data.append({"Account": "  Retained Earnings", "Amount": format_currency(balance_sheet["equity"]["retained_earnings"])})
    data.append({"Account": "Total Equity", "Amount": format_currency(balance_sheet["equity"]["total"])})
    data.append({"Account": "", "Amount": ""})
    data.append({"Account": "Total Liabilities & Equity", "Amount": format_currency(balance_sheet["total_liabilities_and_equity"])})
    
    headers = ["Account", "Amount"]
    filename = f"{tenant_name}_balance_sheet_{as_of_date.strftime('%Y%m%d')}"
    
    if format == "excel":
        file_buffer = export_to_excel(data, headers, filename, f"Balance Sheet - {tenant_name} as of {as_of_date.strftime('%B %d, %Y')}")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file_ext = "xlsx"
    else:
        file_buffer = export_to_pdf(data, headers, filename, f"Balance Sheet as of {as_of_date.strftime('%B %d, %Y')}", tenant_name)
        media_type = "application/pdf"
        file_ext = "pdf"
    
    return StreamingResponse(
        io.BytesIO(file_buffer.read()),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{file_ext}"'}
    )


@router.get("/export/income-statement")
def export_income_statement(
    format: str = Query("pdf", regex="^(pdf|excel)$"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    truck_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Export income statement as PDF or Excel."""
    from app.services.accounting_service import uses_per_asset_accounting
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    per_asset = uses_per_asset_accounting(tenant)
    if per_asset and not truck_id:
        raise HTTPException(status_code=400, detail="truck_id is required for LS Logistics income statement")
    
    income_statement = generate_income_statement(db, tenant_id, start_date, end_date, truck_id)
    tenant_name = tenant.name if tenant else "Business"
    
    # Prepare data
    data = []
    data.append({"Item": "REVENUE", "Amount": ""})
    # Sum revenue categories for display
    total_revenue = income_statement.get("total_revenue", 0.0)
    if total_revenue == 0.0 and isinstance(income_statement.get("revenue"), dict):
        total_revenue = sum(income_statement["revenue"].values())
    # Show revenue categories if they exist
    if isinstance(income_statement.get("revenue"), dict) and income_statement["revenue"]:
        for rev_name, rev_amount in income_statement["revenue"].items():
            if rev_amount > 0:
                display_name = rev_name.replace("_", " ").title()
                data.append({"Item": f"  {display_name}", "Amount": format_currency(rev_amount)})
    else:
        data.append({"Item": "  Operating Revenue", "Amount": format_currency(total_revenue)})
    data.append({"Item": "Total Revenue", "Amount": format_currency(total_revenue)})
    data.append({"Item": "", "Amount": ""})
    data.append({"Item": "EXPENSES", "Amount": ""})
    
    # Sort expenses by amount descending
    expenses = sorted(income_statement["expenses"].items(), key=lambda x: x[1], reverse=True)
    for exp_name, exp_amount in expenses:
        if exp_amount > 0:
            display_name = exp_name.replace("_", " ").title()
            data.append({"Item": f"  {display_name}", "Amount": format_currency(exp_amount)})
    
    data.append({"Item": "Total Expenses", "Amount": format_currency(income_statement["total_expenses"])})
    data.append({"Item": "", "Amount": ""})
    net_income = income_statement["net_income"]
    data.append({"Item": "NET INCOME", "Amount": format_currency(net_income)})
    
    headers = ["Item", "Amount"]
    truck_suffix = f"_truck_{truck_id}" if truck_id else ""
    filename = f"{tenant_name}_income_statement_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}{truck_suffix}"
    
    if format == "excel":
        file_buffer = export_to_excel(data, headers, filename, f"Income Statement - {tenant_name} ({start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')})")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file_ext = "xlsx"
    else:
        file_buffer = export_to_pdf(data, headers, filename, f"Income Statement ({start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')})", tenant_name)
        media_type = "application/pdf"
        file_ext = "pdf"
    
    return StreamingResponse(
        io.BytesIO(file_buffer.read()),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{file_ext}"'}
    )


@router.get("/export/trial-balance")
def export_trial_balance(
    format: str = Query("csv", regex="^(csv|excel|pdf)$"),
    as_of_date: Optional[date] = Query(None),
    truck_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Export trial balance as CSV, Excel, or PDF."""
    from app.services.accounting_service import uses_per_asset_accounting
    
    if not as_of_date:
        as_of_date = date.today()
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    per_asset = uses_per_asset_accounting(tenant)
    
    query = db.query(ChartOfAccount).filter(ChartOfAccount.tenant_id == tenant_id)
    if per_asset:
        if truck_id:
            query = query.filter(ChartOfAccount.truck_id == truck_id)
        else:
            query = query.filter(ChartOfAccount.truck_id.isnot(None))
    else:
        query = query.filter(ChartOfAccount.truck_id.is_(None))
    
    accounts = query.order_by(ChartOfAccount.code).all()
    
    data = []
    total_debits = Decimal(0)
    total_credits = Decimal(0)
    
    for account in accounts:
        balance = calculate_account_balance(db, account.id, end_date=as_of_date, truck_id=truck_id)
        
        if account.account_type in ["Asset", "Expense"]:
            debit = balance if balance > 0 else Decimal(0)
            credit = -balance if balance < 0 else Decimal(0)
        else:
            credit = balance if balance > 0 else Decimal(0)
            debit = -balance if balance < 0 else Decimal(0)
        
        total_debits += debit
        total_credits += credit
        
        data.append({
            "Account Code": account.code,
            "Account Name": account.name,
            "Account Type": account.account_type,
            "Debit": float(debit),
            "Credit": float(credit),
        })
    
    # Add totals row
    data.append({
        "Account Code": "",
        "Account Name": "TOTAL",
        "Account Type": "",
        "Debit": float(total_debits),
        "Credit": float(total_credits),
    })
    
    headers = ["Account Code", "Account Name", "Account Type", "Debit", "Credit"]
    tenant_name = tenant.name if tenant else "Business"
    truck_suffix = f"_truck_{truck_id}" if truck_id else ""
    filename = f"{tenant_name}_trial_balance_{as_of_date.strftime('%Y%m%d')}{truck_suffix}"
    
    if format == "excel":
        file_buffer = export_to_excel(data, headers, filename, f"Trial Balance - {tenant_name} as of {as_of_date.strftime('%B %d, %Y')}")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file_ext = "xlsx"
    elif format == "pdf":
        file_buffer = export_to_pdf(data, headers, filename, f"Trial Balance as of {as_of_date.strftime('%B %d, %Y')}", tenant_name)
        media_type = "application/pdf"
        file_ext = "pdf"
    else:
        file_buffer = export_to_csv(data, headers, filename)
        media_type = "text/csv"
        file_ext = "csv"
    
    return StreamingResponse(
        io.BytesIO(file_buffer.read()),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{file_ext}"'}
    )


# Tax report endpoints
@router.get("/tax-year-summary")
def get_tax_year_summary(
    year: int = Query(...),
    truck_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Get tax year summary (Jan 1 - Dec 31) for a specific year."""
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    
    from app.services.accounting_service import uses_per_asset_accounting
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    per_asset = uses_per_asset_accounting(tenant)
    
    if per_asset and not truck_id:
        raise HTTPException(status_code=400, detail="truck_id is required for LS Logistics tax year summary")
    
    income_statement = generate_income_statement(db, tenant_id, start_date, end_date, truck_id)
    balance_sheet = generate_balance_sheet(db, tenant_id, end_date)
    
    # Get total revenue - use total_revenue if available, otherwise sum revenue categories
    total_revenue = income_statement.get("total_revenue", 0.0)
    if total_revenue == 0.0 and isinstance(income_statement.get("revenue"), dict):
        total_revenue = sum(income_statement["revenue"].values())
    
    return {
        "year": year,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "truck_id": truck_id,
        "revenue": {
            "total": float(total_revenue) if total_revenue else 0.0
        },
        "expenses": income_statement.get("expenses", {}),
        "total_expenses": income_statement.get("total_expenses", 0.0),
        "net_income": income_statement.get("net_income", 0.0),
        "account_balances": {
            "cash": balance_sheet["assets"]["cash"],
            "accounts_receivable": balance_sheet["assets"]["accounts_receivable"],
            "vehicles": balance_sheet["assets"]["vehicles"],
            "accumulated_depreciation": balance_sheet["assets"]["accumulated_depreciation"],
            "accounts_payable": balance_sheet["liabilities"]["accounts_payable"],
            "loans_payable": balance_sheet["liabilities"]["loans_payable"],
            "owner_equity": balance_sheet["equity"]["owner_equity"],
            "retained_earnings": balance_sheet["equity"]["retained_earnings"],
        }
    }


@router.get("/schedule-c")
def get_schedule_c(
    year: int = Query(...),
    truck_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Generate Schedule C format report for tax filing."""
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    
    from app.services.accounting_service import uses_per_asset_accounting
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    per_asset = uses_per_asset_accounting(tenant)
    
    if per_asset and not truck_id:
        raise HTTPException(status_code=400, detail="truck_id is required for LS Logistics Schedule C")
    
    income_statement = generate_income_statement(db, tenant_id, start_date, end_date, truck_id)
    
    # Map to Schedule C line items
    schedule_c = {
        "year": year,
        "business_name": tenant.name if tenant else "",
        "ein": tenant.ein if tenant else "",
        "line_1": income_statement["total_revenue"],  # Gross receipts or sales
        "line_27": income_statement["total_expenses"],  # Total expenses
        "line_31": income_statement["net_income"],  # Net profit or (loss)
        "expense_breakdown": {}
    }
    
    # Map expense categories to Schedule C lines (simplified mapping)
    expense_mapping = {
        "fuel": "Line 9 - Car and truck expenses",
        "driver_pay": "Line 26 - Wages",
        "payroll_fee": "Line 26 - Wages",
        "insurance": "Line 15 - Insurance",
        "repairs": "Line 9 - Car and truck expenses",
        "service_on_truck": "Line 9 - Car and truck expenses",
        "loan_interest": "Line 16 - Interest",
        "dispatch_fee": "Line 27 - Other expenses",
        "ifta": "Line 9 - Car and truck expenses",
        "prepass": "Line 9 - Car and truck expenses",
        "truck_parking": "Line 9 - Car and truck expenses",
        "safety": "Line 27 - Other expenses",
        "custom": "Line 27 - Other expenses",
    }
    
    for exp_name, exp_amount in income_statement["expenses"].items():
        if exp_amount > 0:
            line_desc = expense_mapping.get(exp_name, "Line 27 - Other expenses")
            if line_desc not in schedule_c["expense_breakdown"]:
                schedule_c["expense_breakdown"][line_desc] = 0
            schedule_c["expense_breakdown"][line_desc] += exp_amount
    
    return schedule_c


@router.post("/quick-entry/trailer-rental", response_model=JournalEntryResponse)
def create_trailer_rental_entry(
    amount: float = Query(..., description="Rental income amount"),
    entry_date: date = Query(..., description="Date of rental income"),
    description: Optional[str] = Query(None, description="Optional description"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Quick entry for trailer rental income.
    Creates: Debit Cash, Credit Trailer Rental Income (4100)
    """
    from app.models.chart_of_accounts import ChartOfAccount
    from app.services.accounting_service import get_or_create_account, get_cash_account_code
    
    # Ensure accounts exist
    from app.services.accounting_service import ensure_standard_accounts_exist
    ensure_standard_accounts_exist(db, tenant_id, truck_id=None)
    
    # Get or create accounts
    cash_account = get_or_create_account(db, get_cash_account_code(), "Cash", "Asset", tenant_id, truck_id=None)
    rental_income_account = get_or_create_account(db, "4100", "Trailer Rental Income", "Revenue", tenant_id, truck_id=None)
    
    # Create journal entry
    journal_entry = JournalEntry(
        tenant_id=tenant_id,
        truck_id=None,  # Shared account
        entry_date=entry_date,
        reference_type="manual",
        description=description or f"Trailer rental income - ${amount:.2f}"
    )
    db.add(journal_entry)
    db.flush()
    
    # Create lines
    lines = [
        {
            "journal_entry_id": journal_entry.id,
            "account_id": cash_account.id,
            "debit": amount,
            "credit": 0,
            "description": "Trailer rental received",
            "tenant_id": tenant_id
        },
        {
            "journal_entry_id": journal_entry.id,
            "account_id": rental_income_account.id,
            "debit": 0,
            "credit": amount,
            "description": "Trailer rental income",
            "tenant_id": tenant_id
        }
    ]
    
    # Validate
    from app.services.accounting_service import validate_journal_entry_lines
    is_valid, error_msg = validate_journal_entry_lines(lines, tenant_id, db, entry_tenant_id=tenant_id)
    if not is_valid:
        db.rollback()
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Create lines
    for line_data in lines:
        db_line = JournalEntryLine(**line_data)
        db.add(db_line)
    
    db.commit()
    db.refresh(journal_entry)
    return journal_entry


@router.post("/quick-entry/trailer-expense", response_model=JournalEntryResponse)
def create_trailer_expense_entry(
    amount: float = Query(..., description="Expense amount"),
    entry_date: date = Query(..., description="Date of expense"),
    description: str = Query(..., description="Expense description (e.g., 'Trailer parking', 'Trailer repair')"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Quick entry for trailer expenses (parking, repairs, etc.).
    Creates: Debit Trailer Expenses (5200), Credit Cash
    """
    from app.models.chart_of_accounts import ChartOfAccount
    from app.services.accounting_service import get_or_create_account, get_cash_account_code
    
    # Ensure accounts exist
    from app.services.accounting_service import ensure_standard_accounts_exist
    ensure_standard_accounts_exist(db, tenant_id, truck_id=None)
    
    # Get or create accounts
    cash_account = get_or_create_account(db, get_cash_account_code(), "Cash", "Asset", tenant_id, truck_id=None)
    trailer_expense_account = get_or_create_account(db, "5200", "Trailer Expenses", "Expense", tenant_id, truck_id=None)
    
    # Create journal entry
    journal_entry = JournalEntry(
        tenant_id=tenant_id,
        truck_id=None,  # Shared account
        entry_date=entry_date,
        reference_type="manual",
        description=description
    )
    db.add(journal_entry)
    db.flush()
    
    # Create lines
    lines = [
        {
            "journal_entry_id": journal_entry.id,
            "account_id": trailer_expense_account.id,
            "debit": amount,
            "credit": 0,
            "description": description,
            "tenant_id": tenant_id
        },
        {
            "journal_entry_id": journal_entry.id,
            "account_id": cash_account.id,
            "debit": 0,
            "credit": amount,
            "description": "Payment for trailer expense",
            "tenant_id": tenant_id
        }
    ]
    
    # Validate
    from app.services.accounting_service import validate_journal_entry_lines
    is_valid, error_msg = validate_journal_entry_lines(lines, tenant_id, db, entry_tenant_id=tenant_id)
    if not is_valid:
        db.rollback()
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Create lines
    for line_data in lines:
        db_line = JournalEntryLine(**line_data)
        db.add(db_line)
    
    db.commit()
    db.refresh(journal_entry)
    return journal_entry

