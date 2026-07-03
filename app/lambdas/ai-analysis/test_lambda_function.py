import pytest
import json
from unittest.mock import MagicMock, patch
from lambda_function import lambda_handler


@patch("lambda_function.fetch_data")
@patch("lambda_function.call_bedrock")
@patch("lambda_function.table")
def test_lambda_handler_bedrock_failure(mock_table, mock_bedrock, mock_fetch):
    # Simulate Bedrock API call failure
    mock_bedrock.side_effect = Exception("AccessDeniedException: Bedrock API call denied")
    
    event = {"symbol": "XXBTZUSD", "timeframe": "1m"}
    response = lambda_handler(event, None)
    
    assert response["status"] == "error"
    assert "Error calling Bedrock" in response["message"]

@patch("lambda_function.fetch_data")
@patch("lambda_function.call_bedrock")
def test_lambda_handler_sqsevent(mock_bedrock, mock_fetch):
    # Simulate SQS event structure
    mock_fetch.return_value = [{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100, "SK": "TF1m#TS1672531200"}]
    mock_bedrock.return_value = "Mock analysis"
    
    event = {
        "Records": [{
            "body": json.dumps({"symbol": "XXBTZUSD", "timeframe": "1m"})
        }]
    }
    response = lambda_handler(event, None)
    
    assert response["status"] == "success"
    assert response["symbol"] == "XXBTZUSD"
    assert response["analysis"] == "Mock analysis"

@patch("lambda_function.fetch_data")
def test_lambda_handler_no_symbol(mock_fetch):
    event = {"timeframe": "1m"}
    response = lambda_handler(event, None)
    
    assert response["status"] == "error"
    assert "No symbol provided" in response["message"]

@patch("lambda_function.fetch_data")
def test_lambda_handler_no_data(mock_fetch):
    mock_fetch.return_value = []
    event = {"symbol": "XXBTZUSD", "timeframe": "1m"}
    response = lambda_handler(event, None)
    
    assert response["status"] == "error"
    assert "No 1m data found" in response["message"]
