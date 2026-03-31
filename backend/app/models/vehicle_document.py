"""
Vehicle document model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class VehicleDocument(Base):
    __tablename__ = "vehicle_documents"

    id = Column(Integer, primary_key=True, index=True)
    truck_id = Column(Integer, ForeignKey("trucks.id"), nullable=False, index=True)
    document_type = Column(String(50), nullable=False, default="other")
    title = Column(String(255), nullable=True)
    notes = Column(String(1000), nullable=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    truck = relationship("Truck", back_populates="vehicle_documents")

    __table_args__ = (
        CheckConstraint(
            "document_type IN ('title', 'inspection', 'registration', 'insurance', 'permit', 'other')",
            name="check_vehicle_document_type",
        ),
    )
