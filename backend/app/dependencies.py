"""
Dependencies for FastAPI routes
"""
from fastapi import Header, HTTPException, status
from typing import Optional

def get_tenant_id(x_tenant_id: Optional[int] = Header(None, alias="X-Tenant-ID")) -> int:
    """
    Extract tenant ID from request header.
    For now, defaults to tenant_id=1 if not provided (backward compatibility).
    In production, this should be extracted from authentication token.
    """
    if x_tenant_id is None:
        # Default to tenant 1 for backward compatibility
        # TODO: Remove this default once all clients send tenant ID
        return 1
    return x_tenant_id

