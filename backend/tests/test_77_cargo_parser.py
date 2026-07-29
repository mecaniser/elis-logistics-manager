from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models.chart_of_accounts import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from app.models.repair import Repair
from app.models.settlement import Settlement
from app.models.tenant import Tenant
from app.models.truck import Truck
from app.routers import settlements as settlements_router
from app.services import accounting_service as accounting_service_module
from app.services import diesel_price_service as diesel_price_service_module
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

PAGE_2280_1 = """77 Cargo LLC
1115 Ansley Park Dr
Fort Mill, SC 29707
Email: safety@77cargo.com
Phone: (704) 835-2433
Settlement #1857
Date: 04/14/26
Driver:
Truck:
Pay to: ELIS LOGISTICS LLC
1002 Yearden Ln
Monroe, NC 28110
Email: Elislogistics86@gmail.com
Phone: (704) 705-0486
Pay rate: 88%
Load# Pickup Delivery Description Empty Loaded % Rate Amount
Oleksandr Moskaliuk [Drv] #3585
3585 04/07/26 04/08/26 258 448 88% $3,200.00 $2,816.00
Castlewood, VA - Kokomo, IN
Oleksandr Moskaliuk [Drv] #3604
3604 04/08/26 04/09/26 LAFAYETTE, IN - GEORGETOWN, 44 812 88% $3,100.00 $2,728.00
SC
Oleksandr Moskaliuk [Drv] #3621
3621 04/09/26 04/10/26 49 691 88% $3,150.00 $2,772.00
Huger, SC - Cresson, PA
Oleksandr Moskaliuk [Drv] #3622
3622 04/10/26 04/11/26 125 350 88% $2,000.00 $1,760.00
Kingwood, WV - Kernersville, NC
Subtotal: 476 2301 $11,450.00 $10,076.00
Fuel ...8248
Date Description Amount
04/07/26 Oleksandr Moskaliuk [Drv] Lambsburg, VA/ Gallons- 7.74 -$37.05
04/07/26 Oleksandr Moskaliuk [Drv] Lambsburg, VA/ Gallons- 168.51/ Disc- $109.11 -$900.11
04/08/26 Oleksandr Moskaliuk [Drv] Newport, TN/ Gallons- 8.62 -$41.29
04/08/26 Oleksandr Moskaliuk [Drv] Newport, TN/ Gallons- 195.86/ Disc- $104.71 -$1,001.68
04/10/26 Oleksandr Moskaliuk [Drv] Staunton, VA/ Gallons- 150.22/ Disc- $201.11 -$737.60
04/10/26 Oleksandr Moskaliuk [Drv] Staunton, VA/ Gallons- 7 -$33.54
Subtotal: -$2,751.27
Tolls ...4799
Date Description Amount
ezLoads TMS and Driver App
ezloads.net
"""

PAGE_2280_2 = """04/12/26 Oleksandr Moskaliuk [Drv] Exit date: 04/10/26 / Exit plaza: NB -$3.06
04/12/26 Oleksandr Moskaliuk [Drv] Exit date: 04/10/26 / Exit plaza: AS -$13.00
04/12/26 Oleksandr Moskaliuk [Drv] Exit date: 04/10/26 / Exit plaza: BED - Bedford - 146 -$8.92
04/09/26 Oleksandr Moskaliuk [Drv] Exit date: 04/07/26 / Exit plaza: ECN -$13.33
04/09/26 Oleksandr Moskaliuk [Drv] Exit date: 04/08/26 / Exit plaza: ECS -$13.33
Subtotal -$51.64
Deductions
# Date Description Amount
3585 04/07/26 Oleksandr Moskaliuk [Drv] #3585 Castlewood, VA - Kokomo, IN -$960.00
3604 04/08/26 Oleksandr Moskaliuk [Drv] #3604 LAFAYETTE, IN - GEORGETOWN, SC -$930.00
3621 04/09/26 Oleksandr Moskaliuk [Drv] #3621 Huger, SC - Cresson, PA -$945.00
3622 04/10/26 Oleksandr Moskaliuk [Drv] #3622 Kingwood, WV - Kernersville, NC -$600.00
- 04/13/26 Cargo and Liability Insurance Unit 603 -$300.00
Subtotal: -$3,735.00
Settlement total: $3,538.09
Balance due: $3,538.09
ezLoads TMS and Driver App
ezloads.net
"""

