"""
Utility functions for calculating loan interest and managing principal payments
"""
from decimal import Decimal
from typing import Optional, Tuple


def calculate_weekly_loan_interest(loan_balance: Optional[float], interest_rate: Optional[float]) -> float:
    """
    Calculate weekly loan interest payment based on current loan balance.
    
    Args:
        loan_balance: Current loan balance (None or 0 if no loan or paid off)
        interest_rate: Annual interest rate as decimal (e.g., 0.07 for 7%)
    
    Returns:
        Weekly interest amount (0.0 if no loan or invalid rate)
    """
    if not loan_balance or loan_balance <= 0:
        return 0.0
    
    if not interest_rate or interest_rate <= 0:
        return 0.0
    
    # Weekly interest = (loan_balance * annual_interest_rate) / 52
    weekly_interest = (float(loan_balance) * float(interest_rate)) / 52.0
    
    return round(weekly_interest, 2)


def calculate_principal_payment(
    cumulative_net_profit: float,
    cash_investment: Optional[float],
    current_loan_balance: Optional[float]
) -> Tuple[float, Optional[float]]:
    """
    Calculate principal payment based on cumulative net profit and cash investment recovery.
    
    Principal payments only apply after cash investment is 100% recovered.
    Any excess profit after cash recovery goes toward loan principal.
    
    Args:
        cumulative_net_profit: Total net profit accumulated so far
        cash_investment: Cash invested in the vehicle (None if not set)
        current_loan_balance: Current loan balance (None if no loan)
    
    Returns:
        Tuple of (principal_payment_amount, new_loan_balance)
        principal_payment_amount: Amount to apply to principal (0 if cash not recovered or no loan)
        new_loan_balance: Updated loan balance after principal payment
    """
    if not cash_investment or cash_investment <= 0:
        return (0.0, current_loan_balance)
    
    if not current_loan_balance or current_loan_balance <= 0:
        return (0.0, current_loan_balance)
    
    # Check if cash investment is fully recovered
    if cumulative_net_profit < cash_investment:
        # Cash investment not yet recovered, no principal payment
        return (0.0, current_loan_balance)
    
    # Calculate excess profit (profit beyond cash recovery)
    excess_profit = cumulative_net_profit - cash_investment
    
    # Apply excess profit to loan principal (up to current balance)
    principal_payment = min(excess_profit, current_loan_balance)
    new_loan_balance = max(0.0, current_loan_balance - principal_payment)
    
    return (round(principal_payment, 2), round(new_loan_balance, 2))

