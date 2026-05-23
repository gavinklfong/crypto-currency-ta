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
        """Test 1-minute timeframe bucketing."""
        timestamp = 1609459260  # arbitrary timestamp
        timeframe_seconds = TIMEFRAMES["1m"]
        
        result = get_candle_timestamp(timestamp, timeframe_seconds)
        assert result == (timestamp // timeframe_seconds) * timeframe_seconds

    def test_get_candle_timestamp_5m(self):
        """Test 5-minute timeframe bucketing."""
        timestamp = 1609459260
        timeframe_seconds = TIMEFRAMES["5m"]
        
        result = get_candle_timestamp(timestamp, timeframe_seconds)
        expected = (timestamp // timeframe_seconds) * timeframe_seconds
        assert result == expected

    def test_get_candle_timestamp_1h(self):
        """Test 1-hour timeframe bucketing."""
        timestamp = 1609459260
        timeframe_seconds = TIMEFRAMES["1h"]
        
        result = get_candle_timestamp(timestamp, timeframe_seconds)
        expected = (timestamp // timeframe_seconds) * timeframe_seconds
        assert result == expected

    def test_get_candle_timestamp_boundary(self):
        """Test timestamp at exact boundary."""
        timestamp = 1609459200  # exact 1-hour boundary
        timeframe_seconds = TIMEFRAMES["1h"]
        
        result = get_candle_timestamp(timestamp, timeframe_seconds)
        assert result == timestamp


class TestExtractTimestampFromSk:
    """Test the extract_timestamp_from_sk function."""

    def test_extract_timestamp_valid(self):
        """Test extracting timestamp from valid SK."""
        sk = "TF#5m#TS#1609459200"
        result = extract_timestamp_from_sk(sk)
        assert result == 1609459200

    def test_extract_timestamp_different_timeframe(self):
        """Test extracting timestamp with different timeframe."""
        sk = "TF#1h#TS#1609459200"
        result = extract_timestamp_from_sk(sk)
        assert result == 1609459200

    def test_extract_timestamp_invalid_format(self):
        """Test extracting timestamp from invalid SK."""
        sk = "INVALID#FORMAT"
        result = extract_timestamp_from_sk(sk)
        assert result is None

    def test_extract_timestamp_missing_ts(self):
        """Test extracting timestamp when TS part is missing."""
        sk = "TF#5m#NONUM"
        result = extract_timestamp_from_sk(sk)
        assert result is None


class TestAggregateCandles:
    """Test the aggregate_candles function."""

    def create_candle(self, timestamp, open_p, high, low, close_p, volume):
        """Helper to create a candle dict."""
        return {
            "timestamp": timestamp,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close_p,
            "volume": volume,
        }

    def test_aggregate_single_candle(self):
        """Test aggregation with a single candle."""
        candles = [self.create_candle(1609459200, 100.0, 102.0, 99.0, 101.0, 1000.0)]
        
        result = aggregate_candles(candles)
        
        assert result["open"] == 100.0
        assert result["high"] == 102.0
        assert result["low"] == 99.0
        assert result["close"] == 101.0
        assert result["volume"] == 1000.0

    def test_aggregate_multiple_candles(self):
        """Test aggregation with multiple candles."""
        candles = [
            self.create_candle(1609459200, 100.0, 102.0, 99.0, 101.5, 1000.0),
            self.create_candle(1609459260, 101.5, 103.0, 101.0, 102.5, 1200.0),
            self.create_candle(1609459320, 102.5, 105.0, 102.0, 104.0, 1500.0),
        ]
        
        result = aggregate_candles(candles)
        
        assert result["open"] == 100.0  # First candle's open
        assert result["high"] == 105.0  # Max of all highs
        assert result["low"] == 99.0    # Min of all lows
        assert result["close"] == 104.0  # Last candle's close
        assert result["volume"] == 3700.0  # Sum of all volumes

    def test_aggregate_typical_price(self):
        """Test typical price calculation."""
        candles = [self.create_candle(1609459200, 100.0, 110.0, 90.0, 105.0, 1000.0)]
        
        result = aggregate_candles(candles)
        
        typical = (110.0 + 90.0 + 105.0) / 3
        assert result["typical_price"] == pytest.approx(typical)

    def test_aggregate_median_price(self):
        """Test median price calculation."""
        candles = [self.create_candle(1609459200, 100.0, 110.0, 90.0, 105.0, 1000.0)]
        
        result = aggregate_candles(candles)
        
        median = (110.0 + 90.0) / 2
        assert result["median_price"] == median

    def test_aggregate_vwap(self):
        """Test VWAP calculation."""
        candles = [
            self.create_candle(1609459200, 100.0, 102.0, 99.0, 101.0, 1000.0),
            self.create_candle(1609459260, 101.0, 103.0, 101.0, 102.0, 2000.0),
        ]
        
        result = aggregate_candles(candles)
        
        # VWAP = sum(typical_price * volume) / total_volume
        tp1 = (102.0 + 99.0 + 101.0) / 3
        tp2 = (103.0 + 101.0 + 102.0) / 3
        expected_vwap = (tp1 * 1000.0 + tp2 * 2000.0) / 3000.0
        
        assert result["vwap"] == pytest.approx(expected_vwap)

    def test_aggregate_heikin_ashi(self):
        """Test Heikin-Ashi calculation."""
        candles = [self.create_candle(1609459200, 100.0, 110.0, 90.0, 105.0, 1000.0)]
        
        result = aggregate_candles(candles)
        
        ha_close = (100.0 + 110.0 + 90.0 + 105.0) / 4
        ha_open = (100.0 + 105.0) / 2
        ha_high = max(110.0, ha_open, ha_close)
        ha_low = min(90.0, ha_open, ha_close)
        
        assert result["ha_close"] == pytest.approx(ha_close)
        assert result["ha_open"] == pytest.approx(ha_open)
        assert result["ha_high"] == ha_high
        assert result["ha_low"] == ha_low

    def test_aggregate_empty_list(self):
        """Test aggregation with empty list."""
        candles = []
        result = aggregate_candles(candles)
        assert result is None

    def test_aggregate_unsorted_candles(self):
        """Test aggregation with unsorted candles (should sort internally)."""
        candles = [
            self.create_candle(1609459320, 102.5, 105.0, 102.0, 104.0, 1500.0),
            self.create_candle(1609459200, 100.0, 102.0, 99.0, 101.5, 1000.0),
            self.create_candle(1609459260, 101.5, 103.0, 101.0, 102.5, 1200.0),
        ]
        
        result = aggregate_candles(candles)
        
        # Should still use first (by timestamp) open and last close
        assert result["open"] == 100.0
        assert result["close"] == 104.0

    def test_aggregate_zero_volume_vwap(self):
        """Test VWAP with zero volume (fallback to typical price)."""
        candles = [
            self.create_candle(1609459200, 100.0, 110.0, 90.0, 105.0, 0.0),
        ]
        
        result = aggregate_candles(candles)
        
        typical_price = (110.0 + 90.0 + 105.0) / 3
        assert result["vwap"] == pytest.approx(typical_price)


class TestFetch1mCandles:
    """Test the fetch_1m_candles function."""

    @patch("lambda_function.table")
    def test_fetch_1m_candles_success(self, mock_table):
        """Test successful fetch of 1-minute candles."""
        mock_items = [
            {"SK": "TF#1m#TS#1609459200", "open": 100.0, "close": 101.0},
            {"SK": "TF#1m#TS#1609459260", "open": 101.0, "close": 102.0},
        ]
        
        mock_table.query.return_value = {"Items": mock_items}
        
        result = fetch_1m_candles("BTCUSD", 1609459200, 1609459260)
        
        assert len(result) == 2
        assert result[0]["SK"] == "TF#1m#TS#1609459200"
        assert result[1]["SK"] == "TF#1m#TS#1609459260"

    @patch("lambda_function.table")
    def test_fetch_1m_candles_empty(self, mock_table):
        """Test fetch with no results."""
        mock_table.query.return_value = {"Items": []}
        
        result = fetch_1m_candles("BTCUSD", 1609459200, 1609459260)
        
        assert result == []

    @patch("lambda_function.table")
    def test_fetch_1m_candles_query_params(self, mock_table):
        """Test that query is called with correct parameters."""
        mock_table.query.return_value = {"Items": []}
        
        fetch_1m_candles("BTCUSD", 1609459200, 1609459260)
        
        mock_table.query.assert_called_once()
        call_kwargs = mock_table.query.call_args[1]
        
        assert call_kwargs["ExpressionAttributeValues"][":pk"] == "PAIR#BTCUSD"
        assert call_kwargs["ExpressionAttributeValues"][":sk_start"] == "TF#1m#TS#1609459200"
        assert call_kwargs["ExpressionAttributeValues"][":sk_end"] == "TF#1m#TS#1609459260"
        assert call_kwargs["ScanIndexForward"] is True
        assert call_kwargs["ConsistentRead"] is False


class TestProcessPairTimeframe:
    """Test the process_pair_timeframe function."""

    @patch("lambda_function.write_aggregated_candle")
    @patch("lambda_function.fetch_1m_candles")
    def test_process_pair_timeframe_5m(self, mock_fetch, mock_write):
        """Test processing a 5-minute timeframe."""
        # Create mock 1-minute candles
        mock_candles = [
            {"SK": "TF#1m#TS#1609459200", "timestamp": 1609459200, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 100.0},
            {"SK": "TF#1m#TS#1609459260", "timestamp": 1609459260, "open": 100.5, "high": 101.5, "low": 100.0, "close": 101.0, "volume": 120.0},
            {"SK": "TF#1m#TS#1609459320", "timestamp": 1609459320, "open": 101.0, "high": 102.0, "low": 100.5, "close": 101.5, "volume": 150.0},
            {"SK": "TF#1m#TS#1609459380", "timestamp": 1609459380, "open": 101.5, "high": 102.5, "low": 101.0, "close": 102.0, "volume": 180.0},
            {"SK": "TF#1m#TS#1609459440", "timestamp": 1609459440, "open": 102.0, "high": 103.0, "low": 101.5, "close": 102.5, "volume": 200.0},
        ]
        
        mock_fetch.return_value = mock_candles
        
        current_time = 1609459500  # After all candles
        processed = process_pair_timeframe("BTCUSD", "5m", current_time)
        
        assert processed > 0
        mock_write.assert_called()

    @patch("lambda_function.write_aggregated_candle")
    @patch("lambda_function.fetch_1m_candles")
    def test_process_pair_timeframe_no_data(self, mock_fetch, mock_write):
        """Test processing with no 1-minute data."""
        mock_fetch.return_value = []
        
        current_time = 1609459500
        processed = process_pair_timeframe("BTCUSD", "5m", current_time)
        
        assert processed == 0
        mock_write.assert_not_called()

    @patch("lambda_function.write_aggregated_candle")
    @patch("lambda_function.fetch_1m_candles")
    def test_process_pair_timeframe_1h(self, mock_fetch, mock_write):
        """Test processing a 1-hour timeframe."""
        # Create mock 1-minute candles for 1 hour (60 candles)
        mock_candles = [
            {
                "SK": f"TF#1m#TS#{1609459200 + i*60}",
                "timestamp": 1609459200 + i*60,
                "open": 100.0 + i*0.1,
                "high": 100.5 + i*0.1,
                "low": 99.5 + i*0.1,
                "close": 100.2 + i*0.1,
                "volume": 100.0 + i*10,
            }
            for i in range(60)
        ]
        
        mock_fetch.return_value = mock_candles
        
        current_time = 1609459200 + 3600  # 1 hour after start
        processed = process_pair_timeframe("BTCUSD", "1h", current_time)
        
        assert processed > 0
        mock_write.assert_called()


class TestAggregationIntegration:
    """Integration tests for the full aggregation pipeline."""

    @patch("lambda_function.write_aggregated_candle")
    @patch("lambda_function.fetch_1m_candles")
    def test_full_aggregation_pipeline(self, mock_fetch, mock_write):
        """Test full aggregation from fetch to write."""
        # Create realistic 1-minute candle data
        base_time = 1609459200
        mock_candles = []
        
        for i in range(10):
            ts = base_time + (i * 60)
            mock_candles.append({
                "SK": f"TF#1m#TS#{ts}",
                "timestamp": ts,
                "open": 100.0 + (i * 0.2),
                "high": 100.5 + (i * 0.2),
                "low": 99.5 + (i * 0.2),
                "close": 100.3 + (i * 0.2),
                "volume": 1000.0 + (i * 100),
            })
        
        mock_fetch.return_value = mock_candles
        
        # Process 5-minute timeframe
        current_time = base_time + 600
        processed = process_pair_timeframe("BTCUSD", "5m", current_time)
        
        # Should have written at least 1 aggregated candle
        assert processed > 0
        assert mock_write.call_count == processed

    def test_aggregate_realistic_data(self):
        """Test aggregation with realistic market data."""
        candles = [
            {
                "timestamp": 1609459200 + (i * 60),
                "open": 100.0 + (i * 0.1),
                "high": 100.8 + (i * 0.1),
                "low": 99.2 + (i * 0.1),
                "close": 100.3 + (i * 0.1),
                "volume": 5000.0 + (i * 500),
            }
            for i in range(5)  # 5 1-minute candles
        ]
        
        result = aggregate_candles(candles)
        
        assert result is not None
        assert result["open"] == 100.0
        assert result["close"] > 100.0  # Should be higher than first open
        assert result["high"] > result["low"]
        assert result["volume"] > 0
        assert "vwap" in result
        assert "typical_price" in result
        assert "ha_close" in result


class TestLambdaHandler:
    """Test the main lambda_handler function."""

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_with_eventbridge_format(self, mock_process):
        """Test lambda_handler with EventBridge detail wrapper."""
        mock_process.return_value = 2  # Simulate 2 candles processed per timeframe
        
        event = {
            "detail": {
                "symbols": ["BTCUSD", "ETHUSD"]
            }
        }
        
        result = lambda_handler(event, None)
        
        assert result["status"] == "success"
        assert result["symbols_processed"] == 2
        assert "BTCUSD" in result["results"]
        assert "ETHUSD" in result["results"]
        mock_process.assert_called()

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_with_direct_event_format(self, mock_process):
        """Test lambda_handler with direct event (no detail wrapper)."""
        mock_process.return_value = 1
        
        event = {
            "symbols": ["BTCUSD"]
        }
        
        result = lambda_handler(event, None)
        
        assert result["status"] == "success"
        assert result["symbols_processed"] == 1
        assert "BTCUSD" in result["results"]

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_single_pair_multiple_timeframes(self, mock_process):
        """Test lambda_handler processes single symbol across all timeframes."""
        mock_process.return_value = 1
        
        event = {
            "detail": {
                "symbols": ["BTCUSD"]
            }
        }
        
        result = lambda_handler(event, None)
        
        # Should be called for each timeframe (except 1m which is skipped)
        expected_calls = len([tf for tf in TIMEFRAMES.keys() if tf != "1m"])
        assert mock_process.call_count == expected_calls
        assert result["results"]["BTCUSD"]["5m"] == 1

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_multiple_pairs_multiple_timeframes(self, mock_process):
        """Test lambda_handler processes multiple symbols across all timeframes."""
        mock_process.return_value = 2
        
        event = {
            "detail": {
                "symbols": ["BTCUSD", "ETHUSD", "XRPUSD"]
            }
        }
        
        result = lambda_handler(event, None)
        
        assert result["status"] == "success"
        assert result["symbols_processed"] == 3
        assert len(result["results"]) == 3
        
        # Verify all symbols are in results
        for symbol in ["BTCUSD", "ETHUSD", "XRPUSD"]:
            assert symbol in result["results"]
            # Each symbol should have results for non-1m timeframes
            assert "5m" in result["results"][symbol]
            assert "1h" in result["results"][symbol]

    def test_lambda_handler_no_pairs_specified(self):
        """Test lambda_handler error when no symbols specified."""
        event = {
            "detail": {}
        }
        
        result = lambda_handler(event, None)
        
        assert result["status"] == "error"
        assert "No symbols specified" in result["message"]

    def test_lambda_handler_empty_pairs_list(self):
        """Test lambda_handler error when symbols list is empty."""
        event = {
            "detail": {
                "symbols": []
            }
        }
        
        result = lambda_handler(event, None)
        
        assert result["status"] == "error"

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_per_pair_error_handling(self, mock_process):
        """Test lambda_handler handles errors per symbol gracefully."""
        # First symbol succeeds, second symbol fails
        side_effects = [1, Exception("DynamoDB error"), 0]
        mock_process.side_effect = side_effects
        
        event = {
            "detail": {
                "symbols": ["BTCUSD", "ETHUSD"]
            }
        }
        
        result = lambda_handler(event, None)
        
        # Handler should return success even if some symbols fail
        assert result["status"] == "success"
        assert result["symbols_processed"] == 2
        # Both symbols should be in results
        assert "BTCUSD" in result["results"]
        assert "ETHUSD" in result["results"]

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_returns_aggregation_counts(self, mock_process):
        """Test lambda_handler returns aggregation counts per timeframe."""
        mock_process.return_value = 5  # 5 candles aggregated per timeframe
        
        event = {
            "detail": {
                "symbols": ["BTCUSD"]
            }
        }
        
        result = lambda_handler(event, None)
        
        # Verify structure
        assert "results" in result
        assert "BTCUSD" in result["results"]
        assert "5m" in result["results"]["BTCUSD"]
        assert result["results"]["BTCUSD"]["5m"] == 5

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_timestamp_in_response(self, mock_process):
        """Test lambda_handler includes current timestamp in response."""
        mock_process.return_value = 1
        
        event = {
            "detail": {
                "symbols": ["BTCUSD"]
            }
        }
        
        before_call = int(datetime.now(timezone.utc).timestamp())
        result = lambda_handler(event, None)
        after_call = int(datetime.now(timezone.utc).timestamp())
        
        assert "current_time" in result
        assert before_call <= result["current_time"] <= after_call + 1

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_all_timeframes_processed(self, mock_process):
        """Test that all timeframes are processed for each symbol."""
        mock_process.return_value = 1
        
        event = {
            "detail": {
                "symbols": ["BTCUSD"]
            }
        }
        
        result = lambda_handler(event, None)
        
        # Get all timeframes except 1m
        expected_timeframes = {tf for tf in TIMEFRAMES.keys() if tf != "1m"}
        actual_timeframes = set(result["results"]["BTCUSD"].keys())
        
        assert expected_timeframes == actual_timeframes

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_processes_correct_timeframes(self, mock_process):
        """Test that handler calls process_pair_timeframe with correct timeframes."""
        mock_process.return_value = 1
        
        event = {
            "detail": {
                "symbols": ["BTCUSD"]
            }
        }
        
        lambda_handler(event, None)
        
        # Extract all timeframe arguments from mock calls
        called_timeframes = {call[0][1] for call in mock_process.call_args_list}
        
        # Should include 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M (not 1m)
        expected = {"5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"}
        assert called_timeframes == expected

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_with_zero_processed_candles(self, mock_process):
        """Test lambda_handler when no candles are processed (no data available)."""
        mock_process.return_value = 0  # No candles processed
        
        event = {
            "detail": {
                "symbols": ["BTCUSD"]
            }
        }
        
        result = lambda_handler(event, None)
        
        assert result["status"] == "success"
        assert result["results"]["BTCUSD"]["5m"] == 0
        assert result["results"]["BTCUSD"]["1h"] == 0

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_large_number_of_pairs(self, mock_process):
        """Test lambda_handler with many symbols."""
        mock_process.return_value = 3
        
        symbols = [f"PAIR{i}" for i in range(10)]
        event = {
            "detail": {
                "symbols": symbols
            }
        }
        
        result = lambda_handler(event, None)
        
        assert result["status"] == "success"
        assert result["symbols_processed"] == 10
        assert len(result["results"]) == 10
        
        # Verify all symbols processed
        for symbol in symbols:
            assert symbol in result["results"]

    def test_lambda_handler_exception_handling(self):
        """Test lambda_handler handles exceptions from process_pair_timeframe gracefully."""
        event = {
            "detail": {
                "symbols": ["BTCUSD"]
            }
        }
        
        with patch("lambda_function.process_pair_timeframe", side_effect=Exception("Unexpected error")):
            result = lambda_handler(event, None)
        
        # Handler should catch exceptions per symbol and return success with 0 processed
        assert result["status"] == "success"
        assert result["results"]["BTCUSD"]["5m"] == 0

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_respects_event_data_structure(self, mock_process):
        """Test lambda_handler correctly extracts symbols from nested event structure."""
        mock_process.return_value = 1
        
        # EventBridge wraps the actual event in "detail"
        event = {
            "version": "0",
            "id": "12345",
            "detail-type": "EventBridge Event",
            "source": "aws.events",
            "account": "123456789012",
            "time": "2026-05-23T12:00:00Z",
            "region": "us-east-2",
            "resources": [],
            "detail": {
                "symbols": ["BTCUSD", "ETHUSD"]
            }
        }
        
        result = lambda_handler(event, None)
        
        # Should extract symbols from detail correctly
        assert result["status"] == "success"
        assert result["symbols_processed"] == 2

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_aggregation_count_accumulation(self, mock_process):
        """Test that aggregation counts are properly tracked."""
        # Different counts for different timeframes
        mock_process.side_effect = [1, 2, 3, 4, 5, 6, 7, 8]  # 8 timeframes (not 1m)
        
        event = {
            "detail": {
                "symbols": ["BTCUSD"]
            }
        }
        
        result = lambda_handler(event, None)
        
        # Verify counts match mock side effects
        assert result["results"]["BTCUSD"]["5m"] == 1
        assert result["results"]["BTCUSD"]["15m"] == 2
        assert result["results"]["BTCUSD"]["30m"] == 3
        assert result["results"]["BTCUSD"]["1h"] == 4

    @patch("lambda_function.process_pair_timeframe")
    def test_lambda_handler_default_pairs(self, mock_process):
        """Test lambda_handler uses default pairs when none specified."""
        from lambda_function import DEFAULT_SYMBOLS
        
        mock_process.return_value = 1
        
        # Empty event should use DEFAULT_SYMBOLS
        event = {}
        
        result = lambda_handler(event, None)
        
        assert result["status"] == "success"
        assert result["symbols_processed"] == len(DEFAULT_SYMBOLS)

