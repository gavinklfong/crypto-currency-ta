import json
import math
from unittest.mock import MagicMock, call

import pytest

# import the scheduler module (update name if your file is different)
import export_trigger


# Helper: create a FixedDatetime class that returns a deterministic "now"
def make_fixed_datetime(fixed_dt):
    """
    Returns a datetime-like class with a .now(tz) classmethod that returns fixed_dt.
    This lets us monkeypatch export_trigger.datetime to a deterministic value.
    """
    from datetime import datetime as _dt

    class FixedDateTime(_dt):
        @classmethod
        def now(cls, tz=None):
            return fixed_dt

    return FixedDateTime


@pytest.fixture(autouse=True)
def freeze_time(monkeypatch):
    """
    Freeze time for tests to a known UTC datetime:
    2024-05-25T05:15:30Z (so current_hour floors to 05:00 UTC)
    """
    from datetime import datetime, timezone

    fixed_dt = datetime(2024, 5, 25, 5, 15, 30, tzinfo=timezone.utc)
    FixedDateTime = make_fixed_datetime(fixed_dt)
    # Patch the module-level datetime used in export_trigger
    monkeypatch.setattr(export_trigger, "datetime", FixedDateTime)
    yield


@pytest.fixture
def mock_events_client(monkeypatch):
    """
    Replace export_trigger.events with a MagicMock that records put_events calls.
    """
    mock = MagicMock()
    mock.put_events = MagicMock(return_value={"FailedEntryCount": 0, "Entries": []})
    monkeypatch.setattr(export_trigger, "events", mock)
    return mock


def _parse_detail(entry):
    return json.loads(entry["Detail"])


def test_emits_expected_number_of_events_and_batches(mock_events_client, monkeypatch):
    """
    With default config:
      HOUR_WINDOW = 2
      SYMBOLS = ["XXBTXUSD", "XETHZUSD"]  (2)
      TIMEFRAMES = 9
    Expect events_emitted = 2 * 2 * 9 = 36
    Expect put_events called ceil(36/10) = 4 times with batch sizes [10,10,10,6]
    """
    # Ensure module constants are the defaults (they are in the module, but assert for clarity)
    assert export_trigger.HOUR_WINDOW == 2
    assert len(export_trigger.SYMBOLS) == 2
    assert len(export_trigger.TIMEFRAMES) == 9

    result = export_trigger.lambda_handler({}, None)

    # Validate return payload
    assert result["status"] == "scheduled"
    assert result["hours_sent"] == export_trigger.HOUR_WINDOW
    assert result["symbols"] == len(export_trigger.SYMBOLS)
    assert result["timeframes"] == len(export_trigger.TIMEFRAMES)
    assert result["events_emitted"] == len(export_trigger.SYMBOLS) * len(export_trigger.TIMEFRAMES) * export_trigger.HOUR_WINDOW

    total_events = result["events_emitted"]
    expected_batches = math.ceil(total_events / 10)
    assert mock_events_client.put_events.call_count == expected_batches

    # Inspect each put_events call to verify batch sizes
    calls = mock_events_client.put_events.call_args_list
    batch_sizes = [len(call_args[1]["Entries"]) for call_args in calls]
    # expected pattern: [10,10,10, remainder]
    assert all(size <= 10 for size in batch_sizes)
    assert sum(batch_sizes) == total_events

    # Validate structure of first entry in first batch
    first_batch = calls[0][1]["Entries"]
    first_entry = first_batch[0]
    assert first_entry["Source"] == "dynamodb.export.scheduler"
    assert first_entry["DetailType"] == "export-hour"
    assert first_entry["EventBusName"] == export_trigger.EVENT_BUS_NAME

    detail = _parse_detail(first_entry)
    # detail must contain required keys
    assert set(detail.keys()) == {"symbol", "timeframe", "start_ts", "end_ts"}
    assert detail["symbol"] in export_trigger.SYMBOLS
    assert detail["timeframe"] in export_trigger.TIMEFRAMES
    assert isinstance(detail["start_ts"], int)
    assert isinstance(detail["end_ts"], int)
    # start_ts should be less than or equal to end_ts
    assert detail["start_ts"] <= detail["end_ts"]


def test_batches_correctly_when_custom_config(monkeypatch, mock_events_client):
    """
    Override module constants to create a scenario with 12 events (to test 10+2 batching).
    Use:
      HOUR_WINDOW = 1
      SYMBOLS = 6 symbols
      TIMEFRAMES = 2 timeframes
    Expect events = 1 * 6 * 2 = 12 -> put_events called twice with sizes [10,2]
    """
    monkeypatch.setattr(export_trigger, "HOUR_WINDOW", 1)
    monkeypatch.setattr(export_trigger, "SYMBOLS", [f"S{i}" for i in range(6)])
    monkeypatch.setattr(export_trigger, "TIMEFRAMES", ["1m", "1h"])

    result = export_trigger.lambda_handler({}, None)

    assert result["status"] == "scheduled"
    assert result["events_emitted"] == 12

    # Two put_events calls expected
    assert mock_events_client.put_events.call_count == 2
    calls = mock_events_client.put_events.call_args_list
    batch_sizes = [len(c[1]["Entries"]) for c in calls]
    assert batch_sizes == [10, 2]

    # Verify that all emitted details are valid and unique combinations
    all_details = []
    for c in calls:
        for entry in c[1]["Entries"]:
            d = _parse_detail(entry)
            all_details.append((d["symbol"], d["timeframe"], d["start_ts"], d["end_ts"]))

    assert len(all_details) == 12
    # ensure there are no duplicate (symbol, timeframe, start_ts) triples
    triples = {(s, tf, st) for s, tf, st, et in all_details}
    assert len(triples) == 12


def test_event_timestamps_are_hour_aligned(mock_events_client):
    """
    Verify that start_ts and end_ts correspond to the full previous hour(s).
    With frozen now = 2024-05-25T05:15:30Z:
      current_hour = 05:00
      For i=1 -> start_hour = 04:00, end_hour = 04:59:59
      For i=2 -> start_hour = 03:00, end_hour = 03:59:59
    Check a sample detail to ensure timestamps align to hour boundaries.
    """
    result = export_trigger.lambda_handler({}, None)
    # grab one detail from the emitted entries
    calls = mock_events_client.put_events.call_args_list
    # find any entry and parse
    any_entry = calls[0][1]["Entries"][0]
    detail = _parse_detail(any_entry)

    start_ts = detail["start_ts"]
    end_ts = detail["end_ts"]

    # start_ts should be divisible by 3600 (hour boundary)
    assert start_ts % 3600 == 0
    # end_ts should be start_ts + 3600 - 1
    assert end_ts == start_ts + 3600 - 1
