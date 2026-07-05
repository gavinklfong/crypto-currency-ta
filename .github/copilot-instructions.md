# Copilot Instructions for Crypto Currency TA

## Build, Test, and Lint

### Build
- **Full Build Pipeline:** Run `python build.py` to build both Lambda layers and Lambda functions.
- **Incremental Lambda Build:** Run `python build_lambdas.py` to rebuild only the Lambda functions that have changes.
- **Build Layers:** Run `python build_layers.py` to rebuild Lambda layers.

### Test
- **Run All Tests:** Run `python run_tests.py` to discover and run all `test_*.py` files across all Lambda functions using `pytest`.
- **Run Single Test:** Run `pytest <path_to_test_file>` within the specific Lambda directory (e.g., `cd app/lambdas/calculate-ta && pytest test_ema.py`). Note that you may need to install test dependencies first using `pip install -r requirements-test.txt`.

### Lint
- No formal linting command is configured. Ensure code quality and adherence to Python best practices.

## High-Level Architecture

This is a serverless cryptocurrency technical analysis platform built on AWS. It automates market data collection, aggregation, and technical indicator calculation.

### Core Components
- **`fetch-market-data`**: Fetches 1-minute OHLC data from the Kraken API and stores it in DynamoDB.
- **`aggregate-timeframe`**: Groups 1-minute candles into larger timeframes (5m, 15m, 30m, 1h, 4h, 1d, 1w) and calculates OHLCV + derived metrics (VWAP, Heikin-Ashi, typical price).
- **`calculate-ta`**: Computes technical indicators (EMA, RSI, MACD) on aggregated candles and stores the results in DynamoDB.

### Infrastructure & Data
- **Infrastructure:** Managed via Terraform in the `infra/` directory.
- **Data Storage:** DynamoDB.
  - **Partition Key (PK):** `PAIR#{symbol}` (e.g., `PAIR#XBTUSD`)
  - **Sort Key (SK):** `TF#{timeframe}#TS#{timestamp}` (e.g., `TF#5m#TS#1234567890`)
- **Automation:** Orchestrated via AWS EventBridge (CloudWatch Events).
- **Communication:** Some components use SQS FIFO queues for reliable processing.

## Key Conventions

- **Lambda Function Structure:** Each function resides in its own directory under `app/lambdas/{function-name}/`.
- **Dependency Management:** Each Lambda function manages its own dependencies via a `requirements.txt` file in its directory. Test-specific dependencies should be placed in `requirements-test.txt`.
- **Infrastructure Registration:** When adding a new Lambda function, it must be registered in the `lambdas` map within `infra/variables.tf`.
- **Testing Pattern:** Tests are located in the same directory as the Lambda function they test, following the `test_*.py` naming convention.
- **DynamoDB Schema:** Always use the `PAIR#{symbol}` and `TF#{timeframe}#TS#{timestamp}` pattern for Partition and Sort keys to ensure consistency with the aggregation and calculation logic.
