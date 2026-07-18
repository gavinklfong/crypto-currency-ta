import json
import os
import unittest
import base64
from unittest.mock import patch, MagicMock
from lambda_function import lambda_handler

class TestLambdaHandler(unittest.TestCase):

    @patch('lambda_function.ec2')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'JOB_SCRIPT_NAME': 'ta_job.py'
    })
    def test_lambda_handler_success(self, mock_ec2):
        # Arrange
        event = {
            'detail': {
                'symbol': 'XBTUSD',
                'timeframe': '1h'
            }
        }
        context = MagicMock()
        mock_ec2.run_instances.return_value = {'Instances': [{'InstanceId': 'i-0123456789abcdef0'}]}

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['instance_id'], 'i-0123456789abcdef0')
        
        # Verify run_instances was called with correct parameters
        args, kwargs = mock_ec2.run_instances.call_args
        self.assertEqual(kwargs['LaunchTemplate']['LaunchTemplateId'], 'lt-12345678')
        
        # Check if symbol and timeframe are in UserData
        user_data_encoded = kwargs['UserData']
        user_data = base64.b64decode(user_data_encoded).decode('utf-8')
        self.assertIn('XBTUSD', user_data)
        self.assertIn('1h', user_data)
        self.assertIn('aws s3 cp s3://test-bucket/ta_job.py /tmp/ta_job.py', user_data)

    @patch.dict(os.environ, {'LAUNCH_TEMPLATE_ID': 'lt-12345678'})
    def test_lambda_handler_missing_params(self):
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

    @patch.dict(os.environ, {}, clear=True)
    def test_lambda_handler_missing_env_var(self):
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
            'JOB_SCRIPT_NAME not set' in body['error']
        )

if __name__ == '__main__':
    unittest.main()
