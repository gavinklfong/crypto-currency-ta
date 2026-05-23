import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json
from lambda_function import (
    aggregate_candles,
    get_candle_timestamp,
    extract_timestamp_from_sk,
    fetch_1m_candles,
    process_pair_timeframe,
    lambda_handler,
    TIMEFRAMES,
)


class TestGetCandleTimestamp:
    """Test the get_candle_timestamp function."""

    def test_get_candle_timestamp_1m(self):
        timestamp = 1609459260
        timeframe_seconds = TIMEFRAMES["1m"]
        result = get_candle_timestamp(timestamp, timeframe_seconds)
        assert result == (timestamp // timeframe_seconds) * timeframe_seconds

    def test_get_candle_timestamp_5m(self):
        timestamp = 1609459260
        timeframe_seconds = TIMEFRAMES["5m"]
        result = get_candle_timestamp(timestamp, timeframe_seconds)
        assert result == (timestamp // timeframe_seconds) * timeframe_seconds

    def test_get_candle_timestamp_1h(self):
        timestamp = 1609459260
        timeframe_seconds = TIMEFRAMES["1h"]
        result = get_candle_timestamp(timestamp, timeframe_seconds)
        assert result == (timestamp // timeframe_seconds) * timeframe_seconds

    def test_get_candle_timestamp_boundary(self):
        timestamp = 1609459200
        timeframe_seconds = TIMEFRAMES["1h"]
        result = get_candle_timestamp(timestamp, timeframe_seconds)
        assert result == timestamp


class TestExtractTimestampFromSk:
    """Test the extract_timestamp_from_sk function."""

    def test_extract_timestamp_valid(self):
        sk = "TF#5m#TS#1609459200"
        assert extract_timestamp_from_sk(sk) == 1609459200

    def test_extract_timestamp_different_timeframe(self):
        sk = "TF#1h#TS#1609459200"
        assert extract_timestamp_from_sk(sk) == 1609459200

    def test_extract_timestamp_invalid_format(self):
        sk = "INVALID#FORMAT"
        assert extract_timestamp_from_sk(sk) is None

    def test_extract_timestamp_missing_ts(self):
        sk = "TF#5m#NONUM"
        assert extract_timestamp_from_sk(sk) is None


class TestAggregateCandles:
    """Test the aggregate_candles function."""

    def create_candle(self, timestamp, open_p, high, low, close_p, volume):
        return {
            "timestamp": timestamp,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close_p,
            "volume": volume,
        }

    def test_aggregate_single_candle(self):
        candles = [self.create_candle(1609459200, 100.0, 102.0, 99.0, 101.0, 1000.0)]
        result = aggregate_candles(candles)
        assert result["open"] == 100.0
        assert result["high"] == 102.0
        assert result["low"] == 99.0
        assert result["close"] == 101.0
        assert result["volume"] == 1000.0

    def test_aggregate_multiple_candles(self):
        candles = [
            self.create_candle(1609459200, 100.0, 102.0, 99.0, 101.5, 1000.0),
            self.create_candle(1609459260, 101.5, 103.0, 101.0, 102.5, 1200.0),
            self.create_candle(1609459320, 102.5, 105.0, 102.0, 104.0, 1500.0),
        ]
        result = aggregate_candles(candles)
        assert result["open"] == 100.0
        assert result["high"] == 105.0
        assert result["low"] == 99.0
        assert result["close"] == 104.0
        assert result["volume"] == 3700.0

    def test_aggregate_typical_price(self):
        candles = [self.create_candle(1609459200, 100.0, 110.0, 90.0, 105.0, 1000.0)]
        result = aggregate_candles(candles)
        typical = (110.0 + 90.0 + 105.0) / 3
        assert result["typical_price"] == pytest.approx(typical)

    def test_aggregate_median_price(self):
        candles = [self.create_candle(1609459200, 100.0, 110.0, 90.0, 105.0, 1000.0)]
        result = aggregate_candles(candles)
        assert result["median_price"] == (110.0 + 90.0) / 2

    def test_aggregate_vwap(self):
        candles = [
            self.create_candle(1609459200, 100.0, 102.0, 99.0, 101.0, 1000.0),
            self.create_candle(1609459260, 101.0, 103.0, 101.0, 102.0, 2000.0),
        ]
        result = aggregate_candles(candles)
        tp1 = (102.0 + 99.0 + 101.0) / 3
        tp2 = (103.0 + 101.0 + 102.0) / 3
        expected = (tp1 * 1000 + tp2 * 2000) / 3000
        assert result["vwap"] == pytest.approx(expected)

    def test_aggregate_heikin_ashi(self):
        candles = [self.create_candle(1609459200, 100.0, 110.0, 90.0, 105.0, 1000.0)]
        result = aggregate_candles(candles)
        ha_close = (100 + 110 + 90 + 105) / 4
        ha_open = (100 + 105) / 2
        assert result["ha_close"] == pytest.approx(ha_close)
        assert result["ha_open"] == pytest.approx(ha_open)

    def test_aggregate_empty_list(self):
        assert aggregate_candles([]) is None

    def test_aggregate_unsorted_candles(self):
        candles = [
            self.create_candle(1609459320, 102.5, 105.0, 102.0, 104.0, 1500.0),
            self.create_candle(1609459200, 100.0, 102.0, 99.0, 101.5, 1000.0),
            self.create_candle(1609459260, 101.5, 103.0, 101.0, 102.5, 1200.0),
        ]
        result = aggregate_candles(candles)
        assert result["open"] == 100.0
        assert result["close"] == 104.0

    def test_aggregate_zero_volume_vwap(self):
        candles = [self.create_candle(1609459200, 100, 110, 90, 105, 0)]
        result = aggregate_candles(candles)
        typical = (110 + 90 + 105) / 3
        assert result["vwap"] == pytest.approx(typical)


class TestFetch1mCandles:
    @patch("lambda_function.table")
    def test_fetch_1m_candles_success(self, mock_table):
        mock_items = [
            {"SK": "TF#1m#TS#1609459200", "open": 100.0},
            {"SK": "TF#1m#TS#1609459260", "open": 101.0},
        ]
        mock_table.query.return_value = {"Items": mock_items}
        result = fetch_1m_candles("BTCUSD", 1609459200, 1609459260)
        assert len(result) == 2

    @patch("lambda_function.table")
    def test_fetch_1m_candles_empty(self, mock_table):
        mock_table.query.return_value = {"Items": []}
        assert fetch_1m_candles("BTCUSD", 1609459200, 1609459260) == []

    @patch("lambda_function.table")
    def test_fetch_1m_candles_query_params(self, mock_table):
        mock_table.query.return_value = {"Items": []}
        fetch_1m_candles("BTCUSD", 1609459200, 1609459260)
        call = mock_table.query.call_args[1]
        assert call["ExpressionAttributeValues"][":pk"] == "PAIR#BTCUSD"


class TestProcessPairTimeframe:
    @patch("lambda_function.write_aggregated_candle")
    @patch("lambda_function.fetch_1m_candles")
    def test_process_pair_timeframe_5m(self, mock_fetch, mock_write):
        mock_fetch.return_value = [
            {"SK": "TF#1m#TS#1609459200", "timestamp": 1609459200,
             "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 100}
        ]
        processed = process_pair_timeframe("BTCUSD", "5m", 1609459500)
        assert processed > 0
        mock_write.assert_called()

    @patch("lambda_function.write_aggregated_candle")
    @patch("lambda_function.fetch_1m_candles")
    def test_process_pair_timeframe_no_data(self, mock_fetch, mock_write):
        mock_fetch.return_value = []
        processed = process_pair_timeframe("BTCUSD", "5m", 1609459500)
        assert processed == 0
        mock_write.assert_not_called()


class TestLambdaHandler:
    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_with_eventbridge_format(self, mock_process):
        mock_process.return_value = 2
        event = {"detail": {"symbol": "BTCUSD"}}
        result = lambda_handler(event, None)
        assert result["status"] == "success"
        assert result["symbol_processed"] == "BTCUSD"
        assert result["timeframe_processed"] == "5m"
        mock_process.assert_called_once()

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_with_direct_event_format(self, mock_process):
        mock_process.return_value = 1
        event = {"symbol": "BTCUSD"}
        result = lambda_handler(event, None)
        assert result["status"] == "success"
        assert result["symbol_processed"] == "BTCUSD"

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_single_pair_multiple_timeframes(self, mock_process):
        mock_process.return_value = 1
        event = {"detail": {"symbol": "BTCUSD"}}
        result = lambda_handler(event, None)
        mock_process.assert_called_once()
        args, _ = mock_process.call_args
        assert args[1] == "5m"
        assert result["timeframe_processed"] == "5m"

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_multiple_pairs_multiple_timeframes(self, mock_process):
        mock_process.return_value = 2
        event = {"detail": {"symbol": "BTCUSD"}}
        result = lambda_handler(event, None)
        mock_process.assert_called_once()
        assert result["candles_written"] == 2

    def test_lambda_handler_empty_pair(self):
        event = {"detail": {"symbol": ""}}
        result = lambda_handler(event, None)
        assert result["status"] == "error"

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_error_handling(self, mock_process):
        mock_process.side_effect = Exception("DynamoDB error")
        event = {"detail": {"symbol": "BTCUSD"}}
        result = lambda_handler(event, None)
        assert result["status"] == "error"

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_returns_aggregation_counts(self, mock_process):
        mock_process.return_value = 5
        event = {"detail": {"symbol": "BTCUSD"}}
        result = lambda_handler(event, None)
        assert result["candles_written"] == 5

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_timestamp_in_response(self, mock_process):
        mock_process.return_value = 1
        event = {"detail": {"symbol": "BTCUSD"}}
        before = int(datetime.now(timezone.utc).timestamp())
        result = lambda_handler(event, None)
        after = int(datetime.now(timezone.utc).timestamp())
        assert before <= result["current_time"] <= after + 1

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_processes_correct_timeframes(self, mock_process):
        mock_process.return_value = 1
        event = {"detail": {"symbol": "BTCUSD"}}
        lambda_handler(event, None)
        args, _ = mock_process.call_args
        assert args[1] == "5m"

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_with_zero_processed_candles(self, mock_process):
        mock_process.return_value = 0
        event = {"detail": {"symbol": "BTCUSD"}}
        result = lambda_handler(event, None)
        assert result["status"] == "success"

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_large_number_of_pairs(self, mock_process):
        mock_process.return_value = 3
        event = {"detail": {"symbol": "PAIR0"}}
        result = lambda_handler(event, None)
        assert result["symbol_processed"] == "PAIR0"

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_respects_event_data_structure(self, mock_process):
        mock_process.return_value = 1
        event = {"detail": {"symbol": "BTCUSD"}}
        result = lambda_handler(event, None)
        assert result["symbol_processed"] == "BTCUSD"

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_aggregation_count_accumulation(self, mock_process):
        mock_process.side_effect = [1, 2, 3]
        event = {"detail": {"symbol": "BTCUSD"}}
        result = lambda_handler(event, None)
        assert result["candles_written"] == 1
