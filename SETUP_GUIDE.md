# Complete Setup Guide for Jenkins Slack Bot

## 🔧 Quick Start

```bash
./setup.sh
```

## 📋 Detailed Setup Instructions

### 1. Slack App Configuration

#### Step 1: Create Slack App
1. Visit [Slack API Apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Select **"From scratch"**
4. App Name: `Jenkins Bot`
5. Choose your workspace

#### Step 2: Configure OAuth & Permissions
1. Go to **"OAuth & Permissions"** in sidebar
2. Scroll to **"Scopes"** → **"Bot Token Scopes"**
3. Add these scopes:
   - `chat:write` - Send messages
   - `commands` - Use slash commands
   - `im:write` - Send direct messages

#### Step 3: Install App
1. Click **"Install to Workspace"**
2. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`)

#### Step 4: Create Slash Command
1. Go to **"Slash Commands"** in sidebar
2. Click **"Create New Command"**
3. Command: `/jenkins`
4. Request URL: `https://YOUR_NGROK_URL.ngrok.io/slack/events`
5. Short Description: `List and run Jenkins jobs`
6. Save

#### Step 5: Enable Interactivity
1. Go to **"Interactivity & Shortcuts"**
2. Turn on **"Interactivity"**
3. Request URL: `https://YOUR_NGROK_URL.ngrok.io/slack/events`
4. Save Changes

#### Step 6: Get Signing Secret
1. Go to **"Basic Information"**
2. Copy **"Signing Secret"**

### 2. Jenkins Configuration

#### Step 1: Enable Jenkins API
1. Go to Jenkins → **Manage Jenkins** → **Configure Global Security**
2. Enable **"Enable security"**
3. Under **"CSRF Protection"**, check **"Enable CSRF Protection"**

#### Step 2: Create API Token
1. Click your username (top right)
2. Click **"Configure"**
3. Go to **"API Token"** section
4. Click **"Add new Token"**
5. Give it a name and click **"Generate"**
6. Copy the token immediately

### 3. Ngrok Setup

#### Step 1: Install Ngrok
```bash
# Download and install
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

#### Step 2: Get Ngrok Auth Token
1. Sign up at [ngrok.com](https://ngrok.com)
2. Go to **"Your Authtoken"** in dashboard
3. Copy your authtoken

#### Step 3: Configure Ngrok
```bash
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

### 4. Environment Configuration

Edit `.env` file with your credentials:

```bash
# Slack App Credentials
SLACK_BOT_TOKEN=xoxb-your-bot-token-from-step-1.3
SLACK_SIGNING_SECRET=your-signing-secret-from-step-1.6

# Jenkins Configuration
JENKINS_URL=http://your-jenkins-server:8080
JENKINS_USER=your-jenkins-username
JENKINS_API_TOKEN=your-api-token-from-step-2.2

# Flask Configuration
FLASK_PORT=3000
```

### 5. Running the Application

#### Terminal 1: Start the Flask App
```bash
source venv/bin/activate
python app.py
```

#### Terminal 2: Start Ngrok Tunnel
```bash
ngrok http 3000
```

#### Step 3: Update Slack URLs
1. Copy the ngrok URL (e.g., `https://abc123.ngrok.io`)
2. Go back to Slack App settings
3. Update **Request URLs** in:
   - Slash Commands: `https://abc123.ngrok.io/slack/events`
   - Interactivity & Shortcuts: `https://abc123.ngrok.io/slack/events`

## 🎯 Usage

1. In any Slack channel, type: `/jenkins`
2. Bot shows list of available Jenkins jobs
3. Click **"Run Job"** button
4. If job has parameters, fill the form
5. Bot triggers job and waits for completion
6. Bot extracts and shows Google Doc link from console output

## 🔍 Troubleshooting

### Common Issues:

**"url_verification failed"**
- Check SLACK_SIGNING_SECRET in .env
- Ensure ngrok URL is correct in Slack app settings

**"Jenkins connection failed"**
- Verify JENKINS_URL, JENKINS_USER, JENKINS_API_TOKEN
- Check Jenkins API access and CSRF settings

**"No jobs found"**
- Ensure Jenkins user has permission to view jobs
- Check Jenkins API endpoint accessibility

**"Ngrok tunnel not working"**
- Restart ngrok: `ngrok http 3000`
- Update Slack app URLs with new ngrok URL

### Debug Mode:
Set `debug=True` in app.py for detailed error logs.

## 🚀 Production Deployment

For production, replace ngrok with:
- AWS Application Load Balancer
- Nginx reverse proxy
- Heroku/Railway/Render hosting

Remember to update Slack app URLs accordingly.