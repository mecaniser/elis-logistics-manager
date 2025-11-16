"""
Validation utilities for settlement extraction

Provides validation functions to check the accuracy of extracted settlement data,
especially for multi-truck PDFs where data needs to be correctly separated.
"""
from typing import Dict, List, Optional, Tuple
from decimal import Decimal


class ValidationError:
    """Represents a validation error or warning"""
    
    def __init__(self, level: str, category: str, message: str, details: Optional[Dict] = None):
        """
        Args:
            level: 'error' or 'warning'
            category: Category of validation (e.g., 'revenue', 'expenses', 'blocks')
            message: Human-readable error message
            details: Optional dictionary with additional details
        """
        self.level = level
        self.category = category
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "details": self.details
        }


def validate_revenue(settlements: List[Dict], expected_total: Optional[float] = None, 
                    tolerance: float = 0.01) -> List[ValidationError]:
    """
    Validate that sum of per-truck gross revenue matches expected total.
    
    Args:
        settlements: List of settlement dictionaries (from multi-truck PDF)
        expected_total: Expected total gross revenue (if known)
        tolerance: Allowed difference in dollars
        
    Returns:
        List of ValidationError objects
    """
    errors = []
    
    # Calculate sum of per-truck gross revenue
    total_gross = sum(
        float(s.get("gross_revenue", 0) or 0) 
        for s in settlements
    )
    
    if expected_total is not None:
        difference = abs(total_gross - expected_total)
        if difference > tolerance:
            errors.append(ValidationError(
                level="error",
                category="revenue",
                message=f"Gross revenue mismatch: sum of trucks ({total_gross:.2f}) != expected ({expected_total:.2f})",
                details={
                    "calculated_total": total_gross,
                    "expected_total": expected_total,
                    "difference": difference
                }
            ))
    
    return errors


def validate_expenses(settlements: List[Dict], expected_total: Optional[float] = None,
                     shared_expenses: Optional[Dict[str, float]] = None,
                     tolerance: float = 0.01) -> List[ValidationError]:
    """
    Validate that sum of per-truck expenses matches expected total.
    Accounts for shared expenses that are split between trucks.
    
    Args:
        settlements: List of settlement dictionaries
        expected_total: Expected total expenses (if known)
        shared_expenses: Dictionary of shared expenses (e.g., {"insurance": 700.0})
        tolerance: Allowed difference in dollars
        
    Returns:
        List of ValidationError objects
    """
    errors = []
    
    # Calculate sum of per-truck expenses
    total_expenses = sum(
        float(s.get("expenses", 0) or 0)
        for s in settlements
    )
    
    # If shared expenses are provided, account for them
    # Shared expenses are split, so they appear in each truck's expenses
    # The total should be: sum(truck_expenses) - sum(shared_expenses) + sum(shared_expenses)
    # Which simplifies to: sum(truck_expenses)
    # But we need to account for the fact that shared expenses are duplicated
    
    if shared_expenses:
        shared_total = sum(shared_expenses.values())
        # Shared expenses are split, so each truck has shared_total/num_trucks
        # Total shared expenses in all trucks = shared_total
        # So total_expenses should already include shared expenses correctly
        
        # Check if shared expenses are correctly allocated
        num_trucks = len(settlements)
        expected_shared_per_truck = shared_total / num_trucks if num_trucks > 0 else 0
        
        for idx, settlement in enumerate(settlements):
            expense_categories = settlement.get("expense_categories", {})
            for shared_key, shared_value in shared_expenses.items():
                expected_per_truck = shared_value / num_trucks if num_trucks > 0 else 0
                actual = float(expense_categories.get(shared_key, 0) or 0)
                
                if abs(actual - expected_per_truck) > tolerance:
                    errors.append(ValidationError(
                        level="warning",
                        category="expenses",
                        message=f"Truck {idx + 1}: {shared_key} allocation mismatch (expected {expected_per_truck:.2f}, got {actual:.2f})",
                        details={
                            "truck_index": idx,
                            "expense_category": shared_key,
                            "expected": expected_per_truck,
                            "actual": actual,
                            "difference": abs(actual - expected_per_truck)
                        }
                    ))
    
    if expected_total is not None:
        difference = abs(total_expenses - expected_total)
        if difference > tolerance:
            errors.append(ValidationError(
                level="error",
                category="expenses",
                message=f"Total expenses mismatch: sum of trucks ({total_expenses:.2f}) != expected ({expected_total:.2f})",
                details={
                    "calculated_total": total_expenses,
                    "expected_total": expected_total,
                    "difference": difference
                }
            ))
    
    return errors


