import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
import time
import re

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
                    parameters.append({
                        'name': param['name'],
                        'type': param.get('type', 'StringParameterDefinition'),
                        'description': param.get('description', ''),
                        'defaultValue': param.get('defaultParameterValue', {}).get('value', '')
                    })
    return parameters


def trigger_job_with_params(job_name, params=None):
    headers = get_crumb()
    if params:
        url = f"{JENKINS_URL}/job/{job_name}/buildWithParameters"
        res = requests.post(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN), 
                          headers=headers, data=params)
    else:
        url = f"{JENKINS_URL}/job/{job_name}/build"
        res = requests.post(url, auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN), headers=headers)
    return res.status_code == 201

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