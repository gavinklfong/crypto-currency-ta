import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from main import (
    parse_quarter,
    split_time_period,
    build_s3_key,
    prepare_dataframe,
    dataframe_to_parquet_buffer,
    query_dynamodb,
    export_chunk,
)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def ts(dt_str: str) -> int:
    """Convert ISO datetime string to epoch timestamp."""
    return int(datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc).timestamp())


# ------------------------------------------------------------
# Quarter Parsing Tests
# ------------------------------------------------------------
@pytest.mark.parametrize("time_period, expected_year, expected_quarter", [
    ("2026_Q1", 2026, "Q1"),
    ("2026_Q2", 2026, "Q2"),
    ("2026_Q3", 2026, "Q3"),
    ("2026_Q4", 2026, "Q4"),
    ("2027_Q1", 2027, "Q1"),
    ("2027_Q4", 2027, "Q4"),
    ("1999_Q1", 1999, "Q1"),
    ("2030_Q4", 2030, "Q4"),
])
def test_parse_quarter_valid(time_period, expected_year, expected_quarter):
    start_ts, end_ts = parse_quarter(time_period)

    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)

    assert start_dt.year == expected_year
    assert end_dt.year == expected_year

    if expected_quarter == "Q1":
        assert start_dt.month == 1 and start_dt.day == 1
        assert end_dt.month == 3 and end_dt.day == 31
    elif expected_quarter == "Q2":
        assert start_dt.month == 4 and start_dt.day == 1
        assert end_dt.month == 6 and end_dt.day == 30
    elif expected_quarter == "Q3":
        assert start_dt.month == 7 and start_dt.day == 1
        assert end_dt.month == 9 and end_dt.day == 30
    elif expected_quarter == "Q4":
        assert start_dt.month == 10 and start_dt.day == 1
        assert end_dt.month == 12 and end_dt.day == 31


def test_parse_quarter_with_whitespace():
    """Whitespace should be trimmed."""
    start_ts, end_ts = parse_quarter("  2026_Q2  ")
    expected_start = ts("2026-04-01T00:00:00+00:00")
    assert start_ts == expected_start


@pytest.mark.parametrize("time_period", [
    "2026Q1",
    "2026Q_1",
    "26_Q1",
    "2026_Q5",
    "2026_Q0",
    "abc_Q1",
    "2026_X",
    "2026",
    "",
    "invalid",
])
def test_parse_quarter_invalid(time_period):
    with pytest.raises(ValueError):
        parse_quarter(time_period)


# ------------------------------------------------------------
# Split Time Period Tests
# ------------------------------------------------------------
class TestSplitTimePeriod:
    def test_1m_splits_hourly(self):
        """1m timeframe should split into 1-hour chunks."""
        start_ts = ts("2024-05-25T00:00:00+00:00")
        end_ts = ts("2024-05-25T05:30:00+00:00")

        chunks = split_time_period(start_ts, end_ts, "1m")
        assert len(chunks) == 6  # 6 hourly chunks

        # Verify first chunk starts at 00:00
        assert chunks[0]["start_ts"] == start_ts

    def test_4h_splits_daily(self):
        """4h timeframe should split into 1-day chunks."""
        start_ts = ts("2024-05-25T00:00:00+00:00")
        end_ts = ts("2024-05-27T23:59:59+00:00")

        chunks = split_time_period(start_ts, end_ts, "4h")
        assert len(chunks) == 3  # 3 daily chunks

    def test_1d_splits_daily(self):
        """1d timeframe should split into 1-day chunks."""
        start_ts = ts("2024-05-25T00:00:00+00:00")
        end_ts = ts("2024-05-27T23:59:59+00:00")

        chunks = split_time_period(start_ts, end_ts, "1d")
        assert len(chunks) == 3

    def test_1w_splits_daily(self):
        """1w timeframe should split into 1-day chunks."""
        start_ts = ts("2024-05-25T00:00:00+00:00")
        end_ts = ts("2024-05-31T23:59:59+00:00")

        chunks = split_time_period(start_ts, end_ts, "1w")
        assert len(chunks) == 7  # 7 days

    def test_single_chunk(self):
        """A single hour range should produce one chunk."""
        start_ts = ts("2024-05-25T01:00:00+00:00")
        end_ts = ts("2024-05-25T01:59:59+00:00")

        chunks = split_time_period(start_ts, end_ts, "5m")
        assert len(chunks) == 1

    def test_unsupported_timeframe_raises(self):
        with pytest.raises(ValueError):
            split_time_period(0, 1000, "invalid")


