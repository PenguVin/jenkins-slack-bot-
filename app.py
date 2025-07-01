import os
import re
from flask import Flask, request
import requests
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from dotenv import load_dotenv
import base64
from flask import render_template_string
from requests.auth import HTTPBasicAuth



from jenkins_utils import (
    get_all_jobs, get_job_parameters, trigger_job_with_params,
    wait_for_build_to_complete, get_last_build_console_output,
    extract_google_doc_link, wait_for_specific_build_to_complete,
    get_specific_build_console_output
)


load_dotenv()

# Initialize Slack app
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

def is_date_parameter(param_name, param_description="", default_value=""):
    """Check if parameter is a date parameter"""
    date_indicators = ['date', 'time', 'day', 'month', 'year', 'yyyy-mm-dd', 'yyyy/mm/dd']
    
    if any(indicator in param_name.lower() for indicator in date_indicators):
        return True
    if any(indicator in param_description.lower() for indicator in date_indicators):
        return True
    if re.match(r'^\d{4}-\d{2}-\d{2}$', str(default_value)):
        return True
    
    return False

def create_input_element(param):
    """Create appropriate input element based on parameter type"""
    if is_date_parameter(param['name'], param.get('description', ''), param.get('defaultValue', '')):
        element = {
            "type": "datepicker",
            "action_id": param['name'],
            "placeholder": {"type": "plain_text", "text": "Select a date"}
        }
        
        default_value = str(param.get('defaultValue', ''))
        if re.match(r'^\d{4}-\d{2}-\d{2}$', default_value):
            element["initial_date"] = default_value
        
        return element
    else:
        return {
            "type": "plain_text_input",
            "action_id": param['name'],
            "initial_value": str(param.get('defaultValue', ''))
        }


# Initialize Flask app
flask_app = Flask(__name__)
handler = SlackRequestHandler(slack_app)

@slack_app.command("/jenkins")
def handle_jenkins_command(ack, respond, command):
    ack()
    
    try:
        jobs = get_all_jobs()
        if not jobs:
            respond("No Jenkins jobs found.")
            return
        
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Available Jenkins Jobs:*"}
            }
        ]
        
        for job in jobs:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"• {job}"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Run Job"},
                    "action_id": f"run_job_{job}",
                    "value": job
                }
            })
        
        respond(blocks=blocks)
    except Exception as e:
        respond(f"Error fetching jobs: {str(e)}")

@slack_app.action(re.compile(r"run_job_.*"))
def handle_run_job(ack, body, respond):
    ack()
    
    job_name = body["actions"][0]["value"]
    
    try:
        # Check if job has parameters
        params = get_job_parameters(job_name)
        
        if params:
            # Check if job has file parameters
            has_file_params = any('File' in param.get('type', '') for param in params)
            
            if has_file_params:
                respond(f"📁 This job requires file uploads. Use one of these options:\n" +
                f"• Upload files to this channel, then use: `/jenkins-file {job_name}`\n" +
                f"• Web upload: https://db65-61-12-91-218.ngrok-free.app/upload/{job_name}")

                return

            # Show parameter form
            modal_blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Configure parameters for {job_name}:*"}
                }
            ]
            
            for param in params:
                modal_blocks.append({
                    "type": "input",
                    "block_id": f"param_{param['name']}",
                    "element": create_input_element(param),
                    "label": {
                        "type": "plain_text",
                        "text": f"{param['name']} ({param['type']})"
                    }
                })

            
            slack_app.client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": f"submit_job_{job_name}",
                    "title": {"type": "plain_text", "text": "Job Parameters"},
                    "submit": {"type": "plain_text", "text": "Run Job"},
                    "blocks": modal_blocks
                }
            )
        else:
            # Run job without parameters
            run_jenkins_job(job_name, {}, respond)
            
    except Exception as e:
        respond(f"Error: {str(e)}")

@slack_app.view(re.compile(r"submit_job_.*"))

def handle_job_submission(ack, body, view):
    ack()
    
    job_name = body["view"]["callback_id"].replace("submit_job_", "")
    
    # Extract parameters from form
    # Extract parameters from form
    params = {}
    for block_id, block in view["state"]["values"].items():
        if block_id.startswith("param_"):
            param_name = block_id.replace("param_", "")
            action_data = list(block.values())[0]
            
            # Handle both text input and datepicker
            if "value" in action_data:
                param_value = action_data["value"]  # Text input
            elif "selected_date" in action_data:
                param_value = action_data["selected_date"]  # Date picker
            else:
                param_value = ""
            
            params[param_name] = param_value

    # Send initial response
    channel_id = body["user"]["id"]
    slack_app.client.chat_postMessage(
        channel=channel_id,
        text=f"Starting Jenkins job: {job_name}..."
    )
    
    # Run job in background
    run_jenkins_job(job_name, params, lambda msg: slack_app.client.chat_postMessage(
        channel=channel_id, text=msg
    ))

