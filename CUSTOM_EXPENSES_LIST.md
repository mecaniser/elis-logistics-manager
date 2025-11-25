# Custom Expenses - Complete List

This document lists all expense types that are categorized as "custom" expenses in the system.

## Standard Categories (NOT Custom)

These are the standard expense categories that are tracked separately:

1. **fuel** - Fuel costs
2. **dispatch_fee** - Dispatch fees
3. **insurance** - Insurance costs
4. **safety** - Safety-related expenses
5. **prepass** - Prepass fees
6. **ifta** - IFTA (International Fuel Tax Agreement) fees
7. **driver_pay** - Driver's pay
8. **payroll_fee** - Payroll processing fees
9. **loan_interest** - Loan interest (calculated separately)
10. **truck_parking** - Truck parking fees
11. **service_on_truck** - Service/maintenance on truck

## Custom Expense Categories

Any expense that is **NOT** in the standard list above gets categorized as "custom". Here are the specific types:

### 1. **Decals** (`decals`)
- **Source**: Extracted from PDF `statement_totals.decals`
- **Mapped from**: `decals` field in consolidated settlement JSON
- **Example**: Vehicle decal fees (e.g., $50.00)

### 2. **Deductions** (`deduct`)
- **Source**: Extracted from PDF as "Deductions" or "Other Deductions"
- **Mapped from**: `deductions` field in consolidated settlement JSON → normalized to `deduct` category
- **PDF Patterns**:
  - `Deductions $XXX.XX`
  - `Other Deductions $XXX.XX`
  - `Additional Deductions $XXX.XX`
  - `Total Deductions $XXX.XX`
- **Note**: In multi-truck settlements, deductions are applied to the first truck only (common settlement expense)
- **Example**: Various deductions that don't fit other categories

### 3. **Reimbursement** (`reimbursement`)
- **Source**: Extracted from PDF as "Reimbursement" or "Reimbursment" (typo handling)
- **Mapped from**: `reimbursment` or `reimbursement` field in consolidated settlement JSON
- **Special Handling**: Reimbursements are **credits** (reduce expenses), not charges
- **Calculation**: Subtracted from total expenses rather than added
- **Example**: Reimbursements for tolls, parking, etc.

### 4. **Fees** (`fees`)
- **Source**: Explicitly mapped to custom in analytics
- **Mapped from**: Any category named `fees` or `other`
- **Example**: Miscellaneous fees not categorized elsewhere

### 5. **Other** (`other`)
- **Source**: Explicitly mapped to custom in analytics
- **Mapped from**: Any category named `other`
- **Example**: Other miscellaneous expenses

### 6. **Custom Categories** (`custom_*`)
- **Source**: User-created custom categories
- **Pattern**: Any category starting with `custom_` prefix
- **Examples**:
  - `custom_truck_parking` → "Truck Parking"
  - `custom_handles_replaced` → "Handles Replaced"
  - `custom_registration_fee` → "Registration Fee"

### 7. **Uncategorized Expenses**
- **Source**: Any expense category that doesn't match standard categories
- **When it happens**:
  - PDF parser finds expenses but can't categorize them
  - Calculated expenses (gross revenue - net profit) when no categories found
  - Any new expense type not yet added to standard categories

## How Custom Expenses Are Processed

### In `normalize_expense_categories()` (ingest_consolidated_settlements.py)
```python
cat_map = {
    "decals": totals.get("decals", 0) or 0,
    "deduct": totals.get("deductions", 0) or 0,
    "reimbursement": totals.get("reimbursment", 0) or totals.get("reimbursement", 0) or 0,
    # ... standard categories ...
}
```

### In Analytics Router (`analytics.py`)
Categories are mapped to "custom" if:
1. Category is `fees` or `other` → explicitly mapped
2. Category starts with `custom_` → aggregated into custom
3. Category is NOT in `STANDARD_CATEGORIES` → aggregated into custom

### In PDF Parser (`pdf_parser.py`)
- Deductions extracted from PDF go into `custom` category
- In multi-truck settlements, deductions applied to first truck only
- If expenses are calculated but not categorized, they go into `custom`

## Examples from Actual Data

From `417_consolidated_settlement.json`:
- **decals**: Found with value `50.0` in one settlement
- **deductions**: Found with values like `320.83`, `49.19`, `0.0`
- **reimbursment**: Found with value `0.0` (typo in source data)

## Summary

**Custom expenses include:**
1. ✅ **Decals** - Vehicle decal fees
2. ✅ **Deductions** - Various deductions from settlements
3. ✅ **Reimbursements** - Credits/reimbursements (handled specially)
4. ✅ **Fees** - Miscellaneous fees
5. ✅ **Other** - Other uncategorized expenses
6. ✅ **Custom_*** - User-defined custom categories
7. ✅ **Any uncategorized expense** - Expenses that don't match standard categories

**Note**: Reimbursements are stored as positive values but are subtracted from total expenses since they're credits, not charges.