PAGE_77_LAYOUT_VARIANT = """77 Cargo
Settlement #2138
Date: 05-02-2026
Pay rate: 88%
Load # Pickup Delivery Empty Loaded % Rate Amount
2138 04-27-26 04-28-26 10 100 88 $1,000 $880
Subtotal: 10 100 $1,000 $880
Fuel card ending 8248
Date Description Amount
04/27/26 Sample Driver [Drv] Fuel -$100.00
Subtotal -$100.00
Tolls
Subtotal: -$10.00
Deductions
Date Description Amount
2138 04/27/26 Sample Driver [Drv] #2138 Route -$300.00
- 05/02/26 Cargo and Liability Insurance Unit 603 -$50.00
Subtotal -$350.00
Settlement total: $420.00
"""

PAGE_277_INCOME = """OWNER OPERATOR INCOME SHEET
COMPANY NAME: Date Submitted: 5/16/2025
DRIVER NAME: ELIS LOGISTICS LLC / VW1503 #418 Date Period : 05/04-05/10/2025
CARD# TRUCK# VW1503
DATE P/L D/L LOAD STOPS LOAD MILES LOAD AMT DRIVER PAY DATE FUEL FUEL
05/03-05/05/2025 5G88-GSP1 GSP1 6 908.0 ($ 1,399.04) ($ 570.00) 5/4/2025 ($ 404.12) C. Vereen
05/05-05/06/2025 QBG8-GSP1 GSP1 8 776.0 ($ 1,329.24) ($ 570.00) 5/6/2025 ($ 327.91) card #102
05/06-05/08/2025 R7ZP-CLT5 CLT5 7 904.0 ($ 1,351.54) ($ 570.00) 5/6/2025 ($ 45.40)
05/08-05/09/2025 QRJ0-GSP1 GSP1 5 668.0 ($ 1,084.66) ($ 570.00) 5/7/2025 ($ 315.96)
5/8/2025 ($ 428.44)
5/8/2025 ($ 45.48)
SUMMARY GROSS 3256.0 ($ 5,164.48) ($ 2,280.00) ($ 1,567.31)
DISPATCH FEE 6% ($ 309.87) ($ 148.20)
FUEL ($ 1,567.31)
TOTAL
PAYMENT ($ 3,287.30)
IFTA ($ 50.00)
SAFETY ($ 20.00)
PREPASS ($ 70.00)
INSURANCE ($ 350.00)
DRIVER'S PAY ($ 2,428.20)
SERVICE ON THE TRUCK
TRUCK PARKING
TOTAL ($ 369.10)
PAID TO DRIVER ($ 369.10)
insurance #417 ($ (350.00)
($ 19.10)
"""

