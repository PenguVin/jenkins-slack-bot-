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

def extract_google_doc_link(console_output):
    match = re.search(r"https://docs\.google\.com/[^\s]+", console_output)
    return match.group(0) if match else None

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

