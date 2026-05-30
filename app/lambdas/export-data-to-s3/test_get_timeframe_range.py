import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from lambda_function import get_timeframe_range

class TestGetTimeframeRange:
    @staticmethod
    def _timestamp(year, month, day, hour=0, minute=0, second=0):
        # Create a naive datetime object in local time
        dt = datetime(year, month, day, hour, minute, second)
        # Attach UTC timezone information
        dt_utc = dt.replace(tzinfo=timezone.utc)
        # Return the timestamp for the UTC-aware datetime object
        return int(dt_utc.timestamp())

    # Common now time used for all tests
    NOW = datetime(2024, 5, 12, 13, 45, 0, tzinfo=timezone.utc)

    def run_test_cases(self, testcase):
        timeframe, expected_start_timestamp, expected_end_timestamp = testcase

        start, end = get_timeframe_range(timeframe, now=self.NOW)
    
        assert start == expected_start_timestamp, f"Expected {expected_start_timestamp}, but got {start} for timeframe: '{timeframe}'"
        assert end == expected_end_timestamp, f"Expected {expected_end_timestamp}, but got {end} for timeframe: '{timeframe}'"

    @pytest.mark.parametrize("testcase", [
        # From 2024-05-12 11:00 UTC to 2024-05-12 12:59:59 UTC
        ("1m", 1715511600, 1715518799),
        
        # From 2024-05-12 11:00 UTC to 2024-05-12 12:59:59 UTC
        ("5m", 1715511600, 1715518799),
        
        # From 2024-05-12 11:00 UTC to 2024-05-12 12:59:59 UTC
        ("15m", 1715511600, 1715518799),
        
        # From 2024-05-12 11:00 UTC to 2024-05-12 12:59:59 UTC
        ("30m", 1715511600, 1715518799),
        
        # From 2024-05-12 11:00 UTC to 2024-05-12 12:59:59 UTC
        ("1h", 1715511600, 1715518799),
        
        # From 2024-05-11 00:00 UTC to 2024-05-12 23:59:59 UTC
        ("4h", 1715385600, 1715471999),
        
        # From 2024-05-10 00:00 UTC to 2024-05-12 23:59:59 UTC
        ("1d", 1715299200, 1715471999),
    ])

    def test_timeframes(self, testcase):
        self.run_test_cases(testcase)
