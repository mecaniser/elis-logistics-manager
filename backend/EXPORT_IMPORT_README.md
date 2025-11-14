# Settlement Data Export/Import

This directory contains utilities to export and import settlement data to/from JSON files.

## Export Settlements

Export all settlements from the database to a JSON file:

```bash
cd backend
source venv/bin/activate
python3 export_settlements.py -o settlements_export.json
```

### Export File Structure

The exported JSON file contains:

```json
{
  "export_date": "2025-11-14T04:07:28.293926",
  "version": "1.0",
  "metadata": {
    "total_settlements": 83,
    "total_trucks": 2,
    "total_drivers": 0
  },
  "trucks": [
    {
      "id": 1,
      "name": "Volvo 417",
      "license_plate_active": "VW9327",
      "license_plate_history": ["VW9327", "VV9952"]
    }
  ],
  "drivers": [...],
  "settlements": [
    {
      "id": 111,
      "truck_id": 1,
      "truck_name": "Volvo 417",
      "driver_id": null,
      "driver_name": null,
      "settlement_date": "2025-11-08",
      "week_start": "2025-11-03",
      "week_end": "2025-11-08",
      "miles_driven": null,
      "blocks_delivered": 3,
      "gross_revenue": 5962.32,
      "expenses": 4438.14,
      "expense_categories": {
        "fuel": 1650.0,
        "dispatch_fee": 476.99,
        ...
      },
      "net_profit": 1524.18,
      "license_plate": "VW9327",
      "settlement_type": "277 Logistics",
      "pdf_file_path": "uploads/...",
      "created_at": "2025-11-14T08:43:42"
    }
  ]
}
```

## Import Settlements

Import settlements from a JSON file into the database:

```bash
cd backend
source venv/bin/activate
python3 import_settlements.py settlements_export.json
```

### Options

- `--force`: Overwrite existing settlements (default: skip existing settlements)

### Import Behavior

- **Skips duplicates**: By default, settlements with the same `truck_id` and `settlement_date` are skipped
- **Validates trucks**: Checks that truck IDs exist in the database before importing
- **Preserves relationships**: Maintains truck_id and driver_id relationships

## Use Cases

1. **Backup**: Export all settlement data for backup purposes
2. **Migration**: Move data between databases or environments
3. **Analysis**: Export data for external analysis tools
4. **Data Recovery**: Restore settlements from a backup JSON file

## Notes

- The export includes reference data (trucks, drivers) for context
- All dates are exported in ISO format (YYYY-MM-DD)
- Decimal values are converted to floats for JSON compatibility
- The `id` field is included but will be auto-generated on import (unless using `--force`)

