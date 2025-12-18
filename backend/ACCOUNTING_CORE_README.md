# Accounting Core Implementation

This document describes the core accounting models and endpoints for the Elis Group Manager.

## Models

### Tenant
- `id`: Primary key
- `name`: Business name (unique)
- `business_type`: String enum (LOGISTICS | TECH | REAL_ESTATE)
- `created_at`: Timestamp

### ChartOfAccount
- `id`: Primary key
- `tenant_id`: Foreign key to tenants (required, indexed)
- `code`: Account code string (e.g., "1000")
- `name`: Account name
- `account_type`: String enum (ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE)
- `parent_id`: Optional self-reference for hierarchy
- `truck_id`: Optional foreign key (for per-asset accounting)
- `is_active`: Boolean (default: true)
- `created_at`: Timestamp

**Constraints:**
- Unique: `(tenant_id, code, truck_id)`
- Index: `(tenant_id, account_type, is_active)`

### JournalEntry
- `id`: Primary key
- `tenant_id`: Foreign key to tenants (required, indexed)
- `entry_date`: Date
- `reference_type`: String enum (SETTLEMENT | REPAIR | MANUAL | ADJUSTMENT)
- `reference_id`: Optional integer
- `description`: String
- `truck_id`: Optional foreign key
- `created_at`: Timestamp

### JournalEntryLine
- `id`: Primary key
- `tenant_id`: Foreign key to tenants (required, indexed) - explicit isolation
- `journal_entry_id`: Foreign key to journal_entries
- `account_id`: Foreign key to chart_of_accounts
- `debit`: Numeric (default: 0)
- `credit`: Numeric (default: 0)
- `description`: Optional string
- `truck_id`: Optional foreign key
- `created_at`: Timestamp

## Validation Rules

1. **Balance Rule**: Sum of debits MUST equal sum of credits
2. **XOR Rule**: Each line must have exactly one side: `(debit > 0 XOR credit > 0)` - not both, not neither
3. **Tenant Isolation**: All accounts referenced must belong to same `tenant_id` as the entry
4. **Line Tenant Match**: All lines must share the same `tenant_id` as entry

## Export Features

The system supports exporting accounting reports in multiple formats:

### Export Formats
- **CSV**: For spreadsheet import
- **Excel**: For advanced analysis (.xlsx)
- **PDF**: For professional reporting

### Available Exports
- Journal Entries (CSV, Excel)
- General Ledger (CSV, Excel)
- Balance Sheet (PDF, Excel)
- Income Statement (PDF, Excel)
- Trial Balance (CSV, Excel, PDF)

### Dependencies
Export functionality requires:
- `openpyxl==3.1.2` (Excel)
- `reportlab==4.0.7` (PDF)

Install via:
```bash
pip install -r requirements.txt
```

## Endpoints

### Initialize Chart of Accounts

**POST** `/api/accounting/chart-of-accounts/initialize`

Initializes minimal Logistics Chart of Accounts. Returns 409 if accounts already exist.

**Headers:**
```
X-Tenant-ID: <tenant_id>
```

**Response:** List of created accounts

**Example:**
```bash
curl -X POST "http://localhost:8000/api/accounting/chart-of-accounts/initialize" \
  -H "X-Tenant-ID: 1" \
  -H "Content-Type: application/json"
```

**Minimal Account List (Logistics):**
- **ASSET**: 1000 Cash, 1500 Vehicles & Equipment, 1600 Accumulated Depreciation
- **LIABILITY**: 2100 Loans Payable, 2200 Taxes Payable
- **EQUITY**: 3000 Owner Equity, 3100 Retained Earnings
- **INCOME**: 4000 Settlement Income
- **EXPENSE**: 5000 Fuel, 5100 Maintenance & Repairs, 5200 Insurance, 5300 Dispatch Fees, 5400 Payroll Fees

### Get Chart of Accounts

**GET** `/api/accounting/chart-of-accounts`

**Query Parameters:**
- `account_type` (optional): Filter by account type
- `is_active` (optional): Filter by active status
- `truck_id` (optional): Filter by truck (for per-asset accounting)

**Headers:**
```
X-Tenant-ID: <tenant_id>
```

**Example:**
```bash
curl "http://localhost:8000/api/accounting/chart-of-accounts?account_type=Asset" \
  -H "X-Tenant-ID: 1"
```

### Create Manual Journal Entry

**POST** `/api/accounting/journal-entries`

**Headers:**
```
X-Tenant-ID: <tenant_id>
Content-Type: application/json
```

