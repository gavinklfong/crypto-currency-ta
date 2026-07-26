import boto3
import os
import json
from datetime import datetime, timezone, timedelta
from common.job_status_client import JobStatusClient

ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    # Configuration
    # Defaults to 30 mins inactivity and 8 hours max lifetime
    max_inactivity_minutes = int(os.environ.get('MAX_INACTIVITY_MINUTES', 30))
    max_lifetime_hours = int(os.environ.get('MAX_LIFETIME_HOURS', 8))

    print(f"Starting Reaper scan. Thresholds: Inactivity={max_inactivity_minutes}m, MaxLifetime={max_lifetime_hours}h")

    try:
        job_status = JobStatusClient()
        running_jobs = job_status.get_running_jobs()
    except Exception as e:
        print(f"Error fetching running jobs: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

    if not running_jobs:
        print("No running jobs found.")
        return {'statusCode': 200, 'body': json.dumps({'message': 'No running jobs to check'})}

    now = datetime.now(timezone.utc)
    terminated_count = 0

    for job in running_jobs:
        job_id = job['PK'].replace('JOB#', '')
        instance_id = job.get('instance_id')
        start_time_str = job.get('start_time')
        last_heartbeat_str = job.get('last_heartbeat')

        if not start_time_str or not last_heartbeat_str:
            print(f"Job {job_id} has missing timestamps. Skipping.")
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
            print(f"Job {job_id} flagged for termination: {reason}")

            if instance_id and instance_id != "PENDING":
                try:
                    print(f"Terminating instance {instance_id} for job {job_id}...")
                    ec2.terminate_instances(InstanceIds=[instance_id])

                    # Mark job as failed in DynamoDB
                    job_status.fail_job(job_id, f"TERMINATED_BY_REAPER: {reason}")

                    print(f"Successfully terminated instance {instance_id} and updated job {job_id}.")
                    terminated_count += 1
                except Exception as e:
                    print(f"Error terminating instance {instance_id} for job {job_id}: {str(e)}")
            else:
                print(f"Job {job_id} flagged but no valid instance_id found (or PENDING). Skipping termination.")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Reaper scan complete',
            'terminated_count': terminated_count,
            'total_running_jobs': len(running_jobs)
        })
    }
