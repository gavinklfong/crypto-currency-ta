import boto3
import json
import base64
import os

ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    launch_template_id = os.environ.get('LAUNCH_TEMPLATE_ID')
    scripts_bucket = os.environ.get('TA_JOB_SCRIPTS_BUCKET_NAME')
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
        print("Error: TA_JOB_SCRIPTS_BUCKET_NAME environment variable is not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'TA_JOB_SCRIPTS_BUCKET_NAME not set'})
        }

    # Construct UserData script
    # The script will download the TA job from S3
    full_user_data = f"""#!/bin/bash
# Update and install dependencies
yum update -y
yum install -y python3-pip aws-cli

# Install required python packages
pip3 install pandas numpy requests

# Download the TA job script from S3
aws s3 cp s3://{scripts_bucket}/ta_job.py /tmp/ta_job.py

# Execute the TA job
python3 /tmp/ta_job.py {symbol} {timeframe}

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
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'EC2 instance launched successfully',
                'instance_id': instance_id
            })
        }
    except Exception as e:
        print(f"Error launching EC2 instance: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
