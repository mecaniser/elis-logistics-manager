# Settlement PDF Extraction Tool

This tool extracts structured data from settlement PDFs and converts them to JSON format. This approach provides:

- **More accurate data extraction**: Dedicated extraction logic separate from database operations
- **JSON-first workflow**: Store structured JSON instead of PDFs in the database
- **Batch processing**: Process multiple PDFs at once
- **Validation**: Validate extracted data before importing
- **Flexibility**: Use JSON files for data migration, backups, or external processing

## Architecture

```
PDF Files → Extraction Tool → JSON Files → Database Import
```

Instead of:
```
PDF Files → Direct Database Upload → PDF stored in DB
```

## Usage

### 1. Extract Single PDF

```bash
cd backend
python extract_settlements.py path/to/settlement.pdf
```

This creates `settlement_extracted.json` in the same directory.

### 2. Extract with Custom Output

```bash
python extract_settlements.py settlement.pdf -o output.json
```

### 3. Extract with Settlement Type Hint

```bash
python extract_settlements.py settlement.pdf -t "277 Logistics"
```

Available types:
- `277 Logistics`
- `NBM Transport LLC`
- `Owner Operator Income Sheet`

### 4. Batch Extract Directory

```bash
python extract_settlements.py ./pdfs/ -b
```

Processes all PDFs in the directory and creates corresponding JSON files.

### 5. Batch Extract with Output Directory

```bash
python extract_settlements.py ./pdfs/ -b -o ./json_output/
```

## JSON Structure

The extracted JSON follows this structure:

```json
{
  "source_file": "settlement.pdf",
  "extraction_date": "2025-01-15T10:30:00",
  "settlement_type": "277 Logistics",
  "settlements": [
    {
      "metadata": {
        "settlement_date": "2025-01-10",
        "week_start": "2025-01-06",
        "week_end": "2025-01-10",
        "license_plate": "VW9327",
        "driver_id": null
      },
      "revenue": {
        "gross_revenue": 5000.00,
        "net_profit": 3500.00
      },
      "expenses": {
        "total_expenses": 1500.00,
        "categories": {
          "fuel": 800.00,
          "dispatch_fee": 400.00,
          "driver_pay": 200.00,
          "payroll_fee": 100.00
        }
      },
      "metrics": {
        "miles_driven": 1200.5,
        "blocks_delivered": 12
      },
      "driver_pay": {
        "driver_pay": 2000.00,
        "payroll_fee": 200.00
      }
    }
  ]
}
```

## Importing JSON to Database

### Via API

Use the `/settlements/upload-json` endpoint:

```python
import requests
import json

with open('settlement_extracted.json', 'r') as f:
    json_data = json.load(f)

response = requests.post(
    'http://localhost:8000/api/settlements/upload-json',
    data={'json_data': json.dumps(json_data)}
)
```

### Via Python Script

```python
from app.utils.settlement_extractor import SettlementExtractor
from app.database import get_db
from app.routers.settlements import upload_settlement_json
import json

# Extract from PDF
extractor = SettlementExtractor()
data = extractor.extract_from_pdf('settlement.pdf')

# Import to database
db = next(get_db())
result = upload_settlement_json(json.dumps(data), db)
```

## Benefits

1. **No PDF Storage**: JSON files are much smaller and easier to work with
2. **Better Accuracy**: Extraction logic can be refined independently
3. **Data Validation**: Validate JSON before database import
4. **Batch Processing**: Process hundreds of PDFs efficiently
5. **Version Control**: JSON files can be versioned and tracked
6. **External Processing**: Use JSON with other tools/systems
7. **Backup & Migration**: Easy to backup and migrate data

## Workflow Recommendations

### Recommended Workflow

1. **Extract**: Run extraction tool on PDFs to generate JSON files
2. **Review**: Manually review JSON files for accuracy
3. **Validate**: Validate JSON against schema (optional)
4. **Import**: Import JSON files to database via API or script
5. **Archive**: Archive PDFs separately (not in database)

### PDF Storage Strategy

- **Option 1**: Store PDFs in separate archive directory (not in database)
- **Option 2**: Store PDFs in cloud storage (S3, etc.) with references in JSON
- **Option 3**: Don't store PDFs at all - rely on JSON data only

## Schema Validation

The JSON schema is defined in `app/utils/settlement_json_schema.json`. You can validate extracted JSON files:

```bash
# Using jsonschema library
pip install jsonschema
python -c "import json, jsonschema; jsonschema.validate(json.load(open('settlement_extracted.json')), json.load(open('app/utils/settlement_json_schema.json')))"
```

## Troubleshooting

### Extraction Fails

- Check PDF format matches expected settlement types
- Try specifying settlement type with `-t` flag
- Check PDF is not corrupted or password-protected

### Import Fails

- Ensure trucks exist in database with matching license plates
- Check for duplicate settlements (same truck + date)
- Validate JSON structure matches schema

### Multi-Truck PDFs

For NBM Transport LLC PDFs with multiple trucks:
- Extraction tool automatically detects and separates trucks
- Each truck gets its own entry in the `settlements` array
- Import endpoint processes all settlements from the JSON

## Future Enhancements

- [ ] Add JSON schema validation to extraction tool
- [ ] Add data quality checks (missing fields, outliers)
- [ ] Add PDF metadata extraction (file size, creation date)
- [ ] Add support for additional settlement types
- [ ] Add web UI for JSON upload and validation

