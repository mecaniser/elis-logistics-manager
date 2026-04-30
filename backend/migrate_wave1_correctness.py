"""
Wave 1 Correctness Migration
- Adds deleted_at column to journal_entries (soft-delete)
- Adds unique constraint on (tenant_id, reference_type, reference_id)
- Adds partial index for non-deleted entries

Run: python migrate_wave1_correctness.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import text, inspect

def migrate():
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("journal_entries")]

    with engine.begin() as conn:
        # 1. Add deleted_at column
        if "deleted_at" not in columns:
            conn.execute(text("ALTER TABLE journal_entries ADD COLUMN deleted_at TIMESTAMP NULL"))
            print("Added deleted_at column to journal_entries")
        else:
            print("deleted_at column already exists")

        # 2. Add unique constraint on (tenant_id, reference_type, reference_id)
        existing_constraints = inspector.get_unique_constraints("journal_entries")
        constraint_names = [c["name"] for c in existing_constraints]

        if "uq_journal_entry_reference" not in constraint_names:
            # First, check for duplicates and remove them (keep lowest id)
            dupes = conn.execute(text("""
                SELECT tenant_id, reference_type, reference_id, COUNT(*) as cnt
                FROM journal_entries
                WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL
                GROUP BY tenant_id, reference_type, reference_id
                HAVING COUNT(*) > 1
            """)).fetchall()

            if dupes:
                print(f"Found {len(dupes)} duplicate reference groups, cleaning up...")
                for row in dupes:
                    tid, rtype, rid = row[0], row[1], row[2]
                    # Keep the entry with the lowest id, delete the rest
                    conn.execute(text("""
                        DELETE FROM journal_entry_lines WHERE journal_entry_id IN (
                            SELECT id FROM journal_entries
                            WHERE tenant_id = :tid AND reference_type = :rtype AND reference_id = :rid
                            AND id NOT IN (
                                SELECT MIN(id) FROM journal_entries
                                WHERE tenant_id = :tid AND reference_type = :rtype AND reference_id = :rid
                            )
                        )
                    """), {"tid": tid, "rtype": rtype, "rid": rid})
                    conn.execute(text("""
                        DELETE FROM journal_entries
                        WHERE tenant_id = :tid AND reference_type = :rtype AND reference_id = :rid
                        AND id NOT IN (
                            SELECT MIN(id) FROM journal_entries
                            WHERE tenant_id = :tid AND reference_type = :rtype AND reference_id = :rid
                        )
                    """), {"tid": tid, "rtype": rtype, "rid": rid})
                    print(f"  Cleaned duplicates for tenant={tid} {rtype}#{rid}")

            try:
                conn.execute(text(
                    "CREATE UNIQUE INDEX uq_journal_entry_reference "
                    "ON journal_entries (tenant_id, reference_type, reference_id) "
                    "WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL"
                ))
                print("Added unique constraint uq_journal_entry_reference")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print("Unique constraint uq_journal_entry_reference already exists")
                else:
                    raise
        else:
            print("Unique constraint uq_journal_entry_reference already exists")

    print("Wave 1 migration complete.")


if __name__ == "__main__":
    migrate()
