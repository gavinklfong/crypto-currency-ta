import json
import os
import unittest
import base64
from unittest.mock import patch, MagicMock, call
from lambda_function import lambda_handler


class TestLambdaHandler(unittest.TestCase):

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'INSTANCE_TYPE': 'medium',
    })
    def test_lambda_handler_success(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                'job_script_name': 'ta-job',
            }
        }
        context = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-0123456789abcdef0'}]
        }
        mock_boto3.client.return_value = mock_ec2
        mock_boto3.session.Session.return_value.region_name = 'us-east-1'

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
        self.assertEqual(kwargs['InstanceType'], 't3.medium')

        # Check UserData contains expected env var and command with job_payload
        user_data_encoded = kwargs['UserData']
        user_data = base64.b64decode(user_data_encoded).decode('utf-8')
        self.assertIn('export TA_JOB_ID=', user_data)
        self.assertIn('aws s3 cp s3://test-bucket/ta-job/ /tmp/ta-job/ --recursive', user_data)
        self.assertIn('pip3 install -r /tmp/ta-job/requirements.txt', user_data)
        self.assertIn('python3 /tmp/ta-job/main.py', user_data)
        self.assertIn('{"symbol": "XBTUSD", "timeframe": "1h"}', user_data)

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'INSTANCE_TYPE': 'small',
    })
    def test_lambda_handler_event_override(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                'instance_type': 'large',
                'job_script_name': 'ta-job',
            }
        }
        context = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-0123456789abcdef0'}]
        }
        mock_boto3.client.return_value = mock_ec2
        mock_boto3.session.Session.return_value.region_name = 'us-east-1'
        mock_job_status_instance = mock_job_status_class.return_value

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        args, kwargs = mock_ec2.run_instances.call_args
        self.assertEqual(kwargs['InstanceType'], 't3.large')

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'INSTANCE_TYPE': 'invalid',
    })
    def test_lambda_handler_invalid_env_type_fallback(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                'job_script_name': 'ta-job',
            }
        }
        context = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-0123456789abcdef0'}]
        }
        mock_boto3.client.return_value = mock_ec2
        mock_boto3.session.Session.return_value.region_name = 'us-east-1'
        mock_job_status_instance = mock_job_status_class.return_value

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        args, kwargs = mock_ec2.run_instances.call_args
        self.assertEqual(kwargs['InstanceType'], 't3.small')

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
    })
    def test_lambda_handler_missing_job_payload(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_script_name': 'ta-job',
                # Missing job_payload
            }
        }
        context = MagicMock()

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('Missing job_payload', body['error'])

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
    })
    def test_lambda_handler_missing_job_script_name(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                # Missing job_script_name
            }
        }
        context = MagicMock()

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('Missing job_script_name in event detail', body['error'])

    # ---- Spot Instance Tests ----

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'SPOT_ENABLED': 'true',
    })
    def test_lambda_handler_spot_enabled_via_env(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                'job_script_name': 'ta-job',
            }
        }
        context = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-spot123'}]
        }
        mock_boto3.client.return_value = mock_ec2
        mock_boto3.session.Session.return_value.region_name = 'us-east-1'
        mock_job_status_instance = mock_job_status_class.return_value

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        args, kwargs = mock_ec2.run_instances.call_args
        self.assertIn('InstanceMarketOptions', kwargs)
        self.assertEqual(kwargs['InstanceMarketOptions']['MarketType'], 'spot')
        self.assertEqual(
            kwargs['InstanceMarketOptions']['SpotOptions']['InstanceInterruptionBehavior'],
            'terminate',
        )
        self.assertEqual(
            kwargs['InstanceMarketOptions']['SpotOptions']['SpotInstanceType'],
            'one-time',
        )

        # Verify spot tag is present
        tags = {tag['Key']: tag['Value'] for tag in kwargs['TagSpecifications'][0]['Tags']}
        self.assertEqual(tags['InstanceType'], 'spot')

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
    })
    def test_lambda_handler_spot_enabled_via_event(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                'job_script_name': 'ta-job',
                'spot_enabled': True,
            }
        }
        context = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-spot456'}]
        }
        mock_boto3.client.return_value = mock_ec2
        mock_boto3.session.Session.return_value.region_name = 'us-east-1'
        mock_job_status_instance = mock_job_status_class.return_value

        # Act
        response = lambda_handler(event, context)

        # Assert
        self.assertEqual(response['statusCode'], 200)
        args, kwargs = mock_ec2.run_instances.call_args
        self.assertIn('InstanceMarketOptions', kwargs)
        self.assertEqual(kwargs['InstanceMarketOptions']['MarketType'], 'spot')
        tags = {tag['Key']: tag['Value'] for tag in kwargs['TagSpecifications'][0]['Tags']}
        self.assertEqual(tags['InstanceType'], 'spot')

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'SPOT_ENABLED': 'true',
        'SPOT_MAX_PRICE': '0.05',
    })
    def test_lambda_handler_spot_with_max_price(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                'job_script_name': 'ta-job',
            }
        }
        context = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-spot789'}]
        }
        mock_boto3.client.return_value = mock_ec2
        mock_boto3.session.Session.return_value.region_name = 'us-east-1'
        mock_job_status_instance = mock_job_status_class.return_value

        # Act
        response = lambda_handler(event, context)

        # Assert
        args, kwargs = mock_ec2.run_instances.call_args
        self.assertEqual(
            kwargs['InstanceMarketOptions']['SpotOptions']['MaxPrice'],
            '0.05',
        )

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'SPOT_ENABLED': 'true',
    })
    def test_lambda_handler_spot_no_max_price_defaults_to_default(
        self, mock_job_status_class, mock_boto3
    ):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                'job_script_name': 'ta-job',
            }
        }
        context = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-spot-default'}]
        }
        mock_boto3.client.return_value = mock_ec2
        mock_boto3.session.Session.return_value.region_name = 'us-east-1'
        mock_job_status_instance = mock_job_status_class.return_value

        # Act
        response = lambda_handler(event, context)

        # Assert
        args, kwargs = mock_ec2.run_instances.call_args
        # When no max price specified, it should be None (uses on-demand price)
        self.assertIsNone(
            kwargs['InstanceMarketOptions']['SpotOptions']['MaxPrice'],
        )

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
    })
    def test_lambda_handler_no_spot_by_default(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                'job_script_name': 'ta-job',
            }
        }
        context = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-on-demand'}]
        }
        mock_boto3.client.return_value = mock_ec2
        mock_boto3.session.Session.return_value.region_name = 'us-east-1'
        mock_job_status_instance = mock_job_status_class.return_value

        # Act
        response = lambda_handler(event, context)

        # Assert
        args, kwargs = mock_ec2.run_instances.call_args
        self.assertNotIn('InstanceMarketOptions', kwargs)
        tags = {tag['Key']: tag['Value'] for tag in kwargs['TagSpecifications'][0]['Tags']}
        self.assertEqual(tags['InstanceType'], 'on-demand')

    @patch('lambda_function.boto3')
    @patch('lambda_function.JobStatusClient')
    @patch.dict(os.environ, {
        'LAUNCH_TEMPLATE_ID': 'lt-12345678',
        'JOB_SCRIPTS_BUCKET_NAME': 'test-bucket',
        'SPOT_ENABLED': 'false',
    })
    def test_lambda_handler_spot_disabled_via_env(self, mock_job_status_class, mock_boto3):
        # Arrange
        event = {
            'detail': {
                'job_payload': '{"symbol": "XBTUSD", "timeframe": "1h"}',
                'job_script_name': 'ta-job',
            }
        }
        context = MagicMock()
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-ondemand-false'}]
        }
        mock_boto3.client.return_value = mock_ec2
        mock_boto3.session.Session.return_value.region_name = 'us-east-1'
        mock_job_status_instance = mock_job_status_class.return_value

        # Act
        response = lambda_handler(event, context)

        # Assert
        args, kwargs = mock_ec2.run_instances.call_args
        self.assertNotIn('InstanceMarketOptions', kwargs)
        tags = {tag['Key']: tag['Value'] for tag in kwargs['TagSpecifications'][0]['Tags']}
        self.assertEqual(tags['InstanceType'], 'on-demand')


if __name__ == '__main__':
    unittest.main()
