"""
FastAPI application for Logistics Management System
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.database import engine, Base
from app.routers import trucks, settlements, repairs, analytics

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

# Serve uploaded files
if os.path.exists("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

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

