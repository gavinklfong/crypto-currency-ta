import pytest
from unittest.mock import patch
from freezegun import freeze_time

import lambda_function   # update if needed


# ------------------------------------------------------------
# Hardcoded expected periods for each timeframe
# ------------------------------------------------------------
EXPECTED = {
    "1m": [
        (1716613200, 1716616799),  # 04:00–04:59:59
        (1716609600, 1716613199),  # 03:00–03:59:59
    ],
    "5m": [
        (1716613200, 1716616799),
        (1716609600, 1716613199),
    ],
    "15m": [
        (1716613200, 1716616799),
        (1716609600, 1716613199),
    ],
    "30m": [
        (1716613200, 1716616799),
        (1716609600, 1716613199),
    ],
    "1h": [
        (1716613200, 1716616799),
        (1716609600, 1716613199),
    ],
    "4h": [
        (1716595200, 1716681599),  # previous day 00:00–23:59:59
    ],
    "1d": [
        (1716508800, 1716595199),  # previous day
        (1716422400, 1716508799),  # day before previous
    ],
}

ALL_TIMEFRAMES = list(EXPECTED.keys())


# ------------------------------------------------------------
# Main test — verifies export_data_to_s3() calls exactly
# ------------------------------------------------------------
@freeze_time("2024-05-25 05:15:30 UTC")
@pytest.mark.parametrize("timeframe", ALL_TIMEFRAMES)
@patch("lambda_function.export_data_to_s3")
@patch("lambda_function.s3")
@patch("lambda_function.table")
def test_lambda_handler_all_timeframes(
    mock_table,
    mock_s3,
    mock_export,
    timeframe,
):
    symbol = "BTCUSD"

    # DynamoDB returns empty list (we only test handler logic)
    mock_table.query.return_value = {"Items": []}

    event = {
        "detail": {
            "symbol": symbol,
            "timeframe": timeframe,
        }
    }

    # Run lambda
    result = lambda_function.lambda_handler(event, None)

    # Validate return
    expected_periods = EXPECTED[timeframe]
    assert result["status"] == "ok"
    assert result["symbol"] == symbol
    assert result["timeframe"] == timeframe
    assert result["periods_exported"] == len(expected_periods)

    # Validate export_data_to_s3 calls
    assert mock_export.call_count == len(expected_periods)

    # Extract actual calls: (symbol, timeframe, start_ts, end_ts)
    actual_calls = [
        (c.args[0], c.args[1], c.args[2], c.args[3])
        for c in mock_export.call_args_list
    ]

    # Build expected calls
    expected_calls = [
        (symbol, timeframe, start_ts, end_ts)
        for (start_ts, end_ts) in expected_periods
    ]

    # Compare EXACTLY
    assert actual_calls == expected_calls


# ------------------------------------------------------------
# Error cases
# ------------------------------------------------------------
def test_lambda_handler_missing_symbol():
    event = {"detail": {"timeframe": "1h"}}
    with pytest.raises(ValueError):
        lambda_function.lambda_handler(event, None)


def test_lambda_handler_missing_timeframe():
    event = {"detail": {"symbol": "BTCUSD"}}
    with pytest.raises(ValueError):
        lambda_function.lambda_handler(event, None)
