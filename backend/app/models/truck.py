"""
Truck model - Also supports trailers
"""
from sqlalchemy import Column, Integer, String, DateTime, Date, JSON, Numeric, UniqueConstraint, CheckConstraint, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Truck(Base):
    __tablename__ = "trucks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    vehicle_type = Column(String(20), nullable=False, default='truck')  # 'truck', 'trailer', or 'suv'
    license_plate = Column(String(20), nullable=True)  # For trucks
    tag_number = Column(String(20), nullable=True)  # For trailers (trailer tag number)
    vin = Column(String(17), nullable=True)  # Vehicle Identification Number
    default_trailer_id = Column(Integer, nullable=True)  # Default attached trailer used for settlement income splits
    default_trailer_income_split_amount = Column(Numeric(10, 2), nullable=True)  # Default weekly trailer income allocation
    default_repair_reserve_amount = Column(Numeric(10, 2), nullable=True)  # Default weekly repair/PM reserve allocation
    license_plate_history = Column(JSON, nullable=True)  # List of historical license plates
    cash_investment = Column(Numeric(10, 2), nullable=True)  # Cash invested in vehicle
    loan_amount = Column(Numeric(10, 2), nullable=True)  # Loan amount (trucks only, null for trailers)
    current_loan_balance = Column(Numeric(10, 2), nullable=True)  # Current loan balance (reduces as principal is paid)
    loan_paid_off_date = Column(Date, nullable=True)  # Legacy optional payoff date column; replay-based ROI ignores it
    interest_rate = Column(Numeric(5, 4), nullable=True, default=0.07)  # Annual interest rate (default 7% = 0.07)
    total_cost = Column(Numeric(10, 2), nullable=True)  # Total purchase cost (cash + loan for trucks, cash only for trailers)
    registration_fee = Column(Numeric(10, 2), nullable=True)  # Registration fee for vehicle
    additional_expenses = Column(JSON, nullable=True)  # Additional expenses/fees: [{"description": "...", "amount": 100.00}, ...]
    # Depreciation fields
    purchase_date = Column(Date, nullable=True)  # Date vehicle was purchased/placed in service (for depreciation)
    depreciation_method = Column(String(20), nullable=True, default='MACRS_5')  # 'MACRS_5', 'straight_line', 'none'
    cost_basis = Column(Numeric(10, 2), nullable=True)  # Depreciable cost basis (total_cost minus Section 179/bonus depreciation)
    section_179_deduction = Column(Numeric(10, 2), nullable=True, default=0)  # Section 179 deduction taken in first year
    bonus_depreciation = Column(Numeric(10, 2), nullable=True, default=0)  # Bonus depreciation percentage (e.g., 100 for 100%)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="trucks")
    settlements = relationship("Settlement", back_populates="truck")
    repairs = relationship("Repair", back_populates="truck")
    vehicle_documents = relationship("VehicleDocument", back_populates="truck", cascade="all, delete-orphan")

    # Unique constraint: name must be unique per tenant and vehicle type
    # Check constraint: vehicle_type must be 'truck' or 'trailer'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', 'vehicle_type', name='unique_name_per_tenant_vehicle_type'),
        CheckConstraint("vehicle_type IN ('truck', 'trailer', 'suv')", name='check_vehicle_type'),
        CheckConstraint("depreciation_method IN ('MACRS_5', 'straight_line', 'none') OR depreciation_method IS NULL", name='check_depreciation_method'),
    )
