from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import json
import datetime

def schedule_email_reminder(email, title, due_datetime, description):
    client = tasks_v2.CloudTasksClient()
    
    project = "tempraai-67830"
    queue = "ReminderEmails"
    location = "us-central1"
    url = "http://localhost:5173/emails/send-email-reminder"  # Make public or secure with token

    parent = client.queue_path(project, location, queue)

    # Run time = 10 minutes before due_datetime
    schedule_time = due_datetime - datetime.timedelta(minutes=10)

    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(schedule_time)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": {"Content-type": "application/json"},
            "body": json.dumps({
                "email": email,
                "title": title,
                "description": description,
                "due_datetime": due_datetime.isoformat()
            }).encode()
        },
        "schedule_time": timestamp,
    }

    response = client.create_task(request={"parent": parent, "task": task})
    print("Scheduled email reminder:", response.name)