# ------------------------------------------------------------
# Build S3 Key Tests
# ------------------------------------------------------------
@pytest.mark.parametrize("timeframe, dt_str, expected", [
    ("1m",  "2024-05-25T03:15:00", "symbol=XBTUSD/tf=1m/date=2024-05-25/hour=03/data.parquet"),
    ("5m",  "2024-05-25T03:15:00", "symbol=XBTUSD/tf=5m/date=2024-05-25/hour=03/data.parquet"),
    ("1h",  "2024-05-25T03:15:00", "symbol=XBTUSD/tf=1h/date=2024-05-25/hour=03/data.parquet"),
    ("4h",  "2024-05-25T03:15:00", "symbol=XBTUSD/tf=4h/date=2024-05-25/data.parquet"),
    ("1d",  "2024-05-25T10:00:00", "symbol=XBTUSD/tf=1d/date=2024-05-25/data.parquet"),
    ("1w",  "2024-05-25T10:00:00", "symbol=XBTUSD/tf=1w/week=2024-W21/data.parquet"),
])
def test_build_s3_key(timeframe, dt_str, expected):
    start_ts = ts(dt_str)
    key = build_s3_key("XBTUSD", timeframe, start_ts)
    assert key == expected


def test_build_s3_key_unsupported_raises():
    with pytest.raises(ValueError):
        build_s3_key("XBTUSD", "invalid", 0)


# ------------------------------------------------------------
# DataFrame Preparation Tests
# ------------------------------------------------------------
@pytest.fixture
def sample_items():
    return [
        {
            "pair": "XBTUSD",
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
            "ta_rsi14": 55,
            "ta_macd": {"line": 0.5, "signal": 0.3, "histogram": 0.2},
            "ta_ema20": 104.5,
            "updated_at": "2024-01-01T00:00:00Z",
        }
    ]


def test_prepare_dataframe(sample_items):
    df = prepare_dataframe(sample_items)
    assert df["open"].iloc[0] == 100.0
    assert df["volume"].iloc[0] == 123.45
    assert df["close"].iloc[0] == 105.0
    assert "created_at" in df.columns


def test_prepare_dataframe_missing_cols(sample_items):
    """Items missing some columns should have them filled with None."""
    partial = [{"pair": "XBTUSD", "timestamp": 123}]
    df = prepare_dataframe(partial)
    assert df["open"].iloc[0] is None
    assert df["close"].iloc[0] is None


# ------------------------------------------------------------
# Parquet Buffer Test
# ------------------------------------------------------------
def test_dataframe_to_parquet_buffer(sample_items):
    df = prepare_dataframe(sample_items)
    buffer = dataframe_to_parquet_buffer(df)
    assert buffer.getbuffer().nbytes > 0
    buffer.seek(0)
    # Verify it's valid Parquet
    import pyarrow.parquet as pq
    table = pq.read_table(buffer)
    assert table.num_rows == 1


# ------------------------------------------------------------
# DynamoDB Query Test
# ------------------------------------------------------------
@patch("main.table")
def test_query_dynamodb(mock_table, sample_items):
    mock_table.query.return_value = {"Items": sample_items}
    items = query_dynamodb("XBTUSD", "1m", 1000, 2000)
    assert len(items) == 1
    mock_table.query.assert_called_once()


@patch("main.table")
def test_query_dynamodb_pagination(mock_table, sample_items):
    """Should handle pagination via LastEvaluatedKey."""
    mock_table.query.side_effect = [
        {"Items": sample_items, "LastEvaluatedKey": {"pk": "next"}},
        {"Items": []},
    ]

    items = query_dynamodb("XBTUSD", "1m", 1000, 2000)
    assert len(items) == 1
    assert mock_table.query.call_count == 2


# ------------------------------------------------------------
# Export Chunk Test
# ------------------------------------------------------------
@pytest.fixture
def sample_items():
    return [
        {
            "pair": "XBTUSD",
            "timeframe": "1m",
            "timestamp": 1716615600,
            "open": "100",
            "high": "110",
            "low": "90",
            "close": "105",
            "volume": "123.45",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
    ]


@patch("main.export_chunk")
def test_export_chunk_success(mock_export, sample_items):
    with patch("main.query_dynamodb", return_value=sample_items), \
         patch("main.build_s3_key", return_value="test/key"), \
         patch("main.write_to_s3") as mock_write:
        result = export_chunk("XBTUSD", "1m", ts("2024-05-25T00:00:00+00:00"),
                              ts("2024-05-25T00:00:59+00:00"))
    assert result["status"] == "ok"
    assert result["records"] == 1
    mock_write.assert_called_once()


@patch("main.query_dynamodb")
def test_export_chunk_empty(mock_query):
    mock_query.return_value = []
    result = export_chunk("XBTUSD", "1m", ts("2024-05-25T00:00:00+00:00"),
                          ts("2024-05-25T00:00:59+00:00"))
    assert result["status"] == "empty"
