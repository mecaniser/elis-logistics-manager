import json
import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app.services import accounting_service
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.models.settlement import Settlement
from app.models.tenant import Tenant
from app.models.truck import Truck


def make_truck(
    db,
    *,
    tenant_id=1,
    name="Truck 1",
    vehicle_type="truck",
    license_plate=None,
    tag_number=None,
    default_repair_reserve_amount=None,
    default_trailer_id=None,
    default_trailer_income_split_amount=None,
):
    truck = Truck(
        tenant_id=tenant_id,
        name=name,
        vehicle_type=vehicle_type,
        license_plate=license_plate,
        tag_number=tag_number,
        default_repair_reserve_amount=default_repair_reserve_amount,
        default_trailer_id=default_trailer_id,
        default_trailer_income_split_amount=default_trailer_income_split_amount,
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)
    return truck


def settlement_payload(truck_id: int, settlement_date: str, reserve_amount=None):
    payload = {
        "truck_id": truck_id,
        "settlement_date": settlement_date,
        "week_start": settlement_date,
        "week_end": settlement_date,
        "gross_revenue": 2000.0,
        "expenses": 500.0,
        "net_profit": 1500.0,
        "block_ids": ["B-100"],
    }
    if reserve_amount is not None:
        payload["repair_reserve_amount"] = reserve_amount
    return payload


def repair_form_data(truck_id: int, repair_date: str, *, cost=300.0, paid_from_reserve=False):
    return {
        "repair_json": json.dumps(
            {
                "truck_id": truck_id,
                "repair_date": repair_date,
                "description": "Brake repair",
                "category": "brakes",
                "cost": cost,
                "paid_from_reserve": paid_from_reserve,
            }
        )
    }


def test_settlement_create_respects_cutoff_and_creates_post_cutoff_deposit(client, db, tenant_headers):
    truck = make_truck(db, name="Reserve Truck", license_plate="RES-100")

    pre_response = client.post(
        "/api/settlements",
        json=settlement_payload(truck.id, "2025-12-31", reserve_amount=500.0),
        headers=tenant_headers,
    )
    assert pre_response.status_code == 200
    assert db.query(RepairReserveLedger).count() == 0

    post_response = client.post(
        "/api/settlements",
        json=settlement_payload(truck.id, "2026-01-07", reserve_amount=500.0),
        headers=tenant_headers,
    )
    assert post_response.status_code == 200

    rows = db.query(RepairReserveLedger).order_by(RepairReserveLedger.id.asc()).all()
    assert len(rows) == 1
    assert rows[0].entry_type == "deposit"
    assert float(rows[0].amount) == 500.0
    assert rows[0].truck_id == truck.id


def test_settlement_update_updates_and_deletes_linked_deposit(client, db, tenant_headers):
    truck = make_truck(db, name="Update Truck", license_plate="UPD-100")
    create_response = client.post(
        "/api/settlements",
        json=settlement_payload(truck.id, "2026-02-01", reserve_amount=500.0),
        headers=tenant_headers,
    )
    assert create_response.status_code == 200
    settlement_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/settlements/{settlement_id}",
        data={"settlement_update_json": json.dumps({"repair_reserve_amount": 650.0})},
        headers=tenant_headers,
    )
    assert update_response.status_code == 200

    row = db.query(RepairReserveLedger).filter_by(source_type="settlement", source_id=settlement_id).first()
    assert row is not None
    assert float(row.amount) == 650.0

    zero_response = client.put(
        f"/api/settlements/{settlement_id}",
        data={"settlement_update_json": json.dumps({"repair_reserve_amount": 0})},
        headers=tenant_headers,
    )
    assert zero_response.status_code == 200
    assert db.query(RepairReserveLedger).filter_by(source_type="settlement", source_id=settlement_id).first() is None


