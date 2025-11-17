#!/usr/bin/env python3
"""
Phase 2: Multi-Truck Settlement Processing Script

This script processes multi-truck PDFs with enhanced validation and generates
detailed reports. It's designed to be run after Phase 1 (single-truck extraction).

Usage:
    python process_multi_truck_settlements.py <pdf_directory> [options]
    
Examples:
    # Process multi-truck PDFs in directory
    python process_multi_truck_settlements.py ./pdfs/
    
    # Process with custom output directory
    python process_multi_truck_settlements.py ./pdfs/ -o ./output/
    
    # Process and save consolidated JSON
    python process_multi_truck_settlements.py ./pdfs/ -o ./output/ --consolidate consolidated_multi_truck.json
    
    # Process with detailed validation report
    python process_multi_truck_settlements.py ./pdfs/ -o ./output/ --report validation_report.json
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.utils.settlement_extractor import SettlementExtractor


def process_multi_truck_pdf(pdf_path: str, settlement_type: str = None) -> dict:
    """
    Process a single multi-truck PDF with validation using SettlementExtractor.
    
    Args:
        pdf_path: Path to PDF file
        settlement_type: Optional settlement type hint
        
    Returns:
        Dictionary with extraction results and validation
    """
    try:
        # Use SettlementExtractor with validation enabled
        extractor = SettlementExtractor()
        result = extractor.extract_from_pdf(pdf_path, settlement_type, return_validation=True)
        
        # Get validation result if available
        validation = result.get("validation", {})
        
        # Determine status
        if validation:
            status = "success" if validation.get("is_valid", False) else "validation_errors"
        else:
            # No validation available (shouldn't happen for multi-truck, but handle gracefully)
            status = "success"
            validation = {
                "is_valid": True,
                "errors": [],
                "warnings": [{
                    "level": "warning",
                    "category": "validation",
                    "message": "Validation not available for this PDF",
                    "details": {}
                }],
                "summary": {
                    "total_settlements": len(result.get("settlements", [])),
                    "error_count": 0,
                    "warning_count": 1
                }
            }
        
        return {
            **result,
            "validation": validation,
            "status": status
        }
        
    except Exception as e:
        return {
            "source_file": Path(pdf_path).name,
            "extraction_date": datetime.now().isoformat(),
            "settlement_type": settlement_type,
            "settlements": [],
            "validation": {
                "is_valid": False,
                "errors": [{
                    "level": "error",
                    "category": "processing",
                    "message": f"Error processing PDF: {str(e)}",
                    "details": {"error": str(e)}
                }],
                "warnings": [],
                "summary": {
                    "total_settlements": 0,
                    "error_count": 1,
                    "warning_count": 0
                }
            },
            "status": "error",
            "error": str(e)
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Phase 2: Process multi-truck settlement PDFs with validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "pdf_directory",
        help="Directory containing PDF files"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory for JSON files (defaults to PDF directory)"
    )
    parser.add_argument(
        "--consolidate",
        help="Output path for consolidated JSON file (e.g., consolidated_multi_truck.json)"
    )
    parser.add_argument(
        "--report",
        help="Output path for validation report JSON file"
    )
    parser.add_argument(
        "--skip-individual",
        action="store_true",
        help="Skip creating individual JSON files, only create consolidated file"
    )
    
    args = parser.parse_args()
    
    pdf_dir = Path(args.pdf_directory)
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        print(f"Error: '{pdf_dir}' is not a valid directory")
        sys.exit(1)
    
    output_dir = Path(args.output) if args.output else pdf_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("Phase 2: Multi-Truck Settlement Processing with Validation")
    print("=" * 70)
    print(f"PDF Directory: {pdf_dir}")
    print(f"Output Directory: {output_dir}\n")
    
    extractor = SettlementExtractor()
    
    # Identify multi-truck PDFs
    print("Identifying multi-truck PDFs...")
    multi_truck_pdfs = []
    
    for pdf_file in sorted(pdf_dir.glob("*.pdf")):
        try:
            is_multi_truck = extractor._detect_multiple_trucks(str(pdf_file))
            if is_multi_truck:
                multi_truck_pdfs.append(pdf_file)
        except Exception as e:
            print(f"  Warning: Could not detect type for {pdf_file.name}: {e}")
    
    print(f"Found {len(multi_truck_pdfs)} multi-truck PDFs\n")
    
    if len(multi_truck_pdfs) == 0:
        print("No multi-truck PDFs found. Nothing to process.")
        sys.exit(0)
    
    # Process each multi-truck PDF
    all_settlements = []
    all_results = []
    validation_summary = {
        "total_pdfs": len(multi_truck_pdfs),
        "successful": 0,
        "validation_errors": 0,
        "processing_errors": 0,
        "total_settlements": 0,
        "total_validation_errors": 0,
        "total_validation_warnings": 0
    }
    
    print("Processing multi-truck PDFs...\n")
    
    for pdf_file in multi_truck_pdfs:
        print(f"Processing: {pdf_file.name}")
        
        # Detect settlement type
        settlement_type = extractor._detect_settlement_type(str(pdf_file))
        
        # Process PDF
        result = process_multi_truck_pdf(str(pdf_file), settlement_type)
        all_results.append(result)
        
        # Save individual JSON file if not skipping
        if not args.skip_individual:
            json_path = output_dir / f"{pdf_file.stem}_extracted.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Add settlements to consolidated list
        for settlement in result.get("settlements", []):
            settlement_entry = {
                "source_file": result["source_file"],
                "extraction_date": result["extraction_date"],
                "settlement_type": result["settlement_type"],
                "settlement": settlement
            }
            all_settlements.append(settlement_entry)
        
        # Update summary
        validation = result.get("validation", {})
        validation_summary["total_settlements"] += len(result.get("settlements", []))
        validation_summary["total_validation_errors"] += len(validation.get("errors", []))
        validation_summary["total_validation_warnings"] += len(validation.get("warnings", []))
        
        if result["status"] == "success":
            validation_summary["successful"] += 1
        elif result["status"] == "validation_errors":
            validation_summary["validation_errors"] += 1
        else:
            validation_summary["processing_errors"] += 1
        
        # Print validation status
        if validation.get("is_valid", False):
            print(f"  ✓ Valid extraction ({len(result.get('settlements', []))} settlements)")
        else:
            error_count = len(validation.get("errors", []))
            warning_count = len(validation.get("warnings", []))
            print(f"  ⚠ Validation issues: {error_count} errors, {warning_count} warnings")
            if error_count > 0:
                for error in validation.get("errors", [])[:3]:  # Show first 3 errors
                    print(f"    - {error.get('category')}: {error.get('message')}")
        print()
    
    # Create consolidated data structure
    consolidated_data = {
        "consolidation_date": datetime.now().isoformat(),
        "source": "phase2_multi_truck_extraction",
        "total_settlements": len(all_settlements),
        "settlements": all_settlements,
        "validation_summary": validation_summary
    }
    
    # Save consolidated JSON if requested
    if args.consolidate:
        consolidate_path = Path(args.consolidate)
        if not consolidate_path.is_absolute():
            consolidate_path = output_dir / consolidate_path
        
        print(f"Saving consolidated JSON to: {consolidate_path}")
        with open(consolidate_path, 'w', encoding='utf-8') as f:
            json.dump(consolidated_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Consolidated {len(all_settlements)} settlements")
        print(f"  File: {consolidate_path}\n")
    
    # Create validation report if requested
    if args.report:
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = output_dir / report_path
        
        validation_report = {
            "report_date": datetime.now().isoformat(),
            "summary": validation_summary,
            "pdf_results": all_results
        }
        
        print(f"Saving validation report to: {report_path}")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(validation_report, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Validation report saved")
        print(f"  File: {report_path}\n")
    
    # Print final summary
    print("=" * 70)
    print("Phase 2 Summary")
    print("=" * 70)
    print(f"Total PDFs processed: {validation_summary['total_pdfs']}")
    print(f"  Successful: {validation_summary['successful']}")
    print(f"  Validation errors: {validation_summary['validation_errors']}")
    print(f"  Processing errors: {validation_summary['processing_errors']}")
    print(f"Total settlements extracted: {validation_summary['total_settlements']}")
    print(f"Validation errors: {validation_summary['total_validation_errors']}")
    print(f"Validation warnings: {validation_summary['total_validation_warnings']}")
    print("=" * 70)
    print("\nPhase 2 Complete!")
    print("\nNext step: Consolidate all settlements using:")
    print(f"  python consolidate_all_settlements.py {output_dir}")


if __name__ == "__main__":
    main()

