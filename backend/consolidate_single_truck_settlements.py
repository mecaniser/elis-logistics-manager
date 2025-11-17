#!/usr/bin/env python3
"""
Phase 1: Single-Truck Settlement Consolidation Script

This script processes all PDFs in a directory and identifies single-truck PDFs.
It extracts data from single-truck PDFs and consolidates them into a single JSON file.

Usage:
    python consolidate_single_truck_settlements.py <pdf_directory> [options]
    
Examples:
    # Process single-truck PDFs in directory
    python consolidate_single_truck_settlements.py ./pdfs/
    
    # Process with custom output directory
    python consolidate_single_truck_settlements.py ./pdfs/ -o ./output/
    
    # Process and save consolidated JSON
    python consolidate_single_truck_settlements.py ./pdfs/ -o ./output/ --consolidate consolidated_single_truck.json
"""
import sys
import json
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.utils.settlement_extractor import SettlementExtractor


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Phase 1: Extract and consolidate single-truck settlement PDFs",
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
        help="Output path for consolidated JSON file (e.g., consolidated_single_truck.json)"
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
    print("Phase 1: Single-Truck Settlement Extraction")
    print("=" * 70)
    print(f"PDF Directory: {pdf_dir}")
    print(f"Output Directory: {output_dir}\n")
    
    extractor = SettlementExtractor()
    
    # Extract single-truck PDFs
    print("Identifying single-truck vs multi-truck PDFs...")
    result = extractor.extract_single_truck_pdfs(str(pdf_dir), str(output_dir))
    
    print(f"\nFound {len(result['single_truck_pdfs'])} single-truck PDFs")
    print(f"Found {len(result['multi_truck_pdfs'])} multi-truck PDFs (will be processed in Phase 2)\n")
    
    # Show results
    successful = sum(1 for r in result['results'] if r['status'] == 'success')
    failed = len(result['results']) - successful
    
    print(f"Processing Results: {successful} successful, {failed} failed\n")
    
    if successful > 0:
        print("Successfully processed single-truck PDFs:")
        for r in result['results']:
            if r['status'] == 'success':
                print(f"  ✓ {r['pdf_file']}")
            else:
                print(f"  ✗ {r['pdf_file']}: {r.get('error', 'Unknown error')}")
    
    if failed > 0:
        print("\nFailed PDFs:")
        for r in result['results']:
            if r['status'] == 'error':
                print(f"  ✗ {r['pdf_file']}: {r.get('error', 'Unknown error')}")
    
    # Save consolidated JSON if requested
    if args.consolidate:
        consolidate_path = Path(args.consolidate)
        if not consolidate_path.is_absolute():
            consolidate_path = output_dir / consolidate_path
        
        print(f"\nSaving consolidated JSON to: {consolidate_path}")
        with open(consolidate_path, 'w', encoding='utf-8') as f:
            json.dump(result['consolidated_data'], f, indent=2, ensure_ascii=False)
        
        print(f"✓ Consolidated {result['consolidated_data']['total_settlements']} settlements")
        print(f"  File: {consolidate_path}")
    
    # Save summary
    summary = {
        "phase": "phase1_single_truck",
        "single_truck_count": len(result['single_truck_pdfs']),
        "multi_truck_count": len(result['multi_truck_pdfs']),
        "successful_extractions": successful,
        "failed_extractions": failed,
        "total_settlements": result['consolidated_data']['total_settlements'],
        "single_truck_pdfs": result['single_truck_pdfs'],
        "multi_truck_pdfs": result['multi_truck_pdfs']
    }
    
    summary_path = output_dir / "phase1_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Summary saved to: {summary_path}")
    print("\n" + "=" * 70)
    print("Phase 1 Complete!")
    print("=" * 70)
    print(f"\nNext step: Process multi-truck PDFs using:")
    print(f"  python process_multi_truck_settlements.py {pdf_dir} -o {output_dir}")


if __name__ == "__main__":
    main()

