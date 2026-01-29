# Email Setup Guide - Gmail Configuration

## Quick Setup for yayanaji.yn@gmail.com

The email service is already configured with your Gmail address. You just need to set up an App Password.

## Step 1: Enable 2-Step Verification

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
   - This is required to generate App Passwords

## Step 2: Generate App Password

1. Go to [App Passwords](https://myaccount.google.com/apppasswords)
2. Select **Mail** as the app
3. Select **Other (Custom name)** as the device
4. Enter "Iron Mountain Demo" as the name
5. Click **Generate**
6. Copy the 16-character password (it will look like: `abcd efgh ijkl mnop`)

## Step 3: Set Environment Variable

### Option A: Export in Terminal (Temporary)
```bash
export SMTP_PASSWORD="your-16-character-app-password"
```

### Option B: Create .env file (Recommended)
Create a `.env` file in the `chainlit-app/` directory:

```bash
cd chainlit-app
cat > .env << EOF
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yayanaji.yn@gmail.com
SMTP_PASSWORD=your-16-character-app-password-here
SMTP_FROM_EMAIL=yayanaji.yn@gmail.com
SMTP_FROM_NAME=Iron Mountain
OPENAI_API_KEY=your-openai-api-key
CHAINLIT_SECRET_KEY=YLYdeA-4wwjXw6-i_BNnGzkrPD01FwZySCDycRx4fM
EOF
```

### Option C: Set in Docker Compose
If using Docker, add to `docker-compose.yaml`:

```yaml
environment:
  - SMTP_PASSWORD=your-16-character-app-password
```

## Step 4: Test Email

Test the email service:

```bash
curl -X POST http://localhost:8001/api/send-email \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "yayanaji.yn@gmail.com",
    "subject": "Test Email",
    "body_html": "<h1>Test</h1><p>This is a test email from Iron Mountain.</p>"
  }'
```

## Current Configuration

- **SMTP Host:** smtp.gmail.com
- **SMTP Port:** 587 (TLS)
- **From Email:** yayanaji.yn@gmail.com
- **From Name:** Iron Mountain

## Troubleshooting

### "SMTP Authentication failed"
- Make sure you're using an App Password, not your regular Gmail password
- Verify 2-Step Verification is enabled
- Check that the App Password is correct (no spaces)

### "Connection timeout"
- Check your firewall/network settings
- Verify port 587 is not blocked
- Try port 465 with SSL instead (change SMTP_PORT to 465)

### "Email not received"
- Check spam folder
- Verify recipient email address
- Check server logs for errors

## Security Note

⚠️ **Never commit your `.env` file or App Password to version control!**

Add `.env` to `.gitignore`:
```bash
echo ".env" >> .gitignore
```
