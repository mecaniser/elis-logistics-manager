"""
FastAPI application for Logistics Management System
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path

from app.database import engine, Base
from app.routers import trucks, settlements, repairs, analytics, extractor

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Elis Logistics Manager",
    description="Management system for Amazon Relay truck operations",
    version="1.0.0"
)

# Get frontend URL from environment or use default
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(trucks.router, prefix="/api/trucks", tags=["trucks"])
app.include_router(settlements.router, prefix="/api/settlements", tags=["settlements"])
app.include_router(repairs.router, prefix="/api/repairs", tags=["repairs"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(extractor.router, prefix="/api/extractor", tags=["extractor"])

# Serve uploaded files
# Determine uploads directory - backend runs from backend/ directory
current_file_dir = os.path.dirname(os.path.abspath(__file__))  # backend/app/
backend_dir = os.path.dirname(current_file_dir)  # backend/
uploads_dir = os.path.join(backend_dir, "uploads")  # backend/uploads

# Fallback: try relative path if absolute doesn't work
if not os.path.exists(uploads_dir):
    uploads_dir = os.path.join(os.path.dirname(backend_dir), "backend", "uploads")

if os.path.exists(uploads_dir) and os.path.isdir(uploads_dir):
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
    print(f"✓ Serving uploads from: {uploads_dir}")
else:
    print(f"⚠ Warning: uploads directory not found at: {uploads_dir}")
    print(f"  Current file dir: {current_file_dir}")
    print(f"  Backend dir: {backend_dir}")
    print(f"  Attempted uploads path: {uploads_dir}")

# Serve frontend static files (for production)
# This will be added after all routes are registered
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

@app.get("/api")
async def api_info():
    return {
        "message": "Elis Logistics Manager API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

# Serve frontend static files (for production) - must be last
if frontend_dist.exists():
    # Serve static assets (JS, CSS, images, etc.)
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    
    # Serve index.html for all non-API routes (SPA routing)
    # This catch-all route must be registered last, after all API routes
    # Note: StaticFiles mounts (like /uploads, /assets) are handled before this route
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Don't serve frontend for API routes or other backend routes
        # Note: /uploads and /assets are handled by StaticFiles mounts above, so they won't reach here
        if (full_path.startswith("api") or 
            full_path.startswith("docs") or 
            full_path.startswith("openapi.json")):
            return {"detail": "Not Found"}
        
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"detail": "Frontend not built"}
    
    print(f"✓ Serving frontend from: {frontend_dist}")
else:
    print(f"⚠ Frontend dist directory not found at: {frontend_dist}")
    print(f"  Frontend will not be served. Build frontend with: cd frontend && npm run build")

