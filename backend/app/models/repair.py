"""
Repair expense model
"""
from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Repair(Base):
    __tablename__ = "repairs"

    id = Column(Integer, primary_key=True, index=True)
    truck_id = Column(Integer, ForeignKey("trucks.id"), nullable=False)
    repair_date = Column(Date, nullable=False)
    description = Column(Text)
    category = Column(String(50))  # engine, tires, maintenance, etc
    cost = Column(Numeric(10, 2), nullable=False)
    receipt_path = Column(String(255))
    invoice_number = Column(String(50), nullable=True)  # Invoice number from PDF
    image_paths = Column(JSON, nullable=True)  # List of image file paths
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    truck = relationship("Truck", back_populates="repairs")

