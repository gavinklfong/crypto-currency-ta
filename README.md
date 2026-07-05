# Crypto Currency Technical Analysis

A serverless cryptocurrency technical analysis platform built on AWS that fetches market data, aggregates it across multiple timeframes, and calculates technical indicators.

## What This Project Does

This project automates cryptocurrency market data collection and analysis by:

1. **Fetching Market Data**: Retrieves 1-minute OHLC (Open, High, Low, Close) candle data from the Kraken API
2. **Aggregating Candles**: Combines 1-minute candles into larger timeframes (5m, 15m, 30m, 1h, 4h, 1d, 1w)
3. **Calculating Technical Indicators**: Computes key technical analysis metrics including:
   - **EMA** (Exponential Moving Average) with configurable periods
   - **RSI** (Relative Strength Index) for momentum analysis
   - **MACD** (Moving Average Convergence Divergence) for trend detection
4. **Storing Results**: Persists all data and indicators in DynamoDB for querying

The system runs on automated schedules via AWS EventBridge and can be triggered manually via HTTP API Gateway.

## Project Structure

```
.
├── .github/
│   └── workflows/
│       └── deploy.yml             # GitHub Actions CI/CD workflow
├── app/
│   ├── lambdas/                   # Lambda function source code
│   │   ├── aggregate-timeframe/   # Aggregates 1m candles to larger timeframes
│   │   ├── ai-analysis/           # AI-based market analysis
│   │   ├── calculate-ta/          # Calculates technical indicators (EMA, RSI, MACD)
│   │   ├── export-data-to-s3/     # Exports data to Amazon S3
│   │   ├── fetch-market-data/     # Fetches OHLC data from Kraken API
│   │   ├── rerun-controller/      # Manages and controls the rerunning of Lambda functions
│   │   ├── rerun-fetch-market-data/ # Specifically handles rerunning the market data fetch
│   │   ├── send-to-slack/         # Sends alerts and notifications to Slack
│   │   └── trigger-data-export/   # Triggers data export processes
│   ├── layers/                    # Shared Lambda layers
│   └── web/                       # Web components (if any)
├── infra/                         # Terraform infrastructure as code
│   ├── main.tf
│   ├── variables.tf
│   ├── version.tf
│   ├── dynamodb.tf
│   ├── lambda_functions.tf
│   ├── api_gateway.tf
│   ├── cloudwatch_event_scheduler.tf
│   ├── backend.tf
│   └── SCHEDULER_CONFIGURATION.md
├── build.py                       # Build script for packaging Lambdas
├── run_tests.py                   # Test runner for all Lambda functions
└── README.md                      # This file
```

### Component Descriptions

| Component | Purpose |
|-----------|---------|
| **fetch-market-data** | Calls Kraken API to fetch 1-minute OHLC data for configured symbols and stores in DynamoDB |
| **aggregate-timeframe** | Groups 1-minute candles into larger timeframes (5m, 15m, etc.) and calculates OHLCV + derived metrics (VWAP, Heikin-Ashi, typical price) |
| **calculate-ta** | Computes EMA, RSI, and MACD technical indicators on aggregated candles and stores results in DynamoDB |
| **ai-analysis** | Performs AI-driven market analysis |
| **export-data-to-s3** | Exports historical or aggregated data to Amazon S3 |
| **rerun-controller** | Manages and controls the rerunning of various Lambda functions |
| **rerun-fetch-market-data** | Specifically handles rerunning the market data fetching process |
| **send-to-slack** | Sends alerts and notifications to a configured Slack channel |
| **trigger-data-export** | Triggers the data export workflow |

## How to Build

### Prerequisites

- Python 3.9+
- pip
- AWS Account with credentials configured
- Terraform 1.0+

### Step 1: Install Dependencies

```bash
# Install Python dependencies for build and test scripts
pip install boto3 botocore

# Install Terraform (if not already installed)
# See: https://www.terraform.io/downloads.html
```

### Step 2: Build Lambda Packages

The build script packages each Lambda function with its dependencies:

```bash
python build.py
```

