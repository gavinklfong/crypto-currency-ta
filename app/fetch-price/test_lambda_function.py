import json
import pytest
from unittest.mock import patch, MagicMock, call
from lambda_function import lambda_handler, write_ohlc_to_timestream


class TestWriteOhlcToTimestream:
    """Test suite for write_ohlc_to_timestream function"""

    @patch("lambda_function.timestream_client")
    def test_write_ohlc_to_timestream_single_candle(self, mock_client):
        """Test writing a single OHLC candle to Timestream"""
        mock_client.write_records.return_value = {"RecordsIngested": {"Total": 6}}

        # Sample OHLC data: [timestamp, open, high, low, close, vwap, volume]
        ohlc_data = [
            [1704067200, 42000, 42500, 41500, 42200, 42100, 1000.5]
        ]

        records_written = write_ohlc_to_timestream("XBTUSD", 60, ohlc_data)

        # Should create 6 records (open, high, low, close, vwap, volume)
        assert records_written == 6
        mock_client.write_records.assert_called_once()

        # Verify the records structure
        call_args = mock_client.write_records.call_args
        assert call_args.kwargs["DatabaseName"] == "crypto-price-database"
        assert call_args.kwargs["TableName"] == "price-data"
        records = call_args.kwargs["Records"]
        assert len(records) == 6

        # Verify first record structure
        first_record = records[0]
        assert first_record["Dimensions"][0]["Value"] == "XBTUSD"
        assert first_record["Dimensions"][2]["Value"] == "open"
        assert first_record["MeasureValue"] == "42000"
        assert first_record["MeasureValueType"] == "DOUBLE"

    @patch("lambda_function.timestream_client")
    def test_write_ohlc_to_timestream_multiple_candles(self, mock_client):
        """Test writing multiple OHLC candles to Timestream"""
        mock_client.write_records.return_value = {"RecordsIngested": {"Total": 12}}

        ohlc_data = [
            [1704067200, 42000, 42500, 41500, 42200, 42100, 1000.5],
            [1704070800, 42300, 42800, 42000, 42500, 42400, 1100.2],
        ]

        records_written = write_ohlc_to_timestream("XBTUSD", 60, ohlc_data)

        # Should create 12 records (6 per candle)
        assert records_written == 12
        assert mock_client.write_records.call_count == 1

    @patch("lambda_function.timestream_client")
    def test_write_ohlc_to_timestream_batch_writing(self, mock_client):
        """Test batch writing of records when exceeding batch size"""
        mock_client.write_records.return_value = {"RecordsIngested": {"Total": 100}}

        # Create 20 candles (120 records total, will need 2 batches)
        ohlc_data = [
            [1704067200 + i * 3600, 42000 + i, 42500 + i, 41500 + i, 42200 + i, 42100 + i, 1000 + i]
            for i in range(20)
        ]

        records_written = write_ohlc_to_timestream("XBTUSD", 60, ohlc_data)

        # Should create 120 records (6 per candle x 20)
        assert records_written == 120
        # Should call write_records twice (batch size is 100)
        assert mock_client.write_records.call_count == 2

    @patch("lambda_function.timestream_client")
    def test_write_ohlc_to_timestream_dimensions(self, mock_client):
        """Test that dimensions are correctly set"""
        mock_client.write_records.return_value = {"RecordsIngested": {"Total": 6}}

        ohlc_data = [[1704067200, 42000, 42500, 41500, 42200, 42100, 1000.5]]

        write_ohlc_to_timestream("ETHUSD", 300, ohlc_data)

        call_args = mock_client.write_records.call_args
        records = call_args.kwargs["Records"]

        # Check dimensions
        assert records[0]["Dimensions"][0]["Name"] == "pair"
        assert records[0]["Dimensions"][0]["Value"] == "ETHUSD"
        assert records[0]["Dimensions"][1]["Name"] == "interval"
        assert records[0]["Dimensions"][1]["Value"] == "300"
        assert records[0]["Dimensions"][2]["Name"] == "metric"

    @patch("lambda_function.timestream_client")
    def test_write_ohlc_to_timestream_error_handling(self, mock_client):
        """Test error handling when write fails"""
        mock_client.write_records.side_effect = Exception("Timestream write failed")

        ohlc_data = [[1704067200, 42000, 42500, 41500, 42200, 42100, 1000.5]]

        with pytest.raises(Exception):
            write_ohlc_to_timestream("XBTUSD", 60, ohlc_data)


class TestLambdaHandler:
    """Test suite for lambda_handler function"""

    @patch("lambda_function.write_ohlc_to_timestream")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_success(self, mock_get, mock_write):
        """Test lambda handler with successful Kraken API response"""
        mock_write.return_value = 6

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "XBTUSD": [
                    [1704067200, 42000, 42500, 41500, 42200, 42100, 1000.5],
                    [1704070800, 42300, 42800, 42000, 42500, 42400, 1100.2],
                ]
            },
            "error": [],
        }
        mock_get.return_value = mock_response

        response = lambda_handler({}, {})

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["pair"] == "XBTUSD"
        assert body["count"] == 2
        assert body["records_written_to_timestream"] == 6

    @patch("lambda_function.write_ohlc_to_timestream")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_kraken_error(self, mock_get, mock_write):
        """Test lambda handler when Kraken API returns an error"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": ["EAPI:Invalid key"],
        }
        mock_get.return_value = mock_response

        response = lambda_handler({}, {})

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body

    @patch("lambda_function.write_ohlc_to_timestream")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_request_timeout(self, mock_get, mock_write):
        """Test lambda handler when request times out"""
        mock_get.side_effect = Exception("Request timeout")

        response = lambda_handler({}, {})

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body

    @patch("lambda_function.write_ohlc_to_timestream")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_timestream_write_failure(self, mock_get, mock_write):
        """Test lambda handler when Timestream write fails"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "XBTUSD": [
                    [1704067200, 42000, 42500, 41500, 42200, 42100, 1000.5],
                ]
            },
            "error": [],
        }
        mock_get.return_value = mock_response
        mock_write.side_effect = Exception("Timestream error")

        response = lambda_handler({}, {})

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body

    @patch("lambda_function.write_ohlc_to_timestream")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_calls_write_with_correct_params(self, mock_get, mock_write):
        """Test that lambda handler calls write_ohlc_to_timestream with correct parameters"""
        mock_write.return_value = 6

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "ETHUSD": [
                    [1704067200, 2500, 2600, 2400, 2550, 2520, 500.1],
                ]
            },
            "error": [],
        }
        mock_get.return_value = mock_response

        lambda_handler({}, {})

        # Verify write_ohlc_to_timestream was called with correct params
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        assert call_args[0][0] == "ETHUSD"  # pair
        assert call_args[0][1] == 60  # interval
        assert len(call_args[0][2]) == 1  # ohlc_data

    @patch("lambda_function.write_ohlc_to_timestream")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_response_format(self, mock_get, mock_write):
        """Test that lambda handler returns correctly formatted response"""
        mock_write.return_value = 12

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "XBTUSD": [
                    [1704067200, 42000, 42500, 41500, 42200, 42100, 1000.5],
                    [1704070800, 42300, 42800, 42000, 42500, 42400, 1100.2],
                ]
            },
            "error": [],
        }
        mock_get.return_value = mock_response

        response = lambda_handler({}, {})

        assert "statusCode" in response
        assert "body" in response
        body = json.loads(response["body"])
        assert "pair" in body
        assert "count" in body
        assert "records_written_to_timestream" in body
        assert "ohlc" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
