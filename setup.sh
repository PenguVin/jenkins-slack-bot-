#!/bin/bash

echo "🚀 Setting up Jenkins Slack Bot..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Please edit .env file with your credentials"
fi

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your Slack and Jenkins credentials"
echo "2. Install and setup ngrok: https://ngrok.com/download"
echo "3. Run: source venv/bin/activate"
echo "4. Run: python app.py"
echo "5. In another terminal: ngrok http 3000"