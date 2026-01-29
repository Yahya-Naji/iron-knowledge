# Iron Mountain Demo

Voice-enabled customer service assistant for document storage management.

## Quick Start

1. **Copy `.env.example` to `.env` and fill in your values:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and credentials
   ```

2. **Start services:**
   ```bash
   docker-compose up -d
   ```

3. **Setup Autogen Studio:**
   - Autogen Studio needs to be running separately or add it to docker-compose
   - Open Autogen Studio UI (default: http://localhost:8081)
   - Import `config/team_ironmountain_db.json` as Team 2
   - Import `config/team_ironmountain_email.json` as Team 3
   - Note: Update `AUTOGEN_API_URL` in `.env` if Autogen runs elsewhere

4. **Access Chainlit UI:**
   - Open http://localhost:8002
   - Login with any username
   - Press **P** for voice or type messages

## Directory Structure

```
ironmountain-demo/
├── mcp-servers/          # MCP servers (database & email)
├── chainlit-app/         # Chainlit application
├── config/               # Autogen team configurations
├── docker/               # Dockerfiles
├── scripts/              # Database initialization
├── docker-compose.yaml   # Service orchestration
├── .env.example          # Environment variables template
└── README.md            # This file
```

## Features

- 📦 Check customer accounts
- 📊 View box inventory
- 🚚 Request empty boxes
- 📧 Email confirmations
- 🔗 Cancellation links

## Demo Accounts

- IM-10001: Yousef Al-Mansoori
- IM-10002: Sarah Johnson
- IM-10003: Ahmed Hassan
- IM-10004: Emily Roberts
- IM-10005: Mohammed Ali

## Requirements

- Docker & Docker Compose
- OpenAI API key
- SMTP credentials (for email)

## Email Configuration

The email service is pre-configured for Gmail (yayanaji.yn@gmail.com).

**Quick Setup:**
1. Enable 2-Step Verification in your Google Account
2. Generate an App Password: [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Set `SMTP_PASSWORD` environment variable with the 16-character app password

See [EMAIL_SETUP.md](./EMAIL_SETUP.md) for detailed instructions.
