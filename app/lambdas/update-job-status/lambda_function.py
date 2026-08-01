"""
Lambda function to update job status in DynamoDB job tracker table.
Used by Step Functions for job lifecycle management.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB Configuration
JOB_TRACKER_TABLE = os.environ.get('JOB_TRACKER_TABLE', 'crypto-currency-ta-job-tracker')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(JOB_TRACKER_TABLE)


def handler(event, context):
    """
    Step Functions task to update job status.
    
    Input format:
    {
        "job_id": "uuid",
        "status": "RUNNING" | "COMPLETED" | "FAILED",
        "symbol": "XBTUSD",
        "timeframe": "5m",
        "error_message": "optional error description"
    }
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    job_id = event.get('job_id')
    status = event.get('status')
    symbol = event.get('symbol')
    timeframe = event.get('timeframe')
    error_message = event.get('error_message')
    
    if not job_id or not status:
        logger.error(f"Missing required fields: job_id={job_id}, status={status}")
        raise ValueError("job_id and status are required")
    
    try:
        if status == 'RUNNING':
            _create_job_record(job_id, symbol, timeframe)
        elif status == 'COMPLETED':
            _complete_job(job_id, symbol, timeframe)
        elif status == 'FAILED':
            _fail_job(job_id, symbol, timeframe, error_message)
        else:
            logger.warning(f"Unknown status: {status}")
            
        return {
            'statusCode': 200,
            'body': json.dumps({
                'job_id': job_id,
                'status': status
            })
        }
        
    except Exception as e:
        logger.error(f"Failed to update job {job_id}: {e}")
        raise


def _create_job_record(job_id, symbol, timeframe):
    """Create a new job record in RUNNING status."""
    now = datetime.now(timezone.utc)
    pk = f"JOB#{job_id}"
    sk = "METADATA"
    
    item = {
        'pk': pk,
        'sk': sk,
        'job_id': job_id,
        'status': 'RUNNING',
        'symbol': symbol,
        'timeframe': timeframe,
        'created_at': now.isoformat(),
        'updated_at': now.isoformat(),
        'heartbeat': now.isoformat(),
        'job_type': 'step_function',
        'step_function': 'crypto-currency-ta-pipeline',
        'execution_id': f"arn:aws:states:*:*:execution:crypto-currency-ta-pipeline:{job_id}"
    }
    
    table.put_item(Item=item)
    logger.info(f"Created job record: {pk}")


def _complete_job(job_id, symbol, timeframe):
    """Mark job as completed."""
    now = datetime.now(timezone.utc)
    pk = f"JOB#{job_id}"
    sk = "METADATA"
    
    try:
        # Use ExpressionAttributeNames for 'status' which is a reserved keyword
        table.update_item(
            Key={'pk': pk, 'sk': sk},
            UpdateExpression="SET #st = :status, updated_at = :updated_at, completed_at = :completed_at",
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':updated_at': now.isoformat(),
                ':completed_at': now.isoformat()
            }
        )
        logger.info(f"Completed job record: {pk}")
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        logger.warning(f"Job record not found: {pk}")


def _fail_job(job_id, symbol, timeframe, error_message=None):
    """Mark job as failed."""
    now = datetime.now(timezone.utc)
    pk = f"JOB#{job_id}"
    sk = "METADATA"
    
    try:
        # Use ExpressionAttributeNames for 'status' which is a reserved keyword
        update_expr = "SET #st = :status, updated_at = :updated_at, failed_at = :failed_at"
        expr_values = {
            ':status': 'FAILED',
            ':updated_at': now.isoformat(),
            ':failed_at': now.isoformat()
        }
        
        if error_message:
            update_expr += ", failure_reason = :reason"
            expr_values[':reason'] = error_message
        
        table.update_item(
            Key={'pk': pk, 'sk': sk},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues=expr_values
        )
        logger.info(f"Failed job record: {pk}")
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        logger.warning(f"Job record not found: {pk}")