def test_settlement_delete_removes_reserve_deposit(client, db, tenant_headers):
    truck = make_truck(db, name="Delete Truck", license_plate="DEL-100")
    response = client.post(
        "/api/settlements",
        json=settlement_payload(truck.id, "2026-02-08", reserve_amount=400.0),
        headers=tenant_headers,
    )
    assert response.status_code == 200
    settlement_id = response.json()["id"]
    assert db.query(RepairReserveLedger).filter_by(source_type="settlement", source_id=settlement_id).count() == 1

    delete_response = client.delete(f"/api/settlements/{settlement_id}", headers=tenant_headers)
    assert delete_response.status_code == 200
    assert db.query(RepairReserveLedger).filter_by(source_type="settlement", source_id=settlement_id).count() == 0


def test_repair_create_respects_cutoff_and_paid_from_reserve_flag(client, db, tenant_headers):
    truck = make_truck(db, name="Repair Truck", license_plate="REP-100")

    pre_response = client.post(
        "/api/repairs/",
        data=repair_form_data(truck.id, "2025-12-20", paid_from_reserve=True),
        headers=tenant_headers,
    )
    assert pre_response.status_code == 200
    assert db.query(RepairReserveLedger).count() == 0

    post_response = client.post(
        "/api/repairs/",
        data=repair_form_data(truck.id, "2026-03-15", paid_from_reserve=True),
        headers=tenant_headers,
    )
    assert post_response.status_code == 200
    repair_id = post_response.json()["id"]

    row = db.query(RepairReserveLedger).filter_by(source_type="repair", source_id=repair_id).first()
    assert row is not None
    assert row.entry_type == "withdrawal"
    assert float(row.amount) == 300.0


def test_repair_update_updates_and_deletes_withdrawal(client, db, tenant_headers):
    truck = make_truck(db, name="Repair Update Truck", license_plate="RUP-100")
    response = client.post(
        "/api/repairs/",
        data=repair_form_data(truck.id, "2026-03-20", paid_from_reserve=True),
        headers=tenant_headers,
    )
    assert response.status_code == 200
    repair_id = response.json()["id"]

    update_response = client.put(
        f"/api/repairs/{repair_id}",
        data={"repair_update_json": json.dumps({"cost": 425.0, "paid_from_reserve": True})},
        headers=tenant_headers,
    )
    assert update_response.status_code == 200
    row = db.query(RepairReserveLedger).filter_by(source_type="repair", source_id=repair_id).first()
    assert row is not None
    assert float(row.amount) == 425.0

    toggle_response = client.put(
        f"/api/repairs/{repair_id}",
        data={"repair_update_json": json.dumps({"paid_from_reserve": False})},
        headers=tenant_headers,
    )
    assert toggle_response.status_code == 200
    assert db.query(RepairReserveLedger).filter_by(source_type="repair", source_id=repair_id).first() is None


def test_repair_update_works_without_soft_delete_support(client, db, tenant_headers, monkeypatch):
    truck = make_truck(db, name="Compatibility Truck", license_plate="CMP-100")
    response = client.post(
        "/api/repairs/",
        data=repair_form_data(truck.id, "2026-03-22", paid_from_reserve=True),
        headers=tenant_headers,
    )
    assert response.status_code == 200
    repair_id = response.json()["id"]

    monkeypatch.setattr(accounting_service, "_journal_entry_supports_soft_delete", lambda: False)

    update_response = client.put(
        f"/api/repairs/{repair_id}",
        data={"repair_update_json": json.dumps({"cost": 410.0, "paid_from_reserve": True})},
        headers=tenant_headers,
    )
    assert update_response.status_code == 200

    row = db.query(RepairReserveLedger).filter_by(source_type="repair", source_id=repair_id).first()
    assert row is not None
    assert float(row.amount) == 410.0


