"""
Analytics router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.database import get_db
from app.models.settlement import Settlement
from app.models.repair import Repair
from app.models.truck import Truck
from app.dependencies import get_tenant_id
from app.services.diesel_price_service import get_historical_diesel_price
from app.services.loan_balance_service import calculate_loan_metrics_for_truck
from typing import List, Dict, Optional
from datetime import datetime, timedelta, date
from collections import defaultdict

router = APIRouter()


def _safe_per_mile(amount: float, miles: float) -> Optional[float]:
    if miles <= 0:
        return None
    return round(amount / miles, 2)


def _extract_raw_gross_amount(settlement: Settlement) -> float:
    if settlement.overview_amounts and isinstance(settlement.overview_amounts, dict):
        raw_gross = settlement.overview_amounts.get("gross_before_dispatch", 0)
        try:
            raw_gross_float = float(raw_gross or 0)
            if raw_gross_float > 0:
                return raw_gross_float
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _calculate_operational_metrics(
    post_dispatch_revenue: float,
    settlement_expenses: float,
    repair_costs: float,
    miles_driven: float,
    raw_gross_revenue: float = 0.0,
    raw_gross_miles_driven: float = 0.0,
) -> Dict[str, Optional[float]]:
    return {
        "miles_driven": round(miles_driven, 2),
        "post_dispatch_revenue": round(post_dispatch_revenue, 2),
        "settlement_expenses": round(settlement_expenses, 2),
        "repair_costs": round(repair_costs, 2),
        "raw_gross_revenue": round(raw_gross_revenue, 2),
        "raw_gross_miles_driven": round(raw_gross_miles_driven, 2),
        "post_dispatch_revenue_per_mile": _safe_per_mile(post_dispatch_revenue, miles_driven),
        "raw_gross_revenue_per_mile": _safe_per_mile(raw_gross_revenue, raw_gross_miles_driven),
        "settlement_cost_per_mile": _safe_per_mile(settlement_expenses, miles_driven),
        "all_in_cost_per_mile": _safe_per_mile(settlement_expenses + repair_costs, miles_driven),
    }

def get_current_mileage(truck_id: int, db: Session) -> Optional[float]:
    """
    Get the current mileage for a truck.
    Returns the most recent repair's miles value, or None if no repair has miles recorded.
    """
    # Get the most recent repair with miles recorded
    latest_repair_with_miles = db.query(Repair).filter(
        Repair.truck_id == truck_id,
        Repair.miles.isnot(None)
    ).order_by(
        Repair.repair_date.desc().nullslast(),
        Repair.created_at.desc()
    ).first()
    
    if latest_repair_with_miles and latest_repair_with_miles.miles:
        return float(latest_repair_with_miles.miles)
    
    return None

@router.get("/truck-profit/{truck_id}")
def get_truck_profit(truck_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Calculate profit per truck (settlements - repairs)"""
    # Verify truck belongs to tenant
    truck = db.query(Truck).filter(Truck.id == truck_id, Truck.tenant_id == tenant_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    # Get total settlements
    settlements_total = db.query(
        func.sum(Settlement.net_profit).label("total")
    ).filter(Settlement.truck_id == truck_id).scalar() or 0
    
    # Get total repairs
    repairs_total = db.query(
        func.sum(Repair.cost).label("total")
    ).filter(Repair.truck_id == truck_id).scalar() or 0
    
    net_profit = float(settlements_total) - float(repairs_total)
    
    return {
        "truck_id": truck_id,
        "settlements_total": float(settlements_total),
        "repairs_total": float(repairs_total),
        "net_profit": net_profit
    }

@router.get("/vehicle/{truck_id}/roi")
def get_vehicle_roi(truck_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """Calculate ROI metrics for a specific vehicle (truck or trailer)"""
    # Get the vehicle (verify it belongs to tenant)
    vehicle = db.query(Truck).filter(Truck.id == truck_id, Truck.tenant_id == tenant_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Get cumulative net profit (revenue - settlement expenses - repairs)
    vehicle_settlements = db.query(Settlement).filter(Settlement.truck_id == truck_id)
    vehicle_repairs = db.query(Repair).filter(Repair.truck_id == truck_id)
    
    revenue = vehicle_settlements.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    settlement_expenses = vehicle_settlements.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    repair_costs = vehicle_repairs.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    # Get investment fields
    cash_investment = float(vehicle.cash_investment) if vehicle.cash_investment else None
    loan_amount = float(vehicle.loan_amount) if vehicle.loan_amount else None
    interest_rate = float(vehicle.interest_rate) if vehicle.interest_rate else 0.07  # Default 7%
    loan_term_months = int(vehicle.loan_term_months) if vehicle.loan_term_months else None
    trailer_depreciation_reserve_amount = (
        float(vehicle.trailer_depreciation_reserve_amount)
        if vehicle.trailer_depreciation_reserve_amount is not None
        else (160.0 if vehicle.vehicle_type == "trailer" else None)
    )
    total_cost = float(vehicle.total_cost) if vehicle.total_cost else None
    registration_fee = float(vehicle.registration_fee) if vehicle.registration_fee else None
    loan_metrics = calculate_loan_metrics_for_truck(db, vehicle)
    
    # Calculate cumulative loan interest from stored settlement data
    # Interest is stored in expense_categories["loan_interest"] for each settlement
    cumulative_loan_interest = 0.0
    settlements_list = vehicle_settlements.all()
    for settlement in settlements_list:
        if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
            loan_interest = settlement.expense_categories.get("loan_interest", 0)
            if loan_interest:
                cumulative_loan_interest += float(loan_interest)
    
    # Net profit: revenue - settlement expenses (which already includes loan interest) - repairs
    # Note: settlement_expenses already includes loan_interest, so we don't subtract it again
    cumulative_net_profit = float(revenue) - float(settlement_expenses) - float(repair_costs)
    
    # Calculate cash recovery metrics (based on cash_investment only)
    cash_recovery_percentage = None
    cash_recovery_amount = None
    cash_recovery_achieved = False
    remaining_to_cash_recovery = None
    
    if cash_investment and cash_investment > 0:
        # Cash recovery amount is capped at cash_investment
        cash_recovery_amount = min(cumulative_net_profit, cash_investment)
        cash_recovery_percentage = (cash_recovery_amount / cash_investment) * 100
        cash_recovery_achieved = cumulative_net_profit >= cash_investment
        remaining_to_cash_recovery = max(0.0, cash_investment - cumulative_net_profit)
    
    # Calculate loan balance dynamically based on current cumulative net profit
    # Excess profit after cash recovery goes toward loan principal
    principal_paid_from_excess = 0.0
    calculated_loan_balance = None
    
    if vehicle.vehicle_type in ['truck', 'trailer'] and loan_amount and loan_amount > 0:
        calculated_loan_balance = loan_metrics["current_loan_balance"]
        if calculated_loan_balance is None:
            calculated_loan_balance = loan_amount
        principal_paid_from_excess = loan_metrics["principal_paid_total"]
    
    # Calculate ROI metrics based on total_cost (which includes cash, loan, and registration)
    investment_recovery_percentage = None
    remaining_to_break_even = None
    break_even_achieved = False
    
    if total_cost and total_cost > 0:
        investment_recovery_percentage = (cumulative_net_profit / total_cost) * 100
        remaining_to_break_even = max(0.0, total_cost - cumulative_net_profit)
        break_even_achieved = cumulative_net_profit >= total_cost
    
    # Calculate clean cash return (profit after cash + loan fully recovered)
    # This is the "overflow" profit after all investments are recovered
    clean_cash_return = None
    loan_fully_paid = calculated_loan_balance is not None and calculated_loan_balance == 0.0
    
    if cash_recovery_achieved and loan_fully_paid:
        # Clean cash = cumulative profit - cash investment - loan amount
        # This represents pure profit after all debts and investments are recovered
        total_recovered = (cash_investment or 0.0) + (loan_amount or 0.0)
        clean_cash_return = max(0.0, cumulative_net_profit - total_recovered)

    trailer_settlement_count = 0
    trailer_depreciation_reserve_total = None
    trailer_free_profit = None
    trailer_cash_position_total = None
    trailer_break_even_sale_price = None
    trailer_projected_three_year_reserve = None

    if vehicle.vehicle_type == "trailer":
        trailer_settlement_count = len([
            settlement for settlement in settlements_list
            if float(settlement.gross_revenue or 0) > 0
        ])
        weekly_reserve = float(trailer_depreciation_reserve_amount or 0.0)
        trailer_depreciation_reserve_total = round(weekly_reserve * trailer_settlement_count, 2)
        trailer_free_profit = round(cumulative_net_profit - trailer_depreciation_reserve_total, 2)
        trailer_cash_position_total = round(trailer_depreciation_reserve_total + trailer_free_profit, 2)

        current_balance_for_sale = calculated_loan_balance
        if current_balance_for_sale is None:
            current_balance_for_sale = loan_amount or 0.0
        owner_cash_basis = max(0.0, (total_cost or 0.0) - (loan_amount or 0.0))
        trailer_break_even_sale_price = round(
            max(0.0, current_balance_for_sale + owner_cash_basis - cumulative_net_profit),
            2,
        )
        trailer_projected_three_year_reserve = round(weekly_reserve * 156, 2)
    
    return {
        "vehicle_id": truck_id,
        "vehicle_name": vehicle.name,
        "vehicle_type": vehicle.vehicle_type,
        "cash_investment": cash_investment,
        "loan_amount": loan_amount,
        "loan_term_months": loan_term_months,
        "trailer_depreciation_reserve_amount": trailer_depreciation_reserve_amount,
        "loan_payoff_date": loan_metrics["loan_payoff_date"],
        "projected_payoff_date": loan_metrics["projected_payoff_date"],
        "estimated_settlements_to_payoff": loan_metrics["estimated_settlements_to_payoff"],
        "average_principal_payment": loan_metrics["average_principal_payment"],
        "latest_settlement_date": loan_metrics["latest_settlement_date"],
        "current_loan_balance": round(calculated_loan_balance, 2) if calculated_loan_balance is not None else None,
        "principal_paid_from_excess": round(principal_paid_from_excess, 2),
        "interest_rate": interest_rate,
        "total_cost": total_cost,
        "registration_fee": registration_fee,
        "cumulative_revenue": float(revenue),
        "cumulative_settlement_expenses": float(settlement_expenses),
        "cumulative_repair_costs": float(repair_costs),
        "cumulative_loan_interest": round(cumulative_loan_interest, 2),
        "cumulative_net_profit": round(cumulative_net_profit, 2),
        "trailer_settlement_count": trailer_settlement_count,
        "trailer_depreciation_reserve_total": trailer_depreciation_reserve_total,
        "trailer_free_profit": trailer_free_profit,
        "trailer_cash_position_total": trailer_cash_position_total,
        "trailer_break_even_sale_price": trailer_break_even_sale_price,
        "trailer_projected_three_year_reserve": trailer_projected_three_year_reserve,
        "cash_recovery_percentage": round(cash_recovery_percentage, 2) if cash_recovery_percentage is not None else None,
        "cash_recovery_amount": round(cash_recovery_amount, 2) if cash_recovery_amount is not None else None,
        "cash_recovery_achieved": cash_recovery_achieved,
        "remaining_to_cash_recovery": round(remaining_to_cash_recovery, 2) if remaining_to_cash_recovery is not None else None,
        "clean_cash_return": round(clean_cash_return, 2) if clean_cash_return is not None else None,
        "investment_recovery_percentage": round(investment_recovery_percentage, 2) if investment_recovery_percentage is not None else None,
        "remaining_to_break_even": round(remaining_to_break_even, 2) if remaining_to_break_even is not None else None,
        "break_even_achieved": break_even_achieved
    }

@router.get("/dashboard")
def get_dashboard(
    truck_id: int = None, 
    vehicle_type: Optional[str] = None, 
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """Get dashboard summary data with expense categories. Separates trucks and trailers."""
    import traceback
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        return _get_dashboard_impl(truck_id, vehicle_type, db, tenant_id)
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Dashboard error: {error_trace}")
        print(f"DASHBOARD ERROR: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}\n\nTraceback:\n{error_trace}")

def _get_dashboard_impl(truck_id: int, vehicle_type: Optional[str], db: Session, tenant_id: int):
    """Internal implementation of dashboard endpoint."""
    # Build queries with tenant filter
    trucks_query = db.query(Truck).filter(Truck.tenant_id == tenant_id)
    settlements_query = db.query(Settlement).join(Truck).filter(Truck.tenant_id == tenant_id)
    repairs_query = db.query(Repair).join(Truck).filter(Truck.tenant_id == tenant_id)
    
    if truck_id is not None:
        trucks_query = trucks_query.filter(Truck.id == truck_id)
        settlements_query = settlements_query.filter(Settlement.truck_id == truck_id)
        repairs_query = repairs_query.filter(Repair.truck_id == truck_id)
    
    if truck_id is None and vehicle_type:
        vt = vehicle_type.lower()
        if vt in ["truck", "trailer"]:
            trucks_query = trucks_query.filter(Truck.vehicle_type == vt)
            # Already joined Truck above, just add filter
            settlements_query = settlements_query.filter(Truck.vehicle_type == vt)
            repairs_query = repairs_query.filter(Truck.vehicle_type == vt)
    
    # Separate trucks and trailers queries
    trucks_only_query = trucks_query.filter(Truck.vehicle_type == 'truck')
    trailers_only_query = trucks_query.filter(Truck.vehicle_type == 'trailer')
    
    # Get truck totals
    truck_ids = [t.id for t in trucks_only_query.all()]
    trailer_ids = [t.id for t in trailers_only_query.all()]
    
    truck_settlements_query = settlements_query.filter(Settlement.truck_id.in_(truck_ids)) if truck_ids else settlements_query.filter(False)
    trailer_settlements_query = settlements_query.filter(Settlement.truck_id.in_(trailer_ids)) if trailer_ids else settlements_query.filter(False)
    
    truck_repairs_query = repairs_query.filter(Repair.truck_id.in_(truck_ids)) if truck_ids else repairs_query.filter(False)
    trailer_repairs_query = repairs_query.filter(Repair.truck_id.in_(trailer_ids)) if trailer_ids else repairs_query.filter(False)
    
    # Get totals for trucks
    total_trucks = trucks_only_query.count()
    truck_settlements_count = truck_settlements_query.count()
    truck_revenue = truck_settlements_query.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    truck_expenses = truck_settlements_query.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    truck_repairs_cost = truck_repairs_query.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    # Get totals for trailers
    total_trailers = trailers_only_query.count()
    trailer_settlements_count = trailer_settlements_query.count()
    trailer_revenue = trailer_settlements_query.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    trailer_expenses = trailer_settlements_query.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    trailer_repairs_cost = trailer_repairs_query.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    # Combined totals (for backward compatibility)
    total_settlements = settlements_query.count()
    total_revenue = settlements_query.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    total_expenses = settlements_query.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    total_repairs_cost = repairs_query.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    # Standard expense categories
    STANDARD_CATEGORIES = [
        "fuel", "tolls", "dispatch_fee", "insurance", "safety", "prepass", "ifta",
        "deduct",
        "driver_pay", "payroll_fee", "loan_interest", "truck_parking", "service_on_truck"
    ]
    
    # Helper function to calculate expense categories for a set of settlements
    def calculate_expense_categories(settlements_list, repairs_list):
        """Calculate expense categories from settlements and repairs"""
        expense_cats = {
            "fuel": 0.0,
            "tolls": 0.0,
            "dispatch_fee": 0.0,
            "insurance": 0.0,
            "safety": 0.0,
            "prepass": 0.0,
            "ifta": 0.0,
            "deduct": 0.0,
            "driver_pay": 0.0,
            "payroll_fee": 0.0,
            "loan_interest": 0.0,
            "truck_parking": 0.0,
            "service_on_truck": 0.0,
            "repairs": 0.0,
            "custom": 0.0
        }
        custom_descs = {}
        
        def extract_custom_description(category_key: str) -> str:
            if category_key.startswith("custom_"):
                desc = category_key.replace("custom_", "")
                return " ".join(word.capitalize() for word in desc.split("_"))
            return "Custom"
        
        # Add expenses from settlements
        for settlement in settlements_list:
            if settlement.expense_categories and isinstance(settlement.expense_categories, dict) and len(settlement.expense_categories) > 0:
                for category, amount in settlement.expense_categories.items():
                    try:
                        # Skip reimbursements - they're credits, not expenses
                        if category == "reimbursement":
                            continue
                            
                        amount_float = float(amount) if amount is not None else 0.0
                        if amount_float > 0:
                            if category == "fees" or category == "other":
                                expense_cats["custom"] += amount_float
                            elif category in expense_cats:
                                expense_cats[category] += amount_float
                            elif category.startswith("custom_"):
                                expense_cats["custom"] += amount_float
                                if category not in custom_descs:
                                    custom_descs[category] = extract_custom_description(category)
                            else:
                                expense_cats["custom"] += amount_float
                                # Extract description from deduction_details or reimbursement_details if available
                                description = None
                                if category == "deduct" and settlement.deduction_details:
                                    descriptions = [
                                        d.get("description", "").strip() 
                                        for d in settlement.deduction_details 
                                        if d.get("description") and d.get("description").strip()
                                    ]
                                    if descriptions:
                                        description = "; ".join(descriptions)
                                
                                if category not in custom_descs:
                                    if description:
                                        # Store description with category key for reference
                                        custom_descs[category] = description
                                    else:
                                        custom_descs[category] = extract_custom_description(category)
                                elif description and not custom_descs[category].endswith(description):
                                    # Append description if not already included
                                    existing = custom_descs[category]
                                    if description not in existing:
                                        custom_descs[category] = f"{existing}; {description}"
                    except (ValueError, TypeError):
                        continue
            elif settlement.expenses and float(settlement.expenses) > 0:
                expense_cats["custom"] += float(settlement.expenses)
        
        # Add repairs
        for repair in repairs_list:
            if repair.cost:
                expense_cats["repairs"] += float(repair.cost)
        
        return expense_cats, custom_descs
    
    def calculate_operational_metrics_for_settlements(settlements_list, repair_costs: float):
        miles_driven = 0.0
        post_dispatch_revenue = 0.0
        settlement_expenses = 0.0
        raw_gross_revenue = 0.0
        raw_gross_miles_driven = 0.0

        for settlement in settlements_list:
            miles = float(settlement.miles_driven) if settlement.miles_driven else 0.0
            revenue = float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
            expenses = float(settlement.expenses) if settlement.expenses else 0.0
            raw_gross = _extract_raw_gross_amount(settlement)

            miles_driven += miles
            post_dispatch_revenue += revenue
            settlement_expenses += expenses

            if raw_gross > 0:
                raw_gross_revenue += raw_gross
                raw_gross_miles_driven += miles

        return _calculate_operational_metrics(
            post_dispatch_revenue=post_dispatch_revenue,
            settlement_expenses=settlement_expenses,
            repair_costs=float(repair_costs or 0.0),
            miles_driven=miles_driven,
            raw_gross_revenue=raw_gross_revenue,
            raw_gross_miles_driven=raw_gross_miles_driven,
        )

    # Calculate expense categories separately for trucks and trailers
    truck_settlements = truck_settlements_query.all()
    trailer_settlements = trailer_settlements_query.all()
    truck_repairs = truck_repairs_query.all()
    trailer_repairs = trailer_repairs_query.all()
    
    truck_expense_categories, truck_custom_descriptions = calculate_expense_categories(truck_settlements, truck_repairs)
    trailer_expense_categories, trailer_custom_descriptions = calculate_expense_categories(trailer_settlements, trailer_repairs)
    truck_operational_metrics = calculate_operational_metrics_for_settlements(truck_settlements, float(truck_repairs_cost))
    trailer_operational_metrics = calculate_operational_metrics_for_settlements(trailer_settlements, float(trailer_repairs_cost))
    
    # Combined expense categories (for backward compatibility)
    expense_categories = {
        "fuel": truck_expense_categories["fuel"] + trailer_expense_categories["fuel"],
        "tolls": truck_expense_categories["tolls"] + trailer_expense_categories["tolls"],
        "dispatch_fee": truck_expense_categories["dispatch_fee"] + trailer_expense_categories["dispatch_fee"],
        "insurance": truck_expense_categories["insurance"] + trailer_expense_categories["insurance"],
        "safety": truck_expense_categories["safety"] + trailer_expense_categories["safety"],
        "prepass": truck_expense_categories["prepass"] + trailer_expense_categories["prepass"],
        "ifta": truck_expense_categories["ifta"] + trailer_expense_categories["ifta"],
        "deduct": truck_expense_categories["deduct"] + trailer_expense_categories["deduct"],
        "driver_pay": truck_expense_categories["driver_pay"] + trailer_expense_categories["driver_pay"],
        "payroll_fee": truck_expense_categories["payroll_fee"] + trailer_expense_categories["payroll_fee"],
        "loan_interest": truck_expense_categories["loan_interest"] + trailer_expense_categories["loan_interest"],
        "truck_parking": truck_expense_categories["truck_parking"] + trailer_expense_categories["truck_parking"],
        "service_on_truck": truck_expense_categories["service_on_truck"] + trailer_expense_categories["service_on_truck"],
        "repairs": truck_expense_categories["repairs"] + trailer_expense_categories["repairs"],
        "custom": truck_expense_categories["custom"] + trailer_expense_categories["custom"]
    }
    
    # Merge custom descriptions
    custom_descriptions = {**truck_custom_descriptions, **trailer_custom_descriptions}
    
    # Calculate net profits
    truck_expenses_sum = sum(truck_expense_categories.values())
    trailer_expenses_sum = sum(trailer_expense_categories.values())
    truck_net_profit = float(truck_revenue) - float(truck_expenses_sum)
    trailer_net_profit = float(trailer_revenue) - float(trailer_expenses_sum)
    
    # Combined net profit (for backward compatibility)
    total_expenses_sum = sum(expense_categories.values())
    net_profit = float(total_revenue) - float(total_expenses_sum)
    combined_operational_metrics = _calculate_operational_metrics(
        post_dispatch_revenue=float(total_revenue),
        settlement_expenses=float(truck_expenses + trailer_expenses),
        repair_costs=float(total_repairs_cost),
        miles_driven=truck_operational_metrics["miles_driven"] + trailer_operational_metrics["miles_driven"],
        raw_gross_revenue=truck_operational_metrics["raw_gross_revenue"] + trailer_operational_metrics["raw_gross_revenue"],
        raw_gross_miles_driven=truck_operational_metrics["raw_gross_miles_driven"] + trailer_operational_metrics["raw_gross_miles_driven"],
    )
    
    # Get truck profits (only trucks, not trailers)
    truck_profits = []
    trucks = trucks_only_query.all()
    for truck in trucks:
        truck_settlements = db.query(Settlement).filter(Settlement.truck_id == truck.id)
        truck_repairs = db.query(Repair).filter(Repair.truck_id == truck.id)
        
        truck_revenue = truck_settlements.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
        truck_expenses = truck_settlements.with_entities(func.sum(Settlement.expenses)).scalar() or 0
        truck_repairs_cost = truck_repairs.with_entities(func.sum(Repair.cost)).scalar() or 0
        
        # Calculate profit before repairs (revenue - settlement expenses only)
        profit_before_repairs = float(truck_revenue) - float(truck_expenses)
        
        truck_profits.append({
            "truck_id": truck.id,
            "truck_name": truck.name,
            "license_plate": truck.license_plate,
            "vin": truck.vin,
            "total_revenue": float(truck_revenue),
            "total_expenses": float(truck_expenses) + float(truck_repairs_cost),
            "settlement_expenses": float(truck_expenses),
            "repair_costs": float(truck_repairs_cost),
            "profit_before_repairs": profit_before_repairs,
            "net_profit": float(truck_revenue) - float(truck_expenses) - float(truck_repairs_cost)
        })
    
    # Get trailer profits
    trailer_profits = []
    trailers = trailers_only_query.all()
    for trailer in trailers:
        trailer_settlements = db.query(Settlement).filter(Settlement.truck_id == trailer.id)
        trailer_repairs = db.query(Repair).filter(Repair.truck_id == trailer.id)
        
        trailer_revenue = trailer_settlements.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
        trailer_expenses = trailer_settlements.with_entities(func.sum(Settlement.expenses)).scalar() or 0
        trailer_repairs_cost = trailer_repairs.with_entities(func.sum(Repair.cost)).scalar() or 0
        
        # Calculate profit before repairs (revenue - settlement expenses only)
        profit_before_repairs = float(trailer_revenue) - float(trailer_expenses)
        
        trailer_profits.append({
            "truck_id": trailer.id,
            "truck_name": trailer.name,
            "tag_number": trailer.tag_number,
            "vin": trailer.vin,
            "total_revenue": float(trailer_revenue),
            "total_expenses": float(trailer_expenses) + float(trailer_repairs_cost),
            "settlement_expenses": float(trailer_expenses),
            "repair_costs": float(trailer_repairs_cost),
            "profit_before_repairs": profit_before_repairs,
            "net_profit": float(trailer_revenue) - float(trailer_expenses) - float(trailer_repairs_cost)
        })
    
    # Get blocks by truck and month
    blocks_by_truck_month = []
    trucks_for_blocks = trucks_query.all()
    
    for truck in trucks_for_blocks:
        truck_settlements = db.query(Settlement).filter(Settlement.truck_id == truck.id)
        if truck_id is not None:
            # Already filtered above
            pass
        
        # Group settlements by month using individual block delivery dates when available,
        # otherwise split proportionally based on period dates
        settlements_by_month = {}
        
        def assign_blocks_by_delivery_dates(block_ids: list) -> dict:
            """
            Assign blocks to months based on individual delivery dates.
            Returns dict mapping month_key to (blocks_count, block_ids_list, month_label)
            """
            result = {}
            
            for block_item in block_ids:
                # Handle both formats: string or object with delivery_date
                if isinstance(block_item, str):
                    # Legacy format: just block ID string, skip (no date info)
                    continue
                elif isinstance(block_item, dict):
                    block_id = block_item.get("block_id", "")
                    delivery_date_str = block_item.get("delivery_date")
                    
                    if not block_id or not delivery_date_str:
                        continue
                    
                    # Parse delivery date
                    try:
                        delivery_date = datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        continue
                    
                    month_key = delivery_date.strftime("%Y-%m")
                    month_label = delivery_date.strftime("%b %Y")
                    
                    if month_key not in result:
                        result[month_key] = {
                            "blocks": 0,
                            "block_ids": [],
                            "month": month_label
                        }
                    
                    result[month_key]["blocks"] += 1
                    # Preserve the full block object with delivery_date for frontend display
                    result[month_key]["block_ids"].append({
                        "block_id": block_id,
                        "delivery_date": delivery_date_str
                    })
            
            return result
        
        def split_blocks_by_calendar_months(period_start: date, period_end: date, 
                                           blocks_count: int, block_ids: list) -> dict:
            """
            Split blocks across calendar months based on period dates.
            Returns dict mapping month_key to (blocks_count, block_ids_list)
            """
            if not period_start or not period_end:
                return {}
            
            result = {}
            current_date = period_start
            total_days = (period_end - period_start).days + 1  # Inclusive
            
            # Track days and blocks per month
            month_data = {}
            
            while current_date <= period_end:
                month_key = current_date.strftime("%Y-%m")
                month_label = current_date.strftime("%b %Y")
                
                if month_key not in month_data:
                    month_data[month_key] = {
                        "month": month_label,
                        "month_key": month_key,
                        "days": 0
                    }
                
                month_data[month_key]["days"] += 1
                current_date = current_date + timedelta(days=1)
            
            # Distribute blocks proportionally
            total_blocks_assigned = 0
            total_block_ids_assigned = 0
            
            month_keys_sorted = sorted(month_data.keys())
            for idx, month_key in enumerate(month_keys_sorted):
                month_info = month_data[month_key]
                days_in_month = month_info["days"]
                proportion = days_in_month / total_days
                
                # Calculate blocks for this month (round to nearest integer)
                blocks_for_month = round(blocks_count * proportion)
                
                # For the last month, assign remaining blocks to ensure total matches
                if idx == len(month_keys_sorted) - 1:
                    blocks_for_month = blocks_count - total_blocks_assigned
                else:
                    total_blocks_assigned += blocks_for_month
                
                # Distribute block IDs proportionally
                block_ids_for_month = []
                if block_ids:
                    block_ids_count = round(len(block_ids) * proportion)
                    if idx == len(month_keys_sorted) - 1:
                        # Last month gets remaining block IDs
                        block_ids_for_month = block_ids[total_block_ids_assigned:]
                    else:
                        block_ids_for_month = block_ids[total_block_ids_assigned:total_block_ids_assigned + block_ids_count]
                        total_block_ids_assigned += block_ids_count
                
                if blocks_for_month > 0:
                    result[month_key] = {
                        "blocks": blocks_for_month,
                        "block_ids": block_ids_for_month,
                        "month": month_info["month"]
                    }
            
            return result
        
        for settlement in truck_settlements.all():
            if settlement.blocks_delivered and settlement.blocks_delivered > 0:
                block_ids = settlement.block_ids if settlement.block_ids and isinstance(settlement.block_ids, list) else []
                
                # Separate blocks with delivery dates from those without
                blocks_with_dates = []
                blocks_without_dates = []
                
                for item in block_ids:
                    if isinstance(item, dict) and item.get("delivery_date"):
                        blocks_with_dates.append(item)
                    elif isinstance(item, dict) and "block_id" in item:
                        # Block object but no delivery_date - extract block_id for fallback
                        blocks_without_dates.append(item.get("block_id", ""))
                    elif isinstance(item, str):
                        # Legacy format - string block ID
                        blocks_without_dates.append(item)
                
                # Start with blocks that have delivery dates
                month_splits = assign_blocks_by_delivery_dates(blocks_with_dates) if blocks_with_dates else {}
                
                # If there are blocks without delivery dates, use proportional splitting for them
                if blocks_without_dates:
                    period_start = settlement.week_start  # This is period_start from JSON
                    period_end = settlement.week_end if settlement.week_end else settlement.settlement_date
                    
                    # If we don't have period dates, fall back to settlement_date
                    if not period_start:
                        period_start = settlement.settlement_date
                    if not period_end:
                        period_end = settlement.settlement_date
                    
                    # Calculate how many blocks we've already assigned
                    blocks_already_assigned = sum(split_data["blocks"] for split_data in month_splits.values())
                    blocks_needing_assignment = len(blocks_without_dates)
                    
                    # Use proportional splitting for blocks without dates
                    proportional_splits = split_blocks_by_calendar_months(
                        period_start,
                        period_end,
                        blocks_needing_assignment,
                        blocks_without_dates
                    )
                    
                    # Merge proportional splits into month_splits
                    for month_key, split_data in proportional_splits.items():
                        if month_key not in month_splits:
                            month_splits[month_key] = {
                                "blocks": 0,
                                "block_ids": [],
                                "month": split_data["month"]
                            }
                        month_splits[month_key]["blocks"] += split_data["blocks"]
                        # Add block IDs as strings (no delivery dates available)
                        month_splits[month_key]["block_ids"].extend([
                            bid if isinstance(bid, str) else {"block_id": bid, "delivery_date": None}
                            for bid in split_data["block_ids"]
                        ])
                
                # Add to settlements_by_month
                for month_key, split_data in month_splits.items():
                    # Filter out future months (beyond current date)
                    current_date = date.today()
                    month_date = date(int(month_key[:4]), int(month_key[5:7]), 1)
                    if month_date > current_date.replace(day=1):
                        continue  # Skip future months
                    
                    if month_key not in settlements_by_month:
                        settlements_by_month[month_key] = {
                            "month": split_data["month"],
                            "month_key": month_key,
                            "blocks": 0,
                            "block_ids": []
                        }
                    
                    settlements_by_month[month_key]["blocks"] += split_data["blocks"]
                    settlements_by_month[month_key]["block_ids"].extend(split_data["block_ids"])
        
        # Convert to list and sort by month
        for month_key in sorted(settlements_by_month.keys()):
            blocks_by_truck_month.append({
                "truck_id": truck.id,
                "truck_name": truck.name,
                "month": settlements_by_month[month_key]["month"],
                "month_key": settlements_by_month[month_key]["month_key"],
                "blocks": settlements_by_month[month_key]["blocks"],
                "block_ids": settlements_by_month[month_key]["block_ids"]  # Include all block IDs for this month
            })
    
    # Get individual repairs by month (each repair separate)
    repairs_by_month = []
    repairs_for_monthly = repairs_query.all()
    
    # Get truck names for reference
    truck_map = {truck.id: truck.name for truck in trucks_query.all()}
    
    # Create list of individual repairs with month info
    for repair in repairs_for_monthly:
        if repair.repair_date and repair.cost:
            month_key = repair.repair_date.strftime("%Y-%m")
            month_label = repair.repair_date.strftime("%b %Y")
            
            repairs_by_month.append({
                "repair_id": repair.id,
                "month": month_label,
                "month_key": month_key,
                "cost": float(repair.cost),
                "truck_id": repair.truck_id,
                "truck_name": truck_map.get(repair.truck_id, f"Truck {repair.truck_id}"),
                "description": repair.description or "No description",
                "category": repair.category or "other",
                "repair_date": repair.repair_date.isoformat() if repair.repair_date else None
            })
    
    # Sort by month_key and repair_date
    repairs_by_month.sort(key=lambda x: (x["month_key"], x["repair_date"] or ""))
    
    # Get PM (Preventive Maintenance) status for each truck (exclude trailers)
    # Calculate PM status dynamically by querying repairs (not from truck model fields)
    # PM is based on time: every 10 weeks (70 days) (primary)
    # Fallback to mileage-based: every 25,000 miles when date is not available
    pm_status = []
    trucks_for_pm = trucks_query.filter(Truck.vehicle_type == 'truck').all()  # Only trucks, not trailers
    pm_threshold_miles = 25000  # PM due every 25,000 miles (fallback when date unavailable)
    pm_threshold_days = 70  # PM due every 10 weeks (primary method)
    
    for truck in trucks_for_pm:
        # Find all PM repairs for this truck
        # PM repairs are identified by:
        # 1. Repairs with "d13" AND "full pm" in description/title/details (primary pattern)
        # 2. Repairs with category "maintenance" AND "pm" in description/title/details (secondary pattern)
        pm_repairs_primary = db.query(Repair).filter(
            and_(
                Repair.truck_id == truck.id,
                or_(
                    and_(
                        or_(
                            Repair.description.ilike('%d13%'),
                            Repair.title.ilike('%d13%'),
                            Repair.details.ilike('%d13%')
                        ),
                        or_(
                            Repair.description.ilike('%full pm%'),
                            Repair.title.ilike('%full pm%'),
                            Repair.details.ilike('%full pm%')
                        )
                    )
                )
            )
        ).order_by(Repair.repair_date.desc().nullslast()).all()
        
        # Also check for maintenance category repairs with "pm" in description/title/details
        pm_repairs_secondary = db.query(Repair).filter(
            and_(
                Repair.truck_id == truck.id,
                Repair.category == 'maintenance',
                or_(
                    Repair.description.ilike('%pm%'),
                    Repair.title.ilike('%pm%'),
                    Repair.details.ilike('%pm%')
                )
            )
        ).order_by(Repair.repair_date.desc().nullslast()).all()
        
        # Combine and deduplicate, prioritizing primary matches
        pm_repair_ids = {r.id for r in pm_repairs_primary}
        all_pm_repairs = list(pm_repairs_primary)
        for repair in pm_repairs_secondary:
            if repair.id not in pm_repair_ids:
                all_pm_repairs.append(repair)
        
        # Sort by repair_date descending (most recent first)
        all_pm_repairs.sort(key=lambda r: (r.repair_date or date.min, r.created_at or datetime.min), reverse=True)
        
        last_pm_date = None
        last_pm_miles = None
        last_pm_repair_id = None
        if all_pm_repairs:
            last_pm_repair = all_pm_repairs[0]  # Most recent
            last_pm_date = last_pm_repair.repair_date
            last_pm_repair_id = last_pm_repair.id
            if last_pm_repair.miles:
                last_pm_miles = float(last_pm_repair.miles)
        
        # Get current mileage for the truck
        current_miles = get_current_mileage(truck.id, db)
        
        # Calculate if due for PM - use time-based first (10 weeks), fallback to mileage-based
        is_due = False
        miles_since_pm = None
        miles_overdue = None
        miles_until_due = None
        next_pm_miles = None
        days_since_pm = None
        days_overdue = None
        days_until_due = None
        next_pm_date = None
        pm_method = None  # 'time' or 'mileage'
        
        # Primary method: Time-based PM (10 weeks / 70 days)
        if last_pm_date is not None:
            pm_method = 'time'
            today = date.today()
            days_since_pm = (today - last_pm_date).days
            next_pm_date = last_pm_date + timedelta(days=pm_threshold_days)
            is_due = days_since_pm >= pm_threshold_days
            
            if is_due:
                days_overdue = days_since_pm - pm_threshold_days
            else:
                days_until_due = pm_threshold_days - days_since_pm
        
        # Fallback method: Mileage-based PM (when date is not available but mileage is)
        elif last_pm_miles is not None and current_miles is not None:
            pm_method = 'mileage'
            # Calculate next PM milestone
            next_pm_miles = last_pm_miles + pm_threshold_miles
            miles_since_pm = current_miles - last_pm_miles
            is_due = current_miles >= next_pm_miles
            
            if is_due:
                miles_overdue = current_miles - next_pm_miles
            else:
                miles_until_due = next_pm_miles - current_miles
        
        # No PM history - truck needs PM
        else:
            is_due = True
            pm_method = None
        
        pm_status.append({
            "truck_id": truck.id,
            "truck_name": truck.name,
            "vin": truck.vin,
            "last_pm_date": last_pm_date.isoformat() if last_pm_date else None,
            "last_pm_miles": last_pm_miles,
            "current_miles": current_miles,
            "last_pm_repair_id": last_pm_repair_id,
            "is_due": is_due,
            "pm_method": pm_method,  # 'time', 'mileage', or None
            # Mileage-based fields (fallback)
            "miles_since_pm": miles_since_pm,
            "miles_overdue": miles_overdue,
            "miles_until_due": miles_until_due,
            "next_pm_miles": next_pm_miles,
            "pm_threshold_miles": pm_threshold_miles,
            # Time-based fields (primary)
            "days_since_pm": days_since_pm,
            "days_overdue": days_overdue,
            "days_until_due": days_until_due,
            "next_pm_date": next_pm_date.isoformat() if next_pm_date else None,
            "pm_threshold_days": pm_threshold_days
        })
    
    return {
        # Combined totals (for backward compatibility)
        "total_trucks": total_trucks,
        "total_settlements": total_settlements,
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses_sum),
        "net_profit": net_profit,
        "expense_categories": expense_categories,
        "operational_metrics": combined_operational_metrics,
        "custom_descriptions": custom_descriptions,
        "truck_profits": truck_profits,
        "blocks_by_truck_month": blocks_by_truck_month,
        "repairs_by_month": repairs_by_month,
        "pm_status": pm_status,
        # Separated truck data
        "trucks": {
            "total_trucks": total_trucks,
            "total_settlements": truck_settlements_count,
            "total_revenue": float(truck_revenue),
            "total_expenses": float(truck_expenses_sum),
            "net_profit": truck_net_profit,
            "expense_categories": truck_expense_categories,
            "operational_metrics": truck_operational_metrics,
            "custom_descriptions": truck_custom_descriptions,
            "truck_profits": truck_profits
        },
        # Separated trailer data
        "trailers": {
            "total_trailers": total_trailers,
            "total_settlements": trailer_settlements_count,
            "total_revenue": float(trailer_revenue),
            "total_expenses": float(trailer_expenses_sum),
            "net_profit": trailer_net_profit,
            "expense_categories": trailer_expense_categories,
            "operational_metrics": trailer_operational_metrics,
            "custom_descriptions": trailer_custom_descriptions,
            "trailer_profits": trailer_profits
        }
    }

@router.get("/pm-status")
def get_pm_status(db: Session = Depends(get_db), tenant_id: int = Depends(get_tenant_id)):
    """
    Get PM (Preventive Maintenance) status for all trucks.
    Returns PM status information for each truck based on PM repairs.
    PM is calculated based on time: every 10 weeks (70 days) (primary)
    Fallback to mileage-based: every 25,000 miles when date is not available.
    PM repairs are identified by:
    - Repairs with "d13" AND "full pm" in description/title/details (primary pattern)
    - Repairs with category "maintenance" AND "pm" in description/title/details (secondary pattern)
    """
    pm_status = []
    trucks_for_pm = db.query(Truck).filter(Truck.vehicle_type == 'truck', Truck.tenant_id == tenant_id).all()  # Only trucks for this tenant
    pm_threshold_miles = 25000  # PM due every 25,000 miles (fallback when date unavailable)
    pm_threshold_days = 70  # PM due every 10 weeks (primary method)
    
    for truck in trucks_for_pm:
        # Find all PM repairs for this truck
        # PM repairs are identified by:
        # 1. Repairs with "d13" AND "full pm" in description/title/details (primary pattern)
        # 2. Repairs with category "maintenance" AND "pm" in description/title/details (secondary pattern)
        pm_repairs_primary = db.query(Repair).filter(
            and_(
                Repair.truck_id == truck.id,
                or_(
                    and_(
                        or_(
                            Repair.description.ilike('%d13%'),
                            Repair.title.ilike('%d13%'),
                            Repair.details.ilike('%d13%')
                        ),
                        or_(
                            Repair.description.ilike('%full pm%'),
                            Repair.title.ilike('%full pm%'),
                            Repair.details.ilike('%full pm%')
                        )
                    )
                )
            )
        ).order_by(Repair.repair_date.desc().nullslast()).all()
        
        # Also check for maintenance category repairs with "pm" in description/title/details
        pm_repairs_secondary = db.query(Repair).filter(
            and_(
                Repair.truck_id == truck.id,
                Repair.category == 'maintenance',
                or_(
                    Repair.description.ilike('%pm%'),
                    Repair.title.ilike('%pm%'),
                    Repair.details.ilike('%pm%')
                )
            )
        ).order_by(Repair.repair_date.desc().nullslast()).all()
        
        # Combine and deduplicate, prioritizing primary matches
        pm_repair_ids = {r.id for r in pm_repairs_primary}
        all_pm_repairs = list(pm_repairs_primary)
        for repair in pm_repairs_secondary:
            if repair.id not in pm_repair_ids:
                all_pm_repairs.append(repair)
        
        # Sort by repair_date descending (most recent first)
        all_pm_repairs.sort(key=lambda r: (r.repair_date or date.min, r.created_at or datetime.min), reverse=True)
        
        last_pm_date = None
        last_pm_miles = None
        last_pm_repair_id = None
        if all_pm_repairs:
            last_pm_repair = all_pm_repairs[0]  # Most recent
            last_pm_date = last_pm_repair.repair_date
            last_pm_repair_id = last_pm_repair.id
            if last_pm_repair.miles:
                last_pm_miles = float(last_pm_repair.miles)
        
        # Get current mileage for the truck
        current_miles = get_current_mileage(truck.id, db)
        
        # Calculate if due for PM - use time-based first (10 weeks), fallback to mileage-based
        is_due = False
        miles_since_pm = None
        miles_overdue = None
        miles_until_due = None
        next_pm_miles = None
        days_since_pm = None
        days_overdue = None
        days_until_due = None
        next_pm_date = None
        pm_method = None  # 'time' or 'mileage'
        
        # Primary method: Time-based PM (10 weeks / 70 days)
        if last_pm_date is not None:
            pm_method = 'time'
            today = date.today()
            days_since_pm = (today - last_pm_date).days
            next_pm_date = last_pm_date + timedelta(days=pm_threshold_days)
            is_due = days_since_pm >= pm_threshold_days
            
            if is_due:
                days_overdue = days_since_pm - pm_threshold_days
            else:
                days_until_due = pm_threshold_days - days_since_pm
        
        # Fallback method: Mileage-based PM (when date is not available but mileage is)
        elif last_pm_miles is not None and current_miles is not None:
            pm_method = 'mileage'
            # Calculate next PM milestone
            next_pm_miles = last_pm_miles + pm_threshold_miles
            miles_since_pm = current_miles - last_pm_miles
            is_due = current_miles >= next_pm_miles
            
            if is_due:
                miles_overdue = current_miles - next_pm_miles
            else:
                miles_until_due = next_pm_miles - current_miles
        
        # No PM history - truck needs PM
        else:
            is_due = True
            pm_method = None
        
        pm_status.append({
            "truck_id": truck.id,
            "truck_name": truck.name,
            "vin": truck.vin,
            "last_pm_date": last_pm_date.isoformat() if last_pm_date else None,
            "last_pm_miles": last_pm_miles,
            "current_miles": current_miles,
            "last_pm_repair_id": last_pm_repair_id,
            "is_due": is_due,
            "pm_method": pm_method,  # 'time', 'mileage', or None
            # Mileage-based fields (fallback)
            "miles_since_pm": miles_since_pm,
            "miles_overdue": miles_overdue,
            "miles_until_due": miles_until_due,
            "next_pm_miles": next_pm_miles,
            "pm_threshold_miles": pm_threshold_miles,
            # Time-based fields (primary)
            "days_since_pm": days_since_pm,
            "days_overdue": days_overdue,
            "days_until_due": days_until_due,
            "next_pm_date": next_pm_date.isoformat() if next_pm_date else None,
            "pm_threshold_days": pm_threshold_days
        })
    
    return {"pm_status": pm_status}

@router.get("/time-series")
def get_time_series(
    group_by: Optional[str] = "week_start",
    truck_id: Optional[int] = None,
    vehicle_type: Optional[str] = None,
    include_diesel: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Get time-series data grouped by week and month.
    
    Args:
        group_by: How to group weekly data - "week_start" or "settlement_date" (default: "week_start")
        truck_id: Optional truck filter
        vehicle_type: Optional vehicle type filter ('truck', 'trailer', or 'suv')
    """
    import traceback
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        return _get_time_series_impl(group_by, truck_id, vehicle_type, include_diesel, db, tenant_id)
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Time-series error: {error_trace}")
        print(f"TIME-SERIES ERROR: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Time-series error: {str(e)}\n\nTraceback:\n{error_trace}")

def _get_time_series_impl(
    group_by: str,
    truck_id: Optional[int],
    vehicle_type: Optional[str],
    include_diesel: bool,
    db: Session,
    tenant_id: int
):
    """Internal implementation of time-series endpoint."""
    # Validate group_by parameter
    if group_by not in ["week_start", "settlement_date"]:
        group_by = "week_start"
    
    # Build query with tenant filter
    settlements_query = db.query(Settlement).join(Truck).filter(Truck.tenant_id == tenant_id)
    if truck_id is not None:
        settlements_query = settlements_query.filter(Settlement.truck_id == truck_id)
    
    # Apply vehicle type filter when provided (and no explicit truck_id override)
    if vehicle_type:
        vt = vehicle_type.lower()
        if vt in ["truck", "trailer"]:
            vehicle_ids = [t.id for t in db.query(Truck).filter(Truck.vehicle_type == vt, Truck.tenant_id == tenant_id).all()]
            if vehicle_ids:
                settlements_query = settlements_query.filter(Settlement.truck_id.in_(vehicle_ids))
            else:
                # No vehicles of this type; return empty results
                settlements_query = settlements_query.filter(False)
    
    settlements = settlements_query.order_by(Settlement.settlement_date).all()
    
    # Get truck names for reference (only for this tenant)
    trucks = db.query(Truck).filter(Truck.tenant_id == tenant_id).all()
    truck_map = {truck.id: truck.name for truck in trucks}
    
    # Helper function to extract description from custom category key
    def extract_custom_description(category_key: str) -> str:
        """Extract description from custom category key (e.g., 'custom_truck_parking' -> 'Truck Parking')"""
        if category_key.startswith("custom_"):
            desc = category_key.replace("custom_", "")
            # Convert snake_case to Title Case
            return " ".join(word.capitalize() for word in desc.split("_"))
        return "Custom"
    
    # Standard expense categories
    STANDARD_CATEGORIES = ["fuel", "tolls", "dispatch_fee", "insurance", "safety", "prepass", "ifta", "truck_parking", "deduct", "driver_pay", "payroll_fee", "loan_interest"]
    
    # Initialize data structures
    weekly_data = defaultdict(lambda: {
        "gross_revenue": 0.0,
        "raw_gross_revenue": 0.0,
        "raw_gross_miles_driven": 0.0,
        "miles_driven": 0.0,
        "net_profit": 0.0,
        "expenses": 0.0,  # Total expenses from settlement.expenses field
        "trailer_income_split_amount": 0.0,
        "repair_reserve_amount": 0.0,
        "driver_pay": 0.0,
        "payroll_fee": 0.0,
        "fuel": 0.0,
        "tolls": 0.0,
        "dispatch_fee": 0.0,
        "insurance": 0.0,
        "safety": 0.0,
        "prepass": 0.0,
        "ifta": 0.0,
        "deduct": 0.0,
        "loan_interest": 0.0,
        "truck_parking": 0.0,
        "custom": 0.0,
        "trucks": set(),
        "settlement_types": set(),
        "diesel_price_weighted_sum": 0.0,
        "diesel_price_weight": 0.0,
        "week_start": None,
        "week_end": None,
        "settlement_date": None,
        "custom_descriptions": {}  # Track custom category descriptions for this period
    })
    
    monthly_data = defaultdict(lambda: {
        "gross_revenue": 0.0,
        "raw_gross_revenue": 0.0,
        "raw_gross_miles_driven": 0.0,
        "miles_driven": 0.0,
        "net_profit": 0.0,
        "expenses": 0.0,  # Total expenses from settlement.expenses field
        "trailer_income_split_amount": 0.0,
        "repair_reserve_amount": 0.0,
        "driver_pay": 0.0,
        "payroll_fee": 0.0,
        "fuel": 0.0,
        "tolls": 0.0,
        "dispatch_fee": 0.0,
        "insurance": 0.0,
        "safety": 0.0,
        "prepass": 0.0,
        "ifta": 0.0,
        "deduct": 0.0,
        "loan_interest": 0.0,
        "truck_parking": 0.0,
        "custom": 0.0,
        "repairs": 0.0,
        "trucks": set(),
        "settlement_types": set(),
        "diesel_price_weighted_sum": 0.0,
        "diesel_price_weight": 0.0,
        "custom_descriptions": {}  # Track custom category descriptions for this period
    })
    
    yearly_data = defaultdict(lambda: {
        "gross_revenue": 0.0,
        "raw_gross_revenue": 0.0,
        "raw_gross_miles_driven": 0.0,
        "miles_driven": 0.0,
        "net_profit": 0.0,
        "expenses": 0.0,  # Total expenses from settlement.expenses field
        "trailer_income_split_amount": 0.0,
        "repair_reserve_amount": 0.0,
        "driver_pay": 0.0,
        "payroll_fee": 0.0,
        "fuel": 0.0,
        "tolls": 0.0,
        "dispatch_fee": 0.0,
        "insurance": 0.0,
        "safety": 0.0,
        "prepass": 0.0,
        "ifta": 0.0,
        "deduct": 0.0,
        "loan_interest": 0.0,
        "truck_parking": 0.0,
        "custom": 0.0,
        "repairs": 0.0,
        "trucks": set(),
        "settlement_types": set(),
        "diesel_price_weighted_sum": 0.0,
        "diesel_price_weight": 0.0,
        "custom_descriptions": {}  # Track custom category descriptions for this period
    })
    
    # Process each settlement
    for settlement in settlements:
        # Skip settlements without a settlement_date (required for grouping)
        if not settlement.settlement_date:
            continue
            
        # Determine week key based on group_by parameter
        # When grouping by "week_start", we actually group by settlement_date (pay period end date)
        # because settlements with the same pay period should be grouped together,
        # even if their week_start dates differ slightly
        if group_by == "week_start":
            # Use settlement_date as the key to group by pay period
            week_key = settlement.settlement_date.isoformat()
            # Use week_start/week_end from the settlement if available, otherwise use settlement_date
            week_start = settlement.week_start if settlement.week_start else settlement.settlement_date
            week_end = settlement.week_end if settlement.week_end else settlement.settlement_date
        else:
            # When grouping by settlement_date, use settlement_date as key
            week_key = settlement.settlement_date.isoformat()
            week_start = settlement.week_start if settlement.week_start else settlement.settlement_date
            week_end = settlement.week_end if settlement.week_end else settlement.settlement_date
        
        # Determine month key (using existing logic with 28th cutoff)
        date_to_use = None
        if settlement.week_start:
            if settlement.week_start.day >= 28:
                if settlement.week_start.month == 12:
                    date_to_use = settlement.week_start.replace(year=settlement.week_start.year + 1, month=1, day=1)
                else:
                    date_to_use = settlement.week_start.replace(month=settlement.week_start.month + 1, day=1)
            else:
                date_to_use = settlement.week_start
        elif settlement.settlement_date:
            if settlement.settlement_date.day >= 28:
                if settlement.settlement_date.month == 12:
                    date_to_use = settlement.settlement_date.replace(year=settlement.settlement_date.year + 1, month=1, day=1)
                else:
                    date_to_use = settlement.settlement_date.replace(month=settlement.settlement_date.month + 1, day=1)
            else:
                date_to_use = settlement.settlement_date
        
        month_key = date_to_use.strftime("%Y-%m") if date_to_use else None
        
        # Determine year key
        year_key = None
        if date_to_use:
            year_key = date_to_use.strftime("%Y")
        elif settlement.settlement_date:
            year_key = settlement.settlement_date.strftime("%Y")

        miles_driven = float(settlement.miles_driven) if settlement.miles_driven else 0.0
        raw_gross_revenue = _extract_raw_gross_amount(settlement)
        raw_gross_miles_driven = miles_driven if raw_gross_revenue > 0 else 0.0
        diesel_price = None
        diesel_price_weight = 0.0
        if include_diesel:
            reference_date = week_start or settlement.settlement_date
            if reference_date:
                benchmark_price = get_historical_diesel_price(reference_date)
                if benchmark_price and benchmark_price > 0:
                    diesel_price = float(benchmark_price)
                    if settlement.overview_amounts and isinstance(settlement.overview_amounts, dict):
                        try:
                            diesel_price_weight = float(settlement.overview_amounts.get("estimated_gallons") or 0.0)
                        except (TypeError, ValueError):
                            diesel_price_weight = 0.0
                    if diesel_price_weight <= 0:
                        diesel_price_weight = miles_driven if miles_driven > 0 else 1.0

        # Aggregate weekly data
        weekly_data[week_key]["gross_revenue"] += float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
        weekly_data[week_key]["raw_gross_revenue"] += raw_gross_revenue
        weekly_data[week_key]["raw_gross_miles_driven"] += raw_gross_miles_driven
        weekly_data[week_key]["miles_driven"] += miles_driven
        weekly_data[week_key]["net_profit"] += float(settlement.net_profit) if settlement.net_profit else 0.0
        weekly_data[week_key]["expenses"] += float(settlement.expenses) if settlement.expenses else 0.0
        weekly_data[week_key]["trailer_income_split_amount"] += float(settlement.trailer_income_split_amount) if settlement.trailer_income_split_amount else 0.0
        weekly_data[week_key]["repair_reserve_amount"] += float(settlement.repair_reserve_amount) if settlement.repair_reserve_amount else 0.0
        weekly_data[week_key]["trucks"].add(settlement.truck_id)
        if settlement.settlement_type:
            weekly_data[week_key]["settlement_types"].add(settlement.settlement_type)
        if diesel_price is not None and diesel_price_weight > 0:
            weekly_data[week_key]["diesel_price_weighted_sum"] += diesel_price * diesel_price_weight
            weekly_data[week_key]["diesel_price_weight"] += diesel_price_weight
        if not weekly_data[week_key]["week_start"]:
            weekly_data[week_key]["week_start"] = week_start
        if not weekly_data[week_key]["week_end"]:
            weekly_data[week_key]["week_end"] = week_end
        if not weekly_data[week_key]["settlement_date"]:
            weekly_data[week_key]["settlement_date"] = settlement.settlement_date
        
        # Aggregate monthly data
        if month_key:
            monthly_data[month_key]["gross_revenue"] += float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
            monthly_data[month_key]["raw_gross_revenue"] += raw_gross_revenue
            monthly_data[month_key]["raw_gross_miles_driven"] += raw_gross_miles_driven
            monthly_data[month_key]["miles_driven"] += miles_driven
            monthly_data[month_key]["net_profit"] += float(settlement.net_profit) if settlement.net_profit else 0.0
            monthly_data[month_key]["expenses"] += float(settlement.expenses) if settlement.expenses else 0.0
            monthly_data[month_key]["trailer_income_split_amount"] += float(settlement.trailer_income_split_amount) if settlement.trailer_income_split_amount else 0.0
            monthly_data[month_key]["repair_reserve_amount"] += float(settlement.repair_reserve_amount) if settlement.repair_reserve_amount else 0.0
            monthly_data[month_key]["trucks"].add(settlement.truck_id)
            if settlement.settlement_type:
                monthly_data[month_key]["settlement_types"].add(settlement.settlement_type)
            if diesel_price is not None and diesel_price_weight > 0:
                monthly_data[month_key]["diesel_price_weighted_sum"] += diesel_price * diesel_price_weight
                monthly_data[month_key]["diesel_price_weight"] += diesel_price_weight
        
        # Aggregate yearly data
        if year_key:
            yearly_data[year_key]["gross_revenue"] += float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
            yearly_data[year_key]["raw_gross_revenue"] += raw_gross_revenue
            yearly_data[year_key]["raw_gross_miles_driven"] += raw_gross_miles_driven
            yearly_data[year_key]["miles_driven"] += miles_driven
            yearly_data[year_key]["net_profit"] += float(settlement.net_profit) if settlement.net_profit else 0.0
            yearly_data[year_key]["expenses"] += float(settlement.expenses) if settlement.expenses else 0.0
            yearly_data[year_key]["trailer_income_split_amount"] += float(settlement.trailer_income_split_amount) if settlement.trailer_income_split_amount else 0.0
            yearly_data[year_key]["repair_reserve_amount"] += float(settlement.repair_reserve_amount) if settlement.repair_reserve_amount else 0.0
            yearly_data[year_key]["trucks"].add(settlement.truck_id)
            if settlement.settlement_type:
                yearly_data[year_key]["settlement_types"].add(settlement.settlement_type)
            if diesel_price is not None and diesel_price_weight > 0:
                yearly_data[year_key]["diesel_price_weighted_sum"] += diesel_price * diesel_price_weight
                yearly_data[year_key]["diesel_price_weight"] += diesel_price_weight
        
        # Process expense categories
        if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
            for category, amount in settlement.expense_categories.items():
                try:
                    # Skip reimbursements - they're credits, not expenses
                    if category == "reimbursement":
                        continue
                    
                    amount_float = float(amount) if amount is not None else 0.0
                    if amount_float > 0:
                        # Map category names
                        mapped_category = category
                        if category == "fees" or category == "other":
                            mapped_category = "custom"
                        elif category.startswith("custom_") or (category not in STANDARD_CATEGORIES and category != "custom"):
                            # Custom category - aggregate into "custom" and track description
                            mapped_category = "custom"
                            
                            # Extract description from deduction_details if available
                            description = None
                            if category == "deduct" and settlement.deduction_details:
                                descriptions = [
                                    d.get("description", "").strip() 
                                    for d in settlement.deduction_details 
                                    if d.get("description") and d.get("description").strip()
                                ]
                                if descriptions:
                                    description = "; ".join(descriptions)
                            
                            # Track custom description for this period
                            if category not in weekly_data[week_key]["custom_descriptions"]:
                                weekly_data[week_key]["custom_descriptions"][category] = description or extract_custom_description(category)
                            elif description and category in weekly_data[week_key]["custom_descriptions"]:
                                # Append description if not already included
                                existing = weekly_data[week_key]["custom_descriptions"][category]
                                if description and description not in existing:
                                    weekly_data[week_key]["custom_descriptions"][category] = f"{existing}; {description}"
                            
                            if month_key:
                                if category not in monthly_data[month_key]["custom_descriptions"]:
                                    monthly_data[month_key]["custom_descriptions"][category] = description or extract_custom_description(category)
                                elif description and category in monthly_data[month_key]["custom_descriptions"]:
                                    existing = monthly_data[month_key]["custom_descriptions"][category]
                                    if description and description not in existing:
                                        monthly_data[month_key]["custom_descriptions"][category] = f"{existing}; {description}"
                            
                            if year_key:
                                if category not in yearly_data[year_key]["custom_descriptions"]:
                                    yearly_data[year_key]["custom_descriptions"][category] = description or extract_custom_description(category)
                                elif description and category in yearly_data[year_key]["custom_descriptions"]:
                                    existing = yearly_data[year_key]["custom_descriptions"][category]
                                    if description and description not in existing:
                                        yearly_data[year_key]["custom_descriptions"][category] = f"{existing}; {description}"
                        
                        if mapped_category in weekly_data[week_key]:
                            weekly_data[week_key][mapped_category] += amount_float
                        
                        if month_key and mapped_category in monthly_data[month_key]:
                            monthly_data[month_key][mapped_category] += amount_float
                        
                        if year_key and mapped_category in yearly_data[year_key]:
                            yearly_data[year_key][mapped_category] += amount_float
                except (ValueError, TypeError):
                    continue
    
    # Format weekly data
    # Filter out future weeks (only show weeks up to current date)
    current_date = datetime.now().date()
    
    by_week = []
    for week_key in sorted(weekly_data.keys()):
        week_data = weekly_data[week_key]
        week_start_date = week_data["week_start"]
        week_end_date = week_data["week_end"]
        settlement_date = week_data["settlement_date"]
        
        # Skip future weeks - check if week_start or settlement_date is in the future
        date_to_check = week_start_date or settlement_date
        if date_to_check and date_to_check > current_date:
            continue
        
        # Format week label
        if week_start_date and week_end_date and week_start_date != week_end_date:
            week_label = f"{week_start_date.strftime('%b %d')}-{week_end_date.strftime('%d, %Y')}"
        elif week_start_date:
            week_label = week_start_date.strftime('%b %d, %Y')
        elif settlement_date:
            week_label = settlement_date.strftime('%b %d, %Y')
        else:
            week_label = week_key
        
        truck_list = [
            {
                "truck_id": tid,
                "truck_name": truck_map.get(tid, f"Truck {tid}")
            }
            for tid in sorted(week_data["trucks"])
        ]
        
        # Convert custom_descriptions dict to format expected by frontend
        custom_descriptions_formatted = {}
        for key, desc in week_data["custom_descriptions"].items():
            custom_descriptions_formatted[key] = desc
        
        by_week.append({
            "week_key": week_key,
            "week_label": week_label,
            "week_start": week_start_date.isoformat() if week_start_date else None,
            "week_end": week_end_date.isoformat() if week_end_date else None,
            "gross_revenue": round(week_data["gross_revenue"], 2),
            "raw_gross_revenue": round(week_data["raw_gross_revenue"], 2),
            "raw_gross_miles_driven": round(week_data["raw_gross_miles_driven"], 2),
            "miles_driven": round(week_data["miles_driven"], 2),
            "net_profit": round(week_data["net_profit"], 2),
            "expenses": round(week_data["expenses"], 2),
            "trailer_income_split_amount": round(week_data["trailer_income_split_amount"], 2),
            "repair_reserve_amount": round(week_data["repair_reserve_amount"], 2),
            "driver_pay": round(week_data["driver_pay"], 2),
            "payroll_fee": round(week_data["payroll_fee"], 2),
            "fuel": round(week_data["fuel"], 2),
            "tolls": round(week_data["tolls"], 2),
            "dispatch_fee": round(week_data["dispatch_fee"], 2),
            "insurance": round(week_data["insurance"], 2),
            "safety": round(week_data["safety"], 2),
            "prepass": round(week_data["prepass"], 2),
            "ifta": round(week_data["ifta"], 2),
            "deduct": round(week_data["deduct"], 2),
            "loan_interest": round(week_data["loan_interest"], 2),
            "truck_parking": round(week_data["truck_parking"], 2),
            "custom": round(week_data["custom"], 2),
            "diesel_price_per_gallon": round(week_data["diesel_price_weighted_sum"] / week_data["diesel_price_weight"], 3) if week_data["diesel_price_weight"] > 0 else None,
            "custom_descriptions": custom_descriptions_formatted,
            "trucks": truck_list,
            "settlement_types": sorted(week_data["settlement_types"])
        })
    
    # Format monthly data
    # Filter out future months (only show months up to current month)
    current_date = datetime.now().date()
    current_month_key = current_date.strftime("%Y-%m")
    
    # Build a map of which settlements contribute to each month for debugging
    month_settlements_map = defaultdict(list)
    for settlement in settlements:
        # Skip settlements without a settlement_date
        if not settlement.settlement_date:
            continue
            
        # Recalculate month_key for this settlement to match what we used above
        date_to_use = None
        if settlement.week_start:
            if settlement.week_start.day >= 28:
                if settlement.week_start.month == 12:
                    date_to_use = settlement.week_start.replace(year=settlement.week_start.year + 1, month=1, day=1)
                else:
                    date_to_use = settlement.week_start.replace(month=settlement.week_start.month + 1, day=1)
            else:
                date_to_use = settlement.week_start
        elif settlement.settlement_date:
            if settlement.settlement_date.day >= 28:
                if settlement.settlement_date.month == 12:
                    date_to_use = settlement.settlement_date.replace(year=settlement.settlement_date.year + 1, month=1, day=1)
                else:
                    date_to_use = settlement.settlement_date.replace(month=settlement.settlement_date.month + 1, day=1)
            else:
                date_to_use = settlement.settlement_date
        
        if date_to_use:
            month_key = date_to_use.strftime("%Y-%m")
            month_settlements_map[month_key].append({
                "settlement_id": settlement.id,
                "settlement_date": settlement.settlement_date.isoformat() if settlement.settlement_date else None,
                "week_start": settlement.week_start.isoformat() if settlement.week_start else None,
                "truck_id": settlement.truck_id,
                "truck_name": truck_map.get(settlement.truck_id, f"Truck {settlement.truck_id}"),
                "insurance": float(settlement.expense_categories.get("insurance", 0)) if settlement.expense_categories and isinstance(settlement.expense_categories, dict) else 0.0,
                "driver_pay": float(settlement.expense_categories.get("driver_pay", 0)) if settlement.expense_categories and isinstance(settlement.expense_categories, dict) else 0.0,
            })
    
    by_month = []
    for month_key in sorted(monthly_data.keys()):
        # Skip future months
        if month_key > current_month_key:
            continue
            
        month_data = monthly_data[month_key]
        month_date = datetime.strptime(month_key, "%Y-%m")
        month_label = month_date.strftime("%b %Y")
        
        truck_list = [
            {
                "truck_id": tid,
                "truck_name": truck_map.get(tid, f"Truck {tid}")
            }
            for tid in sorted(month_data["trucks"])
        ]
        
        # Convert custom_descriptions dict to format expected by frontend
        custom_descriptions_formatted = {}
        for key, desc in month_data["custom_descriptions"].items():
            custom_descriptions_formatted[key] = desc
        
        by_month.append({
            "month_key": month_key,
            "month_label": month_label,
            "gross_revenue": round(month_data["gross_revenue"], 2),
            "raw_gross_revenue": round(month_data["raw_gross_revenue"], 2),
            "raw_gross_miles_driven": round(month_data["raw_gross_miles_driven"], 2),
            "miles_driven": round(month_data["miles_driven"], 2),
            "net_profit": round(month_data["net_profit"], 2),
            "expenses": round(month_data["expenses"], 2),
            "trailer_income_split_amount": round(month_data["trailer_income_split_amount"], 2),
            "repair_reserve_amount": round(month_data["repair_reserve_amount"], 2),
            "driver_pay": round(month_data["driver_pay"], 2),
            "payroll_fee": round(month_data["payroll_fee"], 2),
            "fuel": round(month_data["fuel"], 2),
            "tolls": round(month_data["tolls"], 2),
            "dispatch_fee": round(month_data["dispatch_fee"], 2),
            "insurance": round(month_data["insurance"], 2),
            "safety": round(month_data["safety"], 2),
            "prepass": round(month_data["prepass"], 2),
            "ifta": round(month_data["ifta"], 2),
            "deduct": round(month_data["deduct"], 2),
            "loan_interest": round(month_data["loan_interest"], 2),
            "truck_parking": round(month_data["truck_parking"], 2),
            "custom": round(month_data["custom"], 2),
            "diesel_price_per_gallon": round(month_data["diesel_price_weighted_sum"] / month_data["diesel_price_weight"], 3) if month_data["diesel_price_weight"] > 0 else None,
            "custom_descriptions": custom_descriptions_formatted,
            "trucks": truck_list,
            "settlement_types": sorted(month_data["settlement_types"]),
            "settlement_count": len(month_settlements_map.get(month_key, [])),
            "settlements": month_settlements_map.get(month_key, [])  # Include settlement details for debugging
        })
    
    # Add repairs to yearly/monthly data and subtract from net profit
    repairs_query = db.query(Repair).join(Truck).filter(Truck.tenant_id == tenant_id)
    if truck_id is not None:
        repairs_query = repairs_query.filter(Repair.truck_id == truck_id)
    elif vehicle_type:
        # Filter repairs by vehicle type when no specific truck_id is provided
        vt = vehicle_type.lower()
        if vt in ["truck", "trailer", "suv"]:
            vehicle_ids = [t.id for t in db.query(Truck).filter(Truck.vehicle_type == vt, Truck.tenant_id == tenant_id).all()]
            if vehicle_ids:
                repairs_query = repairs_query.filter(Repair.truck_id.in_(vehicle_ids))
            else:
                # No vehicles of this type; return empty results
                repairs_query = repairs_query.filter(False)
    
    repairs = repairs_query.all()
    for repair in repairs:
        if repair.cost and repair.repair_date:
            repair_year = repair.repair_date.strftime("%Y")
            if repair_year in yearly_data:
                yearly_data[repair_year]["repairs"] += float(repair.cost)
                # Subtract repairs from net profit to match dashboard calculation
                yearly_data[repair_year]["net_profit"] -= float(repair.cost)
            
            # Also add to monthly if needed (for consistency)
            repair_month = repair.repair_date.strftime("%Y-%m")
            if repair_month in monthly_data:
                monthly_data[repair_month]["repairs"] += float(repair.cost)
                monthly_data[repair_month]["net_profit"] -= float(repair.cost)
    
    # Format yearly data
    # Filter out future years (only show years up to current year)
    current_year = datetime.now().year
    
    by_year = []
    for year_key in sorted(yearly_data.keys()):
        year_int = int(year_key)
        # Skip future years
        if year_int > current_year:
            continue
        
        year_data = yearly_data[year_key]
        year_label = year_key  # e.g., "2025"
        
        truck_list = [
            {
                "truck_id": tid,
                "truck_name": truck_map.get(tid, f"Truck {tid}")
            }
            for tid in sorted(year_data["trucks"])
        ]
        
        # Convert custom_descriptions dict to format expected by frontend
        custom_descriptions_formatted = {}
        for key, desc in year_data["custom_descriptions"].items():
            custom_descriptions_formatted[key] = desc
        
        by_year.append({
            "year_key": year_key,
            "year_label": year_label,
            "gross_revenue": round(year_data["gross_revenue"], 2),
            "raw_gross_revenue": round(year_data["raw_gross_revenue"], 2),
            "raw_gross_miles_driven": round(year_data["raw_gross_miles_driven"], 2),
            "miles_driven": round(year_data["miles_driven"], 2),
            "net_profit": round(year_data["net_profit"], 2),
            "expenses": round(year_data["expenses"], 2),
            "trailer_income_split_amount": round(year_data["trailer_income_split_amount"], 2),
            "repair_reserve_amount": round(year_data["repair_reserve_amount"], 2),
            "driver_pay": round(year_data["driver_pay"], 2),
            "payroll_fee": round(year_data["payroll_fee"], 2),
            "fuel": round(year_data["fuel"], 2),
            "tolls": round(year_data["tolls"], 2),
            "dispatch_fee": round(year_data["dispatch_fee"], 2),
            "insurance": round(year_data["insurance"], 2),
            "safety": round(year_data["safety"], 2),
            "prepass": round(year_data["prepass"], 2),
            "ifta": round(year_data["ifta"], 2),
            "deduct": round(year_data["deduct"], 2),
            "loan_interest": round(year_data["loan_interest"], 2),
            "truck_parking": round(year_data["truck_parking"], 2),
            "custom": round(year_data["custom"], 2),
            "diesel_price_per_gallon": round(year_data["diesel_price_weighted_sum"] / year_data["diesel_price_weight"], 3) if year_data["diesel_price_weight"] > 0 else None,
            "custom_descriptions": custom_descriptions_formatted,
            "repairs": round(year_data.get("repairs", 0.0), 2),
            "trucks": truck_list,
            "settlement_types": sorted(year_data["settlement_types"])
        })
    
    return {
        "by_week": by_week,
        "by_month": by_month,
        "by_year": by_year
    }
