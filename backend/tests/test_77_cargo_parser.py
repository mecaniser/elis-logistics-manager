from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models.chart_of_accounts import ChartOfAccount
from app.models.journal_entry_line import JournalEntryLine
from app.models.settlement import Settlement
from app.models.tenant import Tenant
from app.models.truck import Truck
from app.routers import settlements as settlements_router
from app.services import accounting_service as accounting_service_module
from app.services.accounting_service import create_settlement_journal_entry
from app.utils import pdf_parser as pdf_parser_module
from app.utils import settlement_extractor as settlement_extractor_module
from app.utils.pdf_parser import parse_amazon_relay_pdf
from app.utils.settlement_extractor import SettlementExtractor


PAGE_1 = """77 Cargo LLC
1115 Ansley Park Dr
Fort Mill, SC 29707
Email: safety@77cargo.com
Phone: (704) 835-2433
Settlement #1839
Date: 04/06/26
Driver:
Truck:
Pay to: ELIS LOGISTICS LLC
1002 Yearden Ln
Monroe, NC 28110
Email: Elislogistics86@gmail.com
Phone: (704) 705-0486
Pay rate: 88%
Load# Pickup Delivery Description Empty Loaded % Rate Amount
Oleksandr Moskaliuk [Drv] #3533
3533 03/30/26 03/31/26 0 735 88% $2,500.00 $2,200.00
Huntersville, NC - Hopkins, MI
Oleksandr Moskaliuk [Drv] #3551
3551 03/31/26 04/01/26 97 683 88% $2,950.00 $2,596.00
Elkhart, IN - Fairless Hills, PA
Oleksandr Moskaliuk [Drv] #3564
3564 04/02/26 04/03/26 139 369 88% $1,800.00 $1,584.00
Sparrows Point, MD - Sanford, NC
Subtotal: 236 1787 $7,250.00 $6,380.00
Fuel ...8248
Date Description Amount
03/30/26 Oleksandr Moskaliuk [Drv] Lambsburg, VA/ Gallons- 170.42/ Disc- $99.76 -$886.80
03/30/26 Oleksandr Moskaliuk [Drv] Lambsburg, VA/ Gallons- 5.86 -$28.04
04/01/26 Oleksandr Moskaliuk [Drv] North Lima, OH/ Gallons- 153.82/ Disc- $150.34 -$694.00
04/01/26 Oleksandr Moskaliuk [Drv] North Lima, OH/ Gallons- 10.56 -$49.52
Subtotal: -$1,658.36
Tolls ...4799
Date Description Amount
04/04/26 Oleksandr Moskaliuk [Drv] Exit date: 04/03/26 / Exit plaza: T16 -$2.28
04/04/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: T291 - T291 E -$48.20
04/04/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: CAR - Carlisle - 226 -$116.76
04/04/26 Oleksandr Moskaliuk [Drv] Exit date: 04/03/26 / Exit plaza: T06 -$5.20
ezLoads TMS and Driver App
ezloads.net
"""

