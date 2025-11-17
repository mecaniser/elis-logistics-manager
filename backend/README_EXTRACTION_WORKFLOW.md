# Two-Phase Settlement Extraction Workflow

This document describes the two-phase approach for extracting settlement data from PDFs, designed to handle both reliable single-truck PDFs and complex multi-truck PDFs that require validation.

## Overview

The extraction process is divided into two phases:

1. **Phase 1: Single-Truck PDF Processing** - Processes reliable PDFs that contain one truck per file
2. **Phase 2: Multi-Truck PDF Processing** - Processes complex PDFs with multiple trucks, includes validation
3. **Master Consolidation** - Merges both phases into a final consolidated JSON file

## Problem Statement

- **Single-truck PDFs**: Each PDF contains one truck with clear separation (reliable extraction)
- **Multi-truck PDFs**: One PDF contains both trucks with combined totals (requires careful parsing and validation)
- Current parser struggles to correctly separate blocks, fuel, driver pay, and expenses for multi-truck PDFs

## Phase 1: Single-Truck PDF Processing

### Purpose
Process all PDFs that contain only one license plate. These are reliable and can be batch processed without manual review.

### Usage

```bash
python consolidate_single_truck_settlements.py <pdf_directory> [options]
```

### Examples

```bash
# Process single-truck PDFs in directory
python consolidate_single_truck_settlements.py ./pdfs/

# Process with custom output directory
python consolidate_single_truck_settlements.py ./pdfs/ -o ./output/

# Process and save consolidated JSON
python consolidate_single_truck_settlements.py ./pdfs/ -o ./output/ --consolidate consolidated_single_truck.json
```

### Output

- Individual JSON files for each PDF (unless `--skip-individual` is used)
- Consolidated JSON file with all single-truck settlements
- `phase1_summary.json` with summary statistics

### What It Does

1. Scans directory for PDF files
2. Identifies single-truck vs multi-truck PDFs using detection logic
3. Processes only single-truck PDFs using `parse_amazon_relay_pdf()`
4. Consolidates all extracted settlements into one JSON file
5. Generates summary report

## Phase 2: Multi-Truck PDF Processing

### Purpose
Process PDFs that contain multiple trucks. Includes validation checks to ensure data is correctly separated.

### Usage

```bash
python process_multi_truck_settlements.py <pdf_directory> [options]
```

### Examples

```bash
# Process multi-truck PDFs in directory
python process_multi_truck_settlements.py ./pdfs/

# Process with custom output directory
python process_multi_truck_settlements.py ./pdfs/ -o ./output/

# Process and save consolidated JSON with validation report
python process_multi_truck_settlements.py ./pdfs/ -o ./output/ \
  --consolidate consolidated_multi_truck.json \
  --report validation_report.json
```

### Validation Checks

The script performs the following validation checks:

1. **Revenue Validation**: Sum of per-truck gross revenue matches expected total
2. **Expense Validation**: Sum of per-truck expenses matches expected total (accounting for shared expenses)
3. **Block Validation**: All blocks are assigned to a plate
4. **Fuel Validation**: Per-truck fuel amounts match expected patterns
5. **Driver Pay Validation**: Per-truck driver pay matches expected totals
6. **Net Profit Validation**: `gross_revenue - expenses == net_profit` for each truck

### Output

- Individual JSON files for each PDF (unless `--skip-individual` is used)
- Consolidated JSON file with all multi-truck settlements
- Validation report JSON file (if `--report` is specified)

### What It Does

1. Identifies multi-truck PDFs
2. Processes each PDF using `parse_amazon_relay_pdf_multi_truck()` with validation enabled
3. Runs validation checks on extracted data
4. Generates detailed validation reports
5. Consolidates validated settlements into JSON file

## Master Consolidation

### Purpose
Merge single-truck and multi-truck settlements into a final consolidated file, ensuring no duplicates.

### Usage

```bash
python consolidate_all_settlements.py <json_directory> [options]
```

### Examples

