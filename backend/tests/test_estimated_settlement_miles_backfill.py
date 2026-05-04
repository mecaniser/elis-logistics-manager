import importlib.util
from datetime import date
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.models.settlement import Settlement
from app.models.truck import Truck
from app.services import diesel_price_service


def test_backfill_estimates_missing_miles_and_is_idempotent(db, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "backfill_estimated_settlement_miles.py"
    spec = importlib.util.spec_from_file_location("backfill_estimated_settlement_miles", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(script)

    truck = Truck(
        tenant_id=1,
        name="Backfill Miles Truck",
        vehicle_type="truck",
        license_plate="VW9328",
        estimated_mpg=6.5,
        fuel_card_discount_per_gallon=0.25,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    settlement = Settlement(
        truck_id=truck.id,
        settlement_date=date(2026, 4, 25),
        week_start=date(2026, 4, 19),
        week_end=date(2026, 4, 25),
        gross_revenue=7426.53,
        expenses=4690.88,
        net_profit=2735.65,
        miles_driven=None,
        expense_categories={
            "fuel": 1665.76,
            "dispatch_fee": 618.12,
        },
        overview_amounts={"gross_before_dispatch": 8044.65},
    )
    db.add(settlement)
    db.commit()

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db.bind)
    monkeypatch.setattr(script, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(script, "EIA_API_KEY", "test-key")
    monkeypatch.setattr(diesel_price_service, "get_historical_diesel_price", lambda _date: 4.0)

    assert script.backfill(dry_run=False) is True

    refreshed = db.query(Settlement).filter(Settlement.id == settlement.id).first()
    assert refreshed is not None
    assert float(refreshed.miles_driven) == 2887.32
    assert float(refreshed.overview_amounts["gross_before_dispatch"]) == 8044.65
    assert float(refreshed.overview_amounts["diesel_price_per_gallon"]) == 4.0
    assert float(refreshed.overview_amounts["fuel_card_discount_per_gallon"]) == 0.25
    assert float(refreshed.overview_amounts["effective_fuel_price_per_gallon"]) == 3.75
    assert float(refreshed.overview_amounts["estimated_gallons"]) == 444.2
    assert float(refreshed.overview_amounts["estimated_mpg"]) == 6.5
    assert float(refreshed.overview_amounts["estimated_miles_driven"]) == 2887.32

    assert script.backfill(dry_run=True) is True
    output = capsys.readouterr().out
    assert "updated 1 settlements; skipped 0" in output
    assert "would update 0 settlements; skipped 0" in output