PAGE_2 = """04/04/26 Oleksandr Moskaliuk [Drv] Exit date: 04/03/26 / Exit plaza: T26 -$5.16
04/04/26 Oleksandr Moskaliuk [Drv] Exit date: 04/03/26 / Exit plaza: T18 -$1.88
04/04/26 Oleksandr Moskaliuk [Drv] Exit date: 04/02/26 / Exit plaza: FMT -$24.00
04/03/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: T341 - T341 E -$5.72
04/03/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: T336 - T336 E -$6.28
04/03/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: 211 -$42.50
04/03/26 Oleksandr Moskaliuk [Drv] Exit date: 03/31/26 / Exit plaza: EPT -$31.74
04/03/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: T322 - T322 E -$6.28
04/03/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: GTY - Gateway Barrier - 2 -$31.57
04/03/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: T353 - T353 E -$6.00
04/03/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: T313 - T313 E -$6.88
04/03/26 Oleksandr Moskaliuk [Drv] Exit date: 04/01/26 / Exit plaza: T331 - T331 E -$6.60
04/02/26 Oleksandr Moskaliuk [Drv] Exit date: 03/31/26 / Exit plaza: 4 -$7.25
04/01/26 Oleksandr Moskaliuk [Drv] Exit date: 03/30/26 / Exit plaza: C -$13.00
04/01/26 Oleksandr Moskaliuk [Drv] Exit date: 03/30/26 / Exit plaza: AN -$13.00
04/01/26 Oleksandr Moskaliuk [Drv] Exit date: 03/30/26 / Exit plaza: B -$13.00
Subtotal -$393.30
Deductions
# Date Description Amount
- 03/21/26 Other: Form 2290 Unit 603 -$194.28
- 03/23/26 Other: Title Fee -$16.26
- 03/23/26 Truck Registration: Unit 506 -$709.91
- 03/30/26 Cargo and Liability Insurance Unit 603 -$300.00
3533 03/30/26 Oleksandr Moskaliuk [Drv] #3533 Huntersville, NC - Hopkins, MI -$750.00
3551 03/31/26 Oleksandr Moskaliuk [Drv] #3551 Elkhart, IN - Fairless Hills, PA -$885.00
- 04/01/26 Logbook and Pre-Pass Subscription - Unit 603 -$147.50
3564 04/02/26 Oleksandr Moskaliuk [Drv] #3564 Sparrows Point, MD - Sanford, NC -$540.00
- 04/06/26 Cargo and Liability Insurance Unit 603 -$300.00
Subtotal: -$3,842.95
Settlement total: $485.39
ezLoads TMS and Driver App
ezloads.net
"""

PAGE_3 = """Balance due: $485.39
ezLoads TMS and Driver App
ezloads.net
"""


class FakePage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class FakePDF:
    def __init__(self, pages):
        self.pages = [FakePage(page) for page in pages]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def patch_77_cargo_pdf(monkeypatch):
    def fake_open(*_args, **_kwargs):
        return FakePDF([PAGE_1, PAGE_2, PAGE_3])

    monkeypatch.setattr(pdf_parser_module.pdfplumber, "open", fake_open)
    monkeypatch.setattr(settlement_extractor_module.pdfplumber, "open", fake_open)


def test_parse_77_cargo_pdf_extracts_expected_fields(patch_77_cargo_pdf):
    parsed = parse_amazon_relay_pdf("dummy.pdf")

    assert parsed["settlement_type"] == "77 Cargo LLC"
    assert parsed["settlement_date"] == date(2026, 4, 6)
    assert parsed["week_start"] == date(2026, 3, 30)
    assert parsed["week_end"] == date(2026, 4, 6)
    assert parsed["miles_driven"] == pytest.approx(2023.0)
    assert parsed["blocks_delivered"] == 3
    assert parsed["block_ids"] == [
        {"block_id": "3533", "delivery_date": "2026-03-31"},
        {"block_id": "3551", "delivery_date": "2026-04-01"},
        {"block_id": "3564", "delivery_date": "2026-04-03"},
    ]
    assert parsed["gross_revenue"] == pytest.approx(6380.00)
    assert parsed["expenses"] == pytest.approx(5894.61)
    assert parsed["net_profit"] == pytest.approx(485.39)
    assert parsed["driver_name"] == "Oleksandr Moskaliuk"
    assert parsed["license_plate"] is None
    assert parsed["expense_categories"] == {
        "fuel": 1658.36,
        "tolls": 393.30,
        "insurance": 600.00,
        "prepass": 147.50,
        "driver_pay": 2175.00,
        "deduct": 920.45,
    }
    assert parsed["deduction_details"] == [
        {"description": "Form 2290", "amount": 194.28},
        {"description": "Title Fee", "amount": 16.26},
        {"description": "Truck Registration", "amount": 709.91},
    ]


def test_77_cargo_detection_flows_through_extractor(patch_77_cargo_pdf):
    extractor = SettlementExtractor()

    assert extractor._detect_settlement_type("dummy.pdf") == "77 Cargo LLC"

    extracted = extractor.extract_from_pdf("dummy.pdf")
    assert extracted["settlement_type"] == "77 Cargo LLC"
    assert len(extracted["settlements"]) == 1
    settlement = extracted["settlements"][0]
    assert settlement["metadata"]["driver_name"] == "Oleksandr Moskaliuk"
    assert settlement["expenses"]["categories"]["tolls"] == pytest.approx(393.30)
    assert settlement["revenue"]["gross_revenue"] == pytest.approx(6380.00)
    assert settlement["revenue"]["net_profit"] == pytest.approx(485.39)


