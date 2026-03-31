"""
Tests for vehicle document endpoints.
"""
from pathlib import Path

from fastapi.testclient import TestClient


UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"


def create_vehicle(client: TestClient, tenant_headers) -> int:
    response = client.post(
        "/api/trucks",
        json={"name": "Unit 01", "license_plate": "ABC-123", "cash_investment": 1000},
        headers=tenant_headers,
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_upload_list_and_delete_vehicle_document(client: TestClient, tenant_headers):
    truck_id = create_vehicle(client, tenant_headers)

    upload_response = client.post(
        f"/api/trucks/{truck_id}/documents",
        data={
            "document_type": "title",
            "title": "Vehicle Title",
            "notes": "Original title copy",
        },
        files={"file": ("title.pdf", b"%PDF-1.4 sample title", "application/pdf")},
        headers=tenant_headers,
    )

    assert upload_response.status_code == 200
    document = upload_response.json()
    assert document["document_type"] == "title"
    assert document["title"] == "Vehicle Title"
    assert document["original_filename"] == "title.pdf"

    local_file = UPLOADS_DIR / document["file_path"]
    assert local_file.exists()

    list_response = client.get(f"/api/trucks/{truck_id}/documents", headers=tenant_headers)
    assert list_response.status_code == 200
    listed_documents = list_response.json()
    assert len(listed_documents) == 1
    assert listed_documents[0]["id"] == document["id"]

    delete_response = client.delete(
        f"/api/trucks/{truck_id}/documents/{document['id']}",
        headers=tenant_headers,
    )
    assert delete_response.status_code == 200
    assert not local_file.exists()

    list_after_delete = client.get(f"/api/trucks/{truck_id}/documents", headers=tenant_headers)
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []


def test_rejects_unsupported_vehicle_document_file_type(client: TestClient, tenant_headers):
    truck_id = create_vehicle(client, tenant_headers)

    response = client.post(
        f"/api/trucks/{truck_id}/documents",
        data={"document_type": "inspection"},
        files={"file": ("inspection.docx", b"not supported", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=tenant_headers,
    )

    assert response.status_code == 400
    assert "supported" in response.json()["detail"].lower()
