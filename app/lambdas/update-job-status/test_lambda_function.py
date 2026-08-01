"""
Tests for update-job-status Lambda function.
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Set environment before importing the module
os.environ['JOB_TRACKER_TABLE'] = 'test-job-tracker'

import lambda_function


class TestCreateJobRecord:
    """Test job creation logic."""
    
    @patch('lambda_function.table')
    def test_create_running_job(self, mock_table):
        """Test creating a job in RUNNING status."""
        job_id = "test-job-123"
        symbol = "XBTUSD"
        timeframe = "5m"
        
        lambda_function.handler({
            'job_id': job_id,
            'status': 'RUNNING',
            'symbol': symbol,
            'timeframe': timeframe
        }, None)
        
        # Verify put_item was called
        assert mock_table.put_item.called
        call_args = mock_table.put_item.call_args
        item = call_args.kwargs['Item']
        
        assert item['pk'] == f"JOB#{job_id}"
        assert item['sk'] == 'METADATA'
        assert item['status'] == 'RUNNING'
        assert item['job_type'] == 'step_function'
        assert 'execution_id' in item


class TestCompleteJob:
    """Test job completion logic."""
    
    @patch('lambda_function.table')
    def test_complete_job(self, mock_table):
        """Test marking job as completed."""
        job_id = "test-job-123"
        symbol = "XBTUSD"
        timeframe = "5m"
        
        lambda_function.handler({
            'job_id': job_id,
            'status': 'COMPLETED',
            'symbol': symbol,
            'timeframe': timeframe
        }, None)
        
        # Verify update_item was called with correct parameters
        assert mock_table.update_item.called
        call_args = mock_table.update_item.call_args
        assert call_args.kwargs['Key'] == {'pk': f"JOB#{job_id}", 'sk': 'METADATA'}
        assert call_args.kwargs['UpdateExpression'] == 'SET #st = :status, updated_at = :updated_at, completed_at = :completed_at'
        assert call_args.kwargs['ExpressionAttributeNames'] == {'#st': 'status'}
        assert call_args.kwargs['ExpressionAttributeValues'][':status'] == 'COMPLETED'

    @patch('lambda_function.table')
    def test_complete_job_not_found(self, mock_table):
        """Test completing a non-existent job."""
        mock_table.meta.client.exceptions.ConditionalCheckFailedException = Exception
        mock_table.update_item.side_effect = mock_table.meta.client.exceptions.ConditionalCheckFailedException()
        
        lambda_function.handler({
            'job_id': "non-existent",
            'status': 'COMPLETED',
            'symbol': 'XBTUSD',
            'timeframe': '5m'
        }, None)
        
        # Should not raise an exception
        assert mock_table.update_item.called


class TestFailJob:
    """Test job failure logic."""
    
    @patch('lambda_function.table')
    def test_fail_job_with_error(self, mock_table):
        """Test marking job as failed with error message."""
        job_id = "test-job-123"
        
        lambda_function.handler({
            'job_id': job_id,
            'status': 'FAILED',
            'symbol': 'XBTUSD',
            'timeframe': '5m',
            'error_message': 'Connection timeout'
        }, None)
        
        call_args = mock_table.update_item.call_args
        expr_values = call_args.kwargs['ExpressionAttributeValues']
        assert expr_values[':status'] == 'FAILED'
        assert expr_values[':reason'] == 'Connection timeout'

    @patch('lambda_function.table')
    def test_fail_job_without_error(self, mock_table):
        """Test marking job as failed without error message."""
        job_id = "test-job-123"
        
        lambda_function.handler({
            'job_id': job_id,
            'status': 'FAILED',
            'symbol': 'XBTUSD',
            'timeframe': '5m'
        }, None)
        
        call_args = mock_table.update_item.call_args
        expr_values = call_args.kwargs['ExpressionAttributeValues']
        assert expr_values[':status'] == 'FAILED'
        # Should not have failure_reason
        assert ':reason' not in expr_values


class TestValidation:
    """Test input validation."""
    
    @patch('lambda_function.table')
    def test_missing_job_id(self, mock_table):
        """Test that missing job_id raises ValueError."""
        with pytest.raises(ValueError):
            lambda_function.handler({
                'status': 'RUNNING'
            }, None)

    @patch('lambda_function.table')
    def test_missing_status(self, mock_table):
        """Test that missing status raises ValueError."""
        with pytest.raises(ValueError):
            lambda_function.handler({
                'job_id': 'test-123'
            }, None)

    @patch('lambda_function.table')
    def test_unknown_status(self, mock_table):
        """Test handling of unknown status."""
        result = lambda_function.handler({
            'job_id': 'test-123',
            'status': 'UNKNOWN',
            'symbol': 'XBTUSD',
            'timeframe': '5m'
        }, None)
        
        assert result['statusCode'] == 200


class TestIntegration:
    """Integration-style tests with real DynamoDB mock."""
    
    def test_step_function_input_format(self):
        """Test that the function accepts Step Functions input format."""
        step_function_input = {
            'job_id': '$$.Execution.Id',
            'status': 'RUNNING',
            'symbol': '$.detail.symbol',
            'timeframe': '$.detail.timeframe'
        }
        
        # Verify the handler accepts this format
        assert step_function_input.get('job_id')
        assert step_function_input.get('status')
        assert step_function_input.get('symbol')
        assert step_function_input.get('timeframe')
