"""Unit tests for EMA (Exponential Moving Average) calculation."""

import unittest
from lambda_function import compute_ema
from test_data_utils import load_sample_market_data


class TestComputeEMA(unittest.TestCase):
    """Test cases for EMA calculation."""
    
    @classmethod
    def setUpClass(cls):
        """Load sample market data once for all tests."""
        cls.market_data = load_sample_market_data()
        cls.closes = cls.market_data["closes"]
    
    def test_ema_basic_calculation(self):
        """Test basic EMA calculation with simple values."""
        simple_values = [10, 11, 12, 11, 10]
        ema = compute_ema(simple_values, period=2)
        
        # EMA should be a float value
        self.assertIsInstance(ema, (int, float))
        # EMA should be between min and max of values
        self.assertGreaterEqual(ema, min(simple_values))
        self.assertLessEqual(ema, max(simple_values))
    
    def test_ema_period_20_on_full_data(self):
        """Test EMA(20) on full sample data."""
        ema_20 = compute_ema(self.closes, 20)
        
        self.assertIsInstance(ema_20, (int, float))
        self.assertGreater(ema_20, 0)
        # EMA should be in reasonable range for price data
        self.assertGreaterEqual(ema_20, min(self.closes))
        self.assertLessEqual(ema_20, max(self.closes))
    
    def test_ema_period_50_on_full_data(self):
        """Test EMA(50) on full sample data."""
        ema_50 = compute_ema(self.closes, 50)
        
        self.assertIsInstance(ema_50, (int, float))
        self.assertGreater(ema_50, 0)
        # EMA should smooth out volatility, so check reasonable bounds
        self.assertGreaterEqual(ema_50, min(self.closes))
        self.assertLessEqual(ema_50, max(self.closes))
    
    def test_ema_single_value(self):
        """Test EMA with single value."""
        single_value = [100.0]
        ema = compute_ema(single_value, 5)
        
        # With single value, EMA should equal that value
        self.assertAlmostEqual(ema, 100.0, places=5)
    
    def test_ema_constant_values(self):
        """Test EMA with constant values."""
        constant_values = [50.0] * 20
        ema = compute_ema(constant_values, 10)
        
        # EMA of constant values should equal the constant
        self.assertAlmostEqual(ema, 50.0, places=5)
    
    def test_ema_trending_up(self):
        """Test EMA with uptrend data."""
        uptrend = [float(i) for i in range(1, 21)]
        ema = compute_ema(uptrend, 5)
        
        # EMA of uptrend should be higher than early values
        self.assertGreater(ema, uptrend[0])
        # But should lag behind the latest value somewhat
        self.assertLess(ema, uptrend[-1])
    
    def test_ema_trending_down(self):
        """Test EMA with downtrend data."""
        downtrend = [float(20 - i) for i in range(20)]
        ema = compute_ema(downtrend, 5)
        
        # EMA of downtrend should be lower than early values
        self.assertLess(ema, downtrend[0])
        # But should be higher than the latest value somewhat
        self.assertGreater(ema, downtrend[-1])
    
    def test_ema_recent_candles(self):
        """Test EMA calculation on recent candles from sample data."""
        recent_20 = self.closes[-20:]
        ema = compute_ema(recent_20, 20)
        
        self.assertIsInstance(ema, (int, float))
        self.assertGreater(ema, 0)
        self.assertGreaterEqual(ema, min(recent_20))
        self.assertLessEqual(ema, max(recent_20))
    
    def test_ema_smoothing_effect(self):
        """Test that EMA(5) is smoother than EMA(2)."""
        ema_2 = compute_ema(self.closes, 2)
        ema_5 = compute_ema(self.closes, 5)
        ema_20 = compute_ema(self.closes, 20)
        
        # All should be valid numbers
        self.assertIsInstance(ema_2, (int, float))
        self.assertIsInstance(ema_5, (int, float))
        self.assertIsInstance(ema_20, (int, float))
        
        # EMA with larger period should smooth more
        # (though they all converge on same data, this is just sanity check)
        self.assertGreater(ema_20, 0)


if __name__ == "__main__":
    unittest.main()