```bash
# Consolidate all JSON files in directory
python consolidate_all_settlements.py ./output/

# Consolidate with custom output file
python consolidate_all_settlements.py ./output/ -o final_consolidated.json

# Consolidate from specific phase files
python consolidate_all_settlements.py ./output/ \
  --phase1 consolidated_single_truck.json \
  --phase2 consolidated_multi_truck.json
```

### What It Does

1. Loads Phase 1 consolidated JSON (or scans for individual files)
2. Loads Phase 2 consolidated JSON
3. Merges all settlements
4. Detects and skips duplicates (based on `settlement_date + license_plate`)
5. Generates final consolidated JSON ready for database import

## Complete Workflow Example

```bash
# Step 1: Process single-truck PDFs
python consolidate_single_truck_settlements.py ./pdfs/ \
  -o ./output/ \
  --consolidate consolidated_single_truck.json

# Step 2: Process multi-truck PDFs with validation
python process_multi_truck_settlements.py ./pdfs/ \
  -o ./output/ \
  --consolidate consolidated_multi_truck.json \
  --report validation_report.json

# Step 3: Consolidate everything
python consolidate_all_settlements.py ./output/ \
  -o final_consolidated.json
```

## File Structure

```
backend/
├── consolidate_single_truck_settlements.py  # Phase 1 script
├── process_multi_truck_settlements.py        # Phase 2 script
├── consolidate_all_settlements.py            # Master consolidation
├── app/
│   └── utils/
│       ├── settlement_extractor.py           # Extraction logic
│       ├── pdf_parser.py                     # PDF parsing (enhanced with validation)
│       └── validation.py                     # Validation utilities
└── README_EXTRACTION_WORKFLOW.md            # This file
```

## Validation Details

### Validation Errors vs Warnings

- **Errors**: Critical issues that indicate incorrect extraction (e.g., revenue mismatch, missing blocks)
- **Warnings**: Potential issues that may need review (e.g., truck with zero fuel but has blocks)

### Shared Expenses

For multi-truck PDFs, certain expenses are always split 50/50 between trucks:
- Insurance
- Safety
- Prepass
- IFTA

Variable expenses are assigned per truck based on blocks:
- Fuel
- Driver Pay
- Dispatch Fee (proportional to gross revenue)

## Troubleshooting

### Multi-truck PDFs Not Detected

If a multi-truck PDF is not being detected:
1. Check the PDF header for "Plate#:" line with multiple plates
2. Verify block rows contain license plates
3. Check for OCR errors in plate detection

### Validation Errors

If validation errors occur:
1. Review the validation report JSON file
2. Check individual PDF extraction results
3. Verify expected totals match PDF values
4. Review block assignment logic

### Duplicate Settlements

If duplicates are found during consolidation:
- Duplicates are automatically skipped based on `settlement_date + license_plate`
- Review duplicate details in consolidation summary
- Ensure same PDF isn't processed in both phases

## Best Practices

1. **Always run Phase 1 first** - Process reliable single-truck PDFs before complex multi-truck ones
2. **Review validation reports** - Check Phase 2 validation reports for any issues
3. **Keep original PDFs** - Maintain original PDFs for reference and re-extraction if needed
4. **Version control JSON files** - Track JSON files in version control for audit trail
5. **Test with known PDFs** - Validate extraction accuracy with PDFs where you know the correct values

## Integration with Database

The final consolidated JSON file can be imported into the database using the existing import functionality. Each settlement entry follows the standard structure:

```json
{
  "source_file": "settlement.pdf",
  "extraction_date": "2025-01-XX",
  "settlement_type": "277 Logistics",
  "settlement": {
    "metadata": {...},
    "revenue": {...},
    "expenses": {...},
    "metrics": {...},
    "driver_pay": {...}
  }
}
```

## Support

For issues or questions:
1. Check validation reports for detailed error messages
2. Review individual extraction JSON files
3. Compare extracted values with original PDF values
4. Check logs for parsing errors

