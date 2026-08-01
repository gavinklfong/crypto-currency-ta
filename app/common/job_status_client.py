import boto3
import os
import threading
from datetime import datetime, timezone

JOB_TRACKER_TABLE_NAME = "crypto-currency-ta-job-tracker"

class JobStatusClient:
    def __init__(self, table_name=None):
        region = os.environ.get('AWS_DEFAULT_REGION') or os.environ.get('AWS_REGION')
        session_kwargs = {}
        if region:
            session_kwargs['region_name'] = region
        self.dynamodb = boto3.resource('dynamodb', **session_kwargs)
        self.table_name = table_name or JOB_TRACKER_TABLE_NAME
        if not self.table_name:
            raise ValueError("Table name must be provided or JOB_TRACKER_TABLE_NAME must be set")
        self.table = self.dynamodb.Table(self.table_name)

    def start_job(self, job_id, job_type, instance_id):
        """Initialize a new job record."""
        now = datetime.now(timezone.utc).isoformat()
        self.table.put_item(
            Item={
                'PK': f'JOB#{job_id}',
                'SK': 'METADATA',
                'status': 'RUNNING',
                'job_type': job_type,
                'instance_id': instance_id,
                'start_time': now,
                'last_heartbeat': now,
                'progress': 0
            }
        )

    def heartbeat(self, job_id):
        """Update the last heartbeat timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        self.table.update_item(
            Key={'PK': f'JOB#{job_id}', 'SK': 'METADATA'},
            UpdateExpression="SET last_heartbeat = :now",
            ExpressionAttributeValues={':now': now}
        )

    def report_progress(self, job_id, progress):
        """Update the progress percentage (0-100)."""
        self.table.update_item(
            Key={'PK': f'JOB#{job_id}', 'SK': 'METADATA'},
            UpdateExpression="SET progress = :p, last_heartbeat = :now",
            ExpressionAttributeValues={
                ':p': progress,
                ':now': datetime.now(timezone.utc).isoformat()
            }
        )

    def report_progress_with_detail(self, job_id, progress, detail):
        """Update the progress percentage (0-100) and provide additional detail."""
        self.table.update_item(
            Key={'PK': f'JOB#{job_id}', 'SK': 'METADATA'},
            UpdateExpression="SET progress = :p, progress_detail = :d, last_heartbeat = :now",
            ExpressionAttributeValues={
                ':p': progress,
                ':d': detail,
                ':now': datetime.now(timezone.utc).isoformat()
            }
        )

    def complete_job(self, job_id):
        """Mark the job as completed."""
        now = datetime.now(timezone.utc).isoformat()
        self.table.update_item(
            Key={'PK': f'JOB#{job_id}', 'SK': 'METADATA'},
            UpdateExpression="SET #st = :s, end_time = :now, progress = :p",
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={
                ':s': 'COMPLETED',
                ':now': now,
                ':p': 100
            }
        )

    def fail_job(self, job_id, reason):
        """Mark the job as failed with a reason."""
        now = datetime.now(timezone.utc).isoformat()
        self.table.update_item(
            Key={'PK': f'JOB#{job_id}', 'SK': 'METADATA'},
            UpdateExpression="SET #st = :s, end_time = :now, progress = :p, failure_reason = :e",
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={
                ':s': 'FAILED',
                ':now': now,
                ':p': 0,
                ':e': reason
            }
        )

    def get_running_jobs(self):
        """Returns a list of all currently running jobs using the StatusStartTimeIndex GSI."""
        running_jobs = []
        query_kwargs = {
            'IndexName': 'StatusStartTimeIndex',
            'KeyConditionExpression': '#s = :status',
            'ExpressionAttributeNames': {'#s': 'status'},
            'ExpressionAttributeValues': {':status': 'RUNNING'}
        }

        while True:
            response = self.table.query(**query_kwargs)
            running_jobs.extend(response.get('Items', []))

            if 'LastEvaluatedKey' not in response:
                break
            query_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

        return running_jobs

class HeartbeatThread(threading.Thread):
    def __init__(self, client, job_id, interval=60):
        super().__init__()
        self.client = client
        self.job_id = job_id
        self.interval = interval
        self.stop_event = threading.Event()

    def run(self):
        print(f"Heartbeat thread started for job {self.job_id} (interval={self.interval}s)")
        while not self.stop_event.is_set():
            try:
                self.client.heartbeat(self.job_id)
            except Exception as e:
                print(f"Heartbeat failed: {str(e)}")

            self.stop_event.wait(self.interval)
        print(f"Heartbeat thread stopped for job {self.job_id}")

    def stop(self):
        self.stop_event.set()
