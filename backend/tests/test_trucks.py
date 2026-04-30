"""
Tests for trucks API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date

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
