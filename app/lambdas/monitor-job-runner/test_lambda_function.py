import unittest
from unittest.mock import patch, MagicMock
import os
import json
from datetime import datetime, timedelta, timezone
from lambda_function import lambda_handler

class TestMonitorJobRunner(unittest.TestCase):

    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {
            'JOB_TRACKER_TABLE_NAME': 'test-table',
            'SLACK_SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic',
            'STALLED_THRESHOLD_MINUTES': '10'
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch('boto3.client')
    @patch('boto3.resource')
    @patch('common.job_status_client.JobStatusClient')
    def test_lambda_handler_no_stalled_jobs(self, mock_job_status, mock_dynamodb_resource, mock_sns_client):
        # Arrange
        mock_sns = MagicMock()
        mock_sns_client.return_value = mock_sns

        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        # Mock query returning no items
        mock_table.query.return_value = {'Items': []}

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['body'], "Processed 0 stalled jobs")
        mock_table.query.assert_called_once()
        mock_sns.publish.assert_not_called()

    @patch('boto3.client')
    @patch('boto3.resource')
    @patch('common.job_status_client.JobStatusClient')
    def test_lambda_handler_with_stalled_jobs(self, mock_job_status, mock_dynamodb_resource, mock_sns_client):
        # Arrange
        mock_sns = MagicMock()
        mock_sns_client.return_value = mock_sns

        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        # Mock query returning one stalled job
        stalled_job = {
            'PK': 'JOB#job-123',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': 'i-abc123def',
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['body'], "Processed 1 stalled jobs")

        # Verify status update
        mock_table.update_item.assert_called_once_with(
            Key={'PK': 'JOB#job-123', 'SK': 'METADATA'},
            UpdateExpression="SET status = :s",
            ExpressionAttributeValues={':s': 'STALLED'}
        )

        # Verify SNS notification
        mock_sns.publish.assert_called_once()
        args, kwargs = mock_sns.publish.call_args
        self.assertEqual(kwargs['TopicArn'], 'arn:aws:sns:us-east-1:123456789012:test-topic')
        self.assertIn('job-123', kwargs['Message'])
        self.assertIn('ta-job', kwargs['Message'])
        self.assertIn('i-abc123def', kwargs['Message'])

    @patch.dict(os.environ, {}, clear=True)
    def test_lambda_handler_missing_env_vars(self):
        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 500)
        self.assertIn('Missing JOB_TRACKER_TABLE_NAME', response['body'])

    @patch('boto3.client')
    @patch('boto3.resource')
    @patch('common.job_status_client.JobStatusClient')
    def test_lambda_handler_exception_during_update(self, mock_job_status, mock_dynamodb_resource, mock_sns_client):
        # Arrange
        mock_sns = MagicMock()
        mock_sns_client.return_value = mock_sns

        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        # Mock query returning one stalled job
        stalled_job = {
            'PK': 'JOB#job-123',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': 'i-abc123def',
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Mock update_item to raise an exception
        mock_table.update_item.side_effect = Exception("DynamoDB error")

        # Act
        response = lambda_handler({}, None)

        # Assert
        # The loop should continue even if one update fails
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['body'], "Processed 1 stalled jobs")
        mock_table.update_item.assert_called_once()
        mock_sns.publish.assert_not_called()

if __name__ == '__main__':
    unittest.main()