PAGE_277_PAYSTUB = """277 Logistics
PayeeE:LIS LOGISTICS LLC 277 VW9327
Plate#: VW9327 417
Email: Elislogistics86@gmail.com
Fuel Card #:
Pay Period: 10/25/2025
Generated on: 10/30/2025
Pay Period Block ID Driver Plate # Start of Load End of Load Week Ending Pay Amount Driver's pay Fuel amount Reimb Bonus Deduct
10/25/2025 B-WVNX2XWTZ Dominique Nobles VW9327 10/19/2025 10/20/2025 10/25/2025 $1,987.61 $570.00 $1,650.00 $0.00 $0.00 $70.00
B-KP8BG7QQQ Dominique Nobles VW9327 10/23/2025 10/25/2025 10/25/2025 $2,103.04 $570.00
B-VFQ33B2ZH Jorge Luis Montoya TaVbWar9e3s27 10/21/2025 10/23/2025 10/25/2025 $2,102.11 $600.00
Gross Pay $6,192.76
Dispatch Fee $495.42
Driver's Pay $1,740.00
Driver's Pay Fee $113.10
Fuel $1,650.00
IFTA $50.00
Safety $20.00
Prepass $70.00
Insurance $350.00
Reimbursment $0.00
Bonus $0.00
Deductions $70.00
Net Pay $1,634.24
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


@pytest.fixture
def patch_77_cargo_pdf_2280(monkeypatch):
    def fake_open(*_args, **_kwargs):
        return FakePDF([PAGE_2280_1, PAGE_2280_2])

    monkeypatch.setattr(pdf_parser_module.pdfplumber, "open", fake_open)
    monkeypatch.setattr(settlement_extractor_module.pdfplumber, "open", fake_open)


@pytest.fixture
def patch_277_income_pdf(monkeypatch):
    def fake_open(*_args, **_kwargs):
        return FakePDF([PAGE_277_INCOME])

    monkeypatch.setattr(pdf_parser_module.pdfplumber, "open", fake_open)
    monkeypatch.setattr(settlement_extractor_module.pdfplumber, "open", fake_open)


@pytest.fixture
def patch_277_paystub_pdf(monkeypatch):
    def fake_open(*_args, **_kwargs):
        return FakePDF([PAGE_277_PAYSTUB])

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
    assert parsed["overview_amounts"] == {
        "dispatch_fee": 870.00,
        "gross_before_dispatch": 7250.00,
        "pay_rate_percent": 88.0,
    }
    assert parsed["deduction_details"] == [
        {"description": "Form 2290", "amount": 194.28},
        {"description": "Title Fee", "amount": 16.26},
        {"description": "Truck Registration", "amount": 709.91},
    ]


def test_parse_77_cargo_pdf_handles_inline_route_text_in_load_rows(patch_77_cargo_pdf_2280):
    parsed = parse_amazon_relay_pdf("dummy.pdf")

    assert parsed["settlement_type"] == "77 Cargo LLC"
    assert parsed["settlement_date"] == date(2026, 4, 14)
    assert parsed["week_start"] == date(2026, 4, 7)
    assert parsed["week_end"] == date(2026, 4, 14)
    assert parsed["miles_driven"] == pytest.approx(2777.0)
    assert parsed["blocks_delivered"] == 4
    assert parsed["block_ids"] == [
        {"block_id": "3585", "delivery_date": "2026-04-08"},
        {"block_id": "3604", "delivery_date": "2026-04-09"},
        {"block_id": "3621", "delivery_date": "2026-04-10"},
        {"block_id": "3622", "delivery_date": "2026-04-11"},
    ]
    assert parsed["gross_revenue"] == pytest.approx(10076.00)
    assert parsed["expenses"] == pytest.approx(6537.91)
    assert parsed["net_profit"] == pytest.approx(3538.09)
    assert parsed["driver_name"] == "Oleksandr Moskaliuk"
    assert parsed["expense_categories"] == {
        "fuel": 2751.27,
        "tolls": 51.64,
        "insurance": 300.00,
        "driver_pay": 3435.00,
    }
    assert parsed["overview_amounts"] == {
        "dispatch_fee": 1374.00,
        "gross_before_dispatch": 11450.00,
        "pay_rate_percent": 88.0,
    }
    assert parsed["deduction_details"] is None


def test_parse_77_cargo_pdf_tolerates_header_and_date_layout_changes(monkeypatch):
    """A small exporter change must not send this family through the wrong parser."""
    monkeypatch.setattr(
        pdf_parser_module.pdfplumber,
        "open",
        lambda *_args, **_kwargs: FakePDF([PAGE_77_LAYOUT_VARIANT]),
    )

    parsed = parse_amazon_relay_pdf("driver_settlement_2138_ELIS_LOGISTICS_LLC.pdf")

    assert parsed["settlement_type"] == "77 Cargo LLC"
    assert parsed["settlement_date"] == date(2026, 5, 2)
    assert parsed["week_start"] == date(2026, 4, 27)
    assert parsed["miles_driven"] == pytest.approx(110.0)
    assert parsed["block_ids"] == [{"block_id": "2138", "delivery_date": "2026-04-28"}]
    assert parsed["gross_revenue"] == pytest.approx(880.0)
    assert parsed["expenses"] == pytest.approx(460.0)
    assert parsed["net_profit"] == pytest.approx(420.0)
    assert parsed["expense_categories"] == {
        "fuel": 100.0,
        "tolls": 10.0,
        "insurance": 50.0,
        "driver_pay": 300.0,
    }


def test_parse_77_cargo_pdf_rejoins_wrapped_deduction_rows(monkeypatch):
    # Settlement 2271 has this layout when text is extracted: the date and
    # amount of a long deduction are separated from its description.
    wrapped_page = PAGE_77_LAYOUT_VARIANT.replace(
        "Subtotal -$350.00\nSettlement total: $420.00",
        "Balance In (Remove Negative Balance): Removing Negative Balance from Unit 609 -\n"
        "- 05/03/26 -$99.00\n"
        "Subtotal -$449.00\n"
        "Settlement total: $321.00",
    )
    monkeypatch.setattr(
        pdf_parser_module.pdfplumber,
        "open",
        lambda *_args, **_kwargs: FakePDF([wrapped_page]),
    )

    parsed = parse_amazon_relay_pdf("driver_settlement_2271_ELIS_LOGISTICS_LLC.pdf")

    assert parsed["expenses"] == pytest.approx(460.0)
    assert parsed["net_profit"] == pytest.approx(420.0)
    assert parsed["cash_settlement_amount"] == pytest.approx(321.0)
    assert parsed["cash_adjustments"] == [{
        "type": "prior_balance_offset",
        "description": "Balance In (Remove Negative Balance): Removing Negative Balance from Unit 609",
        "amount": -99.0,
    }]


def test_parse_277_income_sheet_populates_overview_amounts(patch_277_income_pdf):
    parsed = parse_amazon_relay_pdf("dummy.pdf", "277 Logistics")

    assert parsed["settlement_date"] == date(2025, 5, 10)
    assert parsed["week_start"] == date(2025, 5, 4)
    assert parsed["week_end"] == date(2025, 5, 10)
    assert parsed["license_plate"] == "VW1503"
    assert parsed["gross_revenue"] == pytest.approx(5164.48)
    assert parsed["net_profit"] == pytest.approx(369.10)
    assert parsed["expense_categories"]["dispatch_fee"] == pytest.approx(309.87)
    assert parsed["overview_amounts"] == {
        "dispatch_fee": 309.87,
        "gross_before_dispatch": 5474.35,
    }


def test_parse_277_paystub_populates_overview_amounts(patch_277_paystub_pdf):
    parsed = parse_amazon_relay_pdf("dummy.pdf", "277 Logistics")

    assert parsed["settlement_date"] == date(2025, 10, 25)
    assert parsed["week_end"] == date(2025, 10, 25)
    assert parsed["license_plate"] == "VW9327"
    assert parsed["gross_revenue"] == pytest.approx(6192.76)
    assert parsed["net_profit"] == pytest.approx(1634.24)
    assert parsed["expense_categories"]["dispatch_fee"] == pytest.approx(495.42)
    assert parsed["overview_amounts"] == {
        "dispatch_fee": 495.42,
        "gross_before_dispatch": 6688.18,
    }


def test_upload_277_paystub_estimates_miles_from_fuel_spend(
    client: TestClient,
    tenant_headers,
    patch_277_paystub_pdf,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(settlements_router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settlements_router, "upload_pdf", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(diesel_price_service_module, "get_historical_diesel_price", lambda *_args, **_kwargs: 4.0)

    truck_response = client.post(
        "/api/trucks",
        json={
            "name": "Volvo 417",
            "vehicle_type": "truck",
            "license_plate": "VW9327",
            "estimated_mpg": 6.5,
            "fuel_card_discount_per_gallon": 0.25,
        },
        headers=tenant_headers,
    )
    assert truck_response.status_code == 200

    response = client.post(
        "/api/settlements/upload",
        data={"settlement_type": "277 Logistics"},
        files={"file": ("277-paystub.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=tenant_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["license_plate"] == "VW9327"
    assert float(data["miles_driven"]) == pytest.approx(2860.0)
    assert float(data["overview_amounts"]["gross_before_dispatch"]) == pytest.approx(6688.18)
    assert float(data["overview_amounts"]["estimated_miles_driven"]) == pytest.approx(2860.0)
    assert float(data["overview_amounts"]["diesel_price_per_gallon"]) == pytest.approx(4.0)
    assert float(data["overview_amounts"]["fuel_card_discount_per_gallon"]) == pytest.approx(0.25)
    assert float(data["overview_amounts"]["effective_fuel_price_per_gallon"]) == pytest.approx(3.75)
    assert float(data["overview_amounts"]["estimated_gallons"]) == pytest.approx(440.0)


def test_77_cargo_detection_flows_through_extractor(patch_77_cargo_pdf):
    extractor = SettlementExtractor()

    assert extractor._detect_settlement_type("dummy.pdf") == "77 Cargo LLC"

    extracted = extractor.extract_from_pdf("dummy.pdf")
    assert extracted["settlement_type"] == "77 Cargo LLC"
    assert len(extracted["settlements"]) == 1
    settlement = extracted["settlements"][0]
    assert settlement["metadata"]["driver_name"] == "Oleksandr Moskaliuk"
    assert settlement["overview_amounts"]["dispatch_fee"] == pytest.approx(870.00)
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
    assert float(data["overview_amounts"]["dispatch_fee"]) == pytest.approx(870.00)
    assert float(data["expense_categories"]["tolls"]) == pytest.approx(393.30)
    assert data["deduction_details"] == [
        {"description": "Form 2290", "amount": 194.28},
        {"description": "Title Fee", "amount": 16.26},
        {"description": "Truck Registration", "amount": 709.91},
    ]


def test_upload_settlement_allows_zero_net_without_journal_entry(
    client: TestClient,
    db,
    tenant_headers,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(settlements_router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settlements_router, "upload_pdf", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        settlements_router,
        "parse_amazon_relay_pdf",
        lambda *_args, **_kwargs: {
            "settlement_date": date(2026, 5, 3),
            "week_start": date(2026, 4, 27),
            "week_end": date(2026, 5, 3),
            "gross_revenue": 100.0,
            "expenses": 100.0,
            "net_profit": 0.0,
            "expense_categories": {},
            "license_plate": None,
            "block_ids": [],
        },
    )

    truck = Truck(
        tenant_id=1,
        name="Zero Net Truck",
        license_plate="ZERO-01",
        vehicle_type="truck",
    )
    db.add(truck)
    db.commit()
    db.refresh(truck)

    response = client.post(
        "/api/settlements/upload",
        data={"truck_id": str(truck.id)},
        files={"file": ("zero-net.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=tenant_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["truck_id"] == truck.id
    assert float(data["net_profit"]) == pytest.approx(0.0)

    journal_entries = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.reference_type == "settlement",
            JournalEntry.reference_id == data["id"],
        )
        .all()
    )
    assert journal_entries == []


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
    assert data["expense_categories"]["deduct"] == pytest.approx(920.45)
    assert data["trucks"]["expense_categories"]["deduct"] == pytest.approx(920.45)


def test_analytics_exposes_operational_per_mile_inputs_for_77_cargo(
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
            miles_driven=Decimal("2023.00"),
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
            overview_amounts={
                "dispatch_fee": 870.00,
                "gross_before_dispatch": 7250.00,
                "pay_rate_percent": 88.0,
            },
            settlement_type="77 Cargo LLC",
        )
    )
    db.add(
        Repair(
            truck_id=truck.id,
            repair_date=date(2026, 4, 3),
            description="Wheel seal",
            cost=Decimal("500.00"),
        )
    )
    db.commit()

    dashboard_response = client.get("/api/analytics/dashboard", headers=tenant_headers)
    assert dashboard_response.status_code == 200, dashboard_response.text
    dashboard = dashboard_response.json()

    combined_metrics = dashboard["operational_metrics"]
    truck_metrics = dashboard["trucks"]["operational_metrics"]
    for metrics in (combined_metrics, truck_metrics):
        assert metrics["miles_driven"] == pytest.approx(2023.0)
        assert metrics["post_dispatch_revenue"] == pytest.approx(6380.0)
        assert metrics["settlement_expenses"] == pytest.approx(5894.61)
        assert metrics["repair_costs"] == pytest.approx(500.0)
        assert metrics["raw_gross_revenue"] == pytest.approx(7250.0)
        assert metrics["raw_gross_miles_driven"] == pytest.approx(2023.0)
        assert metrics["post_dispatch_revenue_per_mile"] == pytest.approx(3.15)
        assert metrics["raw_gross_revenue_per_mile"] == pytest.approx(3.58)
        assert metrics["settlement_cost_per_mile"] == pytest.approx(2.91)
        assert metrics["all_in_cost_per_mile"] == pytest.approx(3.16)

    time_series_response = client.get("/api/analytics/time-series", headers=tenant_headers)
    assert time_series_response.status_code == 200, time_series_response.text
    time_series = time_series_response.json()

    assert len(time_series["by_week"]) == 1
    weekly = time_series["by_week"][0]
    assert weekly["week_key"] == "2026-04-06"
    assert weekly["gross_revenue"] == pytest.approx(6380.0)
    assert weekly["raw_gross_revenue"] == pytest.approx(7250.0)
    assert weekly["raw_gross_miles_driven"] == pytest.approx(2023.0)
    assert weekly["miles_driven"] == pytest.approx(2023.0)
    assert weekly["expenses"] == pytest.approx(5894.61)
    assert weekly["deduct"] == pytest.approx(920.45)

    assert len(time_series["by_month"]) == 1
    monthly = time_series["by_month"][0]
    assert monthly["month_key"] == "2026-04"
    assert monthly["gross_revenue"] == pytest.approx(6380.0)
    assert monthly["raw_gross_revenue"] == pytest.approx(7250.0)
    assert monthly["raw_gross_miles_driven"] == pytest.approx(2023.0)
    assert monthly["miles_driven"] == pytest.approx(2023.0)
    assert monthly["expenses"] == pytest.approx(5894.61)
    assert monthly["deduct"] == pytest.approx(920.45)

    assert len(time_series["by_year"]) == 1
    yearly = time_series["by_year"][0]
    assert yearly["year_key"] == "2026"
    assert yearly["gross_revenue"] == pytest.approx(6380.0)
    assert yearly["raw_gross_revenue"] == pytest.approx(7250.0)
    assert yearly["raw_gross_miles_driven"] == pytest.approx(2023.0)
    assert yearly["miles_driven"] == pytest.approx(2023.0)
    assert yearly["expenses"] == pytest.approx(5894.61)
    assert yearly["deduct"] == pytest.approx(920.45)


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
