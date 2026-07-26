import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from common.job_status_client import JobStatusClient

class TestJobStatusClient(unittest.TestCase):
    def setUp(self):
        self.mock_dynamodb = MagicMock()
        with patch('boto3.resource', return_value=self.mock_dynamodb):
            self.client = JobStatusClient(table_name="test-table")
            self.mock_table = self.mock_dynamodb.Table.return_value

    def test_start_job(self):
        self.client.start_job("job-123", "test-type", "i-123")
        self.mock_table.put_item.assert_called_once()
        item = self.mock_table.put_item.call_args[1]['Item']
        self.assertEqual(item['PK'], 'JOB#job-123')
        self.assertEqual(item['status'], 'RUNNING')

    def test_heartbeat(self):
        self.client.heartbeat("job-123")
        self.mock_table.update_item.assert_called_once()
        kwargs = self.mock_table.update_item.call_args[1]
        self.assertIn(':now', kwargs['ExpressionAttributeValues'])

    def test_report_progress(self):
        self.client.report_progress("job-123", 50)
        self.mock_table.update_item.assert_called_once()
        kwargs = self.mock_table.update_item.call_args[1]
        self.assertEqual(kwargs['UpdateExpression'], "SET progress = :p, last_heartbeat = :now")
        self.assertEqual(kwargs['ExpressionAttributeValues'][':p'], 50)

    def test_report_progress_with_detail(self):
        self.client.report_progress_with_detail("job-123", 75, "Downloading data")
        self.mock_table.update_item.assert_called_once()
        kwargs = self.mock_table.update_item.call_args[1]
        self.assertEqual(kwargs['UpdateExpression'], "SET progress = :p, progress_detail = :d, last_heartbeat = :now")
        self.assertEqual(kwargs['ExpressionAttributeValues'][':p'], 75)
        self.assertEqual(kwargs['ExpressionAttributeValues'][':d'], "Downloading data")

    def test_complete_job(self):
        self.client.complete_job("job-123")
        self.mock_table.update_item.assert_called_once()
        kwargs = self.mock_table.update_item.call_args[1]
        self.assertEqual(kwargs['ExpressionAttributeValues'][':s'], 'COMPLETED')
        self.assertEqual(kwargs['ExpressionAttributeValues'][':p'], 100)

    def test_fail_job(self):
        self.client.fail_job("job-123", "error occurred")
        self.mock_table.update_item.assert_called_once()
        kwargs = self.mock_table.update_item.call_args[1]
        self.assertEqual(kwargs['ExpressionAttributeValues'][':s'], 'FAILED')
        self.assertEqual(kwargs['ExpressionAttributeValues'][':e'], 'error occurred')

if __name__ == '__main__':
    unittest.main()
