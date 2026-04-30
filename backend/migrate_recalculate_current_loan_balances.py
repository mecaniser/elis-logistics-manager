"""
Backfill current_loan_balance for all trucks using full settlement/repair history.
"""
from app.database import SessionLocal
from app.models.truck import Truck
from app.services.loan_balance_service import sync_current_loan_balance


def main():
    db = SessionLocal()
    try:
        trucks = db.query(Truck).filter(Truck.vehicle_type == "truck").order_by(Truck.id.asc()).all()
        updated = 0

        for truck in trucks:
            before = float(truck.current_loan_balance) if truck.current_loan_balance is not None else None
            after = sync_current_loan_balance(db, truck)
            if before != after:
                updated += 1
                print(f"Truck {truck.id} ({truck.name}): {before} -> {after}")

        db.commit()
        print(f"Recalculated current loan balances for {len(trucks)} truck(s); updated {updated}.")
    finally:
        db.close()


def migrate():
    """Wrapper for master migration runners."""
    main()


if __name__ == "__main__":
    main()
