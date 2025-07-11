import os
import re
from flask import Flask, request
import requests
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from dotenv import load_dotenv
import base64
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import calendar

from jenkins_utils import (
    get_all_jobs, get_job_parameters, trigger_job_with_params,
    extract_result_from_console, wait_for_specific_build_to_complete,
    get_specific_build_console_output
)

load_dotenv()

slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

LOGGING_CHANNEL_ID = "C095E03Q5MW"

def log_jenkins_invocation(user_id, job_name):
    try:
        user_info = slack_app.client.users_info(user=user_id)
        display_name = user_info['user']['profile'].get('display_name') or user_info['user']['profile'].get('real_name') or user_info['user']['name']
        email = user_info['user']['profile'].get('email', 'N/A')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        log_message = f"<@{user_id}> invoked *jenkins-bot* for job `{job_name}` on {timestamp} (Email: {email})"
        slack_app.client.chat_postMessage(channel=LOGGING_CHANNEL_ID, text=log_message, mrkdwn=True)
    except Exception as e:
        print(f"Failed to log invocation: {str(e)}")

def is_date_parameter(param_name, param_description="", default_value=""):
    date_indicators = ['date', 'time', 'day', 'month', 'year', 'yyyy-mm-dd', 'yyyy/mm/dd']
    return (any(indicator in param_name.lower() for indicator in date_indicators) or
            any(indicator in param_description.lower() for indicator in date_indicators) or
            re.match(r'^\d{4}-\d{2}-\d{2}$', str(default_value)))

def create_input_element(param):
    if 'File' in param.get('type', ''):
        return {
            "type": "file_input",
            "action_id": param['name'],
            "filetypes": ["xlsx", "xls", "json", "csv", "txt"],
            "max_files": 1
        }
    elif is_date_parameter(param['name'], param.get('description', ''), param.get('defaultValue', '')):
        today = datetime.now()
        param_name_lower = param['name'].lower()
        
        if 'start' in param_name_lower:
            first_day_prev_month = today.replace(day=1) - timedelta(days=1)
            default_date = first_day_prev_month.replace(day=1).strftime('%Y-%m-%d')
        elif 'end' in param_name_lower:
            first_day_prev_month = today.replace(day=1) - timedelta(days=1)
            last_day_prev_month = calendar.monthrange(first_day_prev_month.year, first_day_prev_month.month)[1]
            default_date = first_day_prev_month.replace(day=last_day_prev_month).strftime('%Y-%m-%d')
        else:
            default_value = str(param.get('defaultValue', ''))
            default_date = default_value if re.match(r'^\d{4}-\d{2}-\d{2}$', default_value) else today.strftime('%Y-%m-%d')
        
        return {
            "type": "datepicker",
            "action_id": param['name'],
            "placeholder": {"type": "plain_text", "text": "Select a date"},
            "initial_date": default_date
        }
    else:
        return {
            "type": "plain_text_input",
            "action_id": param['name'],
            "initial_value": str(param.get('defaultValue', ''))
        }

def download_and_encode_file(file_url, token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(file_url, headers=headers)
    return base64.b64encode(response.content).decode()

flask_app = Flask(__name__)
handler = SlackRequestHandler(slack_app)

message_info = {}  # global handler for message info

@slack_app.command("/jenkins")
def handle_jenkins_command(ack, respond, command):
    ack()
    
    try:
        jobs = get_all_jobs()
        if not jobs:
            respond("No Jenkins jobs found.")
            return
        
        # Create job options for dropdown
        job_options = [{"text": {"type": "plain_text", "text": job}, "value": job} for job in jobs]
        
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Select Jenkins Job:*"},
                "accessory": {
                    "type": "static_select",
                    "action_id": "job_selected",
                    "placeholder": {"type": "plain_text", "text": "Choose a job..."},
                    "options": job_options
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Cancel"},
                        "action_id": "cancel_operation",
                        "style": "danger"
                    }
                ]
            }
        ]
        
        respond(blocks=blocks)
        
    except Exception as e:
        respond(f"Error fetching jobs: {str(e)}")

