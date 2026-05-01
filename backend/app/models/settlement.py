"""
Settlement model - Weekly Amazon Relay settlements
"""
from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey, DateTime, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, index=True)
    truck_id = Column(Integer, ForeignKey("trucks.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    settlement_date = Column(Date, nullable=False)
    week_start = Column(Date)
    week_end = Column(Date)
    miles_driven = Column(Numeric(10, 2))
    blocks_delivered = Column(Integer)
    block_ids = Column(JSON, nullable=True)  # Array of block IDs delivered in this settlement
    gross_revenue = Column(Numeric(10, 2))
    expenses = Column(Numeric(10, 2))  # Fuel, tolls, etc from Amazon
    expense_categories = Column(JSON)  # Categorized expenses: {fuel, dispatch_fee, insurance, etc}
    overview_amounts = Column(JSON, nullable=True)  # Display-only derived amounts: {dispatch_fee, gross_before_dispatch, pay_rate_percent}
    custom_expense_descriptions = Column(JSON, nullable=True)  # Descriptions for custom expenses: {custom_1: "handles replaced", custom_2: "truck parking"}
    custom_expense_validation = Column(JSON, nullable=True)  # Validation status for custom expenses: {deduct: true, decals: false, custom: true}
    reimbursement_details = Column(JSON, nullable=True)  # Reimbursement details: [{"description": "...", "amount": 100.00}]
    deduction_details = Column(JSON, nullable=True)  # Deduction details: [{"description": "...", "amount": 50.00}]
    net_profit = Column(Numeric(10, 2))
    pdf_file_path = Column(String(255))
    license_plate = Column(String(20), nullable=True)  # License plate from this settlement
    settlement_type = Column(String(50), nullable=True)  # Type of settlement PDF
    duplicate_block_ids_warning = Column(JSON, nullable=True)  # Warning about duplicate block IDs: {"has_duplicates": true, "duplicate_block_ids": ["B-123"], "conflicting_settlements": [...]}
    trailer_income_split_trailer_id = Column(Integer, nullable=True)  # Trailer receiving a revenue allocation from this truck settlement
    trailer_income_split_amount = Column(Numeric(10, 2), nullable=True)  # Revenue allocated from the truck settlement to the trailer
    repair_reserve_amount = Column(Numeric(10, 2), nullable=True)  # Weekly repair/PM reserve taken out before carryover profit
    source_settlement_id = Column(Integer, nullable=True)  # Source truck settlement when this is a derived trailer-allocation settlement
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    truck = relationship("Truck", back_populates="settlements")
    driver = relationship("Driver", back_populates="settlements")

    # Unique constraint: one settlement per truck per date
    __table_args__ = (
        UniqueConstraint('truck_id', 'settlement_date', name='unique_truck_settlement'),
    )
