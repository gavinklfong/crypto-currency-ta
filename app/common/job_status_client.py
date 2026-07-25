import boto3
import os
from datetime import datetime, timezone

class JobStatusClient:
    def __init__(self, table_name=None):
        self.dynamodb = boto3.resource('dynamodb')
        self.table_name = table_name or os.environ.get('JOB_TRACKER_TABLE_NAME')
        if not self.table_name:
            raise ValueError("JOB_TRACKER_TABLE_NAME environment variable must be set")
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

    def complete_job(self, job_id):
        """Mark the job as completed."""
        now = datetime.now(timezone.utc).isoformat()
        self.table.update_item(
            Key={'PK': f'JOB#{job_id}', 'SK': 'METADATA'},
            UpdateExpression="SET status = :s, end_time = :now, progress = :p",
            ExpressionAttributeValues={
                ':s': 'COMPLETED',
                ':now': now,
                ':p': 100
            }
        )

    def fail_job(self, job_id, error_msg):
        """Mark the job as failed."""
        now = datetime.now(timezone.utc).isoformat()
        self.table.update_item(
            Key={'PK': f'JOB#{job_id}', 'SK': 'METADATA'},
            UpdateExpression="SET status = :s, end_time = :now, error_msg = :e",
            ExpressionAttributeValues={
                ':s': 'FAILED',
                ':now': now,
                ':e': error_msg
            }
        )
