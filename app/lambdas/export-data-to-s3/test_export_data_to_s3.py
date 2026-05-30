import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from lambda_function import (
    build_s3_key,
    query_dynamodb,
    prepare_dataframe,
    dataframe_to_parquet_buffer,
    write_to_s3,
    lambda_handler
)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def ts(dt_str):
    """Convert ISO datetime to epoch."""
    return int(datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc).timestamp())


# ------------------------------------------------------------
# Partitioning Tests for ALL Timeframes
# ------------------------------------------------------------
def ts(dt_str: str) -> int:
    return int(datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc).timestamp())


@pytest.mark.parametrize("timeframe, dt_str, expected", [
    # Hourly‑partitioned
    ("1m",  "2024-05-25T03:15:00", "symbol=BTCUSD/tf=1m/date=2024-05-25/hour=03/data.parquet"),
    ("5m",  "2024-05-25T03:15:00", "symbol=BTCUSD/tf=5m/date=2024-05-25/hour=03/data.parquet"),
    ("15m", "2024-05-25T03:15:00", "symbol=BTCUSD/tf=15m/date=2024-05-25/hour=03/data.parquet"),
    ("30m", "2024-05-25T03:15:00", "symbol=BTCUSD/tf=30m/date=2024-05-25/hour=03/data.parquet"),
    ("1h",  "2024-05-25T03:15:00", "symbol=BTCUSD/tf=1h/date=2024-05-25/hour=03/data.parquet"),

    # 4h block
    ("4h",  "2024-05-25T03:15:00", "symbol=BTCUSD/tf=4h/date=2024-05-25/data.parquet"),
    ("4h",  "2024-05-25T14:00:00", "symbol=BTCUSD/tf=4h/date=2024-05-25/data.parquet"),

    # Daily
    ("1d",  "2024-05-25T10:00:00", "symbol=BTCUSD/tf=1d/date=2024-05-25/data.parquet"),

    # # Weekly (ISO week 2024‑W21)
    # ("1w",  "2024-05-25T10:00:00", "symbol=BTCUSD/tf=1w/week=2024-W21/data.parquet"),

    # # Monthly
    # ("1M",  "2024-05-25T10:00:00", "symbol=BTCUSD/tf=1M/month=2024-05/data.parquet"),
])
def test_build_s3_key_all_timeframes(timeframe, dt_str, expected):
    start_ts = ts(dt_str)
    key = build_s3_key("BTCUSD", timeframe, start_ts)
    assert key == expected


def test_partitioning_4h():
    # 03:15 → block=00
    start_ts = ts("2024-05-25T03:15:00")
    key = build_s3_key("BTCUSD", "4h", start_ts)
    assert key == "symbol=BTCUSD/tf=4h/date=2024-05-25/data.parquet"

    # 14:00 → block=12
    start_ts = ts("2024-05-25T14:00:00")
    key = build_s3_key("BTCUSD", "4h", start_ts)
    assert key == "symbol=BTCUSD/tf=4h/date=2024-05-25/data.parquet"


def test_partitioning_1d():
    start_ts = ts("2024-05-25T10:00:00")
    key = build_s3_key("BTCUSD", "1d", start_ts)
    assert key == "symbol=BTCUSD/tf=1d/date=2024-05-25/data.parquet"


def test_partitioning_1w():
    # 2024-05-25 is ISO week 21
    start_ts = ts("2024-05-25T10:00:00")
    key = build_s3_key("BTCUSD", "1w", start_ts)
    assert key == "symbol=BTCUSD/tf=1w/week=2024-W21/data.parquet"


def test_partitioning_1M():
    start_ts = ts("2024-05-25T10:00:00")
    key = build_s3_key("BTCUSD", "1M", start_ts)
    assert key == "symbol=BTCUSD/tf=1M/month=2024-05/data.parquet"


# ------------------------------------------------------------
# DynamoDB + DataFrame + Parquet Tests
# ------------------------------------------------------------
@pytest.fixture
def sample_items():
    return [
        {
            "pair": "BTCUSD",
            "timeframe": "1m",
            "timestamp": 1716615600,
            "open": "100",
            "high": "110",
            "low": "90",
            "close": "105",
            "volume": "123.45",
            "ha_open": "100",
            "ha_high": "110",
            "ha_low": "90",
            "ha_close": "105",
            "median_price": "102.5",
            "typical_price": "103.3",
            "vwap": "104.1",
            "timeframe_minutes": "1",
            "created_at": "2024-01-01T00:00:00Z",
            "ta": {"rsi": 55}
        }
    ]


@patch("lambda_function.table")
def test_query_dynamodb(mock_table, sample_items):
    mock_table.query.return_value = {"Items": sample_items}
    items = query_dynamodb("BTCUSD", "1m", 1000, 2000)
    assert len(items) == 1
    mock_table.query.assert_called_once()


def test_prepare_dataframe(sample_items):
    df = prepare_dataframe(sample_items)
    assert df["open"].iloc[0] == 100.0
    assert df["volume"].iloc[0] == 123.45
    assert "created_at" in df.columns


def test_dataframe_to_parquet_buffer(sample_items):
    df = prepare_dataframe(sample_items)
    buffer = dataframe_to_parquet_buffer(df)
    assert buffer.getbuffer().nbytes > 0


# ------------------------------------------------------------
# S3 Upload Test
# ------------------------------------------------------------
@patch("lambda_function.s3")
def test_write_to_s3(mock_s3, sample_items):
    df = prepare_dataframe(sample_items)
    buffer = dataframe_to_parquet_buffer(df)
    write_to_s3(buffer, "test/path.parquet")
    mock_s3.put_object.assert_called_once()


# ------------------------------------------------------------
# Lambda Handler Tests
# ------------------------------------------------------------
@patch("lambda_function.write_to_s3")
@patch("lambda_function.build_s3_key")
@patch("lambda_function.dataframe_to_parquet_buffer")
@patch("lambda_function.prepare_dataframe")
@patch("lambda_function.query_dynamodb")
def test_lambda_handler_success(
    mock_query,
    mock_prepare,
    mock_parquet,
    mock_s3key,
    mock_write,
    sample_items
):
    event = {
        "detail": {
            "symbol": "BTCUSD",
            "timeframe": "1m",
            "start_ts": 1716615600,
            "end_ts": 1716615659
        }
    }

    mock_query.return_value = sample_items
    mock_prepare.return_value = prepare_dataframe(sample_items)
    mock_parquet.return_value = MagicMock()
    mock_s3key.return_value = "symbol=BTCUSD/tf=1m/date=2024-05-25/hour=03/data.parquet"

    result = lambda_handler(event, None)

    assert result["status"] == "ok"
    assert "periods_exported" in result
    assert mock_write.call_count == 2


@patch("lambda_function.query_dynamodb")
def test_lambda_handler_empty(mock_query):
    event = {
        "detail": {
            "symbol": "BTCUSD",
            "timeframe": "1m",
            "start_ts": 1716615600,
            "end_ts": 1716615659
        }
    }

    mock_query.return_value = []
    result = lambda_handler(event, None)
    assert result["status"] == "ok"
