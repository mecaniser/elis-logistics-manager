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


def test_backfill_refreshes_existing_estimated_miles_without_touching_actual_miles(db, monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "backfill_estimated_settlement_miles.py"
    spec = importlib.util.spec_from_file_location("backfill_estimated_settlement_miles", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(script)

    truck = Truck(
        tenant_id=1,
        name="Refresh Estimated Miles Truck",
        vehicle_type="truck",
        license_plate="VW9401",
        estimated_mpg=6.5,
        fuel_card_discount_per_gallon=0.2,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    estimated_settlement = Settlement(
        truck_id=truck.id,
        settlement_date=date(2026, 4, 25),
        week_start=date(2026, 4, 19),
        week_end=date(2026, 4, 25),
        gross_revenue=7426.53,
        expenses=4690.88,
        net_profit=2735.65,
        miles_driven=1908.26,
        expense_categories={"fuel": 1665.76},
        overview_amounts={
            "estimated_mpg": 6.5,
            "estimated_gallons": 293.58,
            "estimated_miles_driven": 1908.26,
            "diesel_price_per_gallon": 5.674,
            "fuel_card_discount_per_gallon": 0.0,
            "effective_fuel_price_per_gallon": 5.674,
        },
    )
    actual_settlement = Settlement(
        truck_id=truck.id,
        settlement_date=date(2026, 5, 2),
        week_start=date(2026, 4, 26),
        week_end=date(2026, 5, 2),
        gross_revenue=8200.00,
        expenses=5100.00,
        net_profit=3100.00,
        miles_driven=2100.0,
        expense_categories={"fuel": 1550.0},
        overview_amounts={"diesel_price_per_gallon": 5.7},
    )
    db.add_all([estimated_settlement, actual_settlement])
    db.commit()

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db.bind)
    monkeypatch.setattr(script, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(script, "EIA_API_KEY", "test-key")
    monkeypatch.setattr(diesel_price_service, "get_historical_diesel_price", lambda _date: 5.674)

    assert script.backfill(dry_run=False, refresh_estimated=True) is True

    refreshed_estimated = db.query(Settlement).filter(Settlement.id == estimated_settlement.id).first()
    refreshed_actual = db.query(Settlement).filter(Settlement.id == actual_settlement.id).first()

    assert refreshed_estimated is not None
    assert float(refreshed_estimated.overview_amounts["fuel_card_discount_per_gallon"]) == 0.2
    assert float(refreshed_estimated.overview_amounts["effective_fuel_price_per_gallon"]) == 5.474
    assert float(refreshed_estimated.miles_driven) == 1977.98
    assert refreshed_actual is not None
    assert float(refreshed_actual.miles_driven) == 2100.0
    assert float(refreshed_actual.overview_amounts["diesel_price_per_gallon"]) == 5.7
