"""
Shared reserve-regime constants and formatting helpers.
"""
from datetime import date


RESERVE_REGIME_START_DATE = date(2026, 1, 1)


def format_deposit_description(settlement) -> str:
    """Format a consistent reserve deposit description."""
    if getattr(settlement, "week_start", None):
        return f"Reserve deposit, week of {settlement.week_start}"
    if getattr(settlement, "settlement_date", None):
        return f"Reserve deposit, settlement {settlement.settlement_date}"
    return "Reserve deposit"


def format_withdrawal_description(repair) -> str:
    """Format a consistent reserve withdrawal description."""
    label = getattr(repair, "title", None) or getattr(repair, "category", None) or "unspecified"
    return f"Repair: {label}"
