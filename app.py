import os
import re
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from dotenv import load_dotenv
from jenkins_utils import (
    get_all_jobs, get_job_parameters, trigger_job_with_params,
    wait_for_build_to_complete, get_last_build_console_output,
    extract_google_doc_link
)

load_dotenv()

# Initialize Slack app
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

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
                    "element": {
                        "type": "plain_text_input",
                        "action_id": param['name'],
                        "initial_value": str(param.get('defaultValue', ''))
                    },
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
    params = {}
    for block_id, block in view["state"]["values"].items():
        if block_id.startswith("param_"):
            param_name = block_id.replace("param_", "")
            param_value = list(block.values())[0]["value"]
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
        # Trigger job
        success = trigger_job_with_params(job_name, params)
        if not success:
            respond_func(f"Failed to trigger job: {job_name}")
            return
        
        respond_func(f"Job {job_name} triggered successfully. Waiting for completion...")
        
        # Wait for completion
        build_number = wait_for_build_to_complete(job_name)
        if not build_number:
            respond_func(f"Job {job_name} timed out or failed to complete.")
            return
        
        # Get console output
        console_output = get_last_build_console_output(job_name)
        
        # Extract Google Doc link
        doc_link = extract_google_doc_link(console_output)
        
        if doc_link:
            respond_func(f"✅ Job {job_name} completed!\n🔗 Google Doc: {doc_link}")
        else:
            respond_func(f"✅ Job {job_name} completed, but no Google Doc link found in console output.")
            
    except Exception as e:
        respond_func(f"Error running job {job_name}: {str(e)}")

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