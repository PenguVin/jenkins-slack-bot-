# Jenkins Slack Bot

A Slack bot that integrates with Jenkins to list jobs, handle parameters, and extract Google Doc links from console output.

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
2. Click "Run Job" button for any job
3. Fill parameters if required
4. Bot will show Google Doc link from console output

## Features

- ✅ List all Jenkins jobs
- ✅ Handle parameterized jobs
- ✅ Extract Google Doc links from console output
- ✅ Real-time job status updates
- ✅ Error handling and timeouts