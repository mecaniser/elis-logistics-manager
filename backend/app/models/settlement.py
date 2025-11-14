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
    gross_revenue = Column(Numeric(10, 2))
    expenses = Column(Numeric(10, 2))  # Fuel, tolls, etc from Amazon
    expense_categories = Column(JSON)  # Categorized expenses: {fuel, dispatch_fee, insurance, etc}
    net_profit = Column(Numeric(10, 2))
    pdf_file_path = Column(String(255))
    license_plate = Column(String(20), nullable=True)  # License plate from this settlement
    settlement_type = Column(String(50), nullable=True)  # Type of settlement PDF
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    truck = relationship("Truck", back_populates="settlements")
    driver = relationship("Driver", back_populates="settlements")

    # Unique constraint: one settlement per truck per date
    __table_args__ = (
        UniqueConstraint('truck_id', 'settlement_date', name='unique_truck_settlement'),
    )

