import json
import pytest
from unittest.mock import patch

import lambda_function  # your lambda file


@pytest.mark.integration
@patch("lambda_function.write_ohlc_to_dynamodb")
def test_lambda_handler_real_kraken(mock_write):
    """
    Real integration test that calls the live Kraken OHLC API.
    DynamoDB writes are mocked.
    """

    # Mock DynamoDB writer to avoid real AWS calls
    mock_write.return_value = 999  # arbitrary number

    # Call the Lambda handler (this will hit the real Kraken API)
    result = lambda_function.lambda_handler({}, {})

    assert result["statusCode"] == 200

    body = json.loads(result["body"])

    # Validate Kraken contract
    assert "pair" in body
    assert "ohlc" in body
    assert "count" in body
    assert isinstance(body["ohlc"], list)
    assert body["count"] == len(body["ohlc"])

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

    # Ensure DynamoDB writer was called
    mock_write.assert_called_once()
