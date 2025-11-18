# Custom Domain Setup: elisprotech.com

## Railway Configuration

### Step 1: Add Custom Domain in Railway

1. Go to Railway Dashboard → Your Project
2. Click on your FastAPI service
3. Go to **Settings** → **Networking**
4. Click **"Custom Domain"**
5. Enter your domain: `elisprotech.com` (or `www.elisprotech.com` if you prefer)
6. Railway will show you DNS records to add

### Step 2: DNS Configuration

Railway will provide you with one of these options:

**Option A: CNAME Record (Recommended)**
```
Type: CNAME
Name: @ (or leave blank for root domain)
Value: your-app.railway.app
```

**Option B: A Record**
```
Type: A
Name: @ (or leave blank for root domain)
Value: [Railway's IP address]
```

**For Subdomain (e.g., logistics.elisprotech.com):**
```
Type: CNAME
Name: logistics
Value: your-app.railway.app
```

### Step 3: Add DNS Records

1. Go to your domain registrar (where you bought elisprotech.com)
2. Navigate to DNS management
3. Add the DNS record Railway provided
4. Save changes

### Step 4: Set Environment Variables in Railway

1. In Railway Dashboard → Your Project → FastAPI Service
2. Go to **Variables** tab
3. Add/Update:
   ```
   FRONTEND_URL=https://elisprotech.com
   ```
   (or `https://www.elisprotech.com` if using www subdomain)

### Step 5: Wait for DNS Propagation

- DNS changes can take 5 minutes to 48 hours
- Usually takes 15-30 minutes
- Check propagation: https://www.whatsmydns.net

### Step 6: SSL Certificate

- Railway automatically provisions SSL certificate via Let's Encrypt
- Certificate is issued automatically after DNS propagates
- Usually takes 5-10 minutes after DNS is active

## Verification

After DNS propagates and SSL is active:

1. Visit `https://elisprotech.com`
2. Check API health: `https://elisprotech.com/api/health`
3. Should return: `{"status": "healthy"}`

## Troubleshooting

### Domain not resolving
- Check DNS records are correct
- Wait longer for propagation
- Verify CNAME/A record is correct

### SSL certificate not issued
- Ensure DNS is fully propagated
- Check Railway logs for SSL errors
- May need to wait up to 24 hours

### CORS errors
- Verify `FRONTEND_URL` environment variable is set correctly
- Should be: `https://elisprotech.com` (with https://)
- Restart service after setting variable

## Notes

- **Root domain vs Subdomain**: 
  - Root: `elisprotech.com` - requires A record or ALIAS
  - Subdomain: `logistics.elisprotech.com` - can use CNAME
  
- **WWW subdomain**: If you want `www.elisprotech.com`:
  - Add CNAME: `www` → `your-app.railway.app`
  - Set `FRONTEND_URL=https://www.elisprotech.com`

- **Both root and www**: You can configure both, but need separate DNS records


