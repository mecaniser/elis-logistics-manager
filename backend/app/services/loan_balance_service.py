"""
Loan balance recalculation helpers.
"""
from datetime import date, datetime, timedelta
from math import ceil
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.repair import Repair
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.utils.loan_interest import calculate_cumulative_principal_paid


def _normalize_to_date(value: Optional[Any]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return value


def calculate_loan_metrics_for_truck(
    db: Session,
    truck: Truck,
    as_of_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Recalculate loan payoff progress and forecast from full settlement/repair history.

    This always starts from the original loan amount, not the stored current balance,
    so recalculation is stable even if the persisted balance is stale.
    """
    normalized_as_of_date = _normalize_to_date(as_of_date)

    metrics: Dict[str, Any] = {
        "loan_amount": None,
        "current_loan_balance": None,
        "principal_paid_total": 0.0,
        "loan_payoff_date": None,
        "average_principal_payment": None,
        "estimated_settlements_to_payoff": None,
        "projected_payoff_date": None,
        "latest_settlement_date": None,
        "principal_payment_count": 0,
    }

    if not truck or truck.vehicle_type != "truck":
        return metrics

    loan_amount = float(truck.loan_amount) if truck.loan_amount else None
    if not loan_amount or loan_amount <= 0:
        return metrics

    metrics["loan_amount"] = round(loan_amount, 2)

    cash_investment = float(truck.cash_investment) if truck.cash_investment else None
    if not cash_investment or cash_investment <= 0:
        metrics["current_loan_balance"] = round(loan_amount, 2)
        return metrics

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
    principal_events: List[Dict[str, Any]] = []
    replayed_settlement_dates: List[date] = []
    payoff_date: Optional[date] = None
    prior_cumulative_principal_paid = 0.0

    for settlement in settlements:
        settlement_effective_date = _normalize_to_date(
            settlement.week_start or settlement.settlement_date or settlement.created_at
        )
        if normalized_as_of_date and settlement_effective_date and settlement_effective_date > normalized_as_of_date:
            break

        cumulative_revenue += float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
        cumulative_settlement_expenses += float(settlement.expenses) if settlement.expenses else 0.0

        settlement_date = settlement_effective_date
        if settlement_date:
            replayed_settlement_dates.append(settlement_date)
        while repair_index < len(repairs):
            repair = repairs[repair_index]
            repair_date = _normalize_to_date(repair.repair_date or repair.created_at)
            if settlement_date and repair_date and repair_date <= settlement_date:
                cumulative_repair_costs += float(repair.cost) if repair.cost else 0.0
                repair_index += 1
            else:
                break

        cumulative_net_profit = cumulative_revenue - cumulative_settlement_expenses - cumulative_repair_costs
        cumulative_principal_paid = calculate_cumulative_principal_paid(
            cumulative_net_profit,
            cash_investment,
            loan_amount,
        )
        principal_payment = round(max(0.0, cumulative_principal_paid - prior_cumulative_principal_paid), 2)
        current_loan_balance = round(max(0.0, loan_amount - cumulative_principal_paid), 2)
        prior_cumulative_principal_paid = cumulative_principal_paid

        if principal_payment > 0:
            principal_events.append({
                "date": _normalize_to_date(settlement.settlement_date) or settlement_date,
                "amount": principal_payment,
                "remaining_balance": current_loan_balance,
            })

        if payoff_date is None and current_loan_balance <= 0:
            payoff_date = _normalize_to_date(settlement.settlement_date) or settlement_date

    current_loan_balance = round(float(current_loan_balance), 2)
    principal_paid_total = round(prior_cumulative_principal_paid, 2)

    metrics["current_loan_balance"] = current_loan_balance
    metrics["principal_paid_total"] = principal_paid_total
    metrics["loan_payoff_date"] = payoff_date.isoformat() if payoff_date else None
    metrics["latest_settlement_date"] = replayed_settlement_dates[-1].isoformat() if replayed_settlement_dates else None
    metrics["principal_payment_count"] = len(principal_events)

    if principal_events:
        average_principal_payment = round(
            sum(event["amount"] for event in principal_events) / len(principal_events),
            2,
        )
        metrics["average_principal_payment"] = average_principal_payment

        if current_loan_balance > 0 and average_principal_payment > 0:
            estimated_settlements = ceil(current_loan_balance / average_principal_payment)
            metrics["estimated_settlements_to_payoff"] = estimated_settlements

            dated_principal_events = [event["date"] for event in principal_events if event["date"]]
            settlement_dates = replayed_settlement_dates
            average_days_between_settlements = 7

            if len(dated_principal_events) >= 2:
                diffs = [
                    max(1, (dated_principal_events[idx] - dated_principal_events[idx - 1]).days)
                    for idx in range(1, len(dated_principal_events))
                ]
                average_days_between_settlements = max(1, round(sum(diffs) / len(diffs)))
            elif len(settlement_dates) >= 2:
                diffs = [
                    max(1, (settlement_dates[idx] - settlement_dates[idx - 1]).days)
                    for idx in range(1, len(settlement_dates))
                ]
                average_days_between_settlements = max(1, round(sum(diffs) / len(diffs)))

            if settlement_dates:
                projected_date = settlement_dates[-1] + timedelta(days=average_days_between_settlements * estimated_settlements)
                metrics["projected_payoff_date"] = projected_date.isoformat()

    return metrics


def calculate_current_loan_balance_for_truck(
    db: Session,
    truck: Truck,
    as_of_date: Optional[date] = None,
) -> Optional[float]:
    """
    Return only the replayed current loan balance.
    """
    return calculate_loan_metrics_for_truck(db, truck, as_of_date)["current_loan_balance"]


def sync_current_loan_balance(db: Session, truck: Truck) -> Optional[float]:
    """
    Recalculate and persist the current loan balance on the truck record.
    """
    recalculated_balance = calculate_current_loan_balance_for_truck(db, truck)
    truck.current_loan_balance = recalculated_balance
    db.add(truck)
    return recalculated_balance