def run_jenkins_job(job_name, params, respond_func):
    try:
        # Get current build number before triggering
        current_builds_url = f"{os.getenv('JENKINS_URL')}/job/{job_name}/api/json"
        response = requests.get(current_builds_url, auth=HTTPBasicAuth(os.getenv('JENKINS_USER'), os.getenv('JENKINS_API_TOKEN')))
        current_build_number = response.json().get('nextBuildNumber', 1)
        
        # Trigger job
        success = trigger_job_with_params(job_name, params)
        if not success:
            respond_func(f"Failed to trigger job: {job_name}")
            return
        
        respond_func(f"Job {job_name} triggered successfully. Waiting for completion...")
        
        # Wait for the SPECIFIC build to complete
        build_number = wait_for_specific_build_to_complete(job_name, current_build_number)
        if not build_number:
            respond_func(f"Job {job_name} timed out or failed to complete.")
            return
        
        # Get console output for the SPECIFIC build
        console_output = get_specific_build_console_output(job_name, build_number)
        
        # Extract Google Doc link
        doc_link = extract_google_doc_link(console_output)
        
        if doc_link:
            respond_func(f"✅ Job {job_name} completed!\n🔗 Google Doc: {doc_link}")
        else:
            respond_func(f"✅ Job {job_name} completed, but no Google Doc link found in console output.")
            
    except Exception as e:
        respond_func(f"Error running job {job_name}: {str(e)}")


# Add after existing imports
def download_and_encode_file(file_url, token):
    """Download file from Slack and encode to base64"""
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(file_url, headers=headers)
    return base64.b64encode(response.content).decode()

# Add new command for file-based jobs
@slack_app.command("/jenkins-file")
def handle_file_jenkins_command(ack, respond, command, client):
    ack()
    
    job_name = command['text'].strip()
    if not job_name:
        respond("Usage: `/jenkins-file <job_name>`")
        return
    
    try:
        # Get recent files from channel
        channel_id = command['channel_id']
        files_response = client.files_list(channel=channel_id, count=10)
        files = files_response['files']
        
        if len(files) < 2:
            respond("Please upload 2 files first (Excel + JSON), then use this command.")
            return
        
        # Get the 2 most recent files
        excel_file = files[0]  # Most recent
        json_file = files[1]   # Second most recent
        
        # Download and encode files
        token = os.environ.get("SLACK_BOT_TOKEN")
        excel_content = download_and_encode_file(excel_file['url_private'], token)
        json_content = download_and_encode_file(json_file['url_private'], token)
        
        # Use correct parameter names
        params = {
            'INPUT_XLSX': excel_content,
            'SERVICE_ACCOUNT_JSON': json_content
        }
        
        # Send initial response
        respond(f"🚀 Starting Jenkins job: {job_name} with uploaded files...")
        
        # Get user ID for direct messages
        user_id = command['user_id']
        
        # Use the same job runner as regular jobs to get Google Doc link
        run_jenkins_job(job_name, params, lambda msg: client.chat_postMessage(
            channel=user_id, text=msg
        ))
        
    except Exception as e:
        respond(f"Error: {str(e)}")

# Add file upload web interface
@flask_app.route("/upload/<job_name>", methods=["GET", "POST"])
def upload_files(job_name):
    if request.method == "GET":
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head><title>Upload Files for {{job_name}}</title></head>
        <body>
            <h2>Upload Files for Jenkins Job: {{job_name}}</h2>
            <form method="POST" enctype="multipart/form-data">
                <p>Excel File: <input type="file" name="excel_file" accept=".xlsx,.xls" required></p>
                <p>JSON File: <input type="file" name="json_file" accept=".json" required></p>
                <p><button type="submit">Trigger Job</button></p>
            </form>
        </body>
        </html>
        """, job_name=job_name)
    
    try:
        # Process uploaded files
        excel_file = request.files['excel_file']
        json_file = request.files['json_file']
        
        params = {
            'INPUT_XLSX': base64.b64encode(excel_file.read()).decode(),
            'SERVICE_ACCOUNT_JSON': base64.b64encode(json_file.read()).decode()
        }
        
        success = trigger_job_with_params(job_name, params)
        
        if success:
            return f"<h2>✅ Job {job_name} triggered successfully!</h2>"
        else:
            return f"<h2>❌ Failed to trigger job {job_name}</h2>"
            
    except Exception as e:
        return f"<h2>Error: {str(e)}</h2>"


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

@flask_app.route("/health", methods=["GET"])
def health_check():
    return {"status": "healthy"}, 200

if __name__ == "__main__":
    flask_app.run(
        host="0.0.0.0",
        port=int(os.environ.get("FLASK_PORT", 3000)),
        debug=True
    )