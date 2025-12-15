"""
Block ID validation utilities
"""
from typing import List, Dict, Set, Optional, Any, Tuple
from sqlalchemy.orm import Session
from app.models.settlement import Settlement


def extract_block_ids(block_ids_data: Optional[List[Any]]) -> Set[str]:
    """
    Extract block IDs from various formats:
    - List of strings: ["B-123", "B-456"]
    - List of objects: [{"block_id": "B-123", "delivery_date": "2024-01-01"}, ...]
    - None or empty list: returns empty set
    
    Returns a set of unique block ID strings.
    """
    if not block_ids_data:
        return set()
    
    block_ids = set()
    for item in block_ids_data:
        if isinstance(item, str):
            block_ids.add(item)
        elif isinstance(item, dict) and "block_id" in item:
            block_ids.add(str(item["block_id"]))
    
    return block_ids


def find_duplicate_block_ids(
    new_block_ids: Set[str],
    db: Session,
    exclude_settlement_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Find existing settlements that contain any of the provided block IDs.
    
    Args:
        new_block_ids: Set of block IDs to check for duplicates
        db: Database session
        exclude_settlement_id: Optional settlement ID to exclude from check (for updates)
    
    Returns:
        List of dicts with:
        - block_id: The duplicate block ID
        - settlement_id: ID of settlement containing this block ID
        - truck_id: Truck ID of that settlement
        - settlement_date: Date of that settlement
    """
    if not new_block_ids:
        return []
    
    # Get all settlements with block_ids (excluding the one being updated if specified)
    query = db.query(Settlement).filter(Settlement.block_ids.isnot(None))
    if exclude_settlement_id:
        query = query.filter(Settlement.id != exclude_settlement_id)
    
    settlements = query.all()
    
    duplicates = []
    for settlement in settlements:
        if not settlement.block_ids:
            continue
        
        existing_block_ids = extract_block_ids(settlement.block_ids)
        overlapping = new_block_ids.intersection(existing_block_ids)
        
        if overlapping:
            for block_id in overlapping:
                duplicates.append({
                    "block_id": block_id,
                    "settlement_id": settlement.id,
                    "truck_id": settlement.truck_id,
                    "settlement_date": str(settlement.settlement_date) if settlement.settlement_date else None,
                })
    
    return duplicates


def validate_block_ids(
    block_ids_data: Optional[List[Any]],
    db: Session,
    exclude_settlement_id: Optional[int] = None
) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
    """
    Check for duplicate block IDs in other settlements (for flagging/warning purposes).
    
    Args:
        block_ids_data: Block IDs data from settlement (can be list of strings or objects)
        db: Database session
        exclude_settlement_id: Optional settlement ID to exclude from check (for updates)
    
    Returns:
        Tuple of (has_duplicates, warning_message, duplicates_list)
        - has_duplicates: True if duplicates found (for flagging)
        - warning_message: Human-readable warning message if duplicates found
        - duplicates_list: List of duplicate block ID details
    """
    new_block_ids = extract_block_ids(block_ids_data)
    
    if not new_block_ids:
        return False, None, []
    
    duplicates = find_duplicate_block_ids(new_block_ids, db, exclude_settlement_id)
    
    if duplicates:
        # Group duplicates by block_id for cleaner warning message
        block_id_to_settlements = {}
        for dup in duplicates:
            block_id = dup["block_id"]
            if block_id not in block_id_to_settlements:
                block_id_to_settlements[block_id] = []
            block_id_to_settlements[block_id].append(dup)
        
        # Build warning message
        duplicate_block_ids = sorted(block_id_to_settlements.keys())
        warning_parts = [f"⚠️ Block ID '{bid}' already exists in other settlement(s):" for bid in duplicate_block_ids]
        
        for block_id, settlements in block_id_to_settlements.items():
            settlement_details = [
                f"Settlement #{s['settlement_id']} (Truck {s['truck_id']}, {s['settlement_date']})"
                for s in settlements
            ]
            warning_parts.append(f"  - {block_id}: {', '.join(settlement_details)}")
        
        warning_message = "\n".join(warning_parts)
        return True, warning_message, duplicates
    
    return False, None, []


