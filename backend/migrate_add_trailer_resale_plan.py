"""Add trailer replacement-planning inputs without changing existing data."""
from sqlalchemy import inspect, text

from app.database import engine


def main() -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("trucks")}
    statements = []
    if "expected_resale_value" not in columns:
        statements.append("ALTER TABLE trucks ADD COLUMN expected_resale_value NUMERIC(10, 2)")
    if "planned_service_weeks" not in columns:
        statements.append("ALTER TABLE trucks ADD COLUMN planned_service_weeks INTEGER")

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    print("Trailer resale-plan migration complete.")


if __name__ == "__main__":
    main()
