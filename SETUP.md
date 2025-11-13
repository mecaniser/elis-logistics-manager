# Setup Guide

## Quick Start

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Initialize database (creates tables)
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Run server
uvicorn app.main:app --reload
```

Backend will run on: http://localhost:8000
API docs: http://localhost:8000/docs

### 2. Test the API

```bash
# Create a truck
curl -X POST "http://localhost:8000/api/trucks" \
  -H "Content-Type: application/json" \
  -d '{"name": "Truck 1", "license_plate": "ABC-123"}'

# Get all trucks
curl http://localhost:8000/api/trucks
```

### 3. Next Steps

1. **Customize PDF Parser:** Update `backend/app/utils/pdf_parser.py` based on your Amazon Relay PDF format
2. **Create Frontend:** Set up React app (see Frontend Setup below)
3. **Deploy to Railway:** Follow Railway deployment guide

## Frontend Setup (Coming Soon)

React frontend will be created next.

## Railway Deployment

1. Push code to GitHub
2. Create Railway account and project
3. Connect GitHub repository
4. Add PostgreSQL service
5. Set environment variables:
   - `FRONTEND_URL` - Your frontend URL
   - `ENVIRONMENT=production`
6. Deploy!

