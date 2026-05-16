# TA Unit Tests Summary

This directory contains comprehensive unit tests for Technical Analysis (TA) indicator calculations in the calculate-ta Lambda function.

## Test Files Created

### 1. test_ema.py
Tests for Exponential Moving Average (EMA) calculation.
- **9 test cases** covering:
  - Basic EMA calculation with simple values
  - EMA(20) and EMA(50) on full sample data
  - Single value and constant value scenarios
  - Uptrend and downtrend behavior
  - Recent candles analysis
  - Smoothing effects of different periods

### 2. test_rsi.py
Tests for Relative Strength Index (RSI) calculation.
- **13 test cases** covering:
  - RSI range validation (0-100)
  - Minimum data requirements
  - RSI(14) and RSI(7) calculations
  - Constant price scenarios
  - Uptrend and downtrend behavior
  - Overbought (>70) and oversold (<30) conditions
  - Different RSI periods
  - Extreme price movements

### 3. test_macd.py
Tests for Moving Average Convergence Divergence (MACD) calculation.
- **13 test cases** covering:
  - Three component validation (line, signal, histogram)
  - Minimum data requirements
  - Default and custom parameters
  - Histogram calculation verification
  - Uptrend and downtrend behavior
  - Constant price scenarios
  - Price spike response
  - Histogram sign analysis

### 4. test_data_utils.py
Utility functions for loading and processing sample market data.
- `load_sample_market_data()` - Load CSV data
- `get_close_prices_list()` - Extract close prices
- `get_sample_window()` - Get a slice of close prices

## Running the Tests

Run all tests:
```bash
cd app/calculate-ta
python -m unittest test_ema.py test_rsi.py test_macd.py -v
```

Run specific test file:
```bash
python -m unittest test_ema.py -v
python -m unittest test_rsi.py -v
python -m unittest test_macd.py -v
```

Run specific test case:
```bash
python -m unittest test_ema.TestComputeEMA.test_ema_period_20_on_full_data -v
```

## Test Data

All tests use `sample_market_data.csv` which contains 101 real market data candles for BTC/USD with:
- OHLCV data (Open, High, Low, Close, Volume)
- 1-minute candle timeframe
- Real price data for validation

## Test Coverage

**Total Test Cases: 35**
- EMA Tests: 9
- RSI Tests: 13
- MACD Tests: 13

**All tests: PASSED** ✓

## Test Scenarios Covered

Each TA indicator is tested for:
1. ✓ Basic calculations with simple data
2. ✓ Full dataset analysis (101 candles)
3. ✓ Edge cases (single value, constant prices)
4. ✓ Trend detection (uptrend, downtrend)
5. ✓ Different parameters/periods
6. ✓ Range validation
7. ✓ Recent candles behavior
8. ✓ Data requirement validation
