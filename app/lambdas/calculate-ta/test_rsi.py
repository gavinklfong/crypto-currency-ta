"""Unit tests for RSI (Relative Strength Index) calculation."""

import unittest
from lambda_function import compute_rsi
from test_data_utils import load_sample_market_data


class TestComputeRSI(unittest.TestCase):
    """Test cases for RSI calculation."""
    
    @classmethod
    def setUpClass(cls):
        """Load sample market data once for all tests."""
        cls.market_data = load_sample_market_data()
        cls.closes = cls.market_data["closes"]
    
    def test_rsi_basic_range(self):
        """Test that RSI returns value between 0 and 100."""
        rsi = compute_rsi(self.closes, period=14)
        
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
    
    def test_rsi_requires_minimum_values(self):
        """Test that RSI returns None with insufficient data."""
        too_few = [100, 101, 102]
        rsi = compute_rsi(too_few, period=14)
        
        # Should return None with less than period + 1 values
        self.assertIsNone(rsi)
    
    def test_rsi_with_exact_minimum_values(self):
        """Test RSI with exactly period + 1 values."""
        exact_min = list(range(1, 16))  # 15 values for period 14
        rsi = compute_rsi(exact_min, period=14)
        
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
    
    def test_rsi_period_14(self):
        """Test RSI(14) on full sample data."""
        rsi = compute_rsi(self.closes, period=14)
        
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
    
    def test_rsi_period_7(self):
        """Test RSI(7) on full sample data."""
        rsi = compute_rsi(self.closes, period=7)
        
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
    
    def test_rsi_constant_values(self):
        """Test RSI with constant prices (no change)."""
        constant = [100.0] * 20
        rsi = compute_rsi(constant, period=14)
        
        # When prices don't change, avg_loss should be 0
        # This should return 100 (no losses, only neutral)
        self.assertIsNotNone(rsi)
        # With no price movement, RSI should be neutral (around 50) or 100
        self.assertIn(rsi, [100.0])  # No losses = RSI 100
    
    def test_rsi_uptrend(self):
        """Test RSI with consistent uptrend."""
        uptrend = [float(i) for i in range(1, 51)]
        rsi = compute_rsi(uptrend, period=14)
        
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50)  # Uptrend should have RSI > 50
        self.assertLessEqual(rsi, 100)
    
    def test_rsi_downtrend(self):
        """Test RSI with consistent downtrend."""
        downtrend = [float(50 - i) for i in range(50)]
        rsi = compute_rsi(downtrend, period=14)
        
        self.assertIsNotNone(rsi)
        self.assertLess(rsi, 50)  # Downtrend should have RSI < 50
        self.assertGreaterEqual(rsi, 0)
    
    def test_rsi_oversold_condition(self):
        """Test RSI approaching oversold (<30) condition."""
        # Simulate sharp downtrend
        values = [100.0] * 10 + [99, 98, 97, 96, 95, 94, 93, 92, 91, 90]
        rsi = compute_rsi(values, period=9)
        
        self.assertIsNotNone(rsi)
        self.assertLess(rsi, 50)
    
    def test_rsi_overbought_condition(self):
        """Test RSI approaching overbought (>70) condition."""
        # Simulate sharp uptrend
        values = [90.0] * 10 + [91, 92, 93, 94, 95, 96, 97, 98, 99, 100]
        rsi = compute_rsi(values, period=9)
        
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50)
    
    def test_rsi_recent_candles(self):
        """Test RSI calculation on recent candles from sample data."""
        recent_30 = self.closes[-30:]
        rsi = compute_rsi(recent_30, period=14)
        
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
    
    def test_rsi_different_periods(self):
        """Test RSI with different periods."""
        rsi_5 = compute_rsi(self.closes, period=5)
        rsi_14 = compute_rsi(self.closes, period=14)
        rsi_21 = compute_rsi(self.closes, period=21)
        
        # All should be valid values
        for rsi in [rsi_5, rsi_14, rsi_21]:
            self.assertIsNotNone(rsi)
            self.assertGreaterEqual(rsi, 0)
            self.assertLessEqual(rsi, 100)
    
    def test_rsi_extreme_prices(self):
        """Test RSI with extreme price movements."""
        # Big spike up
        prices = [100.0] * 10 + [100, 105, 110, 115, 120]
        rsi = compute_rsi(prices, period=5)
        
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 70)  # Should be overbought
    
    def test_rsi_14_exact_value_on_full_data(self):
        """Test RSI(14) exact value on full sample data."""
        rsi_14 = compute_rsi(self.closes, period=14)
        
        # Verify exact value from sample CSV data
        expected = 72.79358132749721
        self.assertIsNotNone(rsi_14)
        self.assertAlmostEqual(rsi_14, expected, places=5,
                             msg=f"Expected RSI(14)={expected}, got {rsi_14}")
    
    def test_rsi_7_exact_value_on_full_data(self):
        """Test RSI(7) exact value on full sample data."""
        rsi_7 = compute_rsi(self.closes, period=7)
        
        # Verify exact value from sample CSV data
        expected = 75.09578544061858
        self.assertIsNotNone(rsi_7)
        self.assertAlmostEqual(rsi_7, expected, places=5,
                             msg=f"Expected RSI(7)={expected}, got {rsi_7}")
    
    def test_rsi_consistency_multiple_runs(self):
        """Test that RSI calculation is deterministic and consistent."""
        # Run calculation multiple times
        rsi1 = compute_rsi(self.closes, period=14)
        rsi2 = compute_rsi(self.closes, period=14)
        rsi3 = compute_rsi(self.closes, period=14)
        
        # All should be identical
        self.assertEqual(rsi1, rsi2)
        self.assertEqual(rsi2, rsi3)
    
    def test_rsi_recent_30_candles_value(self):
        """Test RSI(14) on recent 30 candles has reasonable value."""
        recent_30 = self.closes[-30:]
        rsi = compute_rsi(recent_30, period=14)
        
        self.assertIsNotNone(rsi)
        # From the full data RSI(14) is ~72.79, recent should be in similar range
        self.assertGreater(rsi, 50)
        self.assertLessEqual(rsi, 100)


if __name__ == "__main__":
    unittest.main()
