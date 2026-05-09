import json
import pytest
from unittest.mock import patch, MagicMock
from lambda_function import lambda_handler


class TestLambdaHandler:
    """Test suite for lambda_handler function"""

    @patch("lambda_function.timestream_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_success(self, mock_get, mock_timestream):
        """Test lambda handler with successful Kraken API response and Timestream write"""
        mock_timestream.write_records.return_value = {"RecordsIngested": {"Total": 12}}

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
        assert body["records_written_to_timestream"] == 12

        # Verify Kraken API was called with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://api.kraken.com/0/public/OHLC"
        assert call_args[1]["params"]["pair"] == "XBTUSD"
        assert call_args[1]["params"]["interval"] == 60

        # Verify Timestream write_records was called
        mock_timestream.write_records.assert_called()

    @patch("lambda_function.timestream_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_timestream_write_records_called(self, mock_get, mock_timestream):
        """Test that write_records is called with correct database and table names"""
        mock_timestream.write_records.return_value = {"RecordsIngested": {"Total": 6}}

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

        lambda_handler({}, {})

        # Verify write_records was called with correct database and table
        mock_timestream.write_records.assert_called_once()
        call_kwargs = mock_timestream.write_records.call_args[1]
        assert call_kwargs["DatabaseName"] == "crypto-price-database"
        assert call_kwargs["TableName"] == "price-data"
        assert "Records" in call_kwargs
        assert len(call_kwargs["Records"]) == 6

    @patch("lambda_function.timestream_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_timestream_record_structure(self, mock_get, mock_timestream):
        """Test that Timestream records have correct structure"""
        mock_timestream.write_records.return_value = {"RecordsIngested": {"Total": 6}}

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

        lambda_handler({}, {})

        # Get the records passed to write_records
        call_kwargs = mock_timestream.write_records.call_args[1]
        records = call_kwargs["Records"]

        # Verify first record (open metric)
        first_record = records[0]
        assert first_record["MeasureName"] == "price"
        assert first_record["MeasureValueType"] == "DOUBLE"
        assert first_record["Time"] == "1704067200"
        assert first_record["TimeUnit"] == "SECONDS"
        
        # Verify dimensions
        dimensions = {d["Name"]: d["Value"] for d in first_record["Dimensions"]}
        assert dimensions["pair"] == "XBTUSD"
        assert dimensions["interval"] == "60"
        assert dimensions["metric"] == "open"
        assert first_record["MeasureValue"] == "42000"

    @patch("lambda_function.timestream_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_kraken_error(self, mock_get, mock_timestream):
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
        # Verify Timestream was NOT called on Kraken error
        mock_timestream.write_records.assert_not_called()

    @patch("lambda_function.timestream_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_request_timeout(self, mock_get, mock_timestream):
        """Test lambda handler when request times out"""
        mock_get.side_effect = Exception("Request timeout")

        response = lambda_handler({}, {})

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
        assert "timeout" in body["error"].lower()
        # Verify Timestream was NOT called on request error
        mock_timestream.write_records.assert_not_called()

    @patch("lambda_function.timestream_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_timestream_write_failure(self, mock_get, mock_timestream):
        """Test lambda handler when Timestream write fails"""
        mock_timestream.write_records.side_effect = Exception("Timestream connection error")

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

        response = lambda_handler({}, {})

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body

    @patch("lambda_function.timestream_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_multiple_ohlc_records(self, mock_get, mock_timestream):
        """Test lambda handler writes multiple OHLC candles to Timestream"""
        mock_timestream.write_records.return_value = {"RecordsIngested": {"Total": 18}}

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "ETHUSD": [
                    [1704067200, 2500, 2600, 2400, 2550, 2520, 500.1],
                    [1704070800, 2520, 2630, 2500, 2600, 2560, 520.3],
                    [1704074400, 2600, 2700, 2580, 2650, 2620, 540.5],
                ]
            },
            "error": [],
        }
        mock_get.return_value = mock_response

        response = lambda_handler({}, {})

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["pair"] == "ETHUSD"
        assert body["count"] == 3
        assert body["records_written_to_timestream"] == 18

        # Verify write_records was called with 18 records (6 metrics x 3 candles)
        call_kwargs = mock_timestream.write_records.call_args[1]
        records = call_kwargs["Records"]
        assert len(records) == 18

    @patch("lambda_function.timestream_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_response_includes_ohlc_data(self, mock_get, mock_timestream):
        """Test that lambda handler response includes original OHLC data"""
        mock_timestream.write_records.return_value = {"RecordsIngested": {"Total": 6}}

        ohlc_data = [
            [1704067200, 42000, 42500, 41500, 42200, 42100, 1000.5],
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "XBTUSD": ohlc_data
            },
            "error": [],
        }
        mock_get.return_value = mock_response

        response = lambda_handler({}, {})

        body = json.loads(response["body"])
        assert body["ohlc"] == ohlc_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
