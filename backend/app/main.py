"""
FastAPI application for Logistics Management System
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.database import engine, Base
from app.routers import trucks, settlements, repairs, analytics, extractor

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Elis Logistics Manager",
    description="Management system for Amazon Relay truck operations",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
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

@app.get("/")
async def root():
    return {
        "message": "Elis Logistics Manager API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

