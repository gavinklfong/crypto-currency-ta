# app/lambdas/send-to-slack/test_lambda_live_e2e.py
import pytest
import os
import json
from lambda_function import lambda_handler

@pytest.mark.manual
def test_lambda_e2e_integration():
    """
    End-to-End Integration Test:
    This test calls the Lambda function against the real Slack API via SNS event.
    NOTE: This test will send a real message to Slack. Ensure SLACK_WEBHOOK_URL is set.
    """
    print("\n--- Starting E2E Integration Test: Send to Slack ---")
    
    # Check if SLACK_WEBHOOK_URL is set
    if not os.environ.get('SLACK_WEBHOOK_URL'):
        pytest.skip("Skipping E2E test: SLACK_WEBHOOK_URL environment variable is not set.")

    event = {
        "Records": [
            {
                "Sns": {
                    "Message": "Test message from Lambda E2E integration test."
                }
            }
        ]
    }
    
    try:
        # Execute the lambda_handler with a real SNS event payload
        response = lambda_handler(event, None)
        
        print("\n--- Lambda Execution Complete ---")
        
        # Parse the response body
        body = json.loads(response.get('body', '{}'))
        
        print(f"Test Status: Success (StatusCode {response.get('statusCode')})")
        print(f"Response Body: {body}")
        
        # Basic verification
        assert response.get('statusCode') == 200
        assert body.get('message') == 'Sent to Slack successfully'

    except Exception as e:
        print(f"!!! E2E Test FAILED !!!\nError: {e}")
        raise