def test_repair_requires_date_when_paid_from_reserve(client, db, tenant_headers):
    truck = make_truck(db, name="Date Validation Truck", license_plate="DVR-100")
    response = client.post(
        "/api/repairs/",
        data={
            "repair_json": json.dumps(
                {
                    "truck_id": truck.id,
                    "description": "Missing date repair",
                    "category": "maintenance",
                    "cost": 150.0,
                    "paid_from_reserve": True,
                }
            )
        },
        headers=tenant_headers,
    )
    assert response.status_code == 400
    assert "Set a repair date" in response.json()["detail"]


def test_reserve_balance_endpoint_returns_expected_math(client, db, tenant_headers):
    truck = make_truck(db, name="Balance Truck", license_plate="BAL-100")
    db.add_all(
        [
            RepairReserveLedger(
                tenant_id=1,
                truck_id=truck.id,
                entry_date=date(2026, 1, 7),
                entry_type="deposit",
                amount=Decimal("500.00"),
                source_type="settlement",
                source_id=1,
            ),
            RepairReserveLedger(
                tenant_id=1,
                truck_id=truck.id,
                entry_date=date(2026, 1, 14),
                entry_type="deposit",
                amount=Decimal("500.00"),
                source_type="settlement",
                source_id=2,
            ),
            RepairReserveLedger(
                tenant_id=1,
                truck_id=truck.id,
                entry_date=date(2026, 2, 1),
                entry_type="withdrawal",
                amount=Decimal("300.00"),
                source_type="repair",
                source_id=10,
            ),
            RepairReserveLedger(
                tenant_id=1,
                truck_id=truck.id,
                entry_date=date(2026, 2, 10),
                entry_type="adjustment",
                amount=Decimal("50.00"),
                source_type="manual",
                source_id=99,
            ),
        ]
    )
    db.commit()

    response = client.get(f"/api/trucks/{truck.id}/reserve-balance", headers=tenant_headers)
    assert response.status_code == 200
    data = response.json()
    assert float(data["deposits_total"]) == 1000.0
    assert float(data["withdrawals_total"]) == 300.0
    assert float(data["adjustments_total"]) == 50.0
    assert float(data["balance"]) == 750.0


def test_reserve_endpoints_enforce_tenant_isolation(client, db, tenant_headers):
    db.add(Tenant(id=2, name="Other Tenant", business_type="logistics"))
    db.commit()

    truck_a = make_truck(db, tenant_id=1, name="Tenant A Truck", license_plate="TEN-100")
    truck_b = make_truck(db, tenant_id=2, name="Tenant B Truck", license_plate="TEN-200")

    db.add(
        RepairReserveLedger(
            tenant_id=2,
            truck_id=truck_b.id,
            entry_date=date(2026, 1, 7),
            entry_type="deposit",
            amount=Decimal("500.00"),
            source_type="settlement",
            source_id=20,
        )
    )
    db.commit()

    balance_response = client.get(f"/api/trucks/{truck_b.id}/reserve-balance", headers=tenant_headers)
    assert balance_response.status_code == 404

    ledger_response = client.get(f"/api/trucks/{truck_b.id}/reserve-ledger", headers=tenant_headers)
    assert ledger_response.status_code == 404

    bulk_response = client.get("/api/reserve-balances", headers=tenant_headers)
    assert bulk_response.status_code == 200
    truck_ids = [row["truck_id"] for row in bulk_response.json()]
    assert truck_b.id not in truck_ids
    assert truck_a.id not in truck_ids


def test_reserve_balances_bulk_uses_single_query(client, db, tenant_headers):
    truck = make_truck(db, name="Query Count Truck", license_plate="SQL-100")
    db.add(
        RepairReserveLedger(
            tenant_id=1,
            truck_id=truck.id,
            entry_date=date(2026, 1, 7),
            entry_type="deposit",
            amount=Decimal("500.00"),
            source_type="settlement",
            source_id=1,
        )
    )
    db.commit()

    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        normalized = statement.strip().upper()
        if normalized.startswith("SELECT"):
            statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get("/api/reserve-balances", headers=tenant_headers)
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor_execute)

    assert response.status_code == 200
    assert len(statements) == 1


