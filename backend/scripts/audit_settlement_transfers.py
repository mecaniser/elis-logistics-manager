"""Read-only carryover audit of an explicitly supplied SQLite snapshot.

Run: PYTHONPATH=backend python backend/scripts/audit_settlement_transfers.py \
    --database-path /absolute/path/snapshot.db --tenant-id 1
No app startup, migrations, network requests or record writes are performed.
"""
import argparse
import json
from pathlib import Path
import sqlite3
from app.services.settlement_transfers import audit_transfers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-path', type=Path, required=True)
    parser.add_argument('--tenant-id', type=int, required=True)
    args = parser.parse_args()
    path = args.database_path.resolve(strict=True)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute(
            'SELECT s.*, t.tenant_id FROM settlements s JOIN trucks t ON t.id=s.truck_id WHERE t.tenant_id=?',
            (args.tenant_id,),
        )]
    for row in rows:
        for key in ['expense_categories', 'deduction_details', 'reimbursement_details', 'cash_adjustments']:
            if isinstance(row.get(key), str):
                row[key] = json.loads(row[key])
    # Only identifiers and adjustment amounts leave the private snapshot.
    print(json.dumps({'records': len(rows), 'source_records': sum(not r.get('source_settlement_id') for r in rows),
                      'derived_records': sum(bool(r.get('source_settlement_id')) for r in rows),
                      'transfer_audit': audit_transfers(rows)}, indent=2))


if __name__ == '__main__':
    main()
