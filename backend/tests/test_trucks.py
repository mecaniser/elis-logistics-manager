"""
Tests for trucks API endpoints
"""
import importlib.util
import pytest
from fastapi.testclient import TestClient
from datetime import date
from pathlib import Path
from sqlalchemy.orm import sessionmaker

from app.models.settlement import Settlement
from app.models.truck import Truck


def test_create_truck(client: TestClient, tenant_headers):
    """Test creating a truck"""
    response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"},
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Truck 1"
    assert data["license_plate"] == "ABC-123"
    assert "id" in data
    assert "created_at" in data


def test_create_truck_with_default_trailer_split(client: TestClient, db, tenant_headers):
    """A truck can store its default trailer split settings for future settlement autofill."""
    trailer = Truck(
        tenant_id=1,
        name="Autofill Trailer",
        vehicle_type="trailer",
        tag_number="TRL-777",
    )
    db.add(trailer)
    db.commit()
    db.refresh(trailer)

    response = client.post(
        "/api/trucks",
        json={
            "name": "77 Cargo Truck",
            "vehicle_type": "truck",
            "license_plate": "VW9327",
            "default_trailer_id": trailer.id,
            "default_trailer_income_split_amount": 400.0,
            "default_repair_reserve_amount": 500.0,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["default_trailer_id"] == trailer.id
    assert float(data["default_trailer_income_split_amount"]) == 400.0
    assert float(data["default_repair_reserve_amount"]) == 500.0


def test_create_truck_saves_fuel_estimation_settings(client: TestClient, tenant_headers):
    response = client.post(
        "/api/trucks",
        json={
            "name": "Estimated Miles Truck",
            "vehicle_type": "truck",
            "license_plate": "MPG-650",
            "estimated_mpg": 6.75,
            "fuel_card_discount_per_gallon": 0.325,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert float(data["estimated_mpg"]) == pytest.approx(6.75)
    assert float(data["fuel_card_discount_per_gallon"]) == pytest.approx(0.325)


def test_create_truck_normalizes_percent_interest_rate_input(client: TestClient, tenant_headers):
    """Truck creation should treat 6.5 as 6.5%, not 650%."""
    response = client.post(
        "/api/trucks",
        json={
            "name": "Interest Rate Truck",
            "vehicle_type": "truck",
            "license_plate": "INT-650",
            "cash_investment": 10000,
            "loan_amount": 5000,
            "interest_rate": 6.5,
            "total_cost": 15000,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert float(data["interest_rate"]) == 0.065


def test_create_trailer_accepts_loan_setup(client: TestClient, tenant_headers):
    """Trailers can be financed with loan amount, term, and interest rate."""
    response = client.post(
        "/api/trucks",
        json={
            "name": "Financed Trailer",
            "vehicle_type": "trailer",
            "tag_number": "TRL-LOAN",
            "cash_investment": 1000,
            "loan_amount": 9000,
            "loan_term_months": 60,
            "interest_rate": 6.5,
            "trailer_depreciation_reserve_amount": 160,
            "registration_fee": 250,
            "total_cost": 10250,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert float(data["loan_amount"]) == 9000.0
    assert data["loan_term_months"] == 60
    assert float(data["interest_rate"]) == 0.065
    assert float(data["current_loan_balance"]) == 9000.0
    assert float(data["trailer_depreciation_reserve_amount"]) == 160.0
    assert float(data["total_cost"]) == 10250.0


def test_get_trucks_empty(client: TestClient, tenant_headers):
    """Test getting trucks when none exist"""
    response = client.get("/api/trucks", headers=tenant_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_trucks(client: TestClient, tenant_headers):
    """Test getting all trucks"""
    # Create a truck first
    client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"},
        headers=tenant_headers,
    )
    
    response = client.get("/api/trucks", headers=tenant_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Truck 1"


def test_get_truck_by_id(client: TestClient, tenant_headers):
    """Test getting a specific truck"""
    # Create a truck first
    create_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"},
        headers=tenant_headers,
    )
    truck_id = create_response.json()["id"]
    
    # Get the truck
    response = client.get(f"/api/trucks/{truck_id}", headers=tenant_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == truck_id
    assert data["name"] == "Test Truck 1"


def test_get_truck_not_found(client: TestClient, tenant_headers):
    """Test getting a non-existent truck"""
    response = client.get("/api/trucks/999", headers=tenant_headers)
    assert response.status_code == 404


def test_create_truck_duplicate_name(client: TestClient, tenant_headers):
    """Test creating truck with duplicate name should fail"""
    client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"},
        headers=tenant_headers,
    )
    
    # Try to create another truck with same name
    response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "XYZ-789"},
        headers=tenant_headers,
    )
    assert response.status_code == 400 or response.status_code == 500


def test_update_truck_resyncs_paid_off_loan_balance(client: TestClient, db, tenant_headers):
    """Updating truck investment fields should resync a stale stored loan balance."""
    truck = Truck(
        tenant_id=1,
        name="Truck 417",
        vehicle_type="truck",
        license_plate="VW9327",
        cash_investment=100.0,
        loan_amount=500.0,
        current_loan_balance=500.0,
        interest_rate=0.52,
        total_cost=600.0,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    db.add(
        Settlement(
            truck_id=truck.id,
            settlement_date=date(2024, 1, 14),
            gross_revenue=1000.0,
            expenses=100.0,
            net_profit=900.0,
        )
    )
    db.commit()

    response = client.put(
        f"/api/trucks/{truck.id}",
        json={"cash_investment": 100.0},
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_loan_balance"] == 0.0


def test_update_truck_normalizes_percent_interest_rate_input(client: TestClient, db, tenant_headers):
    """Truck updates should normalize 6.5 to decimal interest storage."""
    truck = Truck(
        tenant_id=1,
        name="Interest Update Truck",
        vehicle_type="truck",
        license_plate="INT-651",
        cash_investment=100.0,
        loan_amount=500.0,
        current_loan_balance=500.0,
        interest_rate=0.07,
        total_cost=600.0,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    response = client.put(
        f"/api/trucks/{truck.id}",
        json={"interest_rate": 6.5},
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert float(data["interest_rate"]) == 0.065


def test_update_truck_saves_fuel_estimation_settings(client: TestClient, db, tenant_headers):
    truck = Truck(
        tenant_id=1,
        name="Estimated Miles Update Truck",
        vehicle_type="truck",
        license_plate="MPG-651",
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    response = client.put(
        f"/api/trucks/{truck.id}",
        json={"estimated_mpg": 6.9, "fuel_card_discount_per_gallon": 0.41},
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert float(data["estimated_mpg"]) == pytest.approx(6.9)
    assert float(data["fuel_card_discount_per_gallon"]) == pytest.approx(0.41)


def test_vehicle_roi_reflects_updated_interest_rate(client: TestClient, db, tenant_headers):
    """Vehicle ROI should show the truck's updated stored interest rate."""
    truck = Truck(
        tenant_id=1,
        name="ROI Interest Truck",
        vehicle_type="truck",
        license_plate="INT-652",
        cash_investment=100.0,
        loan_amount=500.0,
        current_loan_balance=500.0,
        interest_rate=0.07,
        total_cost=600.0,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    update_response = client.put(
        f"/api/trucks/{truck.id}",
        json={"interest_rate": 6.5},
        headers=tenant_headers,
    )
    assert update_response.status_code == 200

    roi_response = client.get(f"/api/analytics/vehicle/{truck.id}/roi", headers=tenant_headers)
    assert roi_response.status_code == 200
    data = roi_response.json()
    assert float(data["interest_rate"]) == 0.065


def test_create_settlement_skips_interest_when_history_already_paid_off(client: TestClient, db, tenant_headers):
    """New settlements should not accrue interest when the truck is already in clean return."""
    truck = Truck(
        tenant_id=1,
        name="Truck 0024",
        vehicle_type="truck",
        license_plate="VW9328",
        cash_investment=100.0,
        loan_amount=500.0,
        current_loan_balance=500.0,
        interest_rate=0.52,
        total_cost=600.0,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    db.add(
        Settlement(
            truck_id=truck.id,
            settlement_date=date(2024, 1, 14),
            gross_revenue=1000.0,
            expenses=100.0,
            net_profit=900.0,
        )
    )
    db.commit()

    response = client.post(
        "/api/settlements",
        json={
            "truck_id": truck.id,
            "settlement_date": "2024-01-21",
            "gross_revenue": 700.0,
            "expenses": 100.0,
            "net_profit": 600.0,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert float(data["expenses"]) == 100.0
    assert float(data["net_profit"]) == 600.0
    assert not data.get("expense_categories") or data["expense_categories"].get("loan_interest", 0) == 0


def test_vehicle_roi_derives_payoff_date_from_settlement_replay(client: TestClient, db, tenant_headers):
    """ROI should derive the payoff date from the settlement that clears the final principal balance."""
    truck = Truck(
        tenant_id=1,
        name="Truck ROI Payoff",
        vehicle_type="truck",
        license_plate="ROI-004",
        cash_investment=100.0,
        loan_amount=500.0,
        current_loan_balance=500.0,
        interest_rate=0.52,
        total_cost=600.0,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    db.add_all([
        Settlement(
            truck_id=truck.id,
            settlement_date=date(2024, 1, 7),
            gross_revenue=150.0,
            expenses=0.0,
            net_profit=150.0,
        ),
        Settlement(
            truck_id=truck.id,
            settlement_date=date(2024, 1, 14),
            gross_revenue=200.0,
            expenses=0.0,
            net_profit=200.0,
        ),
        Settlement(
            truck_id=truck.id,
            settlement_date=date(2024, 1, 21),
            gross_revenue=350.0,
            expenses=0.0,
            net_profit=350.0,
        ),
    ])
    db.commit()

    response = client.get(f"/api/analytics/vehicle/{truck.id}/roi", headers=tenant_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["loan_payoff_date"] == "2024-01-21"
    assert data["current_loan_balance"] == 0.0
    assert data["principal_paid_from_excess"] == 500.0
    assert data["projected_payoff_date"] is None


def test_vehicle_roi_forecasts_remaining_balance_from_replay(client: TestClient, db, tenant_headers):
    """ROI should preserve a positive remaining balance and forecast payoff from replay history."""
    truck = Truck(
        tenant_id=1,
        name="Truck ROI Forecast",
        vehicle_type="truck",
        license_plate="ROI-005",
        cash_investment=100.0,
        loan_amount=500.0,
        current_loan_balance=500.0,
        interest_rate=0.52,
        total_cost=600.0,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    db.add_all([
        Settlement(
            truck_id=truck.id,
            settlement_date=date(2024, 1, 7),
            gross_revenue=150.0,
            expenses=0.0,
            net_profit=150.0,
        ),
        Settlement(
            truck_id=truck.id,
            settlement_date=date(2024, 1, 14),
            gross_revenue=100.0,
            expenses=0.0,
            net_profit=100.0,
        ),
        Settlement(
            truck_id=truck.id,
            settlement_date=date(2024, 1, 21),
            gross_revenue=100.0,
            expenses=0.0,
            net_profit=100.0,
        ),
    ])
    db.commit()

    response = client.get(f"/api/analytics/vehicle/{truck.id}/roi", headers=tenant_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["loan_payoff_date"] is None
    assert data["current_loan_balance"] == 250.0
    assert data["principal_paid_from_excess"] == 250.0
    assert data["average_principal_payment"] == 83.33
    assert data["estimated_settlements_to_payoff"] == 4
    assert data["projected_payoff_date"] == "2024-02-18"


def test_create_settlement_with_trailer_income_split_creates_managed_trailer_settlement(client: TestClient, db, tenant_headers):
    """Creating a truck settlement with trailer split should reduce truck revenue and create trailer income."""
    truck = Truck(
        tenant_id=1,
        name="Truck 0024",
        vehicle_type="truck",
        license_plate="VW9328",
    )
    trailer = Truck(
        tenant_id=1,
        name="Trailer A",
        vehicle_type="trailer",
        tag_number="TRL-400",
    )
    db.add_all([truck, trailer])
    db.commit()
    db.refresh(truck)
    db.refresh(trailer)

    response = client.post(
        "/api/settlements",
        json={
            "truck_id": truck.id,
            "settlement_date": "2024-01-21",
            "gross_revenue": 1000.0,
            "expenses": 100.0,
            "net_profit": 900.0,
            "trailer_income_split_trailer_id": trailer.id,
            "trailer_income_split_amount": 400.0,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert float(data["gross_revenue"]) == 600.0
    assert float(data["net_profit"]) == 500.0
    assert data["trailer_income_split_trailer_id"] == trailer.id
    assert float(data["trailer_income_split_amount"]) == 400.0

    trailer_settlement = db.query(Settlement).filter(Settlement.source_settlement_id == data["id"]).first()
    assert trailer_settlement is not None
    assert trailer_settlement.truck_id == trailer.id
    assert float(trailer_settlement.gross_revenue) == 400.0
    assert float(trailer_settlement.expenses or 0) == 0.0
    assert float(trailer_settlement.net_profit) == 400.0

    truck_roi = client.get(f"/api/analytics/vehicle/{truck.id}/roi", headers=tenant_headers)
    trailer_roi = client.get(f"/api/analytics/vehicle/{trailer.id}/roi", headers=tenant_headers)
    assert truck_roi.status_code == 200
    assert trailer_roi.status_code == 200
    assert truck_roi.json()["cumulative_revenue"] == 600.0
    assert trailer_roi.json()["cumulative_revenue"] == 400.0


def test_financed_trailer_split_accrues_interest_and_replays_payoff(client: TestClient, db, tenant_headers):
    """Managed trailer income should deduct trailer loan interest and reduce principal from net profit."""
    truck = Truck(
        tenant_id=1,
        name="Truck With Financed Trailer",
        vehicle_type="truck",
        license_plate="VW9330",
    )
    trailer = Truck(
        tenant_id=1,
        name="Financed Trailer ROI",
        vehicle_type="trailer",
        tag_number="TRL-FIN",
        cash_investment=100.0,
        loan_amount=500.0,
        current_loan_balance=500.0,
        loan_term_months=24,
        interest_rate=0.52,
        total_cost=600.0,
    )
    db.add_all([truck, trailer])
    db.commit()
    db.refresh(truck)
    db.refresh(trailer)

    response = client.post(
        "/api/settlements",
        json={
            "truck_id": truck.id,
            "settlement_date": "2024-01-21",
            "gross_revenue": 1000.0,
            "expenses": 100.0,
            "net_profit": 900.0,
            "trailer_income_split_trailer_id": trailer.id,
            "trailer_income_split_amount": 400.0,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200

    trailer_settlement = db.query(Settlement).filter(
        Settlement.source_settlement_id == response.json()["id"]
    ).first()
    assert trailer_settlement is not None
    assert float(trailer_settlement.gross_revenue) == 400.0
    assert float(trailer_settlement.expenses) == 5.0
    assert trailer_settlement.expense_categories["loan_interest"] == 5.0
    assert float(trailer_settlement.net_profit) == 395.0

    roi_response = client.get(f"/api/analytics/vehicle/{trailer.id}/roi", headers=tenant_headers)
    assert roi_response.status_code == 200
    data = roi_response.json()
    assert data["loan_term_months"] == 24
    assert data["cumulative_revenue"] == 400.0
    assert data["cumulative_settlement_expenses"] == 5.0
    assert data["trailer_settlement_count"] == 1
    assert data["trailer_depreciation_reserve_amount"] == 160.0
    assert data["trailer_depreciation_reserve_total"] == 160.0
    assert data["trailer_free_profit"] == 235.0
    assert data["trailer_cash_position_total"] == 395.0
    assert data["trailer_break_even_sale_price"] == 0.0
    assert data["trailer_projected_three_year_reserve"] == 24960.0
    assert data["current_loan_balance"] == 205.0
    assert data["principal_paid_from_excess"] == 295.0
    assert data["projected_payoff_date"] == "2024-01-28"


def test_create_settlement_uses_truck_default_trailer_split(client: TestClient, db, tenant_headers):
    """Truck-level default split settings should apply when the settlement omits explicit split fields."""
    trailer = Truck(
        tenant_id=1,
        name="Attached Trailer",
        vehicle_type="trailer",
        tag_number="TRL-778",
    )
    truck = Truck(
        tenant_id=1,
        name="Truck 77 Cargo",
        vehicle_type="truck",
        license_plate="VW9327",
        default_trailer_id=None,
        default_trailer_income_split_amount=None,
    )
    db.add_all([truck, trailer])
    db.commit()
    truck.default_trailer_id = trailer.id
    truck.default_trailer_income_split_amount = 400.0
    db.add(truck)
    db.commit()
    db.refresh(truck)

    response = client.post(
        "/api/settlements",
        json={
            "truck_id": truck.id,
            "settlement_date": "2024-02-04",
            "gross_revenue": 1200.0,
            "expenses": 100.0,
            "net_profit": 1100.0,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["trailer_income_split_trailer_id"] == trailer.id
    assert float(data["trailer_income_split_amount"]) == 400.0
    assert float(data["gross_revenue"]) == 800.0
    assert float(data["net_profit"]) == 700.0

    trailer_settlement = db.query(Settlement).filter(Settlement.source_settlement_id == data["id"]).first()
    assert trailer_settlement is not None
    assert trailer_settlement.truck_id == trailer.id
    assert float(trailer_settlement.gross_revenue) == 400.0
    assert float(trailer_settlement.net_profit) == 400.0


def test_backfill_trailer_income_splits_reapplies_current_truck_default(client: TestClient, db, tenant_headers, monkeypatch):
    """Existing source and managed trailer settlements can be replayed to the current truck default split."""
    script_path = Path(__file__).resolve().parents[1] / "backfill_trailer_income_splits.py"
    spec = importlib.util.spec_from_file_location("backfill_trailer_income_splits", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(script)

    trailer = Truck(
        tenant_id=1,
        name="Replay Trailer",
        vehicle_type="trailer",
        tag_number="TRL-REPLAY",
    )
    db.add(trailer)
    db.commit()
    db.refresh(trailer)

    truck = Truck(
        tenant_id=1,
        name="Replay Truck",
        vehicle_type="truck",
        license_plate="RPL-100",
        default_trailer_id=trailer.id,
        default_trailer_income_split_amount=160.0,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    response = client.post(
        "/api/settlements",
        json={
            "truck_id": truck.id,
            "settlement_date": "2026-05-11",
            "gross_revenue": 1000.0,
            "expenses": 100.0,
            "net_profit": 900.0,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200
    source_id = response.json()["id"]

    source = db.query(Settlement).filter(Settlement.id == source_id).first()
    child = db.query(Settlement).filter(Settlement.source_settlement_id == source_id).first()
    assert float(source.gross_revenue) == 840.0
    assert float(source.net_profit) == 740.0
    assert float(source.trailer_income_split_amount) == 160.0
    assert child is not None
    assert float(child.gross_revenue) == 160.0

    truck.default_trailer_income_split_amount = 400.0
    db.add(truck)
    db.commit()

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db.bind)
    monkeypatch.setattr(script, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(script, "create_settlement_journal_entry", lambda *args, **kwargs: None)
    monkeypatch.setattr(script, "delete_settlement_journal_entry", lambda *args, **kwargs: None)

    assert script.backfill(dry_run=False, from_date=date(2026, 1, 1), truck_id=truck.id) is True
    db.expire_all()

    refreshed_source = db.query(Settlement).filter(Settlement.id == source_id).first()
    refreshed_child = db.query(Settlement).filter(Settlement.source_settlement_id == source_id).first()
    assert float(refreshed_source.gross_revenue) == 600.0
    assert float(refreshed_source.net_profit) == 500.0
    assert float(refreshed_source.trailer_income_split_amount) == 400.0
    assert refreshed_source.trailer_income_split_trailer_id == trailer.id
    assert refreshed_child is not None
    assert float(refreshed_child.gross_revenue) == 400.0
    assert float(refreshed_child.net_profit) == 400.0


def test_cleanup_pre_attachment_trailer_splits_restores_source_and_keeps_manual_trailer_income(client: TestClient, db, tenant_headers, monkeypatch):
    """Cleanup removes pre-cutoff managed trailer splits without deleting standalone trailer income."""
    script_path = Path(__file__).resolve().parents[1] / "cleanup_pre_attachment_trailer_splits.py"
    spec = importlib.util.spec_from_file_location("cleanup_pre_attachment_trailer_splits", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(script)

    trailer = Truck(
        tenant_id=1,
        name="Pre-Attachment Trailer",
        vehicle_type="trailer",
        tag_number="TRL-PRE",
    )
    truck = Truck(
        tenant_id=1,
        name="Pre-Attachment Truck",
        vehicle_type="truck",
        license_plate="PRE-100",
    )
    db.add_all([trailer, truck])
    db.commit()
    db.refresh(trailer)
    db.refresh(truck)

    source = Settlement(
        truck_id=truck.id,
        settlement_date=date(2026, 1, 17),
        gross_revenue=600.0,
        expenses=100.0,
        net_profit=500.0,
        trailer_income_split_trailer_id=trailer.id,
        trailer_income_split_amount=400.0,
    )
    manual = Settlement(
        truck_id=trailer.id,
        settlement_date=date(2026, 1, 18),
        gross_revenue=1600.0,
        expenses=0.0,
        net_profit=1600.0,
        settlement_type="Manual Entry",
    )
    db.add_all([source, manual])
    db.commit()
    db.refresh(source)

    child = Settlement(
        truck_id=trailer.id,
        settlement_date=date(2026, 1, 17),
        gross_revenue=400.0,
        expenses=0.0,
        net_profit=400.0,
        settlement_type="Trailer Income Split",
        source_settlement_id=source.id,
    )
    db.add(child)
    db.commit()
    child_id = child.id

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db.bind)
    monkeypatch.setattr(script, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(script, "create_settlement_journal_entry", lambda *args, **kwargs: None)
    monkeypatch.setattr(script, "delete_settlement_journal_entry", lambda *args, **kwargs: None)

    assert script.cleanup(trailer_id=trailer.id, before_date=date(2026, 4, 1), dry_run=False) is True
    db.expire_all()

    refreshed_source = db.query(Settlement).filter(Settlement.id == source.id).first()
    refreshed_manual = db.query(Settlement).filter(Settlement.id == manual.id).first()
    removed_child = db.query(Settlement).filter(Settlement.id == child_id).first()

    assert float(refreshed_source.gross_revenue) == 1000.0
    assert float(refreshed_source.net_profit) == 900.0
    assert refreshed_source.trailer_income_split_trailer_id is None
    assert refreshed_source.trailer_income_split_amount is None
    assert refreshed_manual is not None
    assert float(refreshed_manual.gross_revenue) == 1600.0
    assert removed_child is None


def test_create_settlement_uses_truck_default_repair_reserve(client: TestClient, db, tenant_headers):
    """Truck-level default repair reserve should reduce carried truck profit when split fields are omitted."""
    truck = Truck(
        tenant_id=1,
        name="Truck Reserve",
        vehicle_type="truck",
        license_plate="VW9330",
        default_repair_reserve_amount=500.0,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    response = client.post(
        "/api/settlements",
        json={
            "truck_id": truck.id,
            "settlement_date": "2024-02-11",
            "gross_revenue": 2000.0,
            "expenses": 200.0,
            "net_profit": 1800.0,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert float(data["repair_reserve_amount"]) == 500.0
    assert float(data["gross_revenue"]) == 1500.0
    assert float(data["net_profit"]) == 1300.0


def test_update_truck_default_repair_reserve_rewrites_2026_settlements_and_ledger(client: TestClient, db, tenant_headers):
    """Changing the truck default reserve should rewrite 2026+ settlements and re-sync deposit ledger rows."""
    from app.models.repair_reserve_ledger import RepairReserveLedger

    truck = Truck(
        tenant_id=1,
        name="Truck Retro Reserve",
        vehicle_type="truck",
        license_plate="VW9331",
        default_repair_reserve_amount=500.0,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    create_response = client.post(
        "/api/settlements",
        json={
            "truck_id": truck.id,
            "settlement_date": "2026-02-11",
            "gross_revenue": 2000.0,
            "expenses": 200.0,
            "net_profit": 1800.0,
        },
        headers=tenant_headers,
    )
    assert create_response.status_code == 200
    settlement_2026_id = create_response.json()["id"]

    legacy_settlement = Settlement(
        truck_id=truck.id,
        settlement_date=date(2025, 12, 20),
        gross_revenue=1500.0,
        expenses=200.0,
        net_profit=1300.0,
        repair_reserve_amount=500.0,
    )
    db.add(legacy_settlement)
    db.commit()
    db.refresh(legacy_settlement)

    update_response = client.put(
        f"/api/trucks/{truck.id}",
        json={"default_repair_reserve_amount": 300.0},
        headers=tenant_headers,
    )
    assert update_response.status_code == 200
    assert float(update_response.json()["default_repair_reserve_amount"]) == 300.0

    refreshed_2026 = db.query(Settlement).filter(Settlement.id == settlement_2026_id).first()
    refreshed_2025 = db.query(Settlement).filter(Settlement.id == legacy_settlement.id).first()
    assert refreshed_2026 is not None
    assert refreshed_2025 is not None

    assert float(refreshed_2026.repair_reserve_amount) == 300.0
    assert float(refreshed_2026.gross_revenue) == 1700.0
    assert float(refreshed_2026.net_profit) == 1500.0

    assert float(refreshed_2025.repair_reserve_amount) == 500.0
    assert float(refreshed_2025.gross_revenue) == 1500.0
    assert float(refreshed_2025.net_profit) == 1300.0

    ledger_row = db.query(RepairReserveLedger).filter_by(source_type="settlement", source_id=settlement_2026_id).first()
    assert ledger_row is not None
    assert float(ledger_row.amount) == 300.0


def test_delete_source_settlement_removes_managed_trailer_income_split(client: TestClient, db, tenant_headers):
    """Deleting the source truck settlement should also delete the managed trailer income settlement."""
    truck = Truck(
        tenant_id=1,
        name="Truck 417",
        vehicle_type="truck",
        license_plate="VW417",
    )
    trailer = Truck(
        tenant_id=1,
        name="Trailer B",
        vehicle_type="trailer",
        tag_number="TRL-401",
    )
    db.add_all([truck, trailer])
    db.commit()
    db.refresh(truck)
    db.refresh(trailer)

    create_response = client.post(
        "/api/settlements",
        json={
            "truck_id": truck.id,
            "settlement_date": "2024-01-28",
            "gross_revenue": 900.0,
            "expenses": 100.0,
            "net_profit": 800.0,
            "trailer_income_split_trailer_id": trailer.id,
            "trailer_income_split_amount": 400.0,
        },
        headers=tenant_headers,
    )
    assert create_response.status_code == 200
    source_settlement_id = create_response.json()["id"]
    trailer_settlement = db.query(Settlement).filter(Settlement.source_settlement_id == source_settlement_id).first()
    assert trailer_settlement is not None

    delete_response = client.delete(f"/api/settlements/{source_settlement_id}", headers=tenant_headers)
    assert delete_response.status_code == 200
    assert db.query(Settlement).filter(Settlement.id == source_settlement_id).first() is None
    assert db.query(Settlement).filter(Settlement.id == trailer_settlement.id).first() is None
