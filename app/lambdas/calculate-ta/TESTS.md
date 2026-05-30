# TA Unit Tests Summary

This directory contains comprehensive unit tests for Technical Analysis (TA) indicator calculations in the calculate-ta Lambda function.

## Test Files Created

### 1. test_ema.py
Tests for Exponential Moving Average (EMA) calculation.
- **13 test cases** covering:
  - Basic EMA calculation with simple values
  - EMA(20) and EMA(50) on full sample data
  - Single value and constant value scenarios
  - Uptrend and downtrend behavior
  - Recent candles analysis
  - Smoothing effects of different periods
  - EMA(20) exact value: `80750.82245806116` ✓
  - EMA(50) exact value: `80748.9618989826` ✓
  - Deterministic consistency across multiple runs
  - Full dataset value bounds validation

### 2. test_rsi.py
Tests for Relative Strength Index (RSI) calculation.
- **17 test cases** covering:
  - RSI range validation (0-100)
  - Minimum data requirements
  - RSI(14) and RSI(7) calculations
  - Constant price scenarios
  - Uptrend and downtrend behavior
  - Overbought (>70) and oversold (<30) conditions
  - Different RSI periods
  - Extreme price movements
  - RSI(14) exact value: `72.79358132749721` ✓
  - RSI(7) exact value: `75.09578544061858` ✓
  - Deterministic consistency across multiple runs
  - Recent 30-candle value validation

### 3. test_macd.py
Tests for Moving Average Convergence Divergence (MACD) calculation.
- **17 test cases** covering:
  - Three component validation (line, signal, histogram)
  - Minimum data requirements
  - Default and custom parameters
  - Histogram calculation verification
  - Uptrend and downtrend behavior
  - Constant price scenarios
  - Price spike response
  - Histogram sign analysis
  - MACD Line exact value: `9.237399617530173` ✓
  - Signal Line exact value: `3.9416095332395145` ✓
  - Histogram exact value: `5.295790084290658` ✓
  - Histogram = Line - Signal formula verification
  - Deterministic consistency across multiple runs
  - Value range bounds for price data

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
python -m unittest test_ema.TestComputeEMA.test_ema_20_exact_value_on_last_20_candles -v
```

## Test Data

All tests use `sample_market_data.csv` which contains 200 real market data candles for BTC/USD with:
- OHLCV data (Open, High, Low, Close, Volume)
- 1-minute candle timeframe
- Real price data for exact value validation

**Data Summary:**
- Total candles: 200
- Min price: 80636.8
- Max price: 80790.2
- First close: 80729.0
- Last close: 80772.6

## Test Coverage

**Total Test Cases: 47** ✓
- EMA Tests: 13 (9 + 4 new deterministic)
- RSI Tests: 17 (13 + 4 new deterministic)
- MACD Tests: 17 (13 + 4 new deterministic)

**All tests: PASSED** ✓

## Test Scenarios Covered

### Behavioral Tests (35 tests)
Each TA indicator is tested for:
1. ✓ Basic calculations with simple data
2. ✓ Full dataset analysis (200 candles)
3. ✓ Edge cases (single value, constant prices)
4. ✓ Trend detection (uptrend, downtrend)
5. ✓ Different parameters/periods
6. ✓ Range validation
7. ✓ Recent candles behavior
8. ✓ Data requirement validation

### Deterministic Tests (12 tests) - **NEW**
Each TA indicator is tested for:
1. ✓ **Exact value consistency** - Verified against sample CSV data
   - EMA(20) on last 20 candles: `80750.82245806116`
   - EMA(50) on last 50 candles: `80748.9618989826`
   - RSI(14) on full data: `72.79358132749721`
   - RSI(7) on full data: `75.09578544061858`
   - MACD Line: `9.237399617530173`
   - MACD Signal: `3.9416095332395145`
   - MACD Histogram: `5.295790084290658`

2. ✓ **Reproducibility** - Same input always produces same output
3. ✓ **Mathematical validation** - Internal relationships verified
4. ✓ **Value bounds** - Results stay within expected ranges

## Key Features

- **Deterministic**: All calculations produce consistent, reproducible results
- **Data-Driven**: Tests use real market data from CSV sample
- **Comprehensive**: Covers both edge cases and typical scenarios
- **Validated**: Exact values verified against sample data
- **Reproducible**: Multiple runs confirm consistency
- **Maintainable**: Clear test names and documentation

## Changes Made

Added 12 new deterministic tests:
- 4 EMA tests with exact value verification
- 4 RSI tests with exact value verification  
- 4 MACD tests with exact value verification

All tests verify that given identical input data from the CSV, the output values are always the same and match expected calculations.
