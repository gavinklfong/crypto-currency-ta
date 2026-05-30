import json
import pytest
from unittest.mock import patch, MagicMock
from lambda_function import lambda_handler


class TestLambdaHandler:
    """Test suite for lambda_handler function"""

    @patch("lambda_function.dynamodb_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_success(self, mock_get, mock_dynamodb):
        """Test lambda handler with successful Kraken API response and DynamoDB write"""
        mock_dynamodb.put_item.return_value = {}

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
        assert body["records_written_to_dynamodb"] == 2
        assert "ohlc" in body

        # Verify Kraken API was called with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://api.kraken.com/0/public/OHLC"
        assert call_args[1]["params"]["pair"] == "XBTUSD"
        assert call_args[1]["params"]["interval"] == 1

        # Verify DynamoDB put_item was called twice (for each of the last 10 or fewer candles)
        # Since we have 2 candles, put_item should be called 2 times
        assert mock_dynamodb.put_item.call_count == 2


    @patch("lambda_function.dynamodb_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_dynamodb_put_item_called(self, mock_get, mock_dynamodb):
        """Test that put_item is called with correct table name"""
        mock_dynamodb.put_item.return_value = {}        

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

        # Verify put_item was called with correct table
        mock_dynamodb.put_item.assert_called_once()
        call_kwargs = mock_dynamodb.put_item.call_args[1]
        assert call_kwargs["TableName"] == "crypto-currency-ta-market-data"

    @patch("lambda_function.dynamodb_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_dynamodb_item_structure(self, mock_get, mock_dynamodb):
        """Test that DynamoDB items have correct structure with correct keys"""
        mock_dynamodb.put_item.return_value = {}

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

        # Get the item passed to put_item
        call_kwargs = mock_dynamodb.put_item.call_args[1]
        item = call_kwargs["Item"]

        # Verify key structure: PAIR#<symbol> and TF#<timeframe>#TS#<epoch>
        assert item["PK"]["S"] == "PAIR#XBTUSD"
        assert item["SK"]["S"] == "TF#1m#TS#1704067200"

        # Verify OHLC data is stored
        assert item["open"]["N"] == "42000.0"
        assert item["high"]["N"] == "42500.0"
        assert item["low"]["N"] == "41500.0"
        assert item["close"]["N"] == "42200.0"
        assert item["vwap"]["N"] == "42100.0"
        assert item["volume"]["N"] == "1000.5"

        # Verify metadata
        assert item["pair"]["S"] == "XBTUSD"
        assert item["timeframe_minutes"]["N"] == "1"
        assert "created_at" in item

    @patch("lambda_function.dynamodb_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_kraken_error(self, mock_get, mock_dynamodb):
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
        # Verify DynamoDB was NOT called on Kraken error
        mock_dynamodb.put_item.assert_not_called()

    @patch("lambda_function.dynamodb_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_request_timeout(self, mock_get, mock_dynamodb):
        """Test lambda handler when request times out"""
        mock_get.side_effect = Exception("Request timeout")

        response = lambda_handler({}, {})

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
        # Verify DynamoDB was NOT called on request error
        mock_dynamodb.put_item.assert_not_called()

    @patch("lambda_function.dynamodb_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_dynamodb_write_failure(self, mock_get, mock_dynamodb):
        """Test lambda handler when DynamoDB write fails"""
        mock_dynamodb.put_item.side_effect = Exception("DynamoDB connection error")

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

    @patch("lambda_function.dynamodb_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_multiple_ohlc_records(self, mock_get, mock_dynamodb):
        """Test lambda handler writes multiple OHLC candles to DynamoDB"""
        mock_dynamodb.put_item.return_value = {}

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
        assert body["records_written_to_dynamodb"] == 3

        # Verify put_item was called 3 times (once for each candle)
        assert mock_dynamodb.put_item.call_count == 3

    @patch("lambda_function.dynamodb_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_response_includes_ohlc_data(self, mock_get, mock_dynamodb):
        """Test that lambda handler response includes original OHLC data"""
        mock_dynamodb.put_item.return_value = {}

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


    @patch("lambda_function.dynamodb_client")
    @patch("lambda_function.requests.get")
    def test_lambda_handler_writes_in_sequence(self, mock_get, mock_dynamodb):
        """Verify that DynamoDB put_item is called for each candle"""

        # Mock put_item to succeed
        mock_dynamodb.put_item.return_value = {}

        # Mock Kraken API response with 3 candles
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "XBTUSD": [
                    [1704067200, 42000, 42500, 41500, 42200, 42100, 1000.5],
                    [1704070800, 42300, 42800, 42000, 42500, 42400, 1100.2],
                    [1704074400, 42600, 43000, 42200, 42800, 42700, 1200.3],
                ]
            },
            "error": [],
        }
        mock_get.return_value = mock_response

        response = lambda_handler({}, {})

        # Validate response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["pair"] == "XBTUSD"
        assert body["count"] == 3
        assert body["records_written_to_dynamodb"] == 3

        # Ensure put_item was called 3 times
        assert mock_dynamodb.put_item.call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])