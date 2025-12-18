"""
Depreciation calculation service using MACRS (Modified Accelerated Cost Recovery System)
"""
from decimal import Decimal
from datetime import date, datetime
from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session
from app.models.truck import Truck
from app.models.chart_of_accounts import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from app.services.accounting_service import get_or_create_account, get_revenue_account_code
from app.utils.account_mapping import ACCUMULATED_DEPRECIATION_CODE


# MACRS 5-year property percentages (half-year convention)
MACRS_5_YEAR_PERCENTAGES = {
    1: Decimal('0.2000'),  # 20.00%
    2: Decimal('0.3200'),  # 32.00%
    3: Decimal('0.1920'),  # 19.20%
    4: Decimal('0.1152'),  # 11.52%
    5: Decimal('0.1152'),  # 11.52%
    6: Decimal('0.0576'),  # 5.76%
}


def calculate_cost_basis(truck: Truck) -> Decimal:
    """
    Calculate the depreciable cost basis for a truck.
    Cost basis = total_cost - section_179_deduction - bonus_depreciation_amount
    """
    if not truck.total_cost:
        return Decimal(0)
    
    total_cost = Decimal(str(truck.total_cost))
    section_179 = Decimal(str(truck.section_179_deduction or 0))
    
    # Calculate bonus depreciation amount
    bonus_pct = Decimal(str(truck.bonus_depreciation or 0)) / Decimal('100')
    remaining_after_s179 = total_cost - section_179
    bonus_amount = remaining_after_s179 * bonus_pct
    
    cost_basis = total_cost - section_179 - bonus_amount
    
    # If cost_basis is explicitly set, use that instead
    if truck.cost_basis:
        return Decimal(str(truck.cost_basis))
    
    return max(Decimal(0), cost_basis)


def get_depreciation_year(purchase_date: date, as_of_date: date) -> int:
    """
    Calculate which depreciation year we're in based on purchase date.
    Year 1 starts from purchase date, Year 2 starts 1 year later, etc.
    Uses half-year convention: first year is partial (6 months).
    """
    if purchase_date > as_of_date:
        return 0
    
    years_diff = as_of_date.year - purchase_date.year
    months_diff = as_of_date.month - purchase_date.month
    
    # If purchase month is after July, first year is shorter (half-year convention)
    # For simplicity, we'll use calendar years: Year 1 = purchase year, Year 2 = purchase year + 1, etc.
    # But adjust for half-year convention in first year
    
    if purchase_date.year == as_of_date.year:
        # Same year as purchase - Year 1 (partial year due to half-year convention)
        return 1
    else:
        # Calculate full years since purchase
        depreciation_year = years_diff + 1
        
        # Cap at 6 years for MACRS 5-year property
        return min(depreciation_year, 6)


def calculate_macrs_depreciation(
    cost_basis: Decimal,
    purchase_date: date,
    as_of_date: date
) -> Tuple[Decimal, int]:
    """
    Calculate MACRS 5-year depreciation for a given date.
    Returns (depreciation_amount, depreciation_year)
    """
    depreciation_year = get_depreciation_year(purchase_date, as_of_date)
    
    if depreciation_year == 0 or depreciation_year > 6:
        return (Decimal(0), 0)
    
    percentage = MACRS_5_YEAR_PERCENTAGES.get(depreciation_year, Decimal(0))
    annual_depreciation = cost_basis * percentage
    
    # For partial years, we need to calculate monthly depreciation
    # MACRS uses half-year convention, so Year 1 is always 6 months
    if depreciation_year == 1:
        # First year: only count months from purchase date to end of year
        # Then add full years, then partial year if applicable
        if purchase_date.year == as_of_date.year:
            # Still in first year - calculate monthly depreciation
            months_in_year = 12 - purchase_date.month + 1  # Months remaining in purchase year
            # Half-year convention: first year is 6 months max
            months_depreciated = min(months_in_year, 6)
            monthly_depreciation = annual_depreciation / Decimal('12')
            depreciation_amount = monthly_depreciation * Decimal(str(months_depreciated))
        else:
            # Past first year - use full year 1 amount
            depreciation_amount = annual_depreciation
    else:
        # Years 2-6: full year depreciation
        depreciation_amount = annual_depreciation
    
    return (depreciation_amount, depreciation_year)


def calculate_accumulated_depreciation(
    cost_basis: Decimal,
    purchase_date: date,
    as_of_date: date
) -> Decimal:
    """
    Calculate total accumulated depreciation from purchase date to as_of_date.
    Uses MACRS 5-year with half-year convention.
    """
    if not purchase_date or purchase_date > as_of_date:
        return Decimal(0)
    
    accumulated = Decimal(0)
    current_year = purchase_date.year
    target_year = as_of_date.year
    
    # Year 1: Half-year convention (assumes 6 months of depreciation in first year)
    if current_year == target_year:
        # Still in purchase year - calculate partial year
        # MACRS half-year convention: first year gets 6 months regardless of purchase month
        percentage = MACRS_5_YEAR_PERCENTAGES[1]
        accumulated = cost_basis * percentage
    else:
        # Past purchase year
        # Year 1: Full year 1 percentage (half-year convention already applied)
        accumulated = cost_basis * MACRS_5_YEAR_PERCENTAGES[1]
        
        # Years 2-6: Full year percentages
        for year_num in range(2, 7):
            if current_year + year_num - 1 < target_year:
                # Full year
                accumulated += cost_basis * MACRS_5_YEAR_PERCENTAGES.get(year_num, Decimal(0))
            elif current_year + year_num - 1 == target_year:
                # Partial year in current year (shouldn't happen with MACRS, but handle it)
                # For simplicity, if we're in the middle of a MACRS year, use full year percentage
                # MACRS doesn't typically prorate within a year
                accumulated += cost_basis * MACRS_5_YEAR_PERCENTAGES.get(year_num, Decimal(0))
                break
    
    # Cap at cost_basis
    return min(accumulated, cost_basis)


