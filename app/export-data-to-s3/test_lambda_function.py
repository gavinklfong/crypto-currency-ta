import pytest
from unittest.mock import patch
from freezegun import freeze_time

import lambda_function

EXPECTED = {
    "1m": [
        (1716606000, 1716609599),
        (1716609600, 1716613199),
    ],
    "5m": [
        (1716606000, 1716609599),
        (1716609600, 1716613199),
    ],
    "15m": [
        (1716606000, 1716609599),
        (1716609600, 1716613199),
    ],
    "30m": [
        (1716606000, 1716609599),
        (1716609600, 1716613199),
    ],
    "1h": [
        (1716606000, 1716609599),
        (1716609600, 1716613199),
    ],
    "4h": [
        (1716508800, 1716595199),
    ],
    "1d": [
        (1716422400, 1716508799),  # 2024‑05‑23 full day
        (1716508800, 1716595199),  # 2024‑05‑24 full day        
    ],
}


ALL_TIMEFRAMES = list(EXPECTED.keys())


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

    mock_table.query.return_value = {"Items": []}

    event = {"detail": {"symbol": symbol, "timeframe": timeframe}}

    result = lambda_function.lambda_handler(event, None)

    expected_periods = EXPECTED[timeframe]

    assert result["status"] == "ok"
    assert result["symbol"] == symbol
    assert result["timeframe"] == timeframe
    assert result["periods_exported"] == len(expected_periods)

    assert mock_export.call_count == len(expected_periods)

    actual_calls = [
        (c.args[0], c.args[1], c.args[2], c.args[3])
        for c in mock_export.call_args_list
    ]

    print("mock_export.call_args_list:")
    print(mock_export.call_args_list)

    expected_calls = [
        (symbol, timeframe, s, e)
        for (s, e) in expected_periods
    ]

    assert actual_calls == expected_calls