def validate_blocks(settlements: List[Dict], expected_total: Optional[int] = None) -> List[ValidationError]:
    """
    Validate that all blocks are assigned to a truck.
    
    Args:
        settlements: List of settlement dictionaries
        expected_total: Expected total number of blocks (if known)
        
    Returns:
        List of ValidationError objects
    """
    errors = []
    
    total_blocks = sum(
        int(s.get("blocks_delivered", 0) or 0)
        for s in settlements
    )
    
    if expected_total is not None:
        if total_blocks != expected_total:
            errors.append(ValidationError(
                level="error",
                category="blocks",
                message=f"Block count mismatch: sum of trucks ({total_blocks}) != expected ({expected_total})",
                details={
                    "calculated_total": total_blocks,
                    "expected_total": expected_total,
                    "difference": total_blocks - expected_total
                }
            ))
    
    # Check if any truck has zero blocks (might indicate assignment issue)
    for idx, settlement in enumerate(settlements):
        blocks = int(settlement.get("blocks_delivered", 0) or 0)
        if blocks == 0:
            errors.append(ValidationError(
                level="warning",
                category="blocks",
                message=f"Truck {idx + 1} ({settlement.get('license_plate', 'unknown')}) has zero blocks assigned",
                details={
                    "truck_index": idx,
                    "license_plate": settlement.get("license_plate"),
                    "blocks": blocks
                }
            ))
    
    return errors


def validate_fuel(settlements: List[Dict], expected_total: Optional[float] = None,
                 tolerance: float = 0.01) -> List[ValidationError]:
    """
    Validate fuel amounts per truck.
    
    Args:
        settlements: List of settlement dictionaries
        expected_total: Expected total fuel amount (if known)
        tolerance: Allowed difference in dollars
        
    Returns:
        List of ValidationError objects
    """
    errors = []
    
    total_fuel = sum(
        float(s.get("expense_categories", {}).get("fuel", 0) or 0)
        for s in settlements
    )
    
    if expected_total is not None:
        difference = abs(total_fuel - expected_total)
        if difference > tolerance:
            errors.append(ValidationError(
                level="error",
                category="fuel",
                message=f"Fuel total mismatch: sum of trucks ({total_fuel:.2f}) != expected ({expected_total:.2f})",
                details={
                    "calculated_total": total_fuel,
                    "expected_total": expected_total,
                    "difference": difference
                }
            ))
    
    # Check for trucks with zero fuel (might indicate extraction issue)
    for idx, settlement in enumerate(settlements):
        fuel = float(settlement.get("expense_categories", {}).get("fuel", 0) or 0)
        blocks = int(settlement.get("blocks_delivered", 0) or 0)
        
        if blocks > 0 and fuel == 0:
            errors.append(ValidationError(
                level="warning",
                category="fuel",
                message=f"Truck {idx + 1} ({settlement.get('license_plate', 'unknown')}) has blocks but zero fuel",
                details={
                    "truck_index": idx,
                    "license_plate": settlement.get("license_plate"),
                    "blocks": blocks,
                    "fuel": fuel
                }
            ))
    
    return errors


