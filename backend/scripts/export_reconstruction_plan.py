"""Export a local SQLite review copy without allowing writes.

Run with PYTHONPATH=backend. Never imports app.main or runs startup migrations.
"""
import argparse
import csv
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.services.reconstruction_plan import reconstruction_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-path', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tenant', type=int, required=True)
    args = parser.parse_args()
    database = args.database_path.resolve(strict=True)
    engine = create_engine('sqlite:///' + database.as_uri() + '?mode=ro&uri=true')
    with Session(engine) as db:
        result = reconstruction_plan(db, args.tenant)
    engine.dispose()
    args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive creation prevents accidentally replacing a prior review artifact.
    with (args.output_dir / 'historical-posting-plan.json').open('x') as file:
        json.dump(result, file, indent=2)
    with (args.output_dir / 'historical-posting-plan.csv').open('x', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['legacy_id', 'date', 'unit', 'status', 'freight', 'remainder', 'blocking_reasons', 'differences', 'evidence_id', 'sha256'])
        for row in result['rows']:
            writer.writerow([row['id'], row['date'], row['name'], row['plan_status'], row['freight'], row['remainder'], ';'.join(row['blocking_reasons']), json.dumps(row['differences']), row['evidence_id'], row['sha256']])
    print(json.dumps({k: result[k] for k in ('counts', 'candidate_totals')}, indent=2))


if __name__ == '__main__':
    main()
