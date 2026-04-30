"""
Loan balance recalculation helpers.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.repair import Repair
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.utils.loan_interest import calculate_principal_payment


def calculate_current_loan_balance_for_truck(db: Session, truck: Truck) -> Optional[float]:
    """
    Recalculate a truck's remaining principal from its full settlement/repair history.

    This always starts from the original loan amount, not the stored current balance,
    so recalculation is stable even if the persisted balance is stale.
    """
    if not truck or truck.vehicle_type != "truck":
        return None

    loan_amount = float(truck.loan_amount) if truck.loan_amount else None
    if not loan_amount or loan_amount <= 0:
        return None

    cash_investment = float(truck.cash_investment) if truck.cash_investment else None
    if not cash_investment or cash_investment <= 0:
        return round(loan_amount, 2)

    settlements = (
        db.query(Settlement)
        .filter(Settlement.truck_id == truck.id)
        .order_by(
            Settlement.week_start.asc().nullslast(),
            Settlement.settlement_date.asc().nullslast(),
            Settlement.created_at.asc(),
        )
        .all()
    )

    repairs = (
        db.query(Repair)
        .filter(Repair.truck_id == truck.id)
        .order_by(Repair.repair_date.asc().nullslast(), Repair.created_at.asc())
        .all()
    )

    current_loan_balance = loan_amount
    cumulative_revenue = 0.0
    cumulative_settlement_expenses = 0.0
    cumulative_repair_costs = 0.0
    repair_index = 0

    for settlement in settlements:
        cumulative_revenue += float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
        cumulative_settlement_expenses += float(settlement.expenses) if settlement.expenses else 0.0

        settlement_date = settlement.week_start or settlement.settlement_date or settlement.created_at
        while repair_index < len(repairs):
            repair = repairs[repair_index]
            repair_date = repair.repair_date or repair.created_at
            if settlement_date and repair_date and repair_date <= settlement_date:
                cumulative_repair_costs += float(repair.cost) if repair.cost else 0.0
                repair_index += 1
            else:
                break

        cumulative_net_profit = cumulative_revenue - cumulative_settlement_expenses - cumulative_repair_costs
        _, current_loan_balance = calculate_principal_payment(
            cumulative_net_profit,
            cash_investment,
            current_loan_balance,
        )

    return round(float(current_loan_balance), 2)


def sync_current_loan_balance(db: Session, truck: Truck) -> Optional[float]:
    """
    Recalculate and persist the current loan balance on the truck record.
    """
    recalculated_balance = calculate_current_loan_balance_for_truck(db, truck)
    truck.current_loan_balance = recalculated_balance
    db.add(truck)
    return recalculated_balance
