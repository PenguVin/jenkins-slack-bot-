import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
import time
import re
import base64

load_dotenv(override=True)

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
    for source in [data.get('actions', []), data.get('property', [])]:
        for item in source:
            if item.get('_class') == 'hudson.model.ParametersDefinitionProperty':
                for param in item.get('parameterDefinitions', []):
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
        files, data = {}, {}
        
        for key, value in params.items():
            if isinstance(value, str) and len(value) > 1000 and value.replace('+', '').replace('/', '').replace('=', '').isalnum():
                try:
                    file_content = base64.b64decode(value)
                    files[key] = ('file', file_content)
                except:
                    data[key] = value
            else:
                data[key] = value
        
        res = requests.post(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN), 
                          headers=headers, data=data, files=files if files else None)
    else:
        url = f"{JENKINS_URL}/job/{job_name}/build"
        res = requests.post(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN), headers=headers)
    
    return res.status_code == 201

def extract_result_from_console(console_output):
    results = []
    lines = console_output.split('\n')
    
    skip_patterns = [
        r"^\[.*\]", 
        r"^Started by", 
        r"^Building", 
        r"^Finished:", 
        r"^Console output",
        r"^\+", 
        r"^>", 
        r"^Archiving", 
        r"^Recording", 
        r"^Running", 
        r"^Triggering",
        r"^Checking out", 
        r"^Using strategy", 
        r"^No changes", 
        r"^Skipping",
        r"^Obtained.*from git", 
        r"^The recommended git tool", 
        r"^using credential",
        r"^Fetching.*from.*Git", 
        r"^using GIT_ASKPASS", r"^Commit message:",
        r"^Defaulting to user installation", 
        r"^Requirement already satisfied:",
        r"^Copying input files", 
        r"^Workspace contents:", 
        r"^total \d+",
        r"^drwx", 
        r"^-rw-", 
        r"^/var/lib/jenkins/.*/site-packages/.*warning",
        r"^warn\(", 
        r"^Successfully converted.*\.xlsx to.*\.csv",
        r"^Successfully processed.*\.csv", 
        r"^All CSVs uploaded successfully"
    ]
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        should_skip = any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns)
        
        if not should_skip:
            if "docs.google.com" in line:
                results.append(f"🔗 {line}")
            else:
                results.append(line)
    
    if "Finished: SUCCESS" in console_output:
        results.append("✅ Build completed successfully")
    
    return results if results else None

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
