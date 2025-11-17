# Elis Logistics Manager

Management system for Amazon Relay truck operations. Track settlements, expenses, repairs, and analyze profitability per truck.

## Tech Stack

- **Backend:** FastAPI (Python)
- **Frontend:** React + TypeScript
- **Database:** PostgreSQL (Railway) / SQLite (local dev)
- **Deployment:** Railway

## Project Structure

```
elis-logistics-app/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── database.py          # Database configuration
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API routes
│   │   └── utils/               # Utilities (PDF parser, etc.)
│   ├── uploads/                  # PDF uploads directory
│   └── requirements.txt
├── frontend/                     # React app (to be created)
└── railway.json                  # Railway configuration
```

## Setup

### Backend Setup

1. **Create virtual environment:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Run migrations (creates database tables):**
```bash
cd backend
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

5. **Run development server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at: http://localhost:8000
API docs at: http://localhost:8000/docs

### Frontend Setup

(To be created)

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

### Trucks
- `GET /api/trucks` - Get all trucks
- `POST /api/trucks` - Create truck
- `GET /api/trucks/{id}` - Get truck by ID

### Settlements
- `GET /api/settlements` - Get all settlements (optional `?truck_id=1`)
- `POST /api/settlements/upload` - Upload PDF settlement
- `POST /api/settlements` - Manually create settlement
- `GET /api/settlements/{id}` - Get settlement by ID

### Repairs
- `GET /api/repairs` - Get all repairs (optional `?truck_id=1`)
- `POST /api/repairs` - Create repair expense
- `GET /api/repairs/{id}` - Get repair by ID
- `DELETE /api/repairs/{id}` - Delete repair

### Analytics
- `GET /api/analytics/dashboard` - Dashboard summary
- `GET /api/analytics/truck-profit/{truck_id}` - Profit per truck

## Deployment to Railway

1. **Create Railway account** and new project
2. **Connect GitHub repository**
3. **Add PostgreSQL service** (Railway will set DATABASE_URL automatically)
4. **Set environment variables:**
   - `FRONTEND_URL` - Your frontend URL
   - `ENVIRONMENT=production`
5. **Deploy** - Railway will auto-detect and deploy

## Development Notes

### PDF Parser

The PDF parser (`app/utils/pdf_parser.py`) is a template. You'll need to customize it based on the actual structure of Amazon Relay PDFs. To do this:

1. Upload a sample PDF
2. Inspect the text extraction output
3. Update regex patterns in `parse_amazon_relay_pdf()` to match your PDF format

### Database

- **Development:** Uses SQLite (`logistics.db`)
- **Production:** Uses PostgreSQL (Railway)

Tables are auto-created on first run via `Base.metadata.create_all()` in `main.py`.

## Next Steps

1. ✅ Backend API structure
2. ⏳ Customize PDF parser for Amazon Relay format
3. ⏳ Create React frontend
4. ⏳ Add authentication (if needed)
5. ⏳ Add data export functionality
6. ⏳ Deploy to Railway

## License

Private project - Elis Logistics
