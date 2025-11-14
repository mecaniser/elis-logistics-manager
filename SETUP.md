# Setup Guide

## Quick Start

### Option 1: Automated Setup (Recommended)

Run the setup script:
```bash
./start.sh
```

This will:
- Create Python virtual environment
- Install backend dependencies
- Install frontend dependencies

### Option 2: Manual Setup

#### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Note:** Database tables are auto-created on first run. No manual migration needed.

#### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install
```

## Running the Application

You need **two terminal windows**:

### Terminal 1 - Backend

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn app.main:app --reload
```

Backend will run on: **http://localhost:8000**  
API docs: **http://localhost:8000/docs**

### Terminal 2 - Frontend

```bash
cd frontend
npm run dev
```

Frontend will run on: **http://localhost:3000**

## Testing

### Test Backend API

```bash
# Health check
curl http://localhost:8000/api/health

# Create a truck
curl -X POST "http://localhost:8000/api/trucks" \
  -H "Content-Type: application/json" \
  -d '{"name": "Truck 1", "license_plate": "ABC-123"}'

# Get all trucks
curl http://localhost:8000/api/trucks
```

### Test PDF Upload

Use the frontend at http://localhost:3000/settlements to upload a PDF, or use the API:

```bash
curl -X POST "http://localhost:8000/api/settlements/upload?truck_id=1" \
  -F "file=@path/to/your/settlement.pdf"
```

## Project Status

✅ Backend API - Complete  
✅ PDF Parser - Customized for Amazon Relay format  
✅ Frontend - Complete React app  
✅ Tests - Backend tests available

## Railway Deployment

1. Push code to GitHub
2. Create Railway account and project
3. Connect GitHub repository
4. Add PostgreSQL service
5. Set environment variables:
   - `FRONTEND_URL` - Your frontend URL
   - `ENVIRONMENT=production`
6. Deploy!

