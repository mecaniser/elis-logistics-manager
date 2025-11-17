#!/usr/bin/env python3
"""
Master Consolidation Script

This script merges single-truck and multi-truck settlement JSONs into a final
consolidated file ready for database import. It ensures no duplicates and
provides a complete summary.

Usage:
    python consolidate_all_settlements.py <json_directory> [options]
    
Examples:
    # Consolidate all JSON files in directory
    python consolidate_all_settlements.py ./output/
    
    # Consolidate with custom output file
    python consolidate_all_settlements.py ./output/ -o consolidated_all_settlements.json
    
    # Consolidate from specific phase files
    python consolidate_all_settlements.py ./output/ --phase1 phase1.json --phase2 phase2.json
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set


def load_json_file(file_path: Path) -> Dict:
    """Load JSON file and return dictionary"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return {}


def get_settlement_key(settlement: Dict) -> str:
    """
    Generate a unique key for a settlement to detect duplicates.
    Key format: settlement_date|license_plate
    """
    metadata = settlement.get("metadata", {})
    settlement_date = metadata.get("settlement_date", "")
    license_plate = metadata.get("license_plate", "")
    return f"{settlement_date}|{license_plate}"


def consolidate_settlements(json_directory: Path, 
                           phase1_file: Path = None,
                           phase2_file: Path = None) -> Dict:
    """
    Consolidate settlements from JSON files in directory or specific phase files.
    
    Args:
        json_directory: Directory containing JSON files
        phase1_file: Optional path to Phase 1 consolidated JSON
        phase2_file: Optional path to Phase 2 consolidated JSON
        
    Returns:
        Consolidated data dictionary
    """
    all_settlements = []
    seen_keys: Set[str] = set()
    duplicates = []
    sources = {
        "phase1_single_truck": 0,
        "phase2_multi_truck": 0,
        "individual_files": 0
    }
    
    # Load Phase 1 consolidated file if provided
    if phase1_file and phase1_file.exists():
        print(f"Loading Phase 1 consolidated file: {phase1_file}")
        phase1_data = load_json_file(phase1_file)
        if phase1_data.get("source") == "phase1_single_truck_extraction":
            for settlement_entry in phase1_data.get("settlements", []):
                settlement = settlement_entry.get("settlement", {})
                key = get_settlement_key(settlement)
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_settlements.append(settlement_entry)
                    sources["phase1_single_truck"] += 1
                else:
                    duplicates.append({
                        "source": "phase1",
                        "settlement": settlement_entry,
                        "key": key
                    })
    
    # Load Phase 2 consolidated file if provided
    if phase2_file and phase2_file.exists():
        print(f"Loading Phase 2 consolidated file: {phase2_file}")
        phase2_data = load_json_file(phase2_file)
        if phase2_data.get("source") == "phase2_multi_truck_extraction":
            for settlement_entry in phase2_data.get("settlements", []):
                settlement = settlement_entry.get("settlement", {})
                key = get_settlement_key(settlement)
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_settlements.append(settlement_entry)
                    sources["phase2_multi_truck"] += 1
                else:
                    duplicates.append({
                        "source": "phase2",
                        "settlement": settlement_entry,
                        "key": key
                    })
    
    # Load individual JSON files if phase files not provided
    if not phase1_file and not phase2_file:
        print(f"Scanning directory for JSON files: {json_directory}")
        
        # Look for phase summary files first
        phase1_summary = json_directory / "phase1_summary.json"
        phase2_consolidated = json_directory / "consolidated_multi_truck.json"
        
        if phase1_summary.exists():
            phase1_summary_data = load_json_file(phase1_summary)
            # Load individual single-truck JSONs
            for pdf_name in phase1_summary_data.get("single_truck_pdfs", []):
                json_name = pdf_name.replace(".pdf", "_extracted.json")
                json_path = json_directory / json_name
                if json_path.exists():
                    data = load_json_file(json_path)
                    for settlement in data.get("settlements", []):
                        settlement_entry = {
                            "source_file": data["source_file"],
                            "extraction_date": data["extraction_date"],
                            "settlement_type": data["settlement_type"],
                            "settlement": settlement
                        }
                        key = get_settlement_key(settlement)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_settlements.append(settlement_entry)
                            sources["phase1_single_truck"] += 1
        
        # Load Phase 2 consolidated if exists
        if phase2_consolidated.exists():
            phase2_data = load_json_file(phase2_consolidated)
            if phase2_data.get("source") == "phase2_multi_truck_extraction":
                for settlement_entry in phase2_data.get("settlements", []):
                    settlement = settlement_entry.get("settlement", {})
                    key = get_settlement_key(settlement)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_settlements.append(settlement_entry)
                        sources["phase2_multi_truck"] += 1
        
        # Also scan for any other individual JSON files
        for json_file in json_directory.glob("*_extracted.json"):
            # Skip if already processed
            if "phase1" in str(json_file) or "phase2" in str(json_file):
                continue
            
            data = load_json_file(json_file)
            if data.get("settlements"):
                for settlement in data.get("settlements", []):
                    settlement_entry = {
                        "source_file": data.get("source_file", json_file.name),
                        "extraction_date": data.get("extraction_date", datetime.now().isoformat()),
                        "settlement_type": data.get("settlement_type"),
                        "settlement": settlement
                    }
                    key = get_settlement_key(settlement)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_settlements.append(settlement_entry)
                        sources["individual_files"] += 1
    
    # Create consolidated structure
    consolidated_data = {
        "consolidation_date": datetime.now().isoformat(),
        "source": "master_consolidation",
        "total_settlements": len(all_settlements),
        "sources": sources,
        "duplicates_skipped": len(duplicates),
        "settlements": all_settlements
    }
    
    if duplicates:
        consolidated_data["duplicate_details"] = [
            {
                "source": dup["source"],
                "key": dup["key"],
                "source_file": dup["settlement"].get("source_file")
            }
            for dup in duplicates[:10]  # Limit to first 10 duplicates
        ]
    
    return consolidated_data


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Master consolidation: Merge single-truck and multi-truck settlements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "json_directory",
        help="Directory containing JSON files or phase consolidated files"
    )
    parser.add_argument(
        "-o", "--output",
        default="consolidated_all_settlements.json",
        help="Output path for consolidated JSON file (default: consolidated_all_settlements.json)"
    )
    parser.add_argument(
        "--phase1",
        help="Path to Phase 1 consolidated JSON file (optional)"
    )
    parser.add_argument(
        "--phase2",
        help="Path to Phase 2 consolidated JSON file (optional)"
    )
    
    args = parser.parse_args()
    
    json_dir = Path(args.json_directory)
    if not json_dir.exists():
        print(f"Error: '{json_dir}' does not exist")
        sys.exit(1)
    
    if not json_dir.is_dir() and not (args.phase1 or args.phase2):
        print(f"Error: '{json_dir}' is not a directory. Use --phase1 and --phase2 flags for specific files.")
        sys.exit(1)
    
    output_path = Path(args.output)
    if not output_path.is_absolute():
        if json_dir.is_dir():
            output_path = json_dir / output_path
        else:
            output_path = json_dir.parent / output_path
    
    phase1_file = Path(args.phase1) if args.phase1 else None
    phase2_file = Path(args.phase2) if args.phase2 else None
    
    print("=" * 70)
    print("Master Consolidation: Merging All Settlements")
    print("=" * 70)
    print(f"Source: {json_dir}")
    if phase1_file:
        print(f"Phase 1 file: {phase1_file}")
    if phase2_file:
        print(f"Phase 2 file: {phase2_file}")
    print(f"Output: {output_path}\n")
    
    # Consolidate
    consolidated_data = consolidate_settlements(json_dir, phase1_file, phase2_file)
    
    # Save consolidated file
    print(f"\nSaving consolidated file to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(consolidated_data, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "=" * 70)
    print("Consolidation Summary")
    print("=" * 70)
    print(f"Total settlements: {consolidated_data['total_settlements']}")
    print(f"\nSources:")
    print(f"  Phase 1 (single-truck): {consolidated_data['sources']['phase1_single_truck']}")
    print(f"  Phase 2 (multi-truck): {consolidated_data['sources']['phase2_multi_truck']}")
    print(f"  Individual files: {consolidated_data['sources']['individual_files']}")
    print(f"\nDuplicates skipped: {consolidated_data['duplicates_skipped']}")
    
    if consolidated_data['duplicates_skipped'] > 0:
        print("\nNote: Some duplicate settlements were skipped (same date + license plate)")
        if consolidated_data.get("duplicate_details"):
            print("Sample duplicates:")
            for dup in consolidated_data["duplicate_details"][:5]:
                print(f"  - {dup['key']} from {dup['source']}")
    
    print(f"\n✓ Consolidated file saved: {output_path}")
    print("=" * 70)
    print("\nConsolidation complete! File is ready for database import.")


if __name__ == "__main__":
    main()

