import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
import time
import re
import base64

load_dotenv(override=True)

# Constants
JENKINS_URL = os.getenv("JENKINS_URL")
JENKINS_USER = os.getenv("JENKINS_USER") 
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN")
AUTH = HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN)

def get_crumb():
    """Get Jenkins CSRF crumb"""
    response = requests.get(f"{JENKINS_URL}/crumbIssuer/api/json", auth=AUTH)
    response.raise_for_status()
    data = response.json()
    return {data['crumbRequestField']: data['crumb']}

def get_all_jobs():
    """Get list of all Jenkins job names"""
    response = requests.get(f"{JENKINS_URL}/api/json", auth=AUTH, headers=get_crumb())
    response.raise_for_status()
    return [job['name'] for job in response.json().get("jobs", [])]

def get_job_parameters(job_name):
    """Get parameters for a specific Jenkins job"""
    response = requests.get(f"{JENKINS_URL}/job/{job_name}/api/json", auth=AUTH)
    response.raise_for_status()
    data = response.json()
    
    parameters = []
    # Search in both actions and property arrays
    for source in [*data.get('actions', []), *data.get('property', [])]:
        if source.get('_class') == 'hudson.model.ParametersDefinitionProperty':
            for param in source.get('parameterDefinitions', []):
                default_param_value = param.get('defaultParameterValue')
                default_value = default_param_value.get('value', '') if default_param_value and isinstance(default_param_value, dict) else ''
                
                param_info = {
                    'name': param['name'],
                    'type': param.get('type', 'StringParameterDefinition'),
                    'description': param.get('description', ''),
                    'defaultValue': default_value
                }
                
                # Add choices for ChoiceParameterDefinition
                if param.get('type') == 'ChoiceParameterDefinition':
                    param_info['choices'] = param.get('choices', [])
                
                parameters.append(param_info)
    return parameters


def trigger_job_with_params(job_name, params=None):
    """Trigger Jenkins job with optional parameters"""
    headers = get_crumb()
    
    if params:
        url = f"{JENKINS_URL}/job/{job_name}/buildWithParameters"
        files, data = {}, {}
        
        for key, value in params.items():
            # Detect base64 encoded files (heuristic: long string with base64 chars)
            if (isinstance(value, str) and len(value) > 1000 and 
                value.replace('+', '').replace('/', '').replace('=', '').isalnum()):
                try:
                    files[key] = ('file', base64.b64decode(value))
                except:
                    data[key] = value
            else:
                data[key] = value
        
        response = requests.post(url, auth=AUTH, headers=headers, data=data, files=files or None)
    else:
        response = requests.post(f"{JENKINS_URL}/job/{job_name}/build", auth=AUTH, headers=headers)
    
    return response.status_code == 201

def extract_result_from_console(console_output):
    """Extract meaningful results from Jenkins console output"""
    if not console_output:
        return None
        
    # Patterns to skip (Jenkins noise)
    skip_patterns = [
        r"^\[.*\]", r"^Started by", r"^Building", r"^Finished:", r"^Console output",
        r"^\+", r"^>", r"^Archiving", r"^Recording", r"^Running", r"^Triggering",
        r"^Checking out", r"^Using strategy", r"^No changes", r"^Skipping",
        r"^Obtained.*from git", r"^The recommended git tool", r"^using credential",
        r"^Fetching.*from.*Git", r"^using GIT_ASKPASS", r"^Commit message:",
        r"^Defaulting to user installation", r"^Requirement already satisfied:",
        r"^Copying input files", r"^Workspace contents:", r"^total \d+",
        r"^drwx", r"^-rw-", r"^/var/lib/jenkins/.*/site-packages/.*warning",
        r"^warn\(", r"^Successfully converted.*\.xlsx to.*\.csv",
        r"^Successfully processed.*\.csv", r"^All CSVs uploaded successfully"
    ]
    
    results = []
    for line in console_output.split('\n'):
        line = line.strip()
        if line and not any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            results.append(f"🔗 {line}" if "docs.google.com" in line else line)
    
    if "Finished: SUCCESS" in console_output:
        results.append("✅ Build completed successfully")
    
    return results or None

def wait_for_specific_build_to_complete(job_name, build_number, timeout=180, interval=5):
    """Wait for a specific Jenkins build to complete"""
    build_url = f"{JENKINS_URL}/job/{job_name}/{build_number}/api/json"
    
    for _ in range(timeout // interval):
        response = requests.get(build_url, auth=AUTH)
        if response.status_code == 200:
            data = response.json()
            if not data.get("building", True):
                return build_number
        time.sleep(interval)
    
    return None

def get_specific_build_console_output(job_name, build_number):
    """Get console output for a specific Jenkins build"""
    response = requests.get(f"{JENKINS_URL}/job/{job_name}/{build_number}/consoleText", auth=AUTH)
    return response.text
