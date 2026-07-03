# GitHub Copilot Instructions for Crypto Currency Technical Analysis

## Build, Test, and Lint

### Building Lambda Packages
The project uses a custom build pipeline to package Lambda functions and their dependencies into deployment-ready ZIP files.

- **Full Build Pipeline**: Run `python build.py` to build all layers and all Lambda functions.
- **Lambda Layers**: Built via `python build_layers.py`.
- **Lambda Functions**: Built via `python build_lambdas.py`.

Deployment ZIP files are stored in the `.package/` directory.

### Running Tests
Tests are organized by Lambda function directory and use `pytest`.

- **Full Test Suite**: Run `python run_tests.py` from the repository root. This script iterates through all Lambda directories and runs their respective tests.
- **Single Lambda Tests**:
  1. `cd app/lambdas/<function_name>`
  2. `pytest` (or `python -m pytest`)
- **Specific Test File**:
  - `pytest <test_file.py>` (e.g., `pytest test_ema.py`)
- **Specific Test Case**:
  - `pytest <test_file.py>::<test_function_name>` (e.g., `pytest test_ema.py::test_ema_20_exact_value_on_last_20_candles`)

## High-Level Architecture

This is a serverless AWS-based platform for cryptocurrency technical analysis. The workflow is data-driven and event-triggered:

1.  **Data Fetching (`fetch-market-data`)**: Periodically fetches 1-minute OHLC (Open, High, Low, Close) candle data from the Kraken API and stores it in DynamoDB.
2.  **Aggregation (`aggregate-timeframe`)**: Consumes 1-minute candles and aggregates them into larger timeframes (5m, 15m, 1h, 1d, etc.). It calculates OHLCV plus derived metrics like VWAP and Heikin-Ashi candles.
3.  **Technical Analysis (`calculate-ta`)**: Triggered after aggregation, this function computes technical indicators (EMA, RSI, MACD) and updates the existing DynamoDB items with these new metrics.
4.  **Data Export (`export-data-to-s3`)**: Periodically exports aggregated data to Amazon S3 in Parquet format for long-term storage and analysis.

### Data Storage (DynamoDB)
Data is stored using a composite key pattern to support efficient time-series queries:
- **Partition Key (PK)**: `PAIR#{symbol}` (e.g., `PAIR#XBTUSD`)
- **Sort Key (SK)**: `TF#{timeframe}#TS#{timestamp}` (e.g., `TF#5m#TS#1234567890`)

## Key Conventions

### Lambda Development
- **Handler Pattern**: All Lambdas implement a `lambda_handler(event, context)` function.
- **Event Sources**: Lambdas can be triggered via:
    - **EventBridge**: Passing a JSON payload with `symbol` and `timeframe` in the `detail` field.
    - **SQS**: Receiving a message where the body contains the `symbol` and `timeframe`.
    - **Direct Invocation**: Passing `symbol` and `timeframe` directly in the event.
- **Range Processing**: The `calculate-ta` Lambda supports a "Range Mode" where an event includes `start_ts` and `end_ts`. In this mode, it re-calculates TA for all candles in the specified range.

### Data Types
- **Decimals for Financial Data**: Always use `decimal.Decimal` when interacting with DynamoDB to avoid floating-point precision issues. The project includes a helper `D(x)` in many Lambdas to safely convert values.
- **Timestamps**: Use Unix timestamps (integers) for all time-related logic and SK construction.

### Terraform Infrastructure
- **Lambda Registration**: New Lambdas must be added to the `lambdas` map in `infra/variables.tf`.
- **Scheduling**: Scheduling is managed via `infra/cloudwatch_event_scheduler.tf`. You can define global schedules in `variables.tf` or override them per-function using `schedule_overrides` in the `lambdas` map.
- **Deduplication**: The infrastructure is designed to deduplicate CloudWatch Event Rules if multiple Lambdas share the same schedule for a specific `{symbol}-{timeframe}` combination.
