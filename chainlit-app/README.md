# Iron Mountain Voice Assistant - Setup Guide

A Chainlit-based voice assistant for Iron Mountain storage services with OpenAI Realtime API integration.

## Features

- 🎤 **Voice Interaction** - Real-time voice conversations using OpenAI Realtime API
- 📦 **Account Management** - Check customer accounts and box inventory
- 🚚 **Box Requests** - Request empty storage boxes with email confirmations
- 🌍 **Multilingual Support** - Responds in the customer's preferred language
- 📧 **Email Notifications** - Automated confirmation emails for box requests

## Prerequisites

- Python 3.10 or higher
- Virtual environment (venv)
- OpenAI API key
- (Optional) SMTP credentials for email features

## Installation

### 1. Navigate to the project directory

```bash
cd chainlit-app
```

### 2. Create and activate virtual environment

**On Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**On Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Create a `.env` file in the `chainlit-app` directory (optional, or set in your shell):

```bash
# Required for voice features
OPENAI_API_KEY=your_openai_api_key_here

# Optional: For email features
SMTP_PASSWORD=your_gmail_app_password_here
SMTP_USER=yayanaji.yn@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

# Optional: For internal notifications
INTERNAL_NOTIFICATION_EMAIL=internal@example.com
```

**Or export them in your shell:**

**Mac/Linux:**
```bash
export OPENAI_API_KEY="your_openai_api_key_here"
export SMTP_PASSWORD="your_gmail_app_password_here"
```

**Windows:**
```cmd
set OPENAI_API_KEY=your_openai_api_key_here
set SMTP_PASSWORD=your_gmail_app_password_here
```

## Running the Application

### Mac/Linux

```bash
./run.sh
```

### Windows

```cmd
run.bat
```

### Manual Start

If you prefer to run manually:

```bash
# Activate virtual environment first
source .venv/bin/activate  # Mac/Linux
# OR
.venv\Scripts\activate  # Windows

# Set environment variables
export CHAINLIT_SECRET_KEY="YLYdeA-4wwjXw6-i_BNnGzkrPD01FwZySCDycRx4fM"
export OPENAI_API_KEY="your_key_here"

# Run the app
python -m chainlit run app.py --host localhost --port 8001
```

## Accessing the Application

Once started, open your browser and navigate to:

```
http://localhost:8001
```

**Important:** Use `localhost` (not `0.0.0.0` or `127.0.0.1`) for microphone permissions to work correctly in Chrome.

## Usage

### Voice Mode

1. Click the **microphone button** (or press **P**) to start voice interaction
2. Speak naturally - the assistant will:
   - Welcome you by name after retrieving your account
   - Confirm your address before processing deliveries
   - Help you check inventory and request boxes
3. You can interrupt the assistant at any time by speaking

### Text Mode

Type your queries directly:
- "My account number is IM-10001"
- "Check my box inventory"
- "I need 10 boxes"

## Project Structure

```
chainlit-app/
├── app.py                 # Main Chainlit application
├── requirements.txt       # Python dependencies
├── run.sh                # Startup script (Mac/Linux)
├── run.bat               # Startup script (Windows)
├── chainlit.md           # Chainlit welcome message
├── .chainlit/
│   └── config.toml       # Chainlit configuration
├── api/
│   └── routes.py         # REST API endpoints
├── db/
│   ├── connection.py     # Database connection
│   └── queries.py        # Database queries
├── services/
│   ├── email.py          # Email service
│   └── cancellation.py   # Cancellation service
└── realtime/
    └── __init__.py       # Custom OpenAI Realtime client
```

## Configuration

### Chainlit Configuration

Edit `.chainlit/config.toml` to customize:
- Audio sample rate
- UI settings
- Authentication

### Email Configuration

Default SMTP settings are configured for Gmail. To use a different provider, update the environment variables:

- `SMTP_HOST` - SMTP server hostname
- `SMTP_PORT` - SMTP server port (587 for TLS, 465 for SSL)
- `SMTP_USER` - Your email address
- `SMTP_PASSWORD` - Your email app password

**Gmail Setup:**
1. Enable 2-factor authentication
2. Generate an app password: https://myaccount.google.com/apppasswords
3. Use the app password as `SMTP_PASSWORD`

## Troubleshooting

### Voice button not appearing

- Check that audio is enabled in `.chainlit/config.toml`:
  ```toml
  [features.audio]
  enabled = true
  ```

### Microphone permission denied

- Use `http://localhost:8001` (not `0.0.0.0:8001`)
- Allow microphone access in your browser settings
- Try a different browser (Chrome recommended)

### Connection timeout

- Verify your `OPENAI_API_KEY` is set correctly
- Check your internet connection
- Ensure you have OpenAI API credits

### Audio cutting out

- The VAD (Voice Activity Detection) settings can be adjusted in `app.py`
- Increase `silence_duration_ms` for less sensitive detection
- Adjust `threshold` for background noise filtering

### Email not sending

- Verify `SMTP_PASSWORD` is set correctly
- Check that you're using an app password (not your regular password for Gmail)
- Review email logs in the terminal output

## Development

### Adding New Tools

1. Create a handler function in `setup_openai_realtime()`:
   ```python
   async def my_new_tool(param: str) -> str:
       # Your logic here
       return "result"
   ```

2. Add tool definition to `tools_config`:
   ```python
   {
       "name": "my_new_tool",
       "description": "What this tool does",
       "parameters": {
           "type": "object",
           "properties": {
               "param": {"type": "string", "description": "Parameter description"}
           },
           "required": ["param"]
       }
   }
   ```

3. The tool will be automatically registered with the RealtimeClient

## API Endpoints

The application exposes REST API endpoints:

- `GET /api/customer/{account_number}` - Get customer account details
- `GET /api/inventory/{account_number}` - Get box inventory
- `POST /api/request-boxes` - Request empty boxes
- `GET /api/health` - Health check

## License

Internal use for Iron Mountain demo purposes.

## Support

For issues or questions, check the logs in the terminal output. All API calls and tool executions are logged for debugging.
