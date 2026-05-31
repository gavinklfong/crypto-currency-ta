import json
from unittest.mock import patch, MagicMock
from pathlib import Path
import lambda_function as lf


def load_mock_kraken_response():
    """Load the large Kraken OHLC mock response from file."""
    file_path = Path("mock_kraken_ohlc.json")
    with open(file_path, "r") as f:
        return json.load(f)


@patch("lambda_function.events")
@patch("lambda_function.dynamodb_client.put_item")
@patch("lambda_function.requests.get")
def test_lambda_handler_verifies_dynamodb_called(
    mock_get, mock_put_item, mock_events
):
    # Load Kraken OHLC mock response from file
    mock_response = load_mock_kraken_response()
    candles = mock_response["result"]["XETHZUSD"]

    # Mock Kraken API response
    mock_get.return_value.json.return_value = mock_response

    # Simulate DynamoDB accepting all writes
    mock_put_item.return_value = {}

    # Prepare event where last_timestamp < end_ts → event emission expected
    last_ts = max(int(c[0]) for c in candles)
    event = {
        "symbol": "XETHZUSD",
        "start_ts": candles[0][0],
        "end_ts": last_ts + 100
    }

    result = lf.lambda_handler(event, None)
    body = json.loads(result["body"])

    # Validate Lambda response
    assert result["statusCode"] == 200
    assert body["pair"] == "XETHZUSD"
    assert body["count"] == len(candles)

    # -----------------------------
    # VERIFY DYNAMODB WAS CALLED
    # -----------------------------
    assert mock_put_item.call_count == len(candles)

    # Validate first call structure
    first_call_args = mock_put_item.call_args_list[0][1]  # kwargs of first call
    assert first_call_args["TableName"] == "crypto-currency-ta-market-data"
    assert "Item" in first_call_args
    assert "PK" in first_call_args["Item"]
    assert "SK" in first_call_args["Item"]

    # -----------------------------
    # VERIFY EVENTBRIDGE WAS CALLED
    # -----------------------------
    mock_events.put_events.assert_called_once()
    event_detail = json.loads(
        mock_events.put_events.call_args[1]["Entries"][0]["Detail"]
    )

    assert event_detail["symbol"] == "XETHZUSD"
    assert event_detail["start_ts"] == last_ts
    assert event_detail["end_ts"] == last_ts + 100