@slack_app.action("job_selected")
def handle_job_selection(ack, body, respond):
    ack()
    
    job_name = body["actions"][0]["selected_option"]["value"]
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    
    try:
        params = get_job_parameters(job_name)
        
        if not params:
            # No parameters - show run button
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Selected Job:* `{job_name}`\n_No parameters required_"}
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🚀 Run Job"},
                            "action_id": f"run_job_direct_{job_name}",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Cancel"},
                            "action_id": "cancel_operation",
                            "style": "danger"
                        }
                    ]
                }
            ]
            respond(blocks=blocks, replace_original=True)
        else:
            # Has parameters - show confirmation and open modal
            user_info = slack_app.client.users_info(user=user_id)
            
            # Replace original message with confirmation
            respond(f"<@{user_id}> invoked *jenkins-bot* for job `{job_name}`", replace_original=True)
            # Open modal for parameters
            modal_blocks = [
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Configure parameters for {job_name}:*"}}
            ]
            
            for param in params:
                modal_blocks.append({
                    "type": "input",
                    "block_id": f"param_{param['name']}",
                    "element": create_input_element(param),
                    "label": {"type": "plain_text", "text": f"{param['name']} ({param['type']})"}
                })
            
            slack_app.client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": f"submit_job_{job_name}",
                    "title": {"type": "plain_text", "text": "Job Parameters"},
                    "submit": {"type": "plain_text", "text": "Run Job"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "private_metadata": f"{channel_id}|{user_id}",
                    "blocks": modal_blocks
                }
            )
            
    except Exception as e:
        respond(f"Error: {str(e)}")

@slack_app.action(re.compile(r"run_job_direct_.*"))
def handle_direct_job_run(ack, body, respond):
    ack()
    
    job_name = body["actions"][0]["action_id"].replace("run_job_direct_", "")
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    
    # Show confirmation message
    user_info = slack_app.client.users_info(user=user_id)
    display_name = user_info['user']['profile'].get('display_name') or user_info['user']['profile'].get('real_name') or user_info['user']['name']
    respond(f"✅ {display_name} triggered Jenkins job `{job_name}`", replace_original=True)
    
    run_jenkins_job(job_name, {}, lambda msg: slack_app.client.chat_postMessage(channel=channel_id, text=msg), user_id)

@slack_app.action("cancel_operation")
def handle_cancel(ack, body, respond):
    ack()
    user_id = body["user"]["id"]
    
    # Clean up stored message info
    if user_id in message_info:
        del message_info[user_id]
    
    respond("❌ Operation cancelled.", replace_original=True)

@slack_app.view(re.compile(r"submit_job_.*"))
def handle_job_submission(ack, body, view):
    ack()
    
    job_name = body["view"]["callback_id"].replace("submit_job_", "")
    
    params = {}
    file_params = {}
    
    for block_id, block in view["state"]["values"].items():
        if block_id.startswith("param_"):
            param_name = block_id.replace("param_", "")
            action_data = list(block.values())[0]
            
            # Handle file inputs
            if "files" in action_data:
                files = action_data["files"]
                if files:
                    file_info = files[0]  # Take first file
                    token = os.environ.get("SLACK_BOT_TOKEN")
                    file_params[param_name] = download_and_encode_file(file_info["url_private"], token)
            else:
                # Handle regular inputs
                params[param_name] = action_data.get("value") or action_data.get("selected_date", "")
    
    # Combine regular and file parameters
    all_params = {**params, **file_params}
    
    # Extract channel and user from private_metadata
    metadata = view.get("private_metadata", "")
    if "|" in metadata:
        channel_id, user_id = metadata.split("|", 1)
    else:
        channel_id = body["user"]["id"]
        user_id = body["user"]["id"]
    
    # Don't update original message here - it was already updated
    run_jenkins_job(job_name, all_params, lambda msg: slack_app.client.chat_postMessage(channel=channel_id, text=msg), user_id)



def run_jenkins_job(job_name, params, respond_func, user_id=None):
    try:
        current_builds_url = f"{os.getenv('JENKINS_URL')}/job/{job_name}/api/json"
        response = requests.get(current_builds_url, auth=HTTPBasicAuth(os.getenv('JENKINS_USER'), os.getenv('JENKINS_API_TOKEN')))
        current_build_number = response.json().get('nextBuildNumber', 1)
        
        success = trigger_job_with_params(job_name, params)
        if not success:
            respond_func(f"Failed to trigger job: {job_name}")
            return
        
        if user_id:
            log_jenkins_invocation(user_id, job_name)
        
        respond_func(f"Job {job_name} triggered successfully. Waiting for completion...")
        
        build_number = wait_for_specific_build_to_complete(job_name, current_build_number)
        if not build_number:
            respond_func(f"Job {job_name} timed out or failed to complete.")
            return
        
        console_output = get_specific_build_console_output(job_name, build_number)
        results = extract_result_from_console(console_output)

        if results:
            result_text = f"✅ Job {job_name} completed!\n" + "\n".join(results)
            respond_func(result_text)
        else:
            respond_func(f"No Results found for job {job_name}. Please check the console output.")

    except Exception as e:
        respond_func(f"Error running job {job_name}: {str(e)}")

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("FLASK_PORT", 3000)), debug=True)
