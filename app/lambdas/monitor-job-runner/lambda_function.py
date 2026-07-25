import boto3
import os
import logging
from datetime import datetime, timedelta, timezone
from common.job_status_client import JobStatusClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    job_tracker_table = os.environ.get('JOB_TRACKER_TABLE_NAME')
    slack_sns_topic_arn = os.environ.get('SLACK_SNS_TOPIC_ARN')
    stalled_threshold_minutes = int(os.environ.get('STALLED_THRESHOLD_MINUTES', 10))

    if not job_tracker_table:
        logger.error("JOB_TRACKER_TABLE_NAME environment variable is not set")
        return {'statusCode': 500, 'body': 'Missing JOB_TRACKER_TABLE_NAME'}
    if not slack_sns_topic_arn:
        logger.error("SLACK_SNS_TOPIC_ARN environment variable is not set")
        return {'statusCode': 500, 'body': 'Missing SLACK_SNS_TOPIC_ARN'}

    client = JobStatusClient(job_tracker_table)
    sns = boto3.client('sns')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(job_tracker_table)

    # Threshold time
    threshold_time = (datetime.now(timezone.utc) - timedelta(minutes=stalled_threshold_minutes)).isoformat()

    logger.info(f"Checking for stalled jobs. Threshold: {threshold_time}")

    # Query for running jobs that haven't had a heartbeat since threshold_time
    # We use the GSI StatusHeartbeatIndex (PK: status, SK: last_heartbeat)
    response = table.query(
        IndexName='StatusHeartbeatIndex',
        KeyConditionExpression='status = :s AND last_heartbeat < :t',
        ExpressionAttributeValues={
            ':s': 'RUNNING',
            ':t': threshold_time
        }
    )

    items = response.get('Items', [])
    logger.info(f"Found {len(items)} potentially stalled jobs")

    for item in items:
        job_id = item['PK'].split('#')[1]
        instance_id = item.get('instance_id', 'Unknown')
        job_type = item.get('job_type', 'Unknown')

        logger.info(f"Marking job {job_id} ({job_type}) on instance {instance_id} as STALLED")

        # 1. Update status to STALLED
        try:
            table.update_item(
                Key={'PK': item['PK'], 'SK': item['SK']},
                UpdateExpression="SET status = :s",
                ExpressionAttributeValues={':s': 'STALLED'}
            )

            # 2. Send Slack notification via SNS
            message = f"⚠️ *Job Stalled Detected*\n\n*Job ID:* {job_id}\n*Type:* {job_type}\n*Instance:* {instance_id}\n*Last Heartbeat:* {item.get('last_heartbeat')}"
            sns.publish(
                TopicArn=slack_sns_topic_arn,
                Message=message
            )
            logger.info(f"Successfully marked job {job_id} as STALLED and notified Slack")

        except Exception as e:
            logger.error(f"Failed to process stalled job {job_id}: {str(e)}")

    return {
        'statusCode': 200,
        'body': f"Processed {len(items)} stalled jobs"
    }
