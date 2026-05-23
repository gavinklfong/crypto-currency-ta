import json
import pytest
from unittest.mock import patch

import lambda_function  # your lambda file


@pytest.mark.integration
@patch("lambda_function.events")
@patch("lambda_function.dynamodb_client")
def test_lambda_handler_real_kraken(mock_dynamodb, mock_events):
    """
    Real integration test that calls the live Kraken OHLC API.
    DynamoDB writes and EventBridge puts are mocked.
    """

    # Mock DynamoDB and events to avoid real AWS calls
    mock_dynamodb.put_item.return_value = {}
    mock_events.put_events.return_value = {}

    # Call the Lambda handler (this will hit the real Kraken API)
    result = lambda_function.lambda_handler({}, {})

    assert result["statusCode"] == 200

    body = json.loads(result["body"])

    # Validate Kraken contract
    assert "pair" in body
    assert "ohlc" in body
    assert "count" in body
    assert isinstance(body["ohlc"], list)
    # count is total from Kraken, but ohlc only contains last 10
    assert body["count"] >= len(body["ohlc"])
    # ohlc should be the last 10 candles (or fewer if less than 10 total)
    assert len(body["ohlc"]) <= 10

    # Validate OHLC candle structure
    first_candle = body["ohlc"][0]
    assert len(first_candle) == 8  # Kraken OHLC always has 8 fields

    # Validate field types
    assert isinstance(first_candle[0], int)  # timestamp
    assert isinstance(first_candle[1], str)  # open
    assert isinstance(first_candle[2], str)  # high
    assert isinstance(first_candle[3], str)  # low
    assert isinstance(first_candle[4], str)  # close
    assert isinstance(first_candle[5], str)  # vwap
    assert isinstance(first_candle[6], str)  # volume
    assert isinstance(first_candle[7], int)  # count

    # Ensure DynamoDB put_item was called
    assert mock_dynamodb.put_item.called
    # Ensure EventBridge put_events was called
    assert mock_events.put_events.called