def test_backfill_populates_2026_only_and_is_idempotent(db, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "backfill_repair_reserves.py"
    spec = importlib.util.spec_from_file_location("backfill_repair_reserves", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(script)

    truck = make_truck(
        db,
        name="Backfill Truck",
        license_plate="BCK-100",
        default_repair_reserve_amount=Decimal("500.00"),
    )
    older_truck = make_truck(
        db,
        name="Older Truck",
        license_plate="OLD-100",
        default_repair_reserve_amount=Decimal("500.00"),
    )

    db.add_all(
        [
            Settlement(
                truck_id=truck.id,
                settlement_date=date(2026, 1, 10),
                week_start=date(2026, 1, 10),
                week_end=date(2026, 1, 10),
                gross_revenue=1000,
                expenses=100,
                net_profit=900,
                repair_reserve_amount=None,
            ),
            Settlement(
                truck_id=older_truck.id,
                settlement_date=date(2025, 12, 20),
                week_start=date(2025, 12, 20),
                week_end=date(2025, 12, 20),
                gross_revenue=900,
                expenses=100,
                net_profit=800,
                repair_reserve_amount=None,
            ),
        ]
    )
    db.commit()

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db.bind)
    monkeypatch.setattr(script, "SessionLocal", TestSessionLocal)

    assert script.backfill(dry_run=False) is True

    refreshed_2026 = db.query(Settlement).filter(Settlement.truck_id == truck.id).first()
    refreshed_2025 = db.query(Settlement).filter(Settlement.truck_id == older_truck.id).first()
    assert float(refreshed_2026.repair_reserve_amount) == 500.0
    assert refreshed_2025.repair_reserve_amount is None
    assert db.query(RepairReserveLedger).filter_by(source_type="settlement", source_id=refreshed_2026.id).count() == 1

    assert script.backfill(dry_run=True) is True
    output = capsys.readouterr().out
    assert "populated repair_reserve_amount on 1 settlements" in output
    assert "would populate repair_reserve_amount on 0 settlements" in output
    assert "would create 0 new deposit rows; would reconcile 0 existing rows" in output


def test_atomic_settlement_write_rolls_back_settlement_child_and_ledger(client, db, tenant_headers, monkeypatch):
    import app.routers.settlements as settlements_router

    trailer = make_truck(db, name="Atomic Trailer", vehicle_type="trailer", tag_number="TRL-100")
    truck = make_truck(
        db,
        name="Atomic Truck",
        license_plate="ATM-100",
        default_trailer_id=trailer.id,
        default_trailer_income_split_amount=Decimal("400.00"),
        default_repair_reserve_amount=Decimal("500.00"),
    )

    def boom(*args, **kwargs):
        raise RuntimeError("journal failure")

    monkeypatch.setattr(settlements_router, "create_settlement_journal_entry", boom)

    response = client.post(
        "/api/settlements",
        json=settlement_payload(truck.id, "2026-04-01"),
        headers=tenant_headers,
    )
    assert response.status_code == 500
    assert db.query(Settlement).count() == 0
    assert db.query(RepairReserveLedger).count() == 0


def test_atomic_repair_write_rolls_back_repair_and_withdrawal(client, db, tenant_headers, monkeypatch):
    import app.routers.repairs as repairs_router

    truck = make_truck(db, name="Atomic Repair Truck", license_plate="ATR-100")

    def boom(*args, **kwargs):
        raise RuntimeError("journal failure")

    monkeypatch.setattr(repairs_router, "create_repair_journal_entry", boom)

    response = client.post(
        "/api/repairs/",
        data=repair_form_data(truck.id, "2026-04-10", paid_from_reserve=True),
        headers=tenant_headers,
    )
    assert response.status_code == 400
    assert db.query(Repair).count() == 0
    assert db.query(RepairReserveLedger).count() == 0
