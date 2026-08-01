import boto3
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from common.job_status_client import JobStatusClient

logger = logging.getLogger(__name__)

ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    # Configuration
    # Defaults to 30 mins inactivity and 8 hours max lifetime
    max_inactivity_minutes = int(os.environ.get('MAX_INACTIVITY_MINUTES', 30))
    max_lifetime_hours = int(os.environ.get('MAX_LIFETIME_HOURS', 8))

    logger.info("Starting Reaper scan. Thresholds: Inactivity=%dm, MaxLifetime=%dh", max_inactivity_minutes, max_lifetime_hours)

    try:
        job_status = JobStatusClient()
        running_jobs = job_status.get_running_jobs()
    except Exception as e:
        logger.error("Error fetching running jobs: %s", str(e))
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

    if not running_jobs:
        logger.info("No running jobs found.")
        return {'statusCode': 200, 'body': json.dumps({'message': 'No running jobs to check'})}

    now = datetime.now(timezone.utc)
    terminated_count = 0

    for job in running_jobs:
        job_id = job['PK'].replace('JOB#', '')
        instance_id = job.get('instance_id')
        start_time_str = job.get('start_time')
        last_heartbeat_str = job.get('last_heartbeat')

        if not start_time_str or not last_heartbeat_str:
            logger.warning("Job %s has missing timestamps. Skipping.", job_id)
            continue

        # Parse ISO timestamps
        # Replacing Z with +00:00 if necessary, though isoformat() usually uses +00:00
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        last_heartbeat = datetime.fromisoformat(last_heartbeat_str.replace('Z', '+00:00'))

        reason = None

        # Check Inactivity
        if (now - last_heartbeat) > timedelta(minutes=max_inactivity_minutes):
            reason = f"Inactivity detected (last heartbeat: {last_heartbeat_str})"

        # Check Max Lifetime
        elif (now - start_time) > timedelta(hours=max_lifetime_hours):
            reason = f"Max lifetime exceeded (started: {start_time_str})"

        if reason:
            logger.info("Job %s flagged for termination: %s", job_id, reason)

            if instance_id and instance_id != "PENDING":
                try:
                    logger.info("Terminating instance %s for job %s...", instance_id, job_id)
                    ec2.terminate_instances(InstanceIds=[instance_id])

                    # Mark job as failed in DynamoDB
                    job_status.fail_job(job_id, f"TERMINATED_BY_REAPER: {reason}")

                    logger.info("Successfully terminated instance %s and updated job %s.", instance_id, job_id)
                    terminated_count += 1
                except Exception as e:
                    logger.error("Error terminating instance %s for job %s: %s", instance_id, job_id, str(e))
            else:
                logger.warning("Job %s flagged but no valid instance_id found (or PENDING). Skipping termination.", job_id)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Reaper scan complete',
            'terminated_count': terminated_count,
            'total_running_jobs': len(running_jobs)
        })
    }
