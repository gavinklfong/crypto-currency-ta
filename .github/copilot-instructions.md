# Copilot Instructions for Crypto Currency TA

## Build, Test, and Lint

### Build
- **Full Build Pipeline:** `python build.py` — builds all Lambda layers then all Lambda functions in order.
- **Build Layers Only:** `python build_layers.py` — incrementally builds layers (`pandas`, `pyarrow`, `common-utils`) using Dockerfile + `build.sh` scripts where applicable.
- **Build Lambdas Only:** `python build_lambdas.py` — incrementally rebuilds only Lambda functions with changed source code (hash-based detection). Copies `app/common/job_status_client.py` into each Lambda's build artifact.
- **Build a Single Lambda:** `cd app/lambdas/<name> && python -m pip install -r requirements.txt -t .` then zip.

### Test
- **Run All Tests:** `python run_tests.py` — auto-discovers all `test_*.py` files across every Lambda directory and the `app/common/` shared code. Installs `requirements-test.txt` per-lambda, sets `PYTHONPATH` to include `app/layers/common-utils`, and runs `pytest`.
- **Run a Single Test:** `cd app/lambdas/<name> && PYTHONPATH=../../layers/common-utils:../../common pip install -r requirements.txt -r requirements-test.txt && pytest test_<file>.py -v`
- **Skip Markers:** Some Lambdas (`ai-analysis`, `send-to-slack`) use `pytest.ini` with `markers = manual` — by default `pytest` skips `@pytest.mark.manual` tests (real AWS calls). Run with `pytest -m "manual"` to execute E2E tests.
- **Common Code Tests:** Tests for shared code live in `app/common/test_*.py` and run via `python run_tests.py`.

### Lint
- No formal linting/linting tools are configured. Follow PEP 8 and use consistent Python style. Run `python -m py_compile <file>` to check syntax.

## High-Level Architecture

This is a serverless cryptocurrency technical analysis platform on AWS that automates market data collection, aggregation, and technical indicator calculation.

### Data Flow
```
Kraken API → fetch-market-data → DynamoDB (1m candles)
                                  ↓
                    aggregate-timeframe → DynamoDB (multi-TF OHLCV)
                                  ↓
                    calculate-ta → DynamoDB (EMA/RSI/MACD etc.)
                                  ↓
                    ai-analysis → Bedrock/LLM analysis
                                  ↓
                    send-to-slack → Slack notifications
```

### Scheduled Workflows
- **EventBridge Scheduler** — Dynamic rules for every `{symbol}-{timeframe}` combination drive recurring Lambda invocations. Rules are deduplicated when multiple Lambdas share the same schedule for a timeframe.
- **On-Demand TA Jobs** — Long-running TA jobs are tracked via DynamoDB (`JOB#{job_id}`), launched on transient EC2 workers via `launch-ec2-job`, and monitored by `monitor-job-runner` (detects stalled jobs and terminates their EC2 instances).

### Lambda Functions (13 total)

| Lambda | Purpose |
|--------|---------|
| `fetch-market-data` | Fetches 1m OHLC data from Kraken API, stores in DynamoDB |
| `aggregate-timeframe` | Groups 1m candles into 5m/15m/30m/1h/4h/1d/1w; computes OHLCV, VWAP, Heikin-Ashi, typical price |
| `calculate-ta` | Computes technical indicators (EMA, RSI, MACD, and 47 total TA indicators) on aggregated candles |
| `ai-analysis` | Processes market data and generates AI analysis via Bedrock/LLM |
| `send-to-slack` | Sends alerts and analysis results to Slack via webhook |
| `launch-ec2-job` | Launches transient EC2 workers for heavy TA jobs |
| `monitor-job-runner` | Detects stalled jobs via heartbeat monitoring and terminates their EC2 instances |
| `update-job-status` | Updates DynamoDB job tracker status/heartbeat |
| `rerun-controller` | Orchestrates rerun pipelines for failed jobs |
| `rerun-fetch-market-data` | Re-fetches market data for a specific symbol/timeframe |
| `launch-ec2-job` | Launches transient EC2 workers for heavy jobs |

### Lambda Layers (3 total)
- **`pandas`** — Built with Dockerfile (multi-stage) + `build.sh`
- **`pyarrow`** — Built with Dockerfile (multi-stage) + `build.sh`
- **`common-utils`** — Plain Python; exports `send_to_sns` helper

