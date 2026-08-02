import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
import json
import os

# Mocking the environment before importing the handler
os.environ['MAX_INACTIVITY_MINUTES'] = '30'
os.environ['MAX_LIFETIME_HOURS'] = '8'

from lambda_function import lambda_handler

class TestReaperLambda(unittest.TestCase):

    @patch('lambda_function.JobStatusClient')
    @patch('lambda_function.ec2')
    def test_reaper_terminates_inactive_job(self, mock_ec2, mock_job_status_client):
        # Setup
        mock_client = mock_job_status_client.return_value
        now = datetime.now(timezone.utc)

        # Job 1: Inactive
        inactive_job = {
            'PK': 'JOB#job-inactive',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'instance_id': 'i-1234567890abcdef0',
            'start_time': (now - timedelta(hours=1)).isoformat(),
            'last_heartbeat': (now - timedelta(minutes=45)).isoformat()
        }

        # Job 2: Active
        active_job = {
            'PK': 'JOB#job-active',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'instance_id': 'i-0987654321fedcba0',
            'start_time': (now - timedelta(minutes=10)).isoformat(),
            'last_heartbeat': (now - timedelta(minutes=1)).isoformat()
        }

        mock_client.get_running_jobs.return_value = [inactive_job, active_job]

        # Execute
        response = lambda_handler({}, None)

        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['terminated_count'], 1)

        # Verify EC2 termination called for inactive job
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=['i-1234567890abcdef0'])

        # Verify fail_job called for inactive job
        mock_client.fail_job.assert_called_once()
        args, _ = mock_client.fail_job.call_args
        self.assertEqual(args[0], 'job-inactive')
        self.assertIn('Inactivity detected', args[1])

    @patch('lambda_function.JobStatusClient')
    @patch('lambda_function.ec2')
    def test_reaper_terminates_expired_job(self, mock_ec2, mock_job_status_client):
        # Setup
        mock_client = mock_job_status_client.return_value
        now = datetime.now(timezone.utc)

        # Job 1: Expired (started 10 hours ago, but heartbeating recently)
        expired_job = {
            'PK': 'JOB#job-expired',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'instance_id': 'i-expired',
            'start_time': (now - timedelta(hours=10)).isoformat(),
            'last_heartbeat': (now - timedelta(minutes=1)).isoformat()
        }

        mock_client.get_running_jobs.return_value = [expired_job]

        # Execute
        response = lambda_handler({}, None)

        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['terminated_count'], 1)

        # Verify EC2 termination called
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=['i-expired'])

        # Verify fail_job called for expired job
        mock_client.fail_job.assert_called_once()
        args, _ = mock_client.fail_job.call_args
        self.assertEqual(args[0], 'job-expired')
        self.assertIn('Max lifetime exceeded', args[1])

    @patch('lambda_function.JobStatusClient')
    @patch('lambda_function.ec2')
    def test_reaper_skips_pending_instance(self, mock_ec2, mock_job_status_client):
        # Setup
        mock_client = mock_job_status_client.return_value
        now = datetime.now(timezone.utc)

        # Job 1: Inactive but instance is still PENDING
        pending_job = {
            'PK': 'JOB#job-pending',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'instance_id': 'PENDING',
            'start_time': (now - timedelta(hours=1)).isoformat(),
            'last_heartbeat': (now - timedelta(minutes=45)).isoformat()
        }

        mock_client.get_running_jobs.return_value = [pending_job]

        # Execute
        response = lambda_handler({}, None)

        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['terminated_count'], 0)

        # Verify EC2 termination NOT called
        mock_ec2.terminate_instances.assert_not_called()

    @patch('lambda_function.JobStatusClient')
    @patch('lambda_function.ec2')
    def test_reaper_handles_spot_interruption(self, mock_ec2, mock_job_status_client):
        # Setup
        mock_client = mock_job_status_client.return_value
        now = datetime.now(timezone.utc)

        # Job: Spot instance already terminated (spot interruption)
        spot_job = {
            'PK': 'JOB#job-spot-interrupted',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'instance_id': 'i-spot-interrupted',
            'start_time': (now - timedelta(hours=1)).isoformat(),
            'last_heartbeat': (now - timedelta(minutes=45)).isoformat()
        }

        mock_client.get_running_jobs.return_value = [spot_job]

        # Mock describe_instances to return terminated state
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'State': {'Name': 'terminated'}
                }]
            }]
        }

        # Execute
        response = lambda_handler({}, None)

        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['terminated_count'], 1)

        # Verify fail_job called with spot interruption message
        mock_client.fail_job.assert_called_once()
        args, _ = mock_client.fail_job.call_args
        self.assertEqual(args[0], 'job-spot-interrupted')
        self.assertIn('SPOT_INTERRUPTION', args[1])
        self.assertIn('externally terminated', args[1])

        # Verify terminate_instances NOT called (already terminated)
        mock_ec2.terminate_instances.assert_not_called()

    @patch('lambda_function.JobStatusClient')
    @patch('lambda_function.ec2')
    def test_reaper_handles_shutting_down_instance(self, mock_ec2, mock_job_status_client):
        # Setup
        mock_client = mock_job_status_client.return_value
        now = datetime.now(timezone.utc)

        shutting_job = {
            'PK': 'JOB#job-shutting-down',
            'SK': 'METADATA',
            'status': 'RUNNING',
            'instance_id': 'i-shutting-down',
            'start_time': (now - timedelta(hours=1)).isoformat(),
            'last_heartbeat': (now - timedelta(minutes=45)).isoformat()
        }

        mock_client.get_running_jobs.return_value = [shutting_job]

        # Mock describe_instances to return shutting-down state
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'State': {'Name': 'shutting-down'}
                }]
            }]
        }

        # Execute
        response = lambda_handler({}, None)

        # Verify
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['terminated_count'], 1)

        # Verify fail_job called
        mock_client.fail_job.assert_called_once()
        args, _ = mock_client.fail_job.call_args
        self.assertIn('SPOT_INTERRUPTION', args[1])

        # Verify terminate_instances NOT called
        mock_ec2.terminate_instances.assert_not_called()

if __name__ == '__main__':
    unittest.main()
