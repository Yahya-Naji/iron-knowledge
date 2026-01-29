# Railway Deployment Guide

## Quick Deploy to Railway

### Option 1: Deploy via Railway Dashboard

1. **Go to [Railway](https://railway.app)** and sign up/login
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Connect your GitHub account and select `iron-knowledge` repository
5. Railway will auto-detect the Python app

### Option 2: Deploy via Railway CLI

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up
```

## Environment Variables

Set these in Railway Dashboard → Your Project → Variables:

### Required:
```
OPENAI_API_KEY=your_openai_api_key
CHAINLIT_SECRET_KEY=YLYdeA-4wwjXw6-i_BNnGzkrPD01FwZySCDycRx4fM
CHAINLIT_AUTH_SECRET=YLYdeA-4wwjXw6-i_BNnGzkrPD01FwZySCDycRx4fM
```

### SMTP Configuration:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_email@gmail.com
SMTP_FROM_NAME=Iron Mountain
TO_EMAIL=your_email@gmail.com
```

### App Configuration:
```
CANCEL_BASE_URL=https://your-app-name.up.railway.app
PORT=8000
```

## Database Setup

The SQLite database will be created automatically on first run. For persistent storage, Railway provides a volume that persists between deployments.

## After Deployment

1. Railway will provide a URL like: `https://your-app-name.up.railway.app`
2. Update `CANCEL_BASE_URL` in Railway environment variables to match your deployed URL
3. Access your app at the provided URL

## Notes

- Railway automatically handles HTTPS
- The database file will persist in Railway's filesystem
- WebSocket support is included
- Free tier includes 500 hours/month