### Shared Code
- **`app/common/job_status_client.py`** — `JobStatusClient` class with DynamoDB job tracking and heartbeat thread. Copied into each Lambda build artifact by `build_lambdas.py`.
- **`app/common/test_job_status_client.py`** — Tests for shared code.

### Application Scripts
- **`app/scripts/ta-job`** — Standalone CLI for simulating heavy TA jobs (uses `JobStatusClient`).
- **`app/web/frontend.py`** — Streamlit dashboard for browsing market data from S3/DynamoDB.

### Infrastructure & Data

- **Infrastructure:** Terraform in `infra/` (19 `.tf` files).
- **Data Storage:** DynamoDB.
  - **Market Data:** PK = `PAIR#{symbol}` (e.g., `PAIR#XBTUSD`), SK = `TF#{timeframe}#TS#{timestamp}` (e.g., `TF#5m#TS#1234567890`)
  - **Job Tracker:** PK = `JOB#{job_id}`, SK = `METADATA` (with 3 GSIs for status/heartbeat/instance queries)
- **S3:** Data exports to `crypto-currency-ta-exports/` partitioned by `symbol/`, `tf=`, `date=`, `hour=`.
- **SQS FIFO:** Reliable message processing for reruns and cross-Lambda communication.
- **SNS:** Notifications for alerts and job completion.
- **API Gateway + Lambda:** REST API for on-demand operations.
- **CloudWatch Logs:** Each Lambda has its own log group.

## Key Conventions

- **Lambda Directory:** Each Lambda is in `app/lambdas/{function-name}/` with `lambda_function.py`, `requirements.txt`, optional `requirements-test.txt`, optional `pytest.ini`, and optional `test_*.py` files.
- **Lambda Registration:** Every Lambda must be registered in `infra/variables.tf` in the `lambdas` map with: name, zip path, timeframes, schedule, layers, environment variables, and IAM role.
- **IAM Permissions:** Defined in `infra/lambda_common.tf`. Each Lambda gets its own IAM role with least-privilege policies. For the full list of ~130 permissions, see `AWS_PERMISSION.md`.
- **EventBridge Overrides:** Per-function per-timeframe schedule overrides are defined in the `lambdas` map in `variables.tf`. Conflicts are detected at plan time. See `infra/SCHEDULER_CONFIGURATION.md` for details.
- **DynamoDB Schema:** Always use `PAIR#{symbol}` / `TF#{timeframe}#TS#{timestamp}` for market data and `JOB#{job_id}` / `METADATA` for job tracking.
- **Timeframes:** Supported: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`.
- **Symbols:** Configured in `infra/variables.tf` (`symbols` variable). Kraken format (e.g., `XBTUSD`, `ETHUSD`).
- **Deploy:** GitHub Actions OIDC workflow in `.github/workflows/deploy.yml`. Push → build+test+deploy. `workflow_dispatch` supports manual runs with `run_terraform_only` option.
- **Layers Dependency:** Lambdas using pandas/pyarrow must reference those layers in the `lambdas` map in `variables.tf`.

## CI/CD

- **Push Trigger:** `python build.py` → `python run_tests.py` → `terraform plan` → `terraform apply` → deploy updated ZIPs to S3.
- **Manual Trigger:** `workflow_dispatch` with optional `run_terraform_only` to skip build/tests and only apply infra changes.
- **Artifacts:** Lambda ZIPs and layer ZIPs are uploaded to S3 and attached as workflow artifacts.

## References

- **AWS IAM Permissions:** `AWS_PERMISSION.md` — full ~130 permission reference.
- **EventBridge Scheduler:** `infra/SCHEDULER_CONFIGURATION.md` — schedule config, overrides, conflict detection.
- **TA Indicator Tests:** `app/lambdas/calculate-ta/TESTS.md` — 47 indicator tests (EMA, RSI, MACD, etc.).
- **AI Analysis Tests:** `app/lambdas/ai-analysis/README.md` — unit vs E2E test patterns, cost warnings.
- **Python/Terraform Standards:** `.continue/rules/python-terraform-standards.md` — architecture context and coding standards.

## Coding Standards

### Python
- Use type hints where practical.
- Prefer `logging` over `print`.
- Handle errors gracefully with specific exception handling.
- Keep Lambda handlers small; delegate to module-level functions.
- Use environment variables for configuration (not hardcoded values).

### Terraform
- Use the `lambdas` map in `variables.tf` for all Lambda configuration (avoid duplicating resources).
- Keep IAM policies minimal and scoped to specific actions/resources.
- Document non-obvious configurations with comments.