def test_upload_settlement_accepts_manual_truck_selection_for_77_cargo(
    client: TestClient,
    tenant_headers,
    patch_77_cargo_pdf,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(settlements_router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settlements_router, "upload_pdf", lambda *_args, **_kwargs: None)

    truck_response = client.post(
        "/api/trucks",
        json={"name": "Volvo 417", "license_plate": "VV9952"},
        headers=tenant_headers,
    )
    assert truck_response.status_code == 200
    truck_id = truck_response.json()["id"]

    response = client.post(
        "/api/settlements/upload",
        data={"truck_id": str(truck_id)},
        files={"file": ("77-cargo.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=tenant_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["truck_id"] == truck_id
    assert data["license_plate"] is None
    assert data["settlement_type"] == "77 Cargo LLC"
    assert float(data["gross_revenue"]) == pytest.approx(6380.00)
    assert float(data["expenses"]) == pytest.approx(5894.61)
    assert float(data["net_profit"]) == pytest.approx(485.39)
    assert float(data["expense_categories"]["tolls"]) == pytest.approx(393.30)
    assert data["deduction_details"] == [
        {"description": "Form 2290", "amount": 194.28},
        {"description": "Title Fee", "amount": 16.26},
        {"description": "Truck Registration", "amount": 709.91},
    ]


def test_dashboard_reports_tolls_as_first_class_expense_category(
    client: TestClient,
    db,
    tenant_headers,
):
    truck = Truck(
        tenant_id=1,
        name="Volvo 417",
        license_plate="VV9952",
        vehicle_type="truck",
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    db.add(
        Settlement(
            truck_id=truck.id,
            settlement_date=date(2026, 4, 6),
            week_start=date(2026, 3, 30),
            week_end=date(2026, 4, 6),
            gross_revenue=Decimal("6380.00"),
            expenses=Decimal("5894.61"),
            net_profit=Decimal("485.39"),
            expense_categories={
                "fuel": 1658.36,
                "tolls": 393.30,
                "insurance": 600.00,
                "prepass": 147.50,
                "driver_pay": 2175.00,
                "deduct": 920.45,
            },
            settlement_type="77 Cargo LLC",
        )
    )
    db.commit()

    response = client.get("/api/analytics/dashboard", headers=tenant_headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["expense_categories"]["tolls"] == pytest.approx(393.30)
    assert data["trucks"]["expense_categories"]["tolls"] == pytest.approx(393.30)


def test_create_settlement_journal_entry_maps_tolls_to_dedicated_account(db, monkeypatch):
    monkeypatch.setattr(
        accounting_service_module,
        "validate_journal_entry_lines",
        lambda *args, **kwargs: (True, ""),
    )

    tenant = db.query(Tenant).filter(Tenant.id == 1).first()
    tenant.name = "LS Logistics"
    db.commit()

    truck = Truck(
        tenant_id=tenant.id,
        name="Volvo 417",
        license_plate="VV9952",
        vehicle_type="truck",
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    settlement = Settlement(
        truck_id=truck.id,
        settlement_date=date(2026, 4, 6),
        week_start=date(2026, 3, 30),
        week_end=date(2026, 4, 6),
        gross_revenue=Decimal("6380.00"),
        expenses=Decimal("5894.61"),
        net_profit=Decimal("485.39"),
        expense_categories={
            "fuel": 1658.36,
            "tolls": 393.30,
            "insurance": 600.00,
        },
        settlement_type="77 Cargo LLC",
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)

    entry = create_settlement_journal_entry(db, settlement)

    assert entry is not None

    tolls_account = db.query(ChartOfAccount).filter(
        ChartOfAccount.tenant_id == tenant.id,
        ChartOfAccount.truck_id == truck.id,
        ChartOfAccount.code == "6013",
    ).first()
    assert tolls_account is not None
    assert tolls_account.name == "Tolls Expense"

    tolls_debit = db.query(JournalEntryLine).filter(
        JournalEntryLine.journal_entry_id == entry.id,
        JournalEntryLine.account_id == tolls_account.id,
        JournalEntryLine.description == "tolls expense",
    ).first()
    assert tolls_debit is not None
    assert float(tolls_debit.debit) == pytest.approx(393.30)
    assert float(tolls_debit.credit) == pytest.approx(0.0)
