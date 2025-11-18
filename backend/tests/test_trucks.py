"""
Tests for trucks API endpoints
"""
import pytest
from fastapi.testclient import TestClient


def test_create_truck(client: TestClient):
    """Test creating a truck"""
    response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Truck 1"
    assert data["license_plate"] == "ABC-123"
    assert "id" in data
    assert "created_at" in data


def test_get_trucks_empty(client: TestClient):
    """Test getting trucks when none exist"""
    response = client.get("/api/trucks")
    assert response.status_code == 200
    assert response.json() == []


def test_get_trucks(client: TestClient):
    """Test getting all trucks"""
    # Create a truck first
    client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    
    response = client.get("/api/trucks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Truck 1"


def test_get_truck_by_id(client: TestClient):
    """Test getting a specific truck"""
    # Create a truck first
    create_response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    truck_id = create_response.json()["id"]
    
    # Get the truck
    response = client.get(f"/api/trucks/{truck_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == truck_id
    assert data["name"] == "Test Truck 1"


def test_get_truck_not_found(client: TestClient):
    """Test getting a non-existent truck"""
    response = client.get("/api/trucks/999")
    assert response.status_code == 404


def test_create_truck_duplicate_name(client: TestClient):
    """Test creating truck with duplicate name should fail"""
    client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "ABC-123"}
    )
    
    # Try to create another truck with same name
    response = client.post(
        "/api/trucks",
        json={"name": "Test Truck 1", "license_plate": "XYZ-789"}
    )
    assert response.status_code == 400 or response.status_code == 500


