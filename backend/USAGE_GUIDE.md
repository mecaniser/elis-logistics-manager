# Settlement Extraction Tool - Quick Usage Guide

## Basic Usage

### 1. Extract Single PDF

```bash
cd backend
python3 extract_settlements.py uploads/your_settlement.pdf
```

This creates `your_settlement_extracted.json` in the same directory.

### 2. Extract with Custom Output File

```bash
python3 extract_settlements.py uploads/settlement.pdf -o extracted_data.json
```

### 3. Extract with Settlement Type Hint

If the tool can't auto-detect the type, specify it:

```bash
python3 extract_settlements.py settlement.pdf -t "277 Logistics"
# or
python3 extract_settlements.py settlement.pdf -t "NBM Transport LLC"
# or
python3 extract_settlements.py settlement.pdf -t "Owner Operator Income Sheet"
```

### 4. Batch Extract All PDFs in a Directory

```bash
python3 extract_settlements.py uploads/ -b
```

This processes all PDFs in `uploads/` and creates corresponding JSON files.

### 5. Batch Extract with Output Directory

```bash
python3 extract_settlements.py uploads/ -b -o json_output/
```

Creates all JSON files in the `json_output/` directory.

## Viewing Extracted Data

After extraction, you can view the JSON:

```bash
# Pretty print JSON
cat settlement_extracted.json | python3 -m json.tool

# Or use jq if installed
cat settlement_extracted.json | jq
```

## Importing JSON to Database

### Option 1: Via API (Recommended)

Use the `/api/settlements/upload-json` endpoint:

```python
import requests
import json

# Read extracted JSON
with open('settlement_extracted.json', 'r') as f:
    json_data = json.load(f)

# Upload to API
response = requests.post(
    'http://localhost:8000/api/settlements/upload-json',
    data={'json_data': json.dumps(json_data)}
)

print(response.json())
```

### Option 2: Via Python Script

```python
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.routers.settlements import upload_settlement_json
import json

# Read JSON file
with open('settlement_extracted.json', 'r') as f:
    json_data = json.dumps(json.load(f))

# Import to database
db = SessionLocal()
try:
    result = upload_settlement_json(json_data, db)
    print(f"Imported {len(result)} settlements")
finally:
    db.close()
```

### Option 3: Via Frontend (Future)

You can add a JSON upload button in the frontend that calls the API endpoint.

## Example Workflow

### Step 1: Extract PDFs

```bash
# Extract all PDFs from uploads directory
cd backend
python3 extract_settlements.py uploads/ -b -o extracted_json/
```

### Step 2: Review JSON Files

```bash
# Check what was extracted
ls -lh extracted_json/
cat extracted_json/settlement_extracted.json | python3 -m json.tool | head -30
```

### Step 3: Import to Database

```python
import requests
import json
import os

api_url = "http://localhost:8000/api/settlements/upload-json"

# Import all JSON files
for json_file in os.listdir("extracted_json/"):
    if json_file.endswith(".json"):
        with open(f"extracted_json/{json_file}", 'r') as f:
            data = json.load(f)
        
        try:
            response = requests.post(api_url, data={'json_data': json.dumps(data)})
            print(f"✓ {json_file}: {response.status_code}")
        except Exception as e:
            print(f"✗ {json_file}: {e}")
```

## Troubleshooting

### "Could not find truck with license plate"

Make sure the truck exists in the database with the correct license plate. Check:

```python
from app.database import SessionLocal
from app.models.truck import Truck

db = SessionLocal()
trucks = db.query(Truck).all()
for t in trucks:
    print(f"{t.name}: {t.license_plate} (history: {t.license_plate_history})")
```

### "Settlement already exists"

The settlement for that truck and date already exists. You can:
- Skip that JSON file
- Delete the existing settlement first
- Modify the date in JSON if it's incorrect

### Extraction fails or returns empty data

- Check PDF format matches expected types
- Try specifying settlement type with `-t` flag
- Check PDF is not corrupted
- Review the PDF manually to see what data is available

## Benefits of This Approach

1. **No PDF Storage**: Database only stores structured JSON data
2. **Batch Processing**: Process hundreds of PDFs at once
3. **Data Validation**: Review JSON before importing
4. **Version Control**: JSON files can be tracked in git
5. **Backup**: Easy to backup and restore JSON data
6. **External Tools**: Use JSON with other systems/tools

## Next Steps

1. Extract your PDFs: `python3 extract_settlements.py uploads/ -b -o json_data/`
2. Review extracted JSON files
3. Import to database via API or script
4. Archive PDFs separately (optional)

