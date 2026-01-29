# SMTP Setup Guide - Quick Start

## Step-by-Step Setup for Gmail (yayanaji.yn@gmail.com)

### Step 1: Enable 2-Step Verification

1. Go to your Google Account: https://myaccount.google.com/security
2. Under "Signing in to Google", click **2-Step Verification**
3. Follow the prompts to enable it (if not already enabled)
   - This is **required** to generate App Passwords

### Step 2: Generate App Password

1. Go directly to App Passwords: https://myaccount.google.com/apppasswords
   - Or: Google Account → Security → 2-Step Verification → App passwords
2. Select **Mail** as the app
3. Select **Other (Custom name)** as the device
4. Enter: `Iron Mountain Demo`
5. Click **Generate**
6. **Copy the 16-character password** (format: `abcd efgh ijkl mnop`)
   - ⚠️ You'll only see this once! Copy it now.

### Step 3: Set the Password

**Option A: Quick Test (Temporary)**
```bash
export SMTP_PASSWORD="your-16-character-app-password-here"
```

**Option B: Add to .env file (Recommended)**
```bash
cd chainlit-app
cat > .env << EOF
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=yayanaji.yn@gmail.com
SMTP_PASSWORD=your-16-character-app-password-here
SMTP_FROM_EMAIL=yayanaji.yn@gmail.com
SMTP_FROM_NAME=Iron Mountain
OPENAI_API_KEY=your-openai-api-key-here
CHAINLIT_SECRET_KEY=YLYdeA-4wwjXw6-i_BNnGzkrPD01FwZySCDycRx4fM
EOF
```

**Option C: Add to run.sh (Mac/Linux)**
Edit `run.sh` and add:
```bash
export SMTP_PASSWORD="your-16-character-app-password-here"
```

**Option D: Add to run.bat (Windows)**
Edit `run.bat` and add:
```cmd
set SMTP_PASSWORD=your-16-character-app-password-here
```

### Step 4: Test the Connection

Run the test script:
```bash
# Activate virtual environment first
source .venv/bin/activate  # Mac/Linux
# OR
.venv\Scripts\activate  # Windows

# Set the password if not in .env
export SMTP_PASSWORD="your-app-password"  # Mac/Linux
# OR
set SMTP_PASSWORD=your-app-password  # Windows

# Run test
python test_smtp.py
```

### Step 5: Verify It Works

The test script will:
- ✅ Test SMTP connection
- ✅ Test authentication
- ✅ Send a test email (if you provide an email address)

If successful, you'll see:
```
✅ SMTP Configuration Test: PASSED
```

## Current Default Configuration

- **SMTP Host:** `smtp.gmail.com`
- **SMTP Port:** `587` (TLS)
- **SMTP User:** `yayanaji.yn@gmail.com`
- **From Email:** `yayanaji.yn@gmail.com`
- **From Name:** `Iron Mountain`

## Troubleshooting

### ❌ "SMTP Authentication failed"

**Solution:**
- Make sure you're using an **App Password**, not your regular Gmail password
- Verify 2-Step Verification is enabled
- Check that the password has no spaces (remove spaces if copied with them)
- Regenerate the App Password if needed

### ❌ "Connection timeout"

**Solution:**
- Check your internet connection
- Verify port 587 is not blocked by firewall
- Try port 465 with SSL instead:
  ```bash
  export SMTP_PORT=465
  ```

### ❌ "Email not received"

**Solution:**
- Check spam/junk folder
- Verify recipient email address is correct
- Check server logs in terminal

## Security Reminder

⚠️ **Never commit your `.env` file or App Password to Git!**

Make sure `.env` is in `.gitignore`:
```bash
echo ".env" >> .gitignore
```

## Next Steps

Once SMTP is configured:
1. ✅ Test emails will be sent when customers request boxes
2. ✅ Confirmation emails will be sent automatically
3. ✅ Internal notifications can be sent (if `INTERNAL_NOTIFICATION_EMAIL` is set)

## Need Help?

Run the test script anytime to verify your configuration:
```bash
python test_smtp.py
```
