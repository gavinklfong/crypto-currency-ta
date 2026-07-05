import json
import unittest
from unittest.mock import patch, MagicMock
import os
from lambda_function import lambda_handler

class TestLambdaFunction(unittest.TestCase):

    def setUp(self):
        self.webhook_url = "https://hooks.slack.com/services/test/webhook"
        self.env_patcher = patch.dict(os.environ, {"SLACK_WEBHOOK_URL": self.webhook_url})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch('urllib.request.urlopen')
    def test_lambda_handler_success(self, mock_urlopen):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        event = {
            'Records': [
                {
                    'Sns': {
                        'Message': 'Test message'
                    }
                }
            ]
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(json.loads(response['body'])['message'], 'Sent to Slack successfully')
        
        # Verify request
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        self.assertEqual(req.get_full_url(), self.webhook_url)
        self.assertEqual(req.method, 'POST')
        self.assertEqual(req.headers['Content-type'], 'application/json')

    def test_lambda_handler_invalid_sns_event(self):
        event = {'not_records': []}
        context = MagicMock()

        response = lambda_handler(event, context)

        self.assertEqual(response['statusCode'], 400)
        self.assertIn('Invalid SNS event structure', json.loads(response['body'])['error'])

    @patch.dict(os.environ, {}, clear=True)
    def test_lambda_handler_missing_webhook_url(self):
        event = {
            'Records': [
                {
                    'Sns': {
                        'Message': 'Test message'
                    }
                }
            ]
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        self.assertEqual(response['statusCode'], 500)
        self.assertIn('SLACK_WEBHOOK_URL not set', json.loads(response['body'])['error'])

    @patch('urllib.request.urlopen')
    def test_lambda_handler_slack_error(self, mock_urlopen):
        # Mock error response
        mock_response = MagicMock()
        mock_response.getcode.return_value = 404
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        event = {
            'Records': [
                {
                    'Sns': {
                        'Message': 'Test message'
                    }
                }
            ]
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        self.assertEqual(response['statusCode'], 404)
        self.assertIn('Slack returned status 404', json.loads(response['body'])['error'])

    @patch('urllib.request.urlopen')
    def test_lambda_handler_exception(self, mock_urlopen):
        # Mock exception
        mock_urlopen.side_effect = Exception("Connection error")

        event = {
            'Records': [
                {
                    'Sns': {
                        'Message': 'Test message'
                    }
                }
            ]
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        self.assertEqual(response['statusCode'], 500)
        self.assertIn('Connection error', json.loads(response['body'])['error'])

if __name__ == '__main__':
    unittest.main()
