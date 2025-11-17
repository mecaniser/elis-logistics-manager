# Railway Troubleshooting: "cd could not be found" Error

## Problem
Railway is trying to execute `cd` command, which doesn't exist in the container execution environment.

## Root Cause
Railway might be using a **startCommand** configured in the Railway dashboard that overrides the Dockerfile CMD/ENTRYPOINT.

## Solution: Check Railway Dashboard Settings

### Step 1: Check Service Settings
1. Go to your Railway project dashboard
2. Click on your **service** (the one running the app)
3. Go to **Settings** tab
4. Look for **"Start Command"** or **"Command"** field
5. **If it contains `cd backend && ...` or any `cd` command:**
   - **DELETE IT** or leave it **EMPTY**
   - Railway should use the Dockerfile ENTRYPOINT/CMD instead

### Step 2: Verify Dockerfile is Being Used
1. In Railway dashboard → **Deployments** tab
2. Check the latest deployment logs
3. You should see: `Using Detected Dockerfile`
4. If you see `Using NIXPACKS` or `Using Buildpacks`, Railway is not using Dockerfile

### Step 3: Clear Railway Cache (if needed)
1. In Railway dashboard → **Settings** → **Advanced**
2. Try **"Clear Build Cache"** or **"Redeploy"**
3. This forces Railway to rebuild from scratch

## Current Dockerfile Configuration

Our Dockerfile uses:
- ✅ **ENTRYPOINT** (Railway cannot override this)
- ✅ **WORKDIR** (no `cd` commands)
- ✅ **start.sh** script (handles PORT environment variable)

```dockerfile
WORKDIR /app/backend
ENTRYPOINT ["./start.sh"]
```

## Verification

After removing startCommand from Railway dashboard:
1. Trigger a new deployment
2. Check logs - should see:
   ```
   Using Detected Dockerfile
   ...
   Container started successfully
   ```
3. No more "cd could not be found" errors

## Alternative: Use Railway CLI

If dashboard doesn't work, use Railway CLI:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link to project
railway link

# Remove startCommand
railway variables --remove START_COMMAND

# Or set it to empty
railway variables --set START_COMMAND=""
```

## Why This Happens

Railway prioritizes configuration in this order:
1. **Dashboard Settings** (startCommand) - **HIGHEST PRIORITY**
2. **railway.json** (startCommand)
3. **Procfile** (web command)
4. **Dockerfile CMD/ENTRYPOINT** - **LOWEST PRIORITY**

If startCommand is set in dashboard, it overrides everything else, including Dockerfile.

## Current Status

✅ Dockerfile is correct (no `cd` commands)
✅ Uses ENTRYPOINT (cannot be overridden)
✅ start.sh script handles PORT correctly
⚠️ **Need to check Railway dashboard for startCommand override**

