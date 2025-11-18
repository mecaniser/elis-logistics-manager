"""
Tests for repairs API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date


def test_create_repair(client: TestClient):
    """Test creating a repair expense"""
    # First create a truck
    truck_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    truck_id = truck_response.json()["id"]
    
    # Create a repair
    repair_data = {
        "truck_id": truck_id,
        "date": "2024-01-15",
        "description": "Oil change",
        "cost": 75.50
    }
    
    response = client.post("/api/repairs", json=repair_data)
    assert response.status_code == 200
    data = response.json()
    assert data["truck_id"] == truck_id
    assert data["description"] == "Oil change"
    assert data["cost"] == 75.50
    assert "id" in data
    assert "created_at" in data


def test_get_repairs(client: TestClient):
    """Test getting all repairs"""
    # Create truck and repair
    truck_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    truck_id = truck_response.json()["id"]
    
    client.post(
        "/api/repairs",
        json={
            "truck_id": truck_id,
            "date": "2024-01-15",
            "description": "Oil change",
            "cost": 75.50
        }
    )
    
    response = client.get("/api/repairs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_get_repairs_filtered_by_truck(client: TestClient):
    """Test getting repairs filtered by truck_id"""
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
    
    # Create repairs for both trucks
    client.post(
        "/api/repairs",
        json={
            "truck_id": truck1_id,
            "date": "2024-01-15",
            "description": "Oil change",
            "cost": 75.50
        }
    )
    
    client.post(
        "/api/repairs",
        json={
            "truck_id": truck2_id,
            "date": "2024-01-16",
            "description": "Tire replacement",
            "cost": 500.00
        }
    )
    
    # Get repairs for truck1 only
    response = client.get(f"/api/repairs?truck_id={truck1_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["truck_id"] == truck1_id


def test_get_repair_by_id(client: TestClient):
    """Test getting a specific repair"""
    # Create truck and repair
    truck_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    truck_id = truck_response.json()["id"]
    
    create_response = client.post(
        "/api/repairs",
        json={
            "truck_id": truck_id,
            "date": "2024-01-15",
            "description": "Oil change",
            "cost": 75.50
        }
    )
    repair_id = create_response.json()["id"]
    
    # Get the repair
    response = client.get(f"/api/repairs/{repair_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == repair_id
    assert data["description"] == "Oil change"


def test_delete_repair(client: TestClient):
    """Test deleting a repair"""
    # Create truck and repair
    truck_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    truck_id = truck_response.json()["id"]
    
    create_response = client.post(
        "/api/repairs",
        json={
            "truck_id": truck_id,
            "date": "2024-01-15",
            "description": "Oil change",
            "cost": 75.50
        }
    )
    repair_id = create_response.json()["id"]
    
    # Delete the repair
    response = client.delete(f"/api/repairs/{repair_id}")
    assert response.status_code == 200
    
    # Verify it's deleted
    get_response = client.get(f"/api/repairs/{repair_id}")
    assert get_response.status_code == 404


def test_get_repair_not_found(client: TestClient):
    """Test getting a non-existent repair"""
    response = client.get("/api/repairs/999")
    assert response.status_code == 404


