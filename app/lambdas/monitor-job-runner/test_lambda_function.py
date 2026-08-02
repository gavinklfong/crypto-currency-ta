import unittest
from unittest.mock import patch, MagicMock, call
from botocore.exceptions import ClientError
import os
import json
from datetime import datetime, timedelta, timezone
from lambda_function import lambda_handler


class TestMonitorJobRunner(unittest.TestCase):

    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {
            'JOB_TRACKER_TABLE_NAME': 'test-table',
            'SLACK_SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic',
            'STALLED_THRESHOLD_MINUTES': '10',
            'MAX_LIFETIME_HOURS': '8',
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_no_stalled_jobs(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
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
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 0)
        self.assertEqual(result['total_stalled_jobs'], 0)
        mock_dynamodb.Table.assert_called_once()
        mock_sns.assert_not_called()
        mock_ec2.terminate_instances.assert_not_called()

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_with_stalled_jobs(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
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
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
            'start_time': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 1)
        self.assertEqual(result['total_stalled_jobs'], 1)

        # Verify EC2 termination
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=['i-abc123def'])

        # Verify SNS notification
        mock_sns.assert_called_once()
        args, kwargs = mock_sns.call_args
        self.assertEqual(kwargs['topic_arn'], 'arn:aws:sns:us-east-1:123456789012:test-topic')
        self.assertIn('job-123', args[0])
        self.assertIn('i-abc123def', args[0])

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_instance_already_terminated(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        stalled_job = {
            'PK': 'JOB#job-456',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': 'i-already-term',
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
            'start_time': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Mock describe_instances returning terminated state
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'State': {'Name': 'terminated'}
                }]
            }]
        }

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 1)

        # Should call describe_instances but NOT terminate_instances
        mock_ec2.describe_instances.assert_called_once_with(InstanceIds=['i-already-term'])
        mock_ec2.terminate_instances.assert_not_called()

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_no_instance_id(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        # Job with no instance_id
        stalled_job = {
            'PK': 'JOB#job-789',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': None,
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 0)
        mock_ec2.terminate_instances.assert_not_called()

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_pending_instance_id(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        # Job with PENDING instance_id
        stalled_job = {
            'PK': 'JOB#job-pending',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': 'PENDING',
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 0)
        mock_ec2.terminate_instances.assert_not_called()

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_ec2_terminate_fails(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        stalled_job = {
            'PK': 'JOB#job-fail',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': 'i-fail-123',
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
            'start_time': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Mock terminate_instances raising an exception
        mock_ec2.terminate_instances.side_effect = Exception("EC2 Error")

        # Act
        response = lambda_handler({}, None)

        # Assert - should still return 200 even if termination failed
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 0)
        self.assertEqual(result['total_stalled_jobs'], 1)

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_max_lifetime_exceeded(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        # Job started more than 8 hours ago
        stalled_job = {
            'PK': 'JOB#job-old',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': 'i-old-123',
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            'start_time': (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 1)

        # Verify SNS notification contains max lifetime reason
        args, kwargs = mock_sns.call_args
        self.assertIn('Max lifetime exceeded', args[0])

    @patch.dict(os.environ, {}, clear=True)
    def test_lambda_handler_missing_env_vars(self):
        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 500)
        self.assertIn('Missing JOB_TRACKER_TABLE_NAME', response['body'])

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_multiple_stalled_jobs(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        stalled_jobs = [
            {
                'PK': 'JOB#job-001',
                'SK': 'METADATA',
                'status': 'RUNNING',
                'job_type': 'ta-job',
                'instance_id': 'i-001',
                'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
                'start_time': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            },
            {
                'PK': 'JOB#job-002',
                'SK': 'METADATA',
                'status': 'RUNNING',
                'job_type': 'data-export',
                'instance_id': 'i-002',
                'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(),
                'start_time': (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            },
        ]
        mock_table.query.return_value = {'Items': stalled_jobs}

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 2)
        self.assertEqual(result['total_stalled_jobs'], 2)
        self.assertEqual(mock_ec2.terminate_instances.call_count, 2)

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_instance_not_found(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        stalled_job = {
            'PK': 'JOB#job-notfound',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': 'i-missing-123',
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
            'start_time': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Mock describe_instances raising InvalidInstanceID.NotFound
        mock_ec2.describe_instances.side_effect = ClientError(
            error_response={'Error': {'Code': 'InvalidInstanceID.NotFound', 'Message': 'Instance i-missing-123 not found'}},
            operation_name='DescribeInstances',
        )

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 1)
        self.assertEqual(result['total_stalled_jobs'], 1)

        # Should call describe_instances but NOT terminate_instances
        mock_ec2.describe_instances.assert_called_once_with(InstanceIds=['i-missing-123'])
        mock_ec2.terminate_instances.assert_not_called()

        # Verify SNS notification contains INSTANCE_NOT_FOUND
        mock_sns.assert_called_once()
        args, kwargs = mock_sns.call_args
        self.assertIn('INSTANCE_NOT_FOUND', args[0])
        self.assertIn('i-missing-123', args[0])

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_none_instance_id(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        stalled_job = {
            'PK': 'JOB#job-no-instance',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': None,
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 0)
        self.assertEqual(result['total_stalled_jobs'], 1)

        # EC2 calls should NOT be made
        mock_ec2.describe_instances.assert_not_called()
        mock_ec2.terminate_instances.assert_not_called()

        # Verify SNS notification sent with ORPHANED reason
        mock_sns.assert_called_once()
        args, kwargs = mock_sns.call_args
        self.assertIn('ORPHANED', args[0])
        self.assertIn('*Instance:* None', args[0])

    @patch('lambda_function.send_to_sns')
    @patch('lambda_function.ec2')
    @patch('boto3.resource')
    def test_lambda_handler_pending_instance_id(self, mock_dynamodb_resource, mock_ec2, mock_sns):
        # Arrange
        mock_dynamodb = MagicMock()
        mock_dynamodb_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        stalled_job = {
            'PK': 'JOB#job-pending-again',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'job_type': 'ta-job',
            'instance_id': 'PENDING',
            'last_heartbeat': (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
        }
        mock_table.query.return_value = {'Items': [stalled_job]}

        # Act
        response = lambda_handler({}, None)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        result = json.loads(response['body'])
        self.assertEqual(result['terminated_count'], 0)
        self.assertEqual(result['total_stalled_jobs'], 1)

        # EC2 calls should NOT be made
        mock_ec2.describe_instances.assert_not_called()
        mock_ec2.terminate_instances.assert_not_called()

        # Verify SNS notification sent with ORPHANED reason
        mock_sns.assert_called_once()
        args, kwargs = mock_sns.call_args
        self.assertIn('ORPHANED', args[0])


if __name__ == '__main__':
    unittest.main()
