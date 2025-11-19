# Railway Deployment Guide

This guide will help you deploy the Elis Logistics App to Railway with your custom domain and PostgreSQL database.

## 🎯 Overview

This application automatically detects the environment and connects to:
- **SQLite** (`elisogistics.db`) when running locally
- **PostgreSQL** when `DATABASE_URL` environment variable is set (Railway)

The database connection is handled automatically by `backend/app/database.py` - no code changes needed!

## Prerequisites

1. Railway account (sign up at https://railway.app)
2. GitHub repository connected to Railway
3. Custom domain ready to use (optional)
4. Local database backup (optional, for importing existing data)

## Step 1: Create Railway Project

1. Go to Railway dashboard
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your `elis-logistics-app` repository
5. Railway will detect the `railway.json` configuration

## Step 2: Add PostgreSQL Database

1. In your Railway project, click "New"
2. Select "Database" → "Add PostgreSQL"
3. Railway will automatically create a PostgreSQL database
4. **Important**: Railway automatically sets the `DATABASE_URL` environment variable
   - Format: `postgresql://user:password@host:port/dbname`
   - The app automatically converts `postgres://` to `postgresql://` if needed
   - No manual configuration required!

## Step 2.5: Configure Cloudinary (Optional but Recommended)

For production, configure Cloudinary to store images and PDFs in the cloud instead of local storage:

1. Sign up for a free Cloudinary account at https://cloudinary.com
2. Get your credentials from the Cloudinary Dashboard:
   - Cloud Name
   - API Key
   - API Secret
3. In Railway, go to your project → Variables
4. Add the following environment variables:
   - `CLOUDINARY_CLOUD_NAME` - Your Cloudinary cloud name
   - `CLOUDINARY_API_KEY` - Your Cloudinary API key
   - `CLOUDINARY_API_SECRET` - Your Cloudinary API secret

**Note**: If Cloudinary is not configured, the app will fall back to local file storage. However, files stored locally will be lost on Railway deployments since the filesystem is ephemeral. Cloudinary ensures files persist across deployments and provides CDN delivery.

### How Database Connection Works

The app uses **environment-based database selection**:

```python
# backend/app/database.py
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./elisogistics.db")

# Automatically handles Railway's postgres:// format
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Creates appropriate engine based on URL
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)  # PostgreSQL
```

**Connection Flow:**
1. Railway provides `DATABASE_URL` → App detects PostgreSQL
2. Tables auto-create on first startup (`Base.metadata.create_all()`)
3. All database operations work seamlessly with SQLAlchemy ORM

## Step 3: Configure Environment Variables

In Railway project settings, add these environment variables:

### Required Variables:
- `DATABASE_URL` - ✅ **Automatically set by Railway PostgreSQL** (don't override)
  - Railway injects this when you add PostgreSQL service
  - Format: `postgresql://user:pass@host:port/dbname`
  - The app handles this automatically - no action needed!

### Optional Variables:
- `FRONTEND_URL` - Your custom domain (e.g., `https://logistics.yourdomain.com`)
  - Used for CORS configuration
  - If not set, defaults to `http://localhost:3000`
- `CLOUDINARY_CLOUD_NAME` - Cloudinary cloud name (for image/PDF storage)
- `CLOUDINARY_API_KEY` - Cloudinary API key (for image/PDF storage)
- `CLOUDINARY_API_SECRET` - Cloudinary API secret (for image/PDF storage)
  - See Step 2.5 above for setup instructions
  - If not set, app falls back to local file storage (files will be lost on redeploy)
- `PORT` - ✅ Railway sets this automatically (don't override)

### Viewing Database Connection Info

To see your database connection details in Railway:
1. Click on your PostgreSQL service
2. Go to "Variables" tab
3. You'll see `DATABASE_URL` with connection string
4. You can also use Railway CLI: `railway variables`

## Step 4: Configure Custom Domain

1. In Railway project settings, go to "Settings" → "Networking"
2. Click "Generate Domain" to get a Railway domain first (for testing)
3. Click "Custom Domain"
4. Enter your domain (e.g., `logistics.yourdomain.com`)
5. Railway will provide DNS records to add:
   - **CNAME**: Point your subdomain to Railway's provided domain
   - Or **A Record**: Point to Railway's IP address

5. Add the DNS records to your domain provider
6. Wait for DNS propagation (can take a few minutes to hours)
7. Railway will automatically provision SSL certificate via Let's Encrypt

## Step 5: Deploy

1. Railway will automatically deploy when you push to main branch
2. Or manually trigger deployment from Railway dashboard
3. Monitor the deployment logs to ensure:
   - ✅ Frontend builds successfully (`npm run build` in `frontend/`)
   - ✅ Backend dependencies install (`pip install -r requirements.txt`)
   - ✅ Database connection established (check for SQLAlchemy logs)
   - ✅ Database tables are created automatically (`Base.metadata.create_all()`)
   - ✅ Application starts on the assigned PORT

### Build Process (from railway.json)

```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "cd frontend && npm install && npm run build && cd ../backend && pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
  }
}
```

**What happens:**
1. Railway detects `railway.json` configuration
2. Builds frontend → creates `frontend/dist/` directory
3. Installs Python dependencies
4. Starts FastAPI server on Railway's assigned PORT
5. FastAPI serves both API (`/api/*`) and frontend static files

## Step 6: Import Existing Data (Optional)

If you want to import your local data to production:

### Option A: Using Railway CLI
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# Run import script
railway run python backend/import_consolidated_settlements.py backend/settlements_extracted/settlements_consolidated.json --clear-existing
```

### Option B: Using Railway Database URL
1. Get your production DATABASE_URL from Railway dashboard
2. Temporarily set it locally:
```bash
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
cd backend
python import_consolidated_settlements.py settlements_extracted/settlements_consolidated.json --clear-existing
```

## Step 7: Verify Deployment

1. Visit your custom domain
2. Check that:
   - Frontend loads correctly
   - API endpoints work (`/api/health` should return `{"status": "healthy"}`)
   - Database connection works (try logging in or viewing dashboard)
   - File uploads work (test PDF upload)

## Troubleshooting

### Frontend not loading
- Check Railway build logs - ensure `npm run build` succeeded
- Verify `frontend/dist` directory exists in build
- Check that static file serving is configured in `main.py`

### Database connection errors
- ✅ Verify `DATABASE_URL` is set correctly in Railway
  - Check PostgreSQL service → Variables tab
  - Should start with `postgresql://` or `postgres://`
- ✅ Check that PostgreSQL service is running (green status)
- ✅ Ensure database tables are created (they auto-create on first run)
- ✅ Check deployment logs for SQLAlchemy connection errors
- ✅ Test connection: `railway connect postgres` (opens psql shell)

### CORS errors
- Update `FRONTEND_URL` environment variable to match your custom domain
- Ensure domain includes `https://` protocol

### File uploads not working
- Railway uses ephemeral storage - uploaded files will be lost on redeploy
- Consider using Railway Volumes for persistent storage
- Or use cloud storage (S3, Cloudinary) for production

## Production Considerations

1. **File Storage**: Railway's filesystem is ephemeral. Consider:
   - Using Railway Volumes for persistent storage
   - Or migrating to cloud storage (AWS S3, Cloudinary, etc.)

2. **Environment Variables**: Keep sensitive data in Railway environment variables, not in code

3. **Database Backups**: Railway PostgreSQL includes automatic backups, but consider:
   - Regular exports using `export_settlements.py`
   - Setting up additional backup strategy

4. **Monitoring**: Set up Railway monitoring/alerts for:
   - Application crashes
   - High memory/CPU usage
   - Database connection issues

## Next Steps After Deployment

1. Test all features in production
2. Set up monitoring and alerts
3. Configure file storage solution (if needed)
4. Set up regular database backups
5. Update DNS records if needed
6. Test custom domain SSL certificate

## Useful Railway Commands

```bash
# Install Railway CLI (if not installed)
npm i -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# View logs (real-time)
railway logs

# View logs (follow mode)
railway logs --follow

# Run commands in Railway environment
railway run python backend/import_consolidated_settlements.py ...

# Open PostgreSQL database shell
railway connect postgres

# View environment variables
railway variables

# View specific service logs
railway logs --service <service-name>
```

## Testing Database Connection

### Method 1: Check Deployment Logs
Look for these in Railway deployment logs:
```
✓ Database connection established
✓ Tables created successfully
```

### Method 2: Use Railway CLI
```bash
# Connect to database shell
railway connect postgres

# Then run SQL queries:
\dt                    # List all tables
SELECT * FROM trucks;  # Test query
```

### Method 3: Test via API
Once deployed, visit:
- `https://your-domain.railway.app/api/health` - Should return `{"status": "healthy"}`
- `https://your-domain.railway.app/api/trucks` - Should return trucks (or empty array)

## Database Connection Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Railway Platform                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐         ┌──────────────┐              │
│  │   FastAPI    │         │  PostgreSQL  │              │
│  │   Service    │◄────────┤   Database   │              │
│  │              │         │   Service    │              │
│  └──────┬───────┘         └──────────────┘              │
│         │                                                 │
│         │ Serves                                          │
│         │                                                 │
│  ┌──────▼──────────────────────────────────┐             │
│  │  Frontend Static Files (dist/)         │             │
│  │  - index.html                           │             │
│  │  - assets/*.js, *.css                  │             │
│  └─────────────────────────────────────────┘             │
│                                                           │
└─────────────────────────────────────────────────────────┘

Connection Flow:
1. Railway sets DATABASE_URL env var automatically
2. App reads DATABASE_URL in database.py
3. SQLAlchemy creates engine with PostgreSQL driver
4. Tables auto-create on startup
5. All ORM operations work seamlessly
```

**Key Points:**
- ✅ No code changes needed - environment detection is automatic
- ✅ Railway handles database provisioning and connection string
- ✅ SQLAlchemy abstracts database differences (SQLite ↔ PostgreSQL)
- ✅ Tables auto-create on first deployment
- ✅ Same code works locally (SQLite) and production (PostgreSQL)

