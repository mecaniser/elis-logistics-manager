#!/usr/bin/env python3
"""
CLI tool for extracting settlement data from PDFs to JSON format.
This tool processes PDFs independently and generates JSON files that can be
imported into the database without storing the original PDFs.

Usage:
    python extract_settlements.py <pdf_file_or_directory> [options]
    
Examples:
    # Extract single PDF
    python extract_settlements.py settlement.pdf
    
    # Extract single PDF with output file
    python extract_settlements.py settlement.pdf -o output.json
    
    # Extract single PDF with settlement type hint
    python extract_settlements.py settlement.pdf -t "277 Logistics"
    
    # Batch extract all PDFs in directory
    python extract_settlements.py ./pdfs/ -b
    
    # Batch extract with output directory
    python extract_settlements.py ./pdfs/ -b -o ./json_output/
"""
import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.utils.settlement_extractor import SettlementExtractor


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract settlement data from PDFs to JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "pdf_path",
        help="Path to PDF file or directory containing PDFs"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file path (for single file) or directory (for batch)"
    )
    parser.add_argument(
        "-t", "--type",
        help="Settlement type hint (277 Logistics, NBM Transport LLC, Owner Operator Income Sheet)"
    )
    parser.add_argument(
        "-b", "--batch",
        action="store_true",
        help="Process directory of PDFs (batch mode)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate extracted JSON against schema"
    )
    
    args = parser.parse_args()
    
    extractor = SettlementExtractor()
    pdf_path = Path(args.pdf_path)
    
    if not pdf_path.exists():
        print(f"Error: Path '{pdf_path}' does not exist")
        sys.exit(1)
    
    if args.batch or pdf_path.is_dir():
        # Batch processing
        if not pdf_path.is_dir():
            print(f"Error: '{pdf_path}' is not a directory. Use -b flag for batch processing.")
            sys.exit(1)
        
        output_dir = Path(args.output) if args.output else pdf_path
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Processing PDFs in: {pdf_path}")
        print(f"Output directory: {output_dir}\n")
        
        results = extractor.batch_extract(str(pdf_path), str(output_dir))
        
        successful = sum(1 for r in results if r["status"] == "success")
        failed = len(results) - successful
        
        print(f"\n{'='*60}")
        print(f"Processing complete: {successful} successful, {failed} failed")
        print(f"{'='*60}\n")
        
        for result in results:
            if result["status"] == "success":
                print(f"  ✓ {result['pdf_file']} -> {result['json_file']}")
            else:
                print(f"  ✗ {result['pdf_file']}: {result.get('error', 'Unknown error')}")
        
        if failed > 0:
            sys.exit(1)
    else:
        # Single file processing
        if not pdf_path.is_file():
            print(f"Error: '{pdf_path}' is not a file")
            sys.exit(1)
        
        print(f"Extracting data from: {pdf_path}")
        
        try:
            json_path = extractor.extract_to_json_file(
                str(pdf_path),
                args.output,
                args.type
            )
            
            print(f"✓ Successfully extracted data")
            print(f"  JSON file: {json_path}")
            
            # Show summary
            import json
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            num_settlements = len(data.get("settlements", []))
            print(f"  Settlements found: {num_settlements}")
            
            if num_settlements > 0:
                first = data["settlements"][0]
                print(f"  Settlement date: {first.get('metadata', {}).get('settlement_date', 'N/A')}")
                print(f"  License plate: {first.get('metadata', {}).get('license_plate', 'N/A')}")
                print(f"  Gross revenue: ${first.get('revenue', {}).get('gross_revenue', 0):,.2f}")
            
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()

