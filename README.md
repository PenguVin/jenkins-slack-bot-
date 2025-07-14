# Jenkins Slack Bot

A Slack bot that integrates with Jenkins to list jobs, handle parameters with smart UI elements, and extract meaningful results from console output.

## Setup Instructions

### 1. Slack App Dashboard Setup

1. Go to [Slack API](https://api.slack.com/apps) and click "Create New App"
2. Choose "From scratch" and name your app (e.g., "Jenkins Bot")
3. Select your workspace

#### OAuth & Permissions:
- Add Bot Token Scopes:
  - `chat:write`
  - `commands`
  - `im:write`
  - `files:read`
  - `users:read`
- Install app to workspace and copy the Bot User OAuth Token

#### Slash Commands:
- Create command: `/jenkins`
- Request URL: `https://your-ngrok-url.ngrok.io/slack/events`
- Description: "List and run Jenkins jobs"

#### Interactivity & Shortcuts:
- Enable Interactivity
- Request URL: `https://your-ngrok-url.ngrok.io/slack/events`

#### Event Subscriptions:
- Enable Events
- Request URL: `https://your-ngrok-url.ngrok.io/slack/events`

### 2. Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your credentials
```

### 3. Jenkins Setup

Ensure Jenkins has:
- API access enabled
- User with API token
- CSRF protection enabled (crumb issuer)

### 4. Ngrok Setup

```bash
# Install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Authenticate (get token from ngrok.com)
ngrok config add-authtoken YOUR_AUTHTOKEN

# Start tunnel
ngrok http 3000
```

### 5. Run the Bot

```bash
python app.py
```

## Usage

1. Type `/jenkins` in any Slack channel
2. Select a job from the dropdown menu
3. For parameterized jobs:
   - Fill parameters in the modal dialog
   - Supports text, date, choice, boolean, and file parameters
   - Smart date defaults (previous month start/end)
4. Bot monitors job execution and shows results
5. Extracts meaningful output and Google Doc links

## Features

- ✅ Interactive job selection with dropdown
- ✅ Smart parameter handling:
  - Text inputs with default values
  - Date pickers with intelligent defaults
  - Choice dropdowns
  - Boolean checkboxes
  - File upload support
- ✅ Real-time build monitoring
- ✅ Console output filtering and result extraction
- ✅ User activity logging
- ✅ Error handling and timeouts
- ✅ CSRF protection for Jenkins API