"""
Tests for settlements API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date


def test_create_settlement(client: TestClient):
    """Test creating a settlement manually"""
    # First create a truck
    truck_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    truck_id = truck_response.json()["id"]
    
    # Create a settlement
    settlement_data = {
        "truck_id": truck_id,
        "settlement_date": "2024-01-15",
        "week_start": "2024-01-08",
        "week_end": "2024-01-14",
        "miles_driven": 1200.5,
        "blocks_delivered": 45,
        "gross_revenue": 5000.00,
        "expenses": 1200.00,
        "net_profit": 3800.00
    }
    
    response = client.post("/api/settlements", json=settlement_data)
    assert response.status_code == 200
    data = response.json()
    assert data["truck_id"] == truck_id
    assert data["miles_driven"] == 1200.5
    assert data["blocks_delivered"] == 45
    assert data["gross_revenue"] == 5000.00


def test_get_settlements(client: TestClient):
    """Test getting all settlements"""
    # Create truck and settlement
    truck_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    truck_id = truck_response.json()["id"]
    
    client.post(
        "/api/settlements",
        json={
            "truck_id": truck_id,
            "settlement_date": "2024-01-15",
            "miles_driven": 1200.5,
            "blocks_delivered": 45,
            "gross_revenue": 5000.00,
            "expenses": 1200.00,
            "net_profit": 3800.00
        }
    )
    
    response = client.get("/api/settlements")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_get_settlements_filtered_by_truck(client: TestClient):
    """Test getting settlements filtered by truck_id"""
    # Create two trucks
    truck1_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    truck1_id = truck1_response.json()["id"]
    
    truck2_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 2", "license_plate": "XYZ-789"}
    )
    truck2_id = truck2_response.json()["id"]
    
    # Create settlements for both trucks
    client.post(
        "/api/settlements",
        json={
            "truck_id": truck1_id,
            "settlement_date": "2024-01-15",
            "miles_driven": 1200.5,
            "blocks_delivered": 45,
            "gross_revenue": 5000.00,
            "expenses": 1200.00,
            "net_profit": 3800.00
        }
    )
    
    client.post(
        "/api/settlements",
        json={
            "truck_id": truck2_id,
            "settlement_date": "2024-01-15",
            "miles_driven": 1500.0,
            "blocks_delivered": 50,
            "gross_revenue": 6000.00,
            "expenses": 1500.00,
            "net_profit": 4500.00
        }
    )
    
    # Get settlements for truck1 only
    response = client.get(f"/api/settlements?truck_id={truck1_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["truck_id"] == truck1_id


def test_get_settlement_by_id(client: TestClient):
    """Test getting a specific settlement"""
    # Create truck and settlement
    truck_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    truck_id = truck_response.json()["id"]
    
    create_response = client.post(
        "/api/settlements",
        json={
            "truck_id": truck_id,
            "settlement_date": "2024-01-15",
            "miles_driven": 1200.5,
            "blocks_delivered": 45,
            "gross_revenue": 5000.00,
            "expenses": 1200.00,
            "net_profit": 3800.00
        }
    )
    settlement_id = create_response.json()["id"]
    
    # Get the settlement
    response = client.get(f"/api/settlements/{settlement_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == settlement_id
    assert data["miles_driven"] == 1200.5


def test_get_settlement_not_found(client: TestClient):
    """Test getting a non-existent settlement"""
    response = client.get("/api/settlements/999")
    assert response.status_code == 404


