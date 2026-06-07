import pytest
from unittest.mock import MagicMock, patch
from lambda_function import calculate_range, MIN_REQUIRED

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def create_mock_candle(timestamp, close_price):
    return {
        "PK": "PAIR#XXBTZUSD",
        "SK": f"TF#1m#TS#{timestamp}",
        "close": close_price,
        "open": close_price - 0.5,
        "high": close_price + 1,
        "low": close_price - 1,
    }

def extract_ts(c):
    return int(c["SK"].split("#")[-1])

# ------------------------------------------------------------
# Tests
# ------------------------------------------------------------

@patch("lambda_function.table")
def test_calculate_range_processes_all_candles_with_sufficient_history(mock_table):
    pair = "XXBTZUSD"
    timeframe = "1m"
    start_ts = 1000000
    end_ts = 1000149  # 150 candles in range

    # 200 candles total: 50 before + 150 in range
    all_candles = [
        create_mock_candle(start_ts - 50 + i, 40000 + i * 10)
        for i in range(200)
    ]

    candles_in_range = [
        c for c in all_candles
        if start_ts <= extract_ts(c) <= end_ts
    ]

    # Correct pagination simulation
    def mock_query(**kwargs):
        if "BETWEEN" in kwargs["KeyConditionExpression"]:
            return {"Items": candles_in_range}
        limit = kwargs.get("Limit", len(all_candles))
        return {"Items": all_candles[-limit:], "LastEvaluatedKey": None}

    mock_table.query.side_effect = mock_query
    mock_table.update_item.return_value = {}

    result = calculate_range(pair, timeframe, start_ts, end_ts)

    expected = len(candles_in_range) - 34  # TA_MIN_HISTORY = 35
    assert result["processed"] == expected
    assert mock_table.update_item.call_count == expected


@patch("lambda_function.table")
def test_calculate_range_skips_candles_without_sufficient_history(mock_table):
    pair = "XXBTZUSD"
    timeframe = "1m"
    start_ts = 1000000
    end_ts = 1000050  # 50 candles in range

    # 100 candles total: 50 before + 50 in range
    all_candles = [
        create_mock_candle(start_ts - 50 + i, 40000 + i * 10)
        for i in range(100)
    ]

    candles_in_range = [
        c for c in all_candles
        if start_ts <= extract_ts(c) <= end_ts
    ]

    # Correct pagination simulation
    def mock_query(**kwargs):
        if "BETWEEN" in kwargs["KeyConditionExpression"]:
            return {"Items": candles_in_range}
        limit = kwargs.get("Limit", len(all_candles))
        return {"Items": all_candles[-limit:], "LastEvaluatedKey": None}

    mock_table.query.side_effect = mock_query
    mock_table.update_item.return_value = {}

    result = calculate_range(pair, timeframe, start_ts, end_ts)

    expected = len(candles_in_range) - 34
    assert result["processed"] == expected
    assert mock_table.update_item.call_count == expected


@patch("lambda_function.table")
def test_calculate_range_returns_no_candles_when_range_empty(mock_table):
    mock_table.query.return_value = {"Items": []}

    result = calculate_range("XXBTZUSD", "1m", 1000000, 1000010)

    assert result["status"] == "no candles found"


@patch("lambda_function.table")
def test_calculate_range_handles_insufficient_history(mock_table):
    candles = [
        create_mock_candle(1000000 + i, 40000 + i * 10)
        for i in range(5)
    ]

    mock_table.query.side_effect = [
        {"Items": candles},  # range
        {"Items": candles}   # window
    ]

    result = calculate_range("XXBTZUSD", "1m", 1000000, 1000003)

    assert result["status"] == "insufficient_history"
    assert result["available_closes"] == 5


@patch("lambda_function.table")
def test_calculate_range_with_pagination(mock_table):
    pair = "XXBTZUSD"
    timeframe = "1m"
    start_ts = 1000000
    end_ts = 1000299  # 300 candles in range

    # 400 candles total: 100 before + 300 in range
    all_candles = [
        create_mock_candle(start_ts - 100 + i, 40000 + i * 10)
        for i in range(400)
    ]

    candles_in_range = [
        c for c in all_candles
        if start_ts <= extract_ts(c) <= end_ts
    ]

    # Correct pagination simulation
    def mock_query(**kwargs):
        if "BETWEEN" in kwargs["KeyConditionExpression"]:
            return {"Items": candles_in_range}
        limit = kwargs.get("Limit", len(all_candles))
        return {"Items": all_candles[-limit:], "LastEvaluatedKey": None}

    mock_table.query.side_effect = mock_query
    mock_table.update_item.return_value = {}

    result = calculate_range(pair, timeframe, start_ts, end_ts)

    expected = len(candles_in_range) - 34
    assert result["processed"] == expected
    assert mock_table.update_item.call_count == expected


@patch("lambda_function.table")
def test_calculate_range_ta_values_are_valid(mock_table):
    pair = "XXBTZUSD"
    timeframe = "1m"
    start_ts = 1000000
    end_ts = 1000050

    candles = [
        create_mock_candle(1000000 - 50 + i, 40000 + i * 5)
        for i in range(100)
    ]

    candles_in_range = [
        c for c in candles
        if start_ts <= extract_ts(c) <= end_ts
    ]

    mock_table.query.side_effect = [
        {"Items": candles_in_range},
        {"Items": candles}
    ]

    updates = []
    def capture_update(**kwargs):
        updates.append(kwargs)

    mock_table.update_item.side_effect = capture_update

    result = calculate_range(pair, timeframe, start_ts, end_ts)

    assert len(updates) > 0

    for call in updates:
        vals = call["ExpressionAttributeValues"]
        assert ":rsi" in vals
        assert ":macd" in vals
        assert ":ema" in vals
        assert ":ts" in vals
