import boto3
import json
import base64
import os
import uuid
from common.job_status_client import JobStatusClient

ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    launch_template_id = os.environ.get('LAUNCH_TEMPLATE_ID')
    scripts_bucket = os.environ.get('JOB_SCRIPTS_BUCKET_NAME')
    job_script_name = os.environ.get('JOB_SCRIPT_NAME')
    job_tracker_table = os.environ.get('JOB_TRACKER_TABLE_NAME')

    print(f"Received event: {json.dumps(event)}")

    detail = event.get('detail', {})
    symbol = detail.get('symbol')
    timeframe = detail.get('timeframe')

    if not symbol or not timeframe:
        print("Error: Missing symbol or timeframe in event detail")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing symbol or timeframe in event detail'})
        }

    if not launch_template_id:
        print("Error: LAUNCH_TEMPLATE_ID environment variable is not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'LAUNCH_TEMPLATE_ID not set'})
        }

    if not scripts_bucket:
        print("Error: JOB_SCRIPTS_BUCKET_NAME environment variable is not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'JOB_SCRIPTS_BUCKET_NAME not set'})
        }

    if not job_script_name:
        print("Error: JOB_SCRIPT_NAME environment variable is not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'JOB_SCRIPT_NAME not set'})
        }

    if not job_tracker_table:
        print("Error: JOB_TRACKER_TABLE_NAME environment variable is not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'JOB_TRACKER_TABLE_NAME not set'})
        }

    # Generate a unique job ID
    job_id = str(uuid.uuid4())

    # Initialize Job Tracker
    try:
        job_status = JobStatusClient(job_tracker_table)
        job_status.start_job(
            job_id=job_id,
            job_type=job_script_name,
            instance_id="PENDING"  # Will be updated by the EC2 instance if possible, or just leave as PENDING for now
        )
    except Exception as e:
        print(f"Error initializing job tracker: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Failed to initialize job tracker: {str(e)}'})
        }

    # Construct UserData script
    # The script will download the TA job from S3
    full_user_data = f"""#!/bin/bash
# Update and install dependencies
yum update -y
yum install -y python3-pip aws-cli

# Install required python packages
pip3 install pandas numpy requests boto3

# Download the TA job script from S3
aws s3 cp s3://{scripts_bucket}/{job_script_name} /tmp/{job_script_name}

# Download the common utilities from S3
aws s3 cp s3://{scripts_bucket}/common/ /tmp/common/ --recursive

# Export PYTHONPATH so common can be found
export PYTHONPATH=$PYTHONPATH:/tmp

# Execute the TA job
python3 /tmp/{job_script_name} {symbol} {timeframe} {job_id}

# Shutdown the instance
sudo shutdown -h now
"""

    print(f"Launching EC2 instance with Launch Template: {launch_template_id}")

    try:
        response = ec2.run_instances(
            LaunchTemplate={'LaunchTemplateId': launch_template_id},
            MinCount=1,
            MaxCount=1,
            UserData=base64.b64encode(full_user_data.encode('utf-8')).decode('utf-8')
        )

        instance_id = response['Instances'][0]['InstanceId']
        print(f"Successfully launched instance: {instance_id}")

        # Update job tracker with the actual instance_id
        try:
            job_status.table.update_item(
                Key={'PK': f'JOB#{job_id}', 'SK': 'METADATA'},
                UpdateExpression="SET instance_id = :i",
                ExpressionAttributeValues={':i': instance_id}
            )
        except Exception as e:
            print(f"Warning: Failed to update instance_id in job tracker: {str(e)}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'EC2 instance launched successfully',
                'instance_id': instance_id,
                'job_id': job_id
            })
        }
    except Exception as e:
        print(f"Error launching EC2 instance: {str(e)}")
        # Mark job as failed if launch failed
        try:
            job_status.fail_job(job_id, f"EC2 Launch failed: {str(e)}")
        except:
            pass

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
