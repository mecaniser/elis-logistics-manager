# Database Connection Guide

## 🔌 How Database Connection Works

This application uses **automatic environment detection** to connect to the appropriate database:

- **Local Development**: SQLite (`elisogistics.db`)
- **Railway Production**: PostgreSQL (via `DATABASE_URL`)

## 📋 Connection Logic

The database connection is handled in `backend/app/database.py`:

```python
# 1. Read DATABASE_URL from environment (or use SQLite default)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./elisogistics.db")

# 2. Handle Railway's postgres:// format (convert to postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. Create appropriate SQLAlchemy engine
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration (local)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL configuration (Railway)
    engine = create_engine(DATABASE_URL)
```

## 🎯 Connection Flow

### Local Development
```
┌─────────────────────────────────────┐
│  Local Environment                  │
│  (No DATABASE_URL set)              │
├─────────────────────────────────────┤
│                                     │
│  app/database.py                    │
│  ↓                                  │
│  DATABASE_URL = "sqlite:///..."     │
│  ↓                                  │
│  SQLite Engine Created              │
│  ↓                                  │
│  Connects to elisogistics.db        │
│                                     │
└─────────────────────────────────────┘
```

### Railway Production
```
┌─────────────────────────────────────┐
│  Railway Platform                   │
├─────────────────────────────────────┤
│                                     │
│  1. PostgreSQL Service Created      │
│     ↓                               │
│  2. DATABASE_URL Auto-Set           │
│     Format: postgresql://...        │
│     ↓                               │
│  3. App Reads DATABASE_URL          │
│     ↓                               │
│  4. PostgreSQL Engine Created       │
│     ↓                               │
│  5. Tables Auto-Create              │
│     (Base.metadata.create_all())    │
│     ↓                               │
│  6. Ready to Use!                   │
│                                     │
└─────────────────────────────────────┘
```

## 🔍 Testing Database Connection

### Method 1: Test Script
```bash
# Local (SQLite)
cd backend
python test_db_connection.py

# Railway (PostgreSQL)
# First, get DATABASE_URL from Railway dashboard
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
python test_db_connection.py
```

### Method 2: Railway CLI
```bash
# Connect to PostgreSQL shell
railway connect postgres

# Then run SQL commands:
\dt                    # List tables
SELECT COUNT(*) FROM trucks;  # Test query
```

### Method 3: Via API
Once deployed, test the connection:
```bash
# Health check
curl https://your-app.railway.app/api/health

# Should return: {"status": "healthy"}

# Test database query
curl https://your-app.railway.app/api/trucks

# Should return: [] (empty array if no trucks) or truck data
```

## 🛠️ Railway Database Setup

### Step 1: Add PostgreSQL Service
1. In Railway project → Click "New"
2. Select "Database" → "Add PostgreSQL"
3. Railway automatically:
   - Creates PostgreSQL database
   - Sets `DATABASE_URL` environment variable
   - Makes it available to your FastAPI service

### Step 2: Verify Connection String
1. Click on PostgreSQL service
2. Go to "Variables" tab
3. You'll see `DATABASE_URL` with format:
   ```
   postgresql://postgres:password@hostname:5432/railway
   ```

### Step 3: Tables Auto-Create
On first app startup, SQLAlchemy automatically creates all tables:
- `trucks`
- `settlements`
- `repairs`

No migrations needed! Tables are created via:
```python
# In app/main.py
Base.metadata.create_all(bind=engine)
```

## 🔐 Security Notes

1. **Never commit `DATABASE_URL`** - It's in `.gitignore`
2. **Railway handles credentials** - Automatically rotated and secured
3. **Connection is encrypted** - PostgreSQL uses SSL by default
4. **Environment variables** - Railway injects `DATABASE_URL` securely

## 📊 Database Schema

The app uses SQLAlchemy ORM models:
- `app/models/truck.py` - Truck information
- `app/models/settlement.py` - Settlement records
- `app/models/repair.py` - Repair records

All models inherit from `Base` (declarative_base), so they're automatically included in table creation.

## 🐛 Troubleshooting

### Connection Refused
**Symptoms**: `OperationalError: could not connect to server`

**Solutions**:
1. Verify PostgreSQL service is running (green status in Railway)
2. Check `DATABASE_URL` is set correctly
3. Ensure FastAPI service is linked to PostgreSQL service in Railway

### Tables Not Found
**Symptoms**: `relation "trucks" does not exist`

**Solutions**:
1. Check deployment logs for table creation errors
2. Verify `Base.metadata.create_all()` runs on startup
3. Manually trigger: Restart deployment in Railway

### Wrong Database Type
**Symptoms**: App connects to SQLite instead of PostgreSQL

**Solutions**:
1. Verify `DATABASE_URL` environment variable is set in Railway
2. Check it starts with `postgresql://` or `postgres://`
3. Restart deployment after setting variable

## 💡 Key Points

✅ **No code changes needed** - Environment detection is automatic  
✅ **Railway handles provisioning** - Just add PostgreSQL service  
✅ **Tables auto-create** - No migrations required  
✅ **Same code works everywhere** - SQLAlchemy abstracts differences  
✅ **Secure by default** - Railway manages credentials  

## 📚 Related Files

- `backend/app/database.py` - Database connection logic
- `backend/app/main.py` - App startup (table creation)
- `backend/app/models/` - SQLAlchemy models
- `backend/test_db_connection.py` - Connection test script
- `RAILWAY_DEPLOYMENT.md` - Full deployment guide

