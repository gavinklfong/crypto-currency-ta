# app/lambdas/ai-analysis/test_lambda_live_e2e.py
import pytest
import os
from unittest.mock import patch
from lambda_function import lambda_handler

@pytest.mark.manual
def test_lambda_e2e_integration():
    """
    End-to-End Integration Test:
    This test calls the Lambda function against the real AWS services (Bedrock and DynamoDB).
    NOTE: This test will incur AWS costs and modify real data.
    """
    print("\n--- Starting E2E Integration Test: BTCUSD ---")
    
    event = {
        "symbol": "XETHZUSD",
        "timeframe": "1m"
    }
    
    try:
        # Execute the lambda_handler with a real event payload
        with patch('lambda_function.send_to_sns') as mock_send_to_sns:
            response = lambda_handler(event, None)
            
            # Verify SNS was called
            mock_send_to_sns.assert_called_once()
            print("SNS mock verification: Success")
            
        print("\n--- Lambda Execution Complete ---")
        print(f"Test Status: Success (Code {response.get('status')})")
        
        # Basic verification that the expected output format is returned
        assert response.get("status") == "success"
        assert "analysis" in response
        
        print(f"Analysis Snippet: {response['analysis'][:100]}...")

    except Exception as e:
        print(f"!!! E2E Test FAILED !!!\nError: {e}")
        raise