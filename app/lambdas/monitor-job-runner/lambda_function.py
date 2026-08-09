import boto3
import os
import json
import logging
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone
from common.job_status_client import JobStatusClient
from common_utils import send_to_sns

logger = logging.getLogger()
logger.setLevel(logging.INFO)
from common_utils import log_info, log_error

ec2 = boto3.client('ec2')


def _terminate_instance(instance_id, job_id, reason, slack_sns_topic_arn=None, job_type=None):
    """Terminate an EC2 instance and mark the job as failed.

    Returns a tuple ``(terminated, already_notified)``:
    - ``terminated``: True if the job was successfully marked as failed.
    - ``already_notified``: True if SNS was already sent (caller should skip its own notification).
    """
    try:
        # Check if instance is already terminated (e.g., spot interruption)
        try:
            instance_state = ec2.describe_instances(InstanceIds=[instance_id])
            state = instance_state['Reservations'][0]['Instances'][0].get('State', {}).get('Name', 'unknown')
            if state in ('shutting-down', 'terminated', 'stopping', 'stopped'):
                logger.info("Instance %s already in state '%s'. Marking job %s as failed.", instance_id, state, job_id)
                job_status = JobStatusClient()
                job_status.fail_job(job_id, f"SPOT_INTERRUPTION: Instance {instance_id} externally terminated (state: {state})")
                return True, False
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
                logger.info("Instance %s not found. Marking job %s as failed.", instance_id, job_id)
                job_status = JobStatusClient()
                job_status.fail_job(job_id, f"INSTANCE_NOT_FOUND: Instance {instance_id} no longer exists (likely externally terminated)")
                if slack_sns_topic_arn and job_type:
                    msg = f"\u26a0\ufe0f *Job Terminated*\n\n*Job ID:* {job_id}\n*Type:* {job_type}\n*Instance:* {instance_id}\n*Reason:* INSTANCE_NOT_FOUND - Instance no longer exists"
                    send_to_sns(msg, topic_arn=slack_sns_topic_arn)
                return True, True
            logger.warning("Could not check instance state for %s: %s", instance_id, str(e))
        except Exception as e:
            logger.warning("Could not check instance state for %s: %s", instance_id, str(e))

        logger.info("Terminating instance %s for job %s...", instance_id, job_id)
        ec2.terminate_instances(InstanceIds=[instance_id])

        # Mark job as failed in DynamoDB
        job_status = JobStatusClient()
        job_status.fail_job(job_id, f"TERMINATED_BY_MONITOR: {reason}")

        log_info("Successfully terminated instance %s and updated job %s.", instance_id, job_id)
        return True, False

    except Exception as e:
        log_error("Error terminating instance %s for job %s: %s", instance_id, job_id, str(e))
        return False, False


def lambda_handler(event, context):
    job_tracker_table = os.environ.get('JOB_TRACKER_TABLE_NAME')
    slack_sns_topic_arn = os.environ.get('SLACK_SNS_TOPIC_ARN')
    stalled_threshold_minutes = int(os.environ.get('STALLED_THRESHOLD_MINUTES', 10))
    max_lifetime_hours = int(os.environ.get('MAX_LIFETIME_HOURS', 8))

    if not job_tracker_table:
        log_error("JOB_TRACKER_TABLE_NAME environment variable is not set")
        return {'statusCode': 500, 'body': 'Missing JOB_TRACKER_TABLE_NAME'}
    if not slack_sns_topic_arn:
        log_error("SLACK_SNS_TOPIC_ARN environment variable is not set")
        return {'statusCode': 500, 'body': 'Missing SLACK_SNS_TOPIC_ARN'}

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(job_tracker_table)

    # Stalled threshold time
    stalled_threshold = (datetime.now(timezone.utc) - timedelta(minutes=stalled_threshold_minutes)).isoformat()
    # Max lifetime threshold
    max_lifetime_threshold = (datetime.now(timezone.utc) - timedelta(hours=max_lifetime_hours)).isoformat()

    logger.info(f"Checking for stalled jobs. Stalled threshold: {stalled_threshold}, Max lifetime threshold: {max_lifetime_threshold}")

    # Query for running jobs that haven't had a heartbeat since stalled_threshold
    # We use the GSI StatusHeartbeatIndex (PK: status, SK: last_heartbeat)
    response = table.query(
        IndexName='StatusHeartbeatIndex',
        KeyConditionExpression='status = :s AND last_heartbeat < :t',
        ExpressionAttributeValues={
            ':s': 'RUNNING',
            ':t': stalled_threshold
        }
    )

    items = response.get('Items', [])
    logger.info(f"Found {len(items)} potentially stalled jobs")

    terminated_count = 0

    for item in items:
        job_id = item['PK'].split('#')[1]
        instance_id = item.get('instance_id', 'Unknown')
        job_type = item.get('job_type', 'Unknown')
        start_time = item.get('start_time')

        # Determine termination reason
        reason = None
        if start_time and start_time < max_lifetime_threshold:
            reason = f"Max lifetime exceeded (started: {start_time})"
        else:
            reason = f"Stalled detected (last heartbeat: {item.get('last_heartbeat')})"

        logger.info(f"Job {job_id} ({job_type}) on instance {instance_id} flagged: {reason}")

        if instance_id and instance_id != 'PENDING':
            try:
                # Terminate the EC2 instance
                terminated, already_notified = _terminate_instance(instance_id, job_id, reason, slack_sns_topic_arn=slack_sns_topic_arn, job_type=job_type)
                if terminated and not already_notified:
                    terminated_count += 1
                    # Send Slack notification via SNS
                    message = f"\u26a0\ufe0f *Job Terminated*\n\n*Job ID:* {job_id}\n*Type:* {job_type}\n*Instance:* {instance_id}\n*Reason:* {reason}"
                    send_to_sns(message, topic_arn=slack_sns_topic_arn)
                    logger.info(f"Successfully terminated job {job_id} and notified Slack")
                elif terminated and already_notified:
                    logger.info(f"Successfully terminated job {job_id} (SNS already sent)")
                    terminated_count += 1

            except Exception as e:
                logger.error(f"Failed to process job {job_id}: {str(e)}")
        else:
            logger.warning("Job %s flagged but no valid instance_id found (or PENDING). Marking as failed.", job_id)
            try:
                job_status = JobStatusClient()
                job_status.fail_job(job_id, f"ORPHANED: No valid EC2 instance (instance_id={instance_id})")
                message = f"\u26a0\ufe0f *Job Terminated*\n\n*Job ID:* {job_id}\n*Type:* {job_type}\n*Instance:* {instance_id}\n*Reason:* ORPHANED - No valid EC2 instance found"
                send_to_sns(message, topic_arn=slack_sns_topic_arn)
                logger.info(f"Successfully marked job {job_id} as failed (orphaned)")
            except Exception as e:
                logger.error(f"Failed to mark job {job_id} as failed (orphaned): {str(e)}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Monitor scan complete',
            'terminated_count': terminated_count,
            'total_stalled_jobs': len(items)
        })
    }