This script will:
1. Check for changes in each Lambda function using file hashing
2. Install dependencies from `requirements.txt` for each function
3. Create deployment ZIP files in `.package/` directory

**Output**: Creates `.package/deployment-*.zip` files ready for deployment

### Step 3: Run Tests (Optional but Recommended)

```bash
python run_tests.py
```

This discovers and runs all `test_*.py` files in each Lambda directory using pytest. Tests validate:
- Technical indicator calculations (EMA, RSI, MACD)
- Data aggregation logic
- API integration with Kraken

### Step 4: Deploy Infrastructure with Terraform

```bash
cd infra/

# Initialize Terraform
terraform init

# Review planned changes
terraform plan

# Set environment variable for slack hook
export TF_VAR_lambda_env='{"send-to-slack":{"SLACK_WEBHOOK_URL":"<placeholder>>"}}'

# Deploy infrastructure
terraform apply
```

### Configuration

#### Customize Symbols

Edit `infra/variables.tf` to change which cryptocurrency pairs to track:

```hcl
variable "symbols" {
  default = ["XXBTZUSD", "XETHZUSD"]  # Bitcoin and Ethereum
}
```

#### Customize Schedules

Edit the `timeframe_schedules` in `infra/variables.tf` to adjust how frequently each timeframe aggregates:

```hcl
variable "timeframe_schedules" {
  default = {
    "1m"  = "rate(1 minute)"
    "5m"  = "rate(1 minute)"
    "15m" = "rate(5 minutes)"
    # ... more timeframes
  }
}
```

## Database Schema

Data is stored in DynamoDB with the following structure:

**Partition Key (PK)**: `PAIR#{symbol}` (e.g., `PAIR#XBTUSD`)  
**Sort Key (SK)**: `TF#{timeframe}#TS#{timestamp}` (e.g., `TF#5m#TS#1234567890`)

### Stored Fields

- OHLCV: `open`, `high`, `low`, `close`, `volume`
- Derived Metrics: `typical_price`, `median_price`, `vwap`, `ha_open`, `ha_high`, `ha_low`, `ha_close`
- Technical Indicators: `ema_20`, `ema_50`, `rsi_14`, `macd_line`, `macd_signal`, `macd_histogram`

## Troubleshooting

### Build Issues

- **`pip: command not found`** - Ensure Python is installed and in PATH
- **Lambda ZIP not created** - Check for syntax errors in Lambda code; see `.build/` directory

### Test Failures

Run tests with verbose output:

```bash
python -m pytest app/calculate-ta/test_ema.py -v
```

### Terraform Errors

- **State lock error** - Remove `.terraform.lock.hcl` and retry
- **AWS credentials not found** - Configure AWS CLI: `aws configure`

## CI/CD

This project uses GitHub Actions for automated continuous integration and deployment.

### Workflow Overview

The deployment workflow (`.github/workflows/deploy.yml`) is triggered on:
- Pushes to the `main` branch that include changes to `.py`, `.tf`, or `requirements*.txt` files.
- Manual trigger via `workflow_dispatch`.

### Pipeline Stages

1. **Build Stage**:
   - Sets up Python environment.
   - Runs all Lambda function tests using `run_tests.py`.
   - Builds Lambda deployment packages using `build.py`.
   - Uploads the built packages as artifacts.

2. **Terraform Stage**:
   - Downloads the build artifacts.
   - Sets up Terraform.
   - Configures AWS credentials using OIDC.
   - Runs `terraform apply` to deploy the infrastructure and updated Lambda functions.

## Additional Documentation

- [Scheduler Configuration](infra/SCHEDULER_CONFIGURATION.md) - Details on EventBridge event scheduling
- [TA Tests](app/calculate-ta/TESTS.md) - Technical indicator test coverage details

## Development

### Adding a New Lambda Function

1. Create a new directory in `app/{function-name}/`
2. Add `lambda_function.py` and `requirements.txt`
3. Add test file: `test_*.py`
4. Update `infra/variables.tf` to register the new Lambda
5. Run `python build.py` to package
6. Run `terraform apply` to deploy
