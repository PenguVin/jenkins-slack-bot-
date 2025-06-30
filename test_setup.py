#!/usr/bin/env python3

import os
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth

def test_environment():
    """Test if environment variables are set"""
    load_dotenv()
    
    required_vars = [
        'SLACK_BOT_TOKEN',
        'SLACK_SIGNING_SECRET', 
        'JENKINS_URL',
        'JENKINS_USER',
        'JENKINS_API_TOKEN'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print("❌ Missing environment variables:")
        for var in missing:
            print(f"   - {var}")
        return False
    
    print("✅ All environment variables set")
    return True

def test_jenkins_connection():
    """Test Jenkins API connection"""
    load_dotenv()
    
    jenkins_url = os.getenv('JENKINS_URL')
    jenkins_user = os.getenv('JENKINS_USER')
    jenkins_token = os.getenv('JENKINS_API_TOKEN')
    
    try:
        url = f"{jenkins_url}/api/json"
        response = requests.get(
            url, 
            auth=HTTPBasicAuth(jenkins_user, jenkins_token),
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Jenkins connection successful")
            jobs = response.json().get('jobs', [])
            print(f"   Found {len(jobs)} jobs")
            return True
        else:
            print(f"❌ Jenkins connection failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Jenkins connection error: {str(e)}")
        return False

def main():
    print("🧪 Testing Jenkins Slack Bot Setup\n")
    
    env_ok = test_environment()
    jenkins_ok = test_jenkins_connection() if env_ok else False
    
    print("\n" + "="*50)
    if env_ok and jenkins_ok:
        print("🎉 Setup test passed! Ready to run the bot.")
        print("\nNext steps:")
        print("1. Run: python app.py")
        print("2. In another terminal: ngrok http 3000")
        print("3. Update Slack app URLs with ngrok URL")
    else:
        print("❌ Setup test failed. Check the errors above.")
        print("Refer to SETUP_GUIDE.md for detailed instructions.")

if __name__ == "__main__":
    main()