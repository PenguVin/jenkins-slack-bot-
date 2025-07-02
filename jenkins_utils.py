import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
import time
import re
import base64

load_dotenv()

JENKINS_URL = os.getenv("JENKINS_URL")
JENKINS_USER = os.getenv("JENKINS_USER")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN")

def get_crumb():
    url = f"{JENKINS_URL}/crumbIssuer/api/json"
    res = requests.get(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN))
    res.raise_for_status()
    data = res.json()
    return {data['crumbRequestField']: data['crumb']}

def get_all_jobs():
    headers = get_crumb()
    url = f"{JENKINS_URL}/api/json"
    res = requests.get(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN), headers=headers)
    res.raise_for_status()
    jobs = res.json().get("jobs", [])
    return [job['name'] for job in jobs]

def get_job_parameters(job_name):
    url = f"{JENKINS_URL}/job/{job_name}/api/json"
    res = requests.get(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN))
    res.raise_for_status()
    data = res.json()
    
    parameters = []
    
    # Check both 'actions' and 'property' arrays
    for source in [data.get('actions', []), data.get('property', [])]:
        for item in source:
            if item.get('_class') == 'hudson.model.ParametersDefinitionProperty':
                for param in item.get('parameterDefinitions', []):
                    # Fix for file parameters - handle None defaultParameterValue
                    default_param_value = param.get('defaultParameterValue')
                    default_value = ''
                    if default_param_value and isinstance(default_param_value, dict):
                        default_value = default_param_value.get('value', '')
                    
                    parameters.append({
                        'name': param['name'],
                        'type': param.get('type', 'StringParameterDefinition'),
                        'description': param.get('description', ''),
                        'defaultValue': default_value
                    })
    return parameters

def trigger_job_with_params(job_name, params=None):
    headers = get_crumb()
    if params:
        url = f"{JENKINS_URL}/job/{job_name}/buildWithParameters"
        
        # Handle file parameters - Jenkins expects multipart/form-data for files
        files = {}
        data = {}
        
        for key, value in params.items():
            # Check if this looks like base64 encoded file content
            if isinstance(value, str) and len(value) > 1000 and value.replace('+', '').replace('/', '').replace('=', '').isalnum():
                # This is likely a base64 encoded file
                try:
                    file_content = base64.b64decode(value)
                    files[key] = ('file', file_content)
                except:
                    # If base64 decode fails, treat as regular parameter
                    data[key] = value
            else:
                data[key] = value
        
        if files:
            # Use files parameter for multipart upload
            res = requests.post(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN), 
                              headers=headers, data=data, files=files)
        else:
            # Regular form data
            res = requests.post(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN), 
                              headers=headers, data=data)
    else:
        url = f"{JENKINS_URL}/job/{job_name}/build"
        res = requests.post(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN), headers=headers)
    
    return res.status_code == 201

def download_and_encode_file(file_url, token):
    """Download file from Slack and encode to base64"""
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(file_url, headers=headers)
    response.raise_for_status()
    return base64.b64encode(response.content).decode()

def get_last_build_console_output(job_name):
    url = f"{JENKINS_URL}/job/{job_name}/lastBuild/consoleText"
    res = requests.get(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN))
    return res.text



#google sheet ki jagah console output
def extract_result_from_console(console_output):
    """Extract relevant results from console output dynamically"""
    results = []
    lines = console_output.split('\n')
    
    # Skip patterns
    skip_patterns = [
        r"^\[.*\]",  # [timestamp] messages
        r"^Started by",
        r"^Building",
        r"^Finished:",
        r"^Console output",
        r"^\+",  # Shell command indicators
        r"^>",   # Shell prompts
        r"^Archiving",
        r"^Recording",
        r"^Running",  # Jenkins job messages
        r"^Triggering",  # Trigger messages
        r"^Checking out",  # SCM checkout messages
        r"^Using strategy",  # SCM strategy messages
        r"^No changes",  # SCM no changes messages
        r"^Skipping",  # Skipping messages
        r"^Obtained.*from git",  # Git checkout messages
        r"^The recommended git tool",  # Git tool messages
        r"^using credential",  # Credential messages
        r"^Fetching.*from.*Git",  # Git fetch messages
        r"^using GIT_ASKPASS",  # Git auth messages
        r"^Commit message:",  # Git commit messages
        r"^Defaulting to user installation",  # pip messages
        r"^Requirement already satisfied:",  # pip requirement messages
        r"^Copying input files",  # File copy messages
        r"^Workspace contents:",  # Workspace listing
        r"^total \d+",  # ls total line
        r"^drwx",  # Directory listings
        r"^-rw-",  # File listings
        r"^/var/lib/jenkins/.*/site-packages/.*warning",  # Python warnings
        r"^warn\(",  # Warning function calls
        r"^Successfully converted.*\.xlsx to.*\.csv",  # File conversion messages
        r"^Successfully processed.*\.csv",  # CSV processing messages
        r"^All CSVs uploaded successfully"  # Upload completion messages
    ]

    
    # Extract everything that doesn't match skip patterns
    for line in lines:
        line = line.strip()
        if not line:  # Skip empty lines
            continue
            
        # Check if line matches any skip pattern
        should_skip = any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns)
        
        if not should_skip:
            # Check if line contains Google Doc URL - format it nicely
            if "docs.google.com" in line:
                url_match = re.search(r"https://docs\.google\.com/[^\s]+", line)
                if url_match:
                    results.append(f"🔗 {line}")
                else:
                    results.append(f"{line}")
            else:
                results.append(f"{line}")
    
    # Success indicator
    if "Finished: SUCCESS" in console_output:
        results.append("✅ Build completed successfully")
    
    return results if results else None

def wait_for_build_to_complete(job_name, timeout=180, interval=5):
    build_url = f"{JENKINS_URL}/job/{job_name}/lastBuild/api/json"
    
    for _ in range(int(timeout / interval)):
        res = requests.get(build_url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN))
        if res.status_code != 200:
            time.sleep(interval)
            continue
        data = res.json()
        if not data.get("building", True):
            return data.get("number")
        time.sleep(interval)
    
    return None

def wait_for_specific_build_to_complete(job_name, build_number, timeout=180, interval=5):
    build_url = f"{JENKINS_URL}/job/{job_name}/{build_number}/api/json"
    
    for _ in range(int(timeout / interval)):
        res = requests.get(build_url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN))
        if res.status_code != 200:
            time.sleep(interval)
            continue
        data = res.json()
        if not data.get("building", True):
            return build_number
        time.sleep(interval)
    
    return None

def get_specific_build_console_output(job_name, build_number):
    url = f"{JENKINS_URL}/job/{job_name}/{build_number}/consoleText"
    res = requests.get(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN))
    return res.text

