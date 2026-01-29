#!/bin/bash
# Startup script for Iron Mountain Chainlit App

cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

# Set environment variables (must be set before Chainlit imports)
export CHAINLIT_SECRET_KEY="${CHAINLIT_SECRET_KEY:-YLYdeA-4wwjXw6-i_BNnGzkrPD01FwZySCDycRx4fM}"
export CHAINLIT_AUTH_SECRET="${CHAINLIT_SECRET_KEY}"

# Optional: Set OpenAI API key if provided
if [ -n "$OPENAI_API_KEY" ]; then
    export OPENAI_API_KEY="$OPENAI_API_KEY"
fi

# Optional: Set SMTP password if provided
if [ -n "$SMTP_PASSWORD" ]; then
    export SMTP_PASSWORD="$SMTP_PASSWORD"
fi

# Run Chainlit
echo "🚀 Starting Iron Mountain Chainlit App..."
echo "📍 URL: http://localhost:8001"
echo "📧 Email: Configure SMTP_PASSWORD for email features"
echo ""
echo "💡 Tip: Use http://localhost:8001 (not 0.0.0.0) for microphone permissions"
echo ""
python -m chainlit run app.py --host localhost --port 8001
