"""Test EventBridge event handling in calculate-ta Lambda."""

import unittest
import json
from unittest.mock import patch, MagicMock
from lambda_function import lambda_handler


class TestEventBridgeHandling(unittest.TestCase):
    """Test cases for EventBridge event handling."""
    
    def setUp(self):
        """Mock DynamoDB before each test."""
        self.patcher = patch('lambda_function.table')
        self.mock_table = self.patcher.start()
    
    def tearDown(self):
        """Stop mocking after each test."""
        self.patcher.stop()
    
    def test_eventbridge_event_format(self):
        """Test that Lambda handles EventBridge wrapped events."""
        # Mock the query response
        self.mock_table.query.return_value = {
            "Items": [
                {
                    "PK": "PAIR#XXBTZUSD",
                    "SK": "TF#1m#TS#1778401080",
                    "close": "80688.1"
                }
            ]
        }
        
        # EventBridge event format
        eventbridge_event = {
            "version": "0",
            "id": "abc123",
            "detail-type": "price-updated",
            "source": "price.fetcher",
            "account": "123456789",
            "time": "2026-05-16T10:00:00Z",
            "region": "us-east-2",
            "detail": {
                "pair": "XXBTZUSD",
                "timeframe": "1m",
                "timestamp": 1778401080
            }
        }
        
        # Should not raise KeyError
        try:
            result = lambda_handler(eventbridge_event, None)
            # If we got here without KeyError, the test passes
            self.assertIn("pair", result)
        except KeyError as e:
            self.fail(f"Lambda raised KeyError with EventBridge format: {e}")
    
    def test_direct_invocation_format(self):
        """Test that Lambda still handles direct invocation format."""
        # Mock the query response
        self.mock_table.query.return_value = {
            "Items": [
                {
                    "PK": "PAIR#XXBTZUSD",
                    "SK": "TF#1m#TS#1778401080",
                    "close": "80688.1"
                }
            ]
        }
        
        # Direct invocation format
        direct_event = {
            "pair": "XXBTZUSD",
            "timeframe": "1m",
            "timestamp": 1778401080
        }
        
        # Should not raise KeyError
        try:
            result = lambda_handler(direct_event, None)
            self.assertIn("pair", result)
        except KeyError as e:
            self.fail(f"Lambda raised KeyError with direct format: {e}")
    
    def test_timestamp_string_conversion(self):
        """Test that timestamp is converted to int even if passed as string."""
        # Mock the query response
        self.mock_table.query.return_value = {
            "Items": [
                {
                    "PK": "PAIR#XXBTZUSD",
                    "SK": "TF#1m#TS#1778401080",
                    "close": "80688.1"
                }
            ]
        }
        
        # EventBridge might pass timestamp as string
        eventbridge_event = {
            "detail": {
                "pair": "XXBTZUSD",
                "timeframe": "1m",
                "timestamp": "1778401080"  # String instead of int
            }
        }
        
        # Should convert string to int without error
        try:
            result = lambda_handler(eventbridge_event, None)
            self.assertIn("pair", result)
            self.assertIn("processed", result)
            self.assertIn("details", result)
            # Verify details contains processed items with timestamps
            if result["processed"] > 0:
                self.assertIn("timestamp", result["details"][0])
                self.assertIn("ta", result["details"][0])
        except (KeyError, TypeError, ValueError) as e:
            self.fail(f"Lambda failed to handle string timestamp: {e}")
    
    def test_eventbridge_event_extraction(self):
        """Test that detail field is properly extracted from EventBridge event."""
        # Mock the query response with sufficient data
        close_prices = [float(80688.1 + i * 0.1) for i in range(200)]
        items = [
            {
                "PK": "PAIR#XXBTZUSD",
                "SK": f"TF#1m#TS#{1778401080 + i}",
                "close": str(close_prices[i])
            }
            for i in range(200)
        ]
        
        self.mock_table.query.return_value = {"Items": items}
        
        eventbridge_event = {
            "source": "price.fetcher",
            "detail-type": "price-updated",
            "detail": {
                "pair": "XXBTZUSD",
                "timeframe": "1m",
                "timestamp": 1778401080 + 199
            }
        }
        
        result = lambda_handler(eventbridge_event, None)
        
        # Verify result contains expected fields
        self.assertEqual(result["pair"], "XXBTZUSD")
        self.assertEqual(result["timeframe"], "1m")
        self.assertIn("processed", result)
        self.assertIn("details", result)
        
        # Verify details array structure
        self.assertGreater(result["processed"], 0)
        self.assertEqual(len(result["details"]), result["processed"])
        
        # Verify first detail item has TA data
        first_detail = result["details"][0]
        self.assertIn("timestamp", first_detail)
        self.assertIn("ta", first_detail)
        ta = first_detail["ta"]
        self.assertIn("rsi14", ta)
        self.assertIn("macd", ta)
        self.assertIn("ema20", ta)


if __name__ == "__main__":
    unittest.main()
