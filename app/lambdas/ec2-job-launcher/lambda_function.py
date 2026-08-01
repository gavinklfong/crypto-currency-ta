import boto3
import json
import base64
import os
import uuid
import logging
from common.job_status_client import JobStatusClient

logger = logging.getLogger(__name__)

ec2 = boto3.client('ec2')

INSTANCE_TYPE_MAP = {
    "small": "t3.small",
    "medium": "t3.medium",
    "large": "t3.large"
}

def lambda_handler(event, context):
    launch_template_id = os.environ.get('LAUNCH_TEMPLATE_ID')
    scripts_bucket = os.environ.get('JOB_SCRIPTS_BUCKET_NAME')
    job_script_name = os.environ.get('JOB_SCRIPT_NAME')
    default_instance_type_key = os.environ.get('INSTANCE_TYPE', 'small')

    logger.info("Received event: %s", json.dumps(event))

    detail = event.get('detail', {})
    symbol = detail.get('symbol')
    timeframe = detail.get('timeframe')
    event_instance_type_key = detail.get('instance_type')

    if not symbol or not timeframe:
        logger.error("Error: Missing symbol or timeframe in event detail")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing symbol or timeframe in event detail'})
        }

    if not launch_template_id:
        logger.error("Error: LAUNCH_TEMPLATE_ID environment variable is not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'LAUNCH_TEMPLATE_ID not set'})
        }

    if not scripts_bucket:
        logger.error("Error: JOB_SCRIPTS_BUCKET_NAME environment variable is not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'JOB_SCRIPTS_BUCKET_NAME not set'})
        }

    if not job_script_name:
        logger.error("Error: JOB_SCRIPT_NAME environment variable is not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'JOB_SCRIPT_NAME not set'})
        }

    # Resolve instance type
    instance_type_key = event_instance_type_key or default_instance_type_key
    aws_instance_type = INSTANCE_TYPE_MAP.get(instance_type_key, INSTANCE_TYPE_MAP['small'])
    logger.info("Selected instance type: %s (from key: %s)", aws_instance_type, instance_type_key)

    # Generate a unique job ID
    job_id = str(uuid.uuid4())

    # Initialize Job Tracker
    try:
        job_status = JobStatusClient()
        job_status.start_job(
            job_id=job_id,
            job_type=job_script_name,
            instance_id="PENDING"  # Will be updated by the EC2 instance if possible, or just leave as PENDING for now
        )
    except Exception as e:
        logger.error("Error initializing job tracker: %s", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Failed to initialize job tracker: {str(e)}'})
        }

    region = boto3.session.Session().region_name

    # Construct UserData script
    # The script will download the TA job directory from S3
    full_user_data = f"""#!/bin/bash
# Update and install dependencies
yum update -y
yum install -y python3-pip aws-cli

# Download the TA job directory from S3
echo "aws s3 cp s3://{scripts_bucket}/{job_script_name}/ /tmp/{job_script_name}/ --recursive"
aws s3 cp s3://{scripts_bucket}/{job_script_name}/ /tmp/{job_script_name}/ --recursive

# Install job-specific dependencies
pip3 install -r /tmp/{job_script_name}/requirements.txt

# Download the common utilities from S3
echo "aws s3 cp s3://{scripts_bucket}/common/ /tmp/common/ --recursive"
aws s3 cp s3://{scripts_bucket}/common/ /tmp/common/ --recursive

# Install common dependencies
pip3 install -r /tmp/common/requirements.txt

# Export PYTHONPATH so common can be found
export PYTHONPATH=$PYTHONPATH:/tmp

# Export AWS region for boto3
echo "Setting AWS region to {region}"
export AWS_DEFAULT_REGION={region}
export AWS_REGION={region}

# Force unbuffered Python output so logs appear in real-time
export PYTHONUNBUFFERED=1

# Execute the TA job main script
python3 /tmp/{job_script_name}/main.py {symbol} {timeframe} {job_id}

# Make sure to sleep for a bit to allow logs to flush before shutdown
sleep 60

# Shutdown the instance
sudo shutdown -h now
"""

    logger.info("Launching EC2 instance with Launch Template: %s and Instance Type: %s", launch_template_id, aws_instance_type)

    try:
        response = ec2.run_instances(
            LaunchTemplate={'LaunchTemplateId': launch_template_id},
            InstanceType=aws_instance_type,
            MinCount=1,
            MaxCount=1,
            UserData=base64.b64encode(full_user_data.encode('utf-8')).decode('utf-8'),
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'ManagedBy', 'Value': 'CryptoTA-JobLauncher'},
                        {'Key': 'JobId', 'Value': job_id}
                    ]
                }
            ]
        )

        instance_id = response['Instances'][0]['InstanceId']
        logger.info("Successfully launched instance: %s", instance_id)

        # Update job tracker with the actual instance_id
        try:
            job_status.table.update_item(
                Key={'PK': f'JOB#{job_id}', 'SK': 'METADATA'},
                UpdateExpression="SET instance_id = :i",
                ExpressionAttributeValues={':i': instance_id}
            )
        except Exception as e:
            logger.warning("Failed to update instance_id in job tracker: %s", str(e))

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'EC2 instance launched successfully',
                'instance_id': instance_id,
                'job_id': job_id
            })
        }
    except Exception as e:
        logger.error("Error launching EC2 instance: %s", str(e))
        # Mark job as failed if launch failed
        try:
            job_status.fail_job(job_id, f"EC2 Launch failed: {str(e)}")
        except:
            pass

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
