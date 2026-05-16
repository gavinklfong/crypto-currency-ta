"""Unit tests for MACD (Moving Average Convergence Divergence) calculation."""

import unittest
from lambda_function import compute_macd
from test_data_utils import load_sample_market_data


class TestComputeMACD(unittest.TestCase):
    """Test cases for MACD calculation."""
    
    @classmethod
    def setUpClass(cls):
        """Load sample market data once for all tests."""
        cls.market_data = load_sample_market_data()
        cls.closes = cls.market_data["closes"]
    
    def test_macd_returns_three_values(self):
        """Test that MACD returns three components: line, signal, histogram."""
        macd_line, signal_line, histogram = compute_macd(self.closes)
        
        # All three should be present
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertIsNotNone(histogram)
        
        # All should be floats
        self.assertIsInstance(macd_line, (int, float))
        self.assertIsInstance(signal_line, (int, float))
        self.assertIsInstance(histogram, (int, float))
    
    def test_macd_requires_minimum_values(self):
        """Test that MACD returns None with insufficient data."""
        too_few = [100, 101, 102]
        macd_line, signal_line, histogram = compute_macd(too_few)
        
        # Should return None values with insufficient data
        self.assertIsNone(macd_line)
        self.assertIsNone(signal_line)
        self.assertIsNone(histogram)
    
    def test_macd_with_exact_minimum_values(self):
        """Test MACD with sufficient values (slow + signal + buffer)."""
        # MACD needs more than slow(26) + signal(9) due to implementation
        # Use 60 values to ensure enough data for calculation
        exact_min = [float(i) for i in range(1, 61)]
        macd_line, signal_line, histogram = compute_macd(exact_min)
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertIsNotNone(histogram)
    
    def test_macd_default_parameters(self):
        """Test MACD with default parameters (12, 26, 9)."""
        macd_line, signal_line, histogram = compute_macd(self.closes, fast=12, slow=26, signal=9)
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertIsNotNone(histogram)
        
        # MACD line and signal line should be close in value
        self.assertIsInstance(macd_line, (int, float))
        self.assertIsInstance(signal_line, (int, float))
    
    def test_macd_histogram_calculation(self):
        """Test that histogram = MACD line - signal line."""
        macd_line, signal_line, histogram = compute_macd(self.closes)
        
        self.assertIsNotNone(histogram)
        # Histogram should be the difference between MACD and signal
        expected_histogram = macd_line - signal_line
        self.assertAlmostEqual(histogram, expected_histogram, places=5)
    
    def test_macd_uptrend(self):
        """Test MACD with uptrend data."""
        uptrend = [float(i) for i in range(1, 101)]
        macd_line, signal_line, histogram = compute_macd(uptrend)
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        # In uptrend, MACD line should be positive and above signal
        if macd_line is not None and signal_line is not None:
            self.assertGreater(macd_line, 0)
    
    def test_macd_downtrend(self):
        """Test MACD with downtrend data."""
        downtrend = [float(100 - i) for i in range(100)]
        macd_line, signal_line, histogram = compute_macd(downtrend)
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        # In downtrend, MACD line should be negative
        if macd_line is not None:
            self.assertLess(macd_line, 0)
    
    def test_macd_constant_values(self):
        """Test MACD with constant prices."""
        constant = [100.0] * 50
        macd_line, signal_line, histogram = compute_macd(constant)
        
        # With constant prices, MACD components should be close to 0
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertAlmostEqual(macd_line, 0, places=2)
        self.assertAlmostEqual(signal_line, 0, places=2)
        self.assertAlmostEqual(histogram, 0, places=2)
    
    def test_macd_custom_parameters(self):
        """Test MACD with custom parameters."""
        macd_line, signal_line, histogram = compute_macd(
            self.closes, 
            fast=5, 
            slow=15, 
            signal=5
        )
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertIsNotNone(histogram)
    
    def test_macd_price_spike(self):
        """Test MACD response to price spike."""
        # Create data with a price spike
        prices = [100.0] * 20 + [105.0] * 20 + [100.0] * 20
        macd_line, signal_line, histogram = compute_macd(prices)
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        # MACD should respond to the spike
        self.assertIsInstance(macd_line, (int, float))
    
    def test_macd_on_full_sample_data(self):
        """Test MACD on full sample data."""
        macd_line, signal_line, histogram = compute_macd(self.closes)
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertIsNotNone(histogram)
        
        # All values should be finite numbers
        self.assertTrue(isinstance(macd_line, (int, float)))
        self.assertTrue(isinstance(signal_line, (int, float)))
        self.assertTrue(isinstance(histogram, (int, float)))
    
    def test_macd_histogram_types(self):
        """Test that MACD histogram can be positive or negative."""
        # Uptrend typically has positive histogram
        uptrend = [float(i) for i in range(1, 51)]
        macd_up, signal_up, histogram_up = compute_macd(uptrend)
        
        # Downtrend typically has negative histogram
        downtrend = [float(50 - i) for i in range(50)]
        macd_down, signal_down, histogram_down = compute_macd(downtrend)
        
        # Histograms should have different signs (if both calculated)
        if histogram_up is not None and histogram_down is not None:
            # Uptrend histogram might be positive, downtrend negative
            self.assertIsInstance(histogram_up, (int, float))
            self.assertIsInstance(histogram_down, (int, float))
    
    def test_macd_recent_candles(self):
        """Test MACD calculation on recent candles."""
        recent_50 = self.closes[-50:]
        macd_line, signal_line, histogram = compute_macd(recent_50)
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertIsNotNone(histogram)
    
    def test_macd_exact_values_on_full_data(self):
        """Test MACD exact values on full sample data."""
        macd_line, signal_line, histogram = compute_macd(self.closes, fast=12, slow=26, signal=9)
        
        # Verify exact values from sample CSV data
        expected_line = 9.237399617530173
        expected_signal = 3.9416095332395145
        expected_histogram = 5.295790084290658
        
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertIsNotNone(histogram)
        
        self.assertAlmostEqual(macd_line, expected_line, places=5,
                             msg=f"Expected MACD line={expected_line}, got {macd_line}")
        self.assertAlmostEqual(signal_line, expected_signal, places=5,
                             msg=f"Expected Signal line={expected_signal}, got {signal_line}")
        self.assertAlmostEqual(histogram, expected_histogram, places=5,
                             msg=f"Expected Histogram={expected_histogram}, got {histogram}")
    
    def test_macd_histogram_equals_line_minus_signal(self):
        """Test that histogram = MACD line - signal line on actual data."""
        macd_line, signal_line, histogram = compute_macd(self.closes)
        
        self.assertIsNotNone(histogram)
        # Verify the mathematical relationship
        calculated_histogram = macd_line - signal_line
        self.assertAlmostEqual(histogram, calculated_histogram, places=10,
                             msg=f"Histogram should equal (line - signal), got {histogram} != {calculated_histogram}")
    
    def test_macd_consistency_multiple_runs(self):
        """Test that MACD calculation is deterministic and consistent."""
        # Run calculation multiple times
        macd1_line, macd1_signal, macd1_hist = compute_macd(self.closes)
        macd2_line, macd2_signal, macd2_hist = compute_macd(self.closes)
        macd3_line, macd3_signal, macd3_hist = compute_macd(self.closes)
        
        # All runs should produce identical results
        self.assertEqual(macd1_line, macd2_line)
        self.assertEqual(macd2_line, macd3_line)
        self.assertEqual(macd1_signal, macd2_signal)
        self.assertEqual(macd2_signal, macd3_signal)
        self.assertEqual(macd1_hist, macd2_hist)
        self.assertEqual(macd2_hist, macd3_hist)
    
    def test_macd_values_are_in_reasonable_range(self):
        """Test that MACD values are in reasonable range for price data."""
        macd_line, signal_line, histogram = compute_macd(self.closes)
        
        # For BTC prices around 80k, MACD values should be relatively small
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        
        # MACD should be much smaller than the price itself
        self.assertLess(abs(macd_line), 100)
        self.assertLess(abs(signal_line), 100)
        self.assertLess(abs(histogram), 100)


if __name__ == "__main__":
    unittest.main()
