"""
Truck model
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Truck(Base):
    __tablename__ = "trucks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    license_plate = Column(String(20))
    vin = Column(String(17), nullable=True)  # Vehicle Identification Number
    license_plate_history = Column(JSON, nullable=True)  # List of historical license plates
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    settlements = relationship("Settlement", back_populates="truck")
    repairs = relationship("Repair", back_populates="truck")

