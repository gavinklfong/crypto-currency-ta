import json
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import MagicMock

import lambda_function as export_scheduler


# ------------------------------------------------------------
# Freeze time at a deterministic moment
# ------------------------------------------------------------
def fixed_now():
    # Saturday 2024-05-25 05:15:30 UTC
    return datetime(2024, 5, 25, 5, 15, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def freeze_time(monkeypatch):
    class FixedDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now()

    monkeypatch.setattr(export_scheduler, "datetime", FixedDT)
    yield


@pytest.fixture
def mock_events(monkeypatch):
    mock = MagicMock()
    mock.put_events = MagicMock(return_value={"FailedEntryCount": 0})
    monkeypatch.setattr(export_scheduler, "events", mock)
    return mock


def parse_detail(entry):
    return json.loads(entry["Detail"])


# ------------------------------------------------------------
# Expected timestamp table for ALL timeframes
# Includes human-readable comments for clarity
#
# NOTE: These expectations match the scheduler's logic which emits
# "previous period(s)" relative to now (index=1 => previous period).
# ------------------------------------------------------------
EXPECTED = {
    "1m": [
        # index=1 -> previous hour: 2024-05-25 04:00:00 -> 04:59:59 UTC
        (1716613200, 1716616799),

        # index=2 -> two hours ago: 2024-05-25 03:00:00 -> 03:59:59 UTC
        (1716609600, 1716613199),
    ],

    "5m": [
        # same hourly windows as 1m
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
        # index=1 -> previous 4h block:
        # block_start = 2024-05-25 04:00 (current block), previous block start = 00:00
        # 2024-05-25 00:00:00 -> 2024-05-25 03:59:59 UTC
        (1716595200, 1716613199),

        # index=2 -> two blocks ago: 2024-05-24 20:00:00 -> 2024-05-24 23:59:59 UTC
        (1716552000, 1716595199),
    ],

    "1d": [
        # index=1 -> previous day: 2024-05-24 00:00:00 -> 2024-05-24 23:59:59 UTC
        (1716508800, 1716595199),

        # index=2 -> two days ago: 2024-05-23 00:00:00 -> 2024-05-23 23:59:59 UTC
        (1716422400, 1716508799),
    ],

    "1w": [
        # The scheduler computes Monday of the current week then subtracts weeks.
        # For fixed_now = 2024-05-25 (Saturday), monday = 2024-05-20.
        # index=1 -> previous week: Mon 2024-05-13 00:00 -> Sun 2024-05-19 23:59:59
        (1715558400, 1716163199),

        # index=2 -> two weeks ago: Mon 2024-05-06 00:00 -> Sun 2024-05-12 23:59:59
        (1714953600, 1715558399),
    ],

    "1M": [
        # index=1 -> previous month (April 2024)
        # 2024-04-01 00:00:00 -> 2024-05-01 00:00:00 - 1s
        (1711929600, 1714521599),
    ],
}


# ------------------------------------------------------------
# Full timeframe test (order-agnostic)
# ------------------------------------------------------------
@pytest.mark.parametrize("timeframe", EXPECTED.keys())
def test_scheduler_all_timeframes(timeframe, mock_events):
    event = {
        "detail": {
            "symbol": "BTCUSD",
            "timeframe": timeframe
        }
    }

    result = export_scheduler.lambda_handler(event, None)

    expected_periods = len(EXPECTED[timeframe])
    assert result["periods_sent"] == expected_periods
    assert result["events_emitted"] == expected_periods

    calls = mock_events.put_events.call_args_list
    assert len(calls) >= 1

    # Collect all emitted entries (they may be batched)
    emitted_entries = []
    for call in calls:
        emitted_entries.extend(call[1]["Entries"])

    assert len(emitted_entries) == expected_periods

    # Parse details and sort by start_ts descending (most recent first)
    emitted_details = [parse_detail(e) for e in emitted_entries]
    emitted_details_sorted = sorted(emitted_details, key=lambda d: d["start_ts"], reverse=True)

    # Sort expected by start_ts descending as well
    expected_sorted = sorted(EXPECTED[timeframe], key=lambda p: p[0], reverse=True)

    # Compare each expected period to emitted period
    for (exp_start, exp_end), emitted in zip(expected_sorted, emitted_details_sorted):
        assert emitted["symbol"] == "BTCUSD"
        assert emitted["timeframe"] == timeframe
        assert emitted["start_ts"] == exp_start
        assert emitted["end_ts"] == exp_end


# ------------------------------------------------------------
# Test batching logic (more than 10 entries)
# ------------------------------------------------------------
def test_scheduler_batching(monkeypatch, mock_events):
    # Force many periods
    monkeypatch.setattr(export_scheduler, "get_period_count", lambda tf: 25)

    event = {
        "detail": {
            "symbol": "BTCUSD",
            "timeframe": "1h"
        }
    }

    result = export_scheduler.lambda_handler(event, None)

    assert result["events_emitted"] == 25

    # 25 entries → 3 batches: 10, 10, 5
    calls = mock_events.put_events.call_args_list
    assert len(calls) == 3

    batch_sizes = [len(c[1]["Entries"]) for c in calls]
    assert batch_sizes == [10, 10, 5]