def validate_driver_pay(settlements: List[Dict], expected_total: Optional[float] = None,
                        tolerance: float = 0.01) -> List[ValidationError]:
    """
    Validate driver pay amounts per truck.
    
    Args:
        settlements: List of settlement dictionaries
        expected_total: Expected total driver pay (if known)
        tolerance: Allowed difference in dollars
        
    Returns:
        List of ValidationError objects
    """
    errors = []
    
    total_driver_pay = sum(
        float(s.get("expense_categories", {}).get("driver_pay", 0) or 0)
        for s in settlements
    )
    
    if expected_total is not None:
        difference = abs(total_driver_pay - expected_total)
        if difference > tolerance:
            errors.append(ValidationError(
                level="error",
                category="driver_pay",
                message=f"Driver pay total mismatch: sum of trucks ({total_driver_pay:.2f}) != expected ({expected_total:.2f})",
                details={
                    "calculated_total": total_driver_pay,
                    "expected_total": expected_total,
                    "difference": difference
                }
            ))
    
    # Check for trucks with zero driver pay but with blocks (might indicate extraction issue)
    for idx, settlement in enumerate(settlements):
        driver_pay = float(settlement.get("expense_categories", {}).get("driver_pay", 0) or 0)
        blocks = int(settlement.get("blocks_delivered", 0) or 0)
        
        if blocks > 0 and driver_pay == 0:
            errors.append(ValidationError(
                level="warning",
                category="driver_pay",
                message=f"Truck {idx + 1} ({settlement.get('license_plate', 'unknown')}) has blocks but zero driver pay",
                details={
                    "truck_index": idx,
                    "license_plate": settlement.get("license_plate"),
                    "blocks": blocks,
                    "driver_pay": driver_pay
                }
            ))
    
    return errors


def validate_net_profit(settlements: List[Dict], tolerance: float = 0.01) -> List[ValidationError]:
    """
    Validate that net profit = gross revenue - expenses for each truck.
    
    Args:
        settlements: List of settlement dictionaries
        tolerance: Allowed difference in dollars
        
    Returns:
        List of ValidationError objects
    """
    errors = []
    
    for idx, settlement in enumerate(settlements):
        gross_revenue = float(settlement.get("gross_revenue", 0) or 0)
        expenses = float(settlement.get("expenses", 0) or 0)
        net_profit = float(settlement.get("net_profit", 0) or 0)
        
        expected_net = gross_revenue - expenses
        difference = abs(net_profit - expected_net)
        
        if difference > tolerance:
            errors.append(ValidationError(
                level="error",
                category="net_profit",
                message=f"Truck {idx + 1} ({settlement.get('license_plate', 'unknown')}): net profit calculation mismatch",
                details={
                    "truck_index": idx,
                    "license_plate": settlement.get("license_plate"),
                    "gross_revenue": gross_revenue,
                    "expenses": expenses,
                    "calculated_net": expected_net,
                    "reported_net": net_profit,
                    "difference": difference
                }
            ))
    
    return errors


def validate_multi_truck_extraction(settlements: List[Dict], 
                                   expected_totals: Optional[Dict] = None,
                                   shared_expenses: Optional[Dict[str, float]] = None) -> Dict:
    """
    Run all validation checks on multi-truck extraction results.
    
    Args:
        settlements: List of settlement dictionaries from multi-truck PDF
        expected_totals: Dictionary with expected totals (e.g., {"gross_revenue": 10000.0, "expenses": 5000.0})
        shared_expenses: Dictionary of shared expenses
        
    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,
            "errors": List[ValidationError],
            "warnings": List[ValidationError],
            "summary": Dict
        }
    """
    all_errors = []
    all_warnings = []
    
    expected_totals = expected_totals or {}
    
    # Run all validation checks
    all_errors.extend(validate_revenue(
        settlements, 
        expected_totals.get("gross_revenue")
    ))
    
    all_errors.extend(validate_expenses(
        settlements,
        expected_totals.get("expenses"),
        shared_expenses
    ))
    
    all_errors.extend(validate_blocks(
        settlements,
        expected_totals.get("blocks_delivered")
    ))
    
    all_errors.extend(validate_fuel(
        settlements,
        expected_totals.get("fuel")
    ))
    
    all_errors.extend(validate_driver_pay(
        settlements,
        expected_totals.get("driver_pay")
    ))
    
    all_errors.extend(validate_net_profit(settlements))
    
    # Separate errors and warnings
    errors_only = []
    warnings_only = []
    
    for error in all_errors:
        if error.level == "error":
            errors_only.append(error)
        else:
            warnings_only.append(error)
    
    # Create summary
    summary = {
        "total_settlements": len(settlements),
        "error_count": len(errors_only),
        "warning_count": len(warnings_only),
        "is_valid": len(errors_only) == 0
    }
    
    return {
        "is_valid": len(errors_only) == 0,
        "errors": [e.to_dict() for e in errors_only],
        "warnings": [w.to_dict() for w in warnings_only],
        "summary": summary
    }