def calculate_straight_line_depreciation(
    cost_basis: Decimal,
    purchase_date: date,
    as_of_date: date,
    useful_life_years: int = 5
) -> Decimal:
    """
    Calculate straight-line depreciation.
    """
    if not purchase_date or purchase_date > as_of_date:
        return Decimal(0)
    
    annual_depreciation = cost_basis / Decimal(str(useful_life_years))
    
    # Calculate years and months
    years_diff = as_of_date.year - purchase_date.year
    months_diff = as_of_date.month - purchase_date.month
    total_months = years_diff * 12 + months_diff
    
    monthly_depreciation = annual_depreciation / Decimal('12')
    depreciation_amount = monthly_depreciation * Decimal(str(total_months))
    
    # Cap at cost_basis
    return min(depreciation_amount, cost_basis)


def calculate_depreciation_for_truck(
    truck: Truck,
    as_of_date: Optional[date] = None
) -> Optional[Decimal]:
    """
    Calculate depreciation for a truck based on its depreciation method.
    Returns accumulated depreciation amount including Section 179 and bonus depreciation.
    """
    if not as_of_date:
        as_of_date = date.today()
    
    if not truck.purchase_date or not truck.total_cost:
        return Decimal(0)
    
    if truck.depreciation_method == 'none' or not truck.depreciation_method:
        return Decimal(0)
    
    # Section 179 is an immediate deduction and should be included in accumulated depreciation
    section_179 = Decimal(str(truck.section_179_deduction or 0))
    
    # Calculate bonus depreciation amount
    total_cost = Decimal(str(truck.total_cost))
    bonus_pct = Decimal(str(truck.bonus_depreciation or 0)) / Decimal('100')
    remaining_after_s179 = total_cost - section_179
    bonus_amount = remaining_after_s179 * bonus_pct
    
    # Cost basis for MACRS calculation (after Section 179 and bonus depreciation)
    cost_basis = calculate_cost_basis(truck)
    
    # Calculate MACRS depreciation on the remaining cost basis
    macrs_depreciation = Decimal(0)
    if truck.depreciation_method == 'MACRS_5':
        macrs_depreciation = calculate_accumulated_depreciation(cost_basis, truck.purchase_date, as_of_date)
    elif truck.depreciation_method == 'straight_line':
        macrs_depreciation = calculate_straight_line_depreciation(cost_basis, truck.purchase_date, as_of_date)
    
    # Total accumulated depreciation = Section 179 + Bonus Depreciation + MACRS Depreciation
    # Note: Section 179 and bonus depreciation are taken immediately in the purchase year
    total_accumulated = section_179 + bonus_amount + macrs_depreciation
    
    # Cap at total_cost
    return min(total_accumulated, Decimal(str(truck.total_cost)))


def create_depreciation_journal_entry(
    db: Session,
    truck: Truck,
    depreciation_amount: Decimal,
    entry_date: date,
    tenant_id: int,
    description: Optional[str] = None
) -> JournalEntry:
    """
    Create a journal entry for depreciation expense.
    Debit: Depreciation Expense
    Credit: Accumulated Depreciation - Vehicles
    """
    if not description:
        description = f"Depreciation expense for {truck.name} - {entry_date.strftime('%B %Y')}"
    
    # Get or create accounts
    depreciation_expense_account = get_or_create_account(
        db, "6013", "Depreciation Expense", "Expense", tenant_id, truck_id=truck.id
    )
    accumulated_dep_account = get_or_create_account(
        db, ACCUMULATED_DEPRECIATION_CODE, "Accumulated Depreciation - Vehicles", "Asset", tenant_id, truck_id=truck.id
    )
    
    # Create journal entry
    journal_entry = JournalEntry(
        tenant_id=tenant_id,
        truck_id=truck.id,
        entry_date=entry_date,
        description=description,
        reference_type="depreciation",
        reference_id=truck.id
    )
    db.add(journal_entry)
    db.flush()
    
    # Create debit line (Depreciation Expense)
    debit_line = JournalEntryLine(
        tenant_id=tenant_id,
        truck_id=truck.id,
        journal_entry_id=journal_entry.id,
        account_id=depreciation_expense_account.id,
        debit=float(depreciation_amount),
        credit=0.0,
        description=description
    )
    db.add(debit_line)
    
    # Create credit line (Accumulated Depreciation)
    credit_line = JournalEntryLine(
        tenant_id=tenant_id,
        truck_id=truck.id,
        journal_entry_id=journal_entry.id,
        account_id=accumulated_dep_account.id,
        debit=0.0,
        credit=float(depreciation_amount),
        description=description
    )
    db.add(credit_line)
    
    db.commit()
    return journal_entry

