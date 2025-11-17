# Railway Quick Start Guide

## 🚀 Quick Deployment Steps

### 1. Create Railway Project
- Go to [railway.app](https://railway.app)
- Click "New Project" → "Deploy from GitHub repo"
- Select your `elis-logistics-app` repository

### 2. Add PostgreSQL Database
- In Railway project, click "New" → "Database" → "Add PostgreSQL"
- ✅ Railway automatically sets `DATABASE_URL` - no action needed!

### 3. Deploy
- Railway auto-deploys on push to `main` branch
- Or click "Deploy" in Railway dashboard
- Monitor logs for successful deployment

### 4. Test Deployment
- Visit your Railway domain (e.g., `https://your-app.railway.app`)
- Check health: `https://your-app.railway.app/api/health`
- Should return: `{"status": "healthy"}`

## 🔌 Database Connection

**How it works:**
- Railway automatically provides `DATABASE_URL` environment variable
- App detects PostgreSQL from `DATABASE_URL`
- Tables auto-create on first startup
- No code changes needed!

**Test connection locally (with Railway DB):**
```bash
# Get DATABASE_URL from Railway dashboard → PostgreSQL service → Variables
export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Test connection
cd backend
python test_db_connection.py
```

**Test connection in Railway:**
```bash
railway connect postgres
# Then run: \dt (list tables)
```

## 📋 Environment Variables

### Auto-Set by Railway:
- ✅ `DATABASE_URL` - PostgreSQL connection string
- ✅ `PORT` - Application port

### Optional (set manually):
- `FRONTEND_URL` - Your custom domain (for CORS)

## 🛠️ Useful Commands

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and link
railway login
railway link

# View logs
railway logs --follow

# Connect to database
railway connect postgres

# View variables
railway variables

# Run commands in Railway
railway run python backend/test_db_connection.py
```

## 🐛 Troubleshooting

**Database connection fails:**
1. Check PostgreSQL service is running (green status)
2. Verify `DATABASE_URL` in Railway → Variables
3. Check deployment logs for SQLAlchemy errors
4. Test: `railway connect postgres`

**Frontend not loading:**
1. Check build logs - ensure `npm run build` succeeded
2. Verify `frontend/dist/` exists in build
3. Check Railway logs for static file serving errors

**CORS errors:**
1. Set `FRONTEND_URL` environment variable
2. Include `https://` protocol in URL
3. Restart deployment after setting variable

## 📚 Full Documentation

See [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md) for complete guide.

