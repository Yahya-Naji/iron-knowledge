@echo off
REM Startup script for Iron Mountain Chainlit App (Windows)

cd /d "%~dp0"

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Set environment variables (must be set before Chainlit imports)
if not defined CHAINLIT_SECRET_KEY (
    set CHAINLIT_SECRET_KEY=YLYdeA-4wwjXw6-i_BNnGzkrPD01FwZySCDycRx4fM
)
set CHAINLIT_AUTH_SECRET=%CHAINLIT_SECRET_KEY%

REM Optional: Set OpenAI API key if provided
if defined OPENAI_API_KEY (
    set OPENAI_API_KEY=%OPENAI_API_KEY%
)

REM Optional: Set SMTP password if provided
if defined SMTP_PASSWORD (
    set SMTP_PASSWORD=%SMTP_PASSWORD%
)

REM Run Chainlit
echo.
echo ========================================
echo   Iron Mountain Chainlit App
echo ========================================
echo.
echo 🚀 Starting Iron Mountain Chainlit App...
echo 📍 URL: http://localhost:8001
echo 📧 Email: Configure SMTP_PASSWORD for email features
echo.
echo 💡 Tip: Use http://localhost:8001 (not 0.0.0.0) for microphone permissions
echo.
python -m chainlit run app.py --host localhost --port 8001

pause
