"""
Vehicle document schemas
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


VehicleDocumentType = Literal["title", "inspection", "registration", "insurance", "permit", "other"]


class VehicleDocumentResponse(BaseModel):
    id: int
    truck_id: int
    document_type: VehicleDocumentType
    title: Optional[str] = None
    notes: Optional[str] = None
    original_filename: str
    file_path: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True
