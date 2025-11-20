"""
Truck model - Also supports trailers
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Truck(Base):
    __tablename__ = "trucks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    vehicle_type = Column(String(20), nullable=False, default='truck')  # 'truck' or 'trailer'
    license_plate = Column(String(20), nullable=True)  # For trucks
    tag_number = Column(String(20), nullable=True)  # For trailers (trailer tag number)
    vin = Column(String(17), nullable=True)  # Vehicle Identification Number
    license_plate_history = Column(JSON, nullable=True)  # List of historical license plates
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    settlements = relationship("Settlement", back_populates="truck")
    repairs = relationship("Repair", back_populates="truck")

    # Unique constraint: name must be unique per vehicle type
    # Check constraint: vehicle_type must be 'truck' or 'trailer'
    __table_args__ = (
        UniqueConstraint('name', 'vehicle_type', name='unique_name_per_vehicle_type'),
        CheckConstraint("vehicle_type IN ('truck', 'trailer')", name='check_vehicle_type'),
    )

