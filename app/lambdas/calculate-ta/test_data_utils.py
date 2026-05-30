"""Utility functions for loading and processing test data."""

import csv
import os
from pathlib import Path


def load_sample_market_data():
    """
    Load sample market data from CSV file.
    
    Returns:
        dict: Dictionary with 'closes' list and 'data' list of all records.
    """
    csv_path = Path(__file__).parent / "sample_market_data.csv"
    
    if not csv_path.exists():
        raise FileNotFoundError(f"Sample data not found at {csv_path}")
    
    closes = []
    data = []
    
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            close_price = float(row["close"])
            closes.append(close_price)
            data.append(row)
    
    return {
        "closes": closes,
        "data": data,
        "count": len(closes)
    }


def get_close_prices_list(market_data):
    """Extract close prices from market data."""
    return market_data["closes"]


def get_sample_window(market_data, window_size=-20):
    """
    Get a slice of close prices for testing.
    
    Args:
        market_data (dict): Market data from load_sample_market_data()
        window_size (int): Number of candles to use. Negative means from end.
    
    Returns:
        list: Close prices for the window.
    """
    closes = market_data["closes"]
    if window_size < 0:
        return closes[window_size:]
    return closes[:window_size]