**Request Body:**
```json
{
  "entry_date": "2024-01-15",
  "description": "Test settlement",
  "reference_type": "manual",
  "lines": [
    {
      "account_id": 1,
      "debit": 1000.00,
      "credit": 0.00,
      "description": "Cash received"
    },
    {
      "account_id": 8,
      "debit": 0.00,
      "credit": 1000.00,
      "description": "Settlement income"
    }
  ]
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/accounting/journal-entries" \
  -H "X-Tenant-ID: 1" \
  -H "Content-Type: application/json" \
  -d '{
    "entry_date": "2024-01-15",
    "description": "Test settlement",
    "reference_type": "manual",
    "lines": [
      {
        "account_id": 1,
        "debit": 1000.00,
        "credit": 0.00,
        "description": "Cash received"
      },
      {
        "account_id": 8,
        "debit": 0.00,
        "credit": 1000.00,
        "description": "Settlement income"
      }
    ]
  }'
```

**Validation Errors:**
- `400 Bad Request`: If debits don't equal credits
- `400 Bad Request`: If any line has both debit and credit > 0
- `400 Bad Request`: If any line has both debit and credit = 0
- `400 Bad Request`: If accounts don't belong to same tenant
- `400 Bad Request`: If line tenant_id doesn't match entry tenant_id

### Get Journal Entries

**GET** `/api/accounting/journal-entries`

**Query Parameters:**
- `start_date` (optional): Filter from date (YYYY-MM-DD)
- `end_date` (optional): Filter to date (YYYY-MM-DD)
- `reference_type` (optional): Filter by reference type
- `reference_id` (optional): Filter by reference ID
- `truck_id` (optional): Filter by truck

**Headers:**
```
X-Tenant-ID: <tenant_id>
```

**Example:**
```bash
curl "http://localhost:8000/api/accounting/journal-entries?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-Tenant-ID: 1"
```

### Export Endpoints

**GET** `/api/accounting/export/journal-entries`
**GET** `/api/accounting/export/general-ledger`
**GET** `/api/accounting/export/balance-sheet`
**GET** `/api/accounting/export/income-statement`
**GET** `/api/accounting/export/trial-balance`

All export endpoints accept format parameter (`csv`, `excel`, or `pdf` where applicable) and return file blobs.

### Financial Reports

**GET** `/api/accounting/income-statement`
**GET** `/api/accounting/balance-sheet`
**GET** `/api/accounting/tax-year-summary`
**GET** `/api/accounting/schedule-c`
**GET** `/api/accounting/general-ledger`

## Migration & Setup

### 1. Run Migration

Add `tenant_id` to `journal_entry_lines` table:

```bash
cd backend
python3 migrate_add_tenant_id_to_journal_entry_lines.py
```

### 2. Seed Test Data

Create test tenant and journal entry:

```bash
cd backend
python3 seed_accounting_core.py
```

This will:
1. Create tenant "Elis Logistics LLC" (business_type: logistics)
2. Initialize chart of accounts
3. Create test journal entry:
   - Debit Cash (1000) = $1,000.00
   - Credit Settlement Income (4000) = $1,000.00

## Testing

After running the seed script, verify:

1. **Tenant exists:**
```bash
curl "http://localhost:8000/api/tenants" | jq
```

2. **Chart of accounts initialized:**
```bash
curl "http://localhost:8000/api/accounting/chart-of-accounts" \
  -H "X-Tenant-ID: 1" | jq
```

3. **Journal entry created:**
```bash
curl "http://localhost:8000/api/accounting/journal-entries" \
  -H "X-Tenant-ID: 1" | jq
```

4. **Test validation - should fail (unbalanced):**
```bash
curl -X POST "http://localhost:8000/api/accounting/journal-entries" \
  -H "X-Tenant-ID: 1" \
  -H "Content-Type: application/json" \
  -d '{
    "entry_date": "2024-01-15",
    "description": "Invalid entry",
    "lines": [
      {"account_id": 1, "debit": 1000.00, "credit": 0.00},
      {"account_id": 8, "debit": 0.00, "credit": 500.00}
    ]
  }'
```

5. **Test validation - should fail (both sides > 0):**
```bash
curl -X POST "http://localhost:8000/api/accounting/journal-entries" \
  -H "X-Tenant-ID: 1" \
  -H "Content-Type: application/json" \
  -d '{
    "entry_date": "2024-01-15",
    "description": "Invalid entry",
    "lines": [
      {"account_id": 1, "debit": 1000.00, "credit": 1000.00}
    ]
  }'
```

6. **Test validation - should fail (both sides = 0):**
```bash
curl -X POST "http://localhost:8000/api/accounting/journal-entries" \
  -H "X-Tenant-ID: 1" \
  -H "Content-Type: application/json" \
  -d '{
    "entry_date": "2024-01-15",
    "description": "Invalid entry",
    "lines": [
      {"account_id": 1, "debit": 0.00, "credit": 0.00}
    ]
  }'
```

## Notes

- All endpoints require `X-Tenant-ID` header for tenant isolation
- Account types use "Revenue" instead of "Income" in the database (mapped from spec)
- The minimal account list matches the specification exactly
- Validation is enforced at both service layer and can be enhanced with DB constraints

