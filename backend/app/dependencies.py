"""
Dependencies for FastAPI routes
"""
from fastapi import Header, HTTPException, status
from typing import Optional

def get_tenant_id(x_tenant_id: Optional[int] = Header(None, alias="X-Tenant-ID")) -> int:
    """
    Extract tenant ID from request header.
    Required for all requests to ensure proper tenant isolation.
    """
    if x_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required"
        )
    return x_tenant_id

