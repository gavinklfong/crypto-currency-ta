# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development

### Prerequisites
- Python 3.9+
- AWS CLI (configured with appropriate credentials)
- Terraform 1.0+

### Common Commands
- **Build all Lambda packages and layers**: `python build.py`
- **Run all tests**: `python run_tests.py`
- **Run a specific test**: `python -m pytest app/lambdas/<lambda-name>/test_<file>.py -v`
- **Deploy infrastructure**:
  ```bash
  cd infra/
  terraform init
  terraform plan
  terraform apply
  ```

### Python Environment
Tests often require specific dependencies per Lambda function. The `run_tests.py` script automatically attempts to install `requirements-test.txt` for each Lambda directory it tests.

## Architecture Overview

This is a serverless cryptocurrency technical analysis platform running on AWS.

### High-Level Flow
1. **Data Ingestion**: `fetch-market-data` Lambda retrieves OHLC data from Kraken API and stores it in DynamoDB.
2. **Aggregation**: `aggregate-timeframe` Lambda converts 1-minute candles into multiple timeframes (5m, 1h, etc.).
3. **Technical Analysis**: `calculate-ta` Lambda computes indicators (EMA, RSI, MACD) on aggregated data.
4. **Analysis & Alerting**: `ai-analysis` processes data, and `send-to-slack` provides notifications.

### Core Components
- **Lambdas (`app/lambdas/`)**: Individual AWS Lambda functions. Each contains its own `lambda_function.py` and `requirements.txt`.
- **Layers (`app/layers/`)**: Shared code and dependencies packaged as Lambda Layers to reduce deployment package size.
- **Infrastructure (`infra/`)**: Terraform configuration defining DynamoDB tables, Lambda functions, API Gateway, and EventBridge schedules.
- **Database (DynamoDB)**:
  - **Partition Key (PK)**: `PAIR#{symbol}`
  - **Sort Key (SK)**: `TF#{timeframe}#TS#{timestamp}`

### Development Workflow for New Lambdas
1. Create directory in `app/lambdas/<new-lambda-name>/`.
2. Implement `lambda_function.py` and add `requirements.txt`.
3. Add tests as `test_*.py`.
4. Register the new Lambda in `infra/variables.tf`.
5. Run `python build.py` to create deployment packages.
6. Apply infrastructure changes via Terraform.
