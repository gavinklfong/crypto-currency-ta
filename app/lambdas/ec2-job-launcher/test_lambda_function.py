import json
import os
import unittest
import base64
from unittest.mock import patch, MagicMock
from lambda_function import lambda_handler

class TestLambdaHandler(unittest.TestCase):

    @patch('lambda_function.JobStatusClient')
    @patch('lambda_function.ec2')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'JOB_SCRIPT_NAME': 'ta_job.py',
        'JOB_TRACKER_TABLE_NAME': 'test-table'
    })
    def test_lambda_handler_success(self, mock_ec2, mock_job_status_class):
        # Arrange
        event = {
            'detail': {
                'symbol': 'XBTUSD',
                'timeframe': '1h'
            }
        }
        context = MagicMock()
        mock_ec2.run_instances.return_value = {'Instances': [{'InstanceId': 'i-0123456789abcdef0'}]}

        # Configure the mock client instance
        mock_job_status_instance = mock_job_status_class.return_value

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['instance_id'], 'i-0123456789abcdef0')

        # Verify JobStatusClient.start_job was called
        mock_job_status_instance.start_job.assert_called_once()

        # Verify run_instances was called with correct parameters
        args, kwargs = mock_ec2.run_instances.call_args
        self.assertEqual(kwargs['LaunchTemplate']['LaunchTemplateId'], 'lt-12345678')

        # Check if symbol and timeframe are in UserData
        user_data_encoded = kwargs['UserData']
        user_data = base64.b64decode(user_data_encoded).decode('utf-8')
        self.assertIn('XBTUSD', user_data)
        self.assertIn('1h', user_data)
        self.assertIn('aws s3 cp s3://test-bucket/ta_job.py /tmp/ta_job.py', user_data)

    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'JOB_SCRIPT_NAME': 'ta_job.py',
        'JOB_TRACKER_TABLE_NAME': 'test-table'
    })
    def test_lambda_handler_missing_params(self, mock_job_status_class):
        # Arrange
        event = {
            'detail': {
                'symbol': 'XBTUSD'
                # Missing timeframe
            }
        }
        context = MagicMock()

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('Missing symbol or timeframe', body['error'])

    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {}, clear=True)
    def test_lambda_handler_missing_env_var(self, mock_job_status_class):
        # Arrange
        event = {
            'detail': {
                'symbol': 'XBTUSD',
                'timeframe': '1h'
            }
        }
        context = MagicMock()

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 500)
        body = json.loads(response['body'])
        self.assertTrue(
            'LAUNCH_TEMPLATE_ID not set' in body['error'] or
            'JOB_SCRIPTS_BUCKET_NAME not set' in body['error'] or
            'JOB_SCRIPT_NAME not set' in body['error'] or
            'JOB_TRACKER_TABLE_NAME not set' in body['error']
        )

if __name__ == '__main__':
    unittest.main()
