import json
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Import your lambda file
import lambda_function as lf


# @pytest.fixture(autouse=True)
# def setup_env():
#     # Inject QUEUE_MAP into environment
#     os.environ["QUEUE_MAP"] = json.dumps({
#         "fetch-market-data": "https://sqs.us-east-2.amazonaws.com/123/fetch.fifo",
#         "calculate-ta": "https://sqs.us-east-2.amazonaws.com/123/calc.fifo"
#     })
#     lf.QUEUE_MAP = json.loads(os.environ["QUEUE_MAP"])

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("QUEUE_MAP", json.dumps({
        "fetch-market-data": "https://sqs.us-east-2.amazonaws.com/123/fetch.fifo",
        "calculate-ta": "https://sqs.us-east-2.amazonaws.com/123/calc.fifo"
    }))


@pytest.fixture
def mock_sqs():
    with patch.object(lf, "sqs") as mock:
        mock.send_message = MagicMock()
        yield mock


@pytest.fixture
def mock_send_event():
    with patch.object(lf, "send_event") as mock:
        yield mock


# ---------------------------------------------------------
# 1. Happy path — direct invocation
# ---------------------------------------------------------
def test_lambda_handler_direct(mock_send_event):
    event = {
        "target": "aggregate-timeframe",
        "symbol": "XXBTZUSD",
        "timeframe": "5m",
        "start_date": "2024-01-01",
        "end_date": "2024-01-03"
    }

    response = lf.lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["target"] == "aggregate-timeframe"
    assert body["symbols"] == ["XXBTZUSD"]
    assert body["timeframes"] == ["5m"]
    assert body["start_date"] == "2024-01-01"
    assert body["end_date"] == "2024-01-03"
    assert body["count"] == 1  # 1 symbol × 1 timeframe

    # Should call send_event 3 times (3 days)
    assert mock_send_event.call_count == 3

    # Extract all calls
    calls = mock_send_event.call_args_list

    expected_calls = [
        ("aggregate-timeframe", "XXBTZUSD", "5m", "2024-01-01", "2024-01-03", "2024-01-01T00:00:00", "2024-01-01T23:59:59"),
        ("aggregate-timeframe", "XXBTZUSD", "5m", "2024-01-01", "2024-01-03", "2024-01-02T00:00:00", "2024-01-02T23:59:59"),
        ("aggregate-timeframe", "XXBTZUSD", "5m", "2024-01-01", "2024-01-03", "2024-01-03T00:00:00", "2024-01-03T23:59:59"),
    ]

    # Validate each call
    for call, expected in zip(calls, expected_calls):
        args, kwargs = call

        assert args[0] == expected[0]   # target
        assert args[1] == expected[1]   # symbol
        assert args[2] == expected[2]   # timeframe

        assert args[3] == expected[3]
        assert args[4] == expected[4]

        # Compare ISO timestamps
        assert args[5].isoformat() == expected[5]
        assert args[6].isoformat() == expected[6]

def test_lambda_handler_direct_calculate_ta(mock_send_event):
    event = {
        "target": "calculate-ta",
        "symbol": "XXBTZUSD",
        "timeframe": "1m",
        "start_date": "2024-01-01",
        "end_date": "2024-01-02"
    }

    response = lf.lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["target"] == "calculate-ta"
    assert body["symbols"] == ["XXBTZUSD"]
    assert body["timeframes"] == ["1m"]
    assert body["start_date"] == "2024-01-01"
    assert body["end_date"] == "2024-01-02"
    assert body["count"] == 1  # 1 symbol × 1 timeframe

    # Should call send_event 12 times (12 hours chunks for 2 days)
    assert mock_send_event.call_count == 12

    # Extract all calls
    calls = mock_send_event.call_args_list

    expected_calls = [
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-01T00:00:00", "2024-01-01T04:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-01T04:00:00", "2024-01-01T08:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-01T08:00:00", "2024-01-01T12:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-01T12:00:00", "2024-01-01T16:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-01T16:00:00", "2024-01-01T20:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-01T20:00:00", "2024-01-02T00:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-02T00:00:00", "2024-01-02T04:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-02T04:00:00", "2024-01-02T08:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-02T08:00:00", "2024-01-02T12:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-02T12:00:00", "2024-01-02T16:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-02T16:00:00", "2024-01-02T20:00:00"),
        ("calculate-ta", "XXBTZUSD", "1m", "2024-01-01", "2024-01-02", "2024-01-02T20:00:00", "2024-01-03T00:00:00")        
    ]

    # Validate each call
    for call, expected in zip(calls, expected_calls):
        args, kwargs = call

        assert args[0] == expected[0]   # target
        assert args[1] == expected[1]   # symbol
        assert args[2] == expected[2]   # timeframe

        assert args[3] == expected[3]
        assert args[4] == expected[4]

        # Compare ISO timestamps
        assert args[5].isoformat() == expected[5]
        assert args[6].isoformat() == expected[6]      

# ---------------------------------------------------------
# 2. Happy path — EventBridge format
# ---------------------------------------------------------
def test_lambda_handler_eventbridge(mock_send_event):
    event = {
        "detail": {
            "target": "aggregate-timeframe",
            "symbol": "XXBTZUSD",
            "timeframe": "5m",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01"
        }
    }

    response = lf.lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["symbols"] == ["XXBTZUSD"]
    assert body["timeframes"] == ["5m"]
    assert mock_send_event.call_count == 1


# ---------------------------------------------------------
# 3. Validation error — invalid timeframe
# ---------------------------------------------------------
def test_lambda_handler_invalid_timeframe():
    event = {
        "target": "aggregate-timeframe",
        "symbol": "XXBTZUSD",
        "timeframe": "99m",  # invalid
        "start_date": "2024-01-01",
        "end_date": "2024-01-02"
    }

    response = lf.lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 500
    assert "Invalid timeframe" in body["error"]


# ---------------------------------------------------------
# 4. Validation error — start_date > end_date
# ---------------------------------------------------------
def test_lambda_handler_invalid_date_range():
    event = {
        "target": "aggregate-timeframe",
        "symbol": "XXBTZUSD",
        "timeframe": "5m",
        "start_date": "2024-01-05",
        "end_date": "2024-01-01"
    }

    response = lf.lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 500
    assert "start_date cannot be after end_date" in body["error"]
