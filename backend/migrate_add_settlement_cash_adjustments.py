"""Add operating-profit/cash-settlement separation to existing databases."""
from sqlalchemy import inspect, text

from app.database import engine


def main():
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("settlements")}
    statements = []
    if "cash_settlement_amount" not in columns:
        statements.append("ALTER TABLE settlements ADD COLUMN cash_settlement_amount NUMERIC(10, 2)")
    if "cash_adjustments" not in columns:
        # SQLite stores JSON as text; PostgreSQL accepts JSON for this column.
        column_type = "JSON" if engine.dialect.name != "sqlite" else "TEXT"
        statements.append(f"ALTER TABLE settlements ADD COLUMN cash_adjustments {column_type}")

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    print("Settlement cash-adjustment migration complete.")


if __name__ == "__main__":
    main()
