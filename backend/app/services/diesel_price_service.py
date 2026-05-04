"""
Historical diesel benchmark lookups and fuel-spend-based mile estimation.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

EIA_API_URL = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
EIA_API_KEY = os.getenv("EIA_API_KEY")
EIA_DIESEL_SERIES = os.getenv("EIA_DIESEL_SERIES", "EMD_EPD2D_PTE_R10_DPG")
MIN_ADJUSTED_DIESEL_PRICE = 0.01


def benchmark_week_start(target_date: date) -> date:
    """Return the Monday-aligned week used by the EIA weekly diesel series."""
    return target_date - timedelta(days=target_date.weekday())


def get_historical_diesel_price(reference_date: date) -> Optional[float]:
    """Return the EIA weekly diesel benchmark for the Monday of the given week."""
    if not EIA_API_KEY:
        return None
    return _fetch_historical_diesel_price(benchmark_week_start(reference_date).isoformat())


@lru_cache(maxsize=256)
def _fetch_historical_diesel_price(period_iso: str) -> Optional[float]:
    params = [
        ("api_key", EIA_API_KEY or ""),
        ("frequency", "weekly"),
        ("data[0]", "value"),
        ("facets[series][]", EIA_DIESEL_SERIES),
        ("start", period_iso),
        ("end", period_iso),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("offset", "0"),
        ("length", "1"),
    ]

    try:
        response = httpx.get(EIA_API_URL, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("response", {}).get("data", [])
        if not rows:
            return None
        value = float(rows[0]["value"])
        return round(value, 3)
    except Exception as exc:
        logger.warning("Failed to fetch EIA diesel price for %s: %s", period_iso, exc)
        return None


def estimate_miles_from_fuel_spend(
    *,
    fuel_spend: float,
    benchmark_price_per_gallon: float,
    mpg: float,
    discount_per_gallon: float = 0.0,
    benchmark_period: Optional[date] = None,
) -> Optional[dict]:
    """Estimate gallons and miles from fuel spend using a weekly diesel benchmark."""
    if fuel_spend <= 0 or benchmark_price_per_gallon <= 0 or mpg <= 0:
        return None

    adjusted_price = max(benchmark_price_per_gallon - max(discount_per_gallon, 0.0), MIN_ADJUSTED_DIESEL_PRICE)
    estimated_gallons = fuel_spend / adjusted_price
    estimated_miles = estimated_gallons * mpg

    return {
        "diesel_price_per_gallon": round(benchmark_price_per_gallon, 3),
        "fuel_card_discount_per_gallon": round(max(discount_per_gallon, 0.0), 3),
        "effective_fuel_price_per_gallon": round(adjusted_price, 3),
        "estimated_gallons": round(estimated_gallons, 2),
        "estimated_mpg": round(mpg, 2),
        "estimated_miles_driven": round(estimated_miles, 2),
    }


def merge_overview_amounts(
    overview_amounts: Optional[Dict[str, Any]],
    extra_amounts: Dict[str, float],
) -> Dict[str, Any]:
    """Merge derived display-only values without discarding existing overview amounts."""
    merged = dict(overview_amounts or {})
    merged.update(extra_amounts)
    return merged


def maybe_populate_estimated_miles(
    settlement_data: Dict[str, Any],
    *,
    mpg: float,
    discount_per_gallon: float = 0.0,
) -> bool:
    """Populate estimated miles on a settlement payload when fuel spend exists but miles do not."""
    existing_miles = settlement_data.get("miles_driven")
    try:
        if existing_miles is not None and float(existing_miles) > 0:
            return False
    except (TypeError, ValueError):
        return False

    expense_categories = settlement_data.get("expense_categories")
    if not isinstance(expense_categories, dict):
        return False

    fuel_spend = float(expense_categories.get("fuel") or 0.0)
    if fuel_spend <= 0:
        return False

    reference_date = settlement_data.get("week_start") or settlement_data.get("settlement_date")
    if not isinstance(reference_date, date):
        return False

    benchmark_period = benchmark_week_start(reference_date)
    benchmark_price = get_historical_diesel_price(benchmark_period)
    if benchmark_price is None:
        return False

    estimate = estimate_miles_from_fuel_spend(
        fuel_spend=fuel_spend,
        benchmark_price_per_gallon=benchmark_price,
        mpg=mpg,
        discount_per_gallon=discount_per_gallon,
        benchmark_period=benchmark_period,
    )
    if not estimate:
        return False

    settlement_data["miles_driven"] = estimate["estimated_miles_driven"]
    settlement_data["overview_amounts"] = merge_overview_amounts(
        settlement_data.get("overview_amounts"),
        estimate,
    )
    return True
