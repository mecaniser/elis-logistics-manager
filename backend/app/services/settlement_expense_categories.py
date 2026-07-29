"""Canonical categories for settlement deduction lines."""


def category_for_deduction(description: str) -> str:
    """Return a category based on the source description, never an estimate."""
    normalized = (description or "").lower()
    if "fleet manager" in normalized or "fleet management" in normalized:
        return "fleet_manager_support"
    if "cargo and liability insurance" in normalized or "insurance" in normalized:
        return "insurance"
    if "pre-pass" in normalized or "prepass" in normalized or "logbook" in normalized:
        return "prepass"
    if "ifta" in normalized:
        return "ifta"
    if "parking" in normalized:
        return "truck_parking"
    if "loan interest" in normalized or "interest" in normalized:
        return "loan_interest"
    return "deduct"
