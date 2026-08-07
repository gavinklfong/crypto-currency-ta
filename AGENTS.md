# AGENTS.md

## Build, Test, and Deploy

- **Full build**: `python build.py` — runs `build_layers.py` then `build_lambdas.py` in order. Outputs ZIPs to `build/package/`.
- **Layers only**: `python build_layers.py` — builds `pandas`, `pyarrow`, `common-utils` from `app/layers/` using each layer's `build.sh`.
- **Lambdas only**: `python build_lambdas.py` — hash-based incremental rebuild. Copies `app/common/` into each Lambda artifact.
- **Run all tests**: `python run_tests.py` — auto-discovers `test_*.py` across all Lambda dirs, installs per-lambda `requirements-test.txt`, sets `PYTHONPATH` to include `app/layers/common-utils`, runs `pytest -v`.
- **Run a single Lambda's tests**: `cd app/lambdas/<name> && PYTHONPATH=../../layers/common-utils:../../common pytest test_*.py -v`
- **Skip manual/E2E tests**: `pytest -m "manual"` — `ai-analysis/` and `send-to-slack/` have `pytest.ini` with `markers = manual` and `addopts = -m "not manual"`. `fetch-market-data/` has `integration` marker but no skip.
- **Deploy infra**: `cd infra && terraform init && terraform plan && terraform apply`
- **Deploy env var**: `export TF_VAR_lambda_env='{"send-to-slack":{"SLACK_WEBHOOK_URL":"<url>"}}'`
- **CI/CD**: `.github/workflows/deploy.yml` — push to `main` triggers build → test → upload artifacts → `terraform apply` via OIDC. `workflow_dispatch` supports `run_terraform_only`.

## Architecture

- **Data flow**: Kraken API → `fetch-market-data` → DynamoDB (1m candles) → `aggregate-timeframe` → DynamoDB (multi-TF) → `calculate-ta` → DynamoDB (TA indicators) → `ai-analysis` → `send-to-slack`.
- **Job system**: `launch-ec2-job` → transient EC2 workers → `update-job-status` (heartbeat) → `monitor-job-runner` (detects stalls) → SQS FIFO → `rerun-controller` / `rerun-fetch-market-data`.
- **11 Lambda directories** in `app/lambdas/` (9 registered in Terraform), **3 layers** in `app/layers/` (pandas, pyarrow, common-utils), **19 Terraform files** in `infra/`.
- **DynamoDB tables**: `crypto-currency-ta-market-data` (PK=`PAIR#{symbol}`, SK=`TF#{timeframe}#TS#{timestamp}`) and `crypto-currency-ta-job-tracker` (PK=`JOB#{job_id}`, SK=`METADATA`, 3 GSIs).
- **S3 exports**: `crypto-currency-ta-exports/` partitioned by `symbol/`, `tf=`, `date=`, `hour=`.
- **Shared code**: `app/common/job_status_client.py` (`JobStatusClient` with heartbeat thread) — copied into every Lambda build artifact.

## Key Conventions

- **Lambda directory structure**: `app/lambdas/{name}/` → `lambda_function.py`, `requirements.txt`, optional `requirements-test.txt`, optional `pytest.ini`, optional `test_*.py`.
- **Registering a new Lambda**: add to `infra/variables.tf` `lambdas` map with `function_name`, `zip_path`, `layers`, `timeframes`, `environment`. Every field matters — omitting `layers` means no pandas/pyarrow.
- **Layers**: Lambdas using pandas/pyarrow must reference those layers in the `lambdas` map. `common-utils` layer must be listed explicitly (e.g., `"layers": ["common-utils"]`).
- **DynamoDB schema**: Always use `PAIR#{symbol}` / `TF#{timeframe}#TS#{timestamp}` for market data. Never deviate from this key format.
- **Symbols**: Kraken format (e.g., `XBTUSD`, `ETHUSD`). Configured in `infra/variables.tf` `symbols` variable.
- **Timeframes**: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`. Configured in `infra/variables.tf` `timeframe_schedules`.
- **IAM**: Defined in `infra/lambda_common.tf` with least-privilege per Lambda. Full reference in `AWS_PERMISSION.md`.
- **Schedule overrides**: Per-function per-timeframe overrides defined in `lambdas` map in `variables.tf`. Conflicts detected at plan time. See `infra/SCHEDULER_CONFIGURATION.md`.
- **Python**: Use `logging` over `print`. Type hints where practical. Lambda handlers delegate to module-level functions.
- **Terraform**: Use `terraform fmt`. Configure Lambdas via `lambdas` map in `variables.tf` — don't duplicate resources.

## References

- `infra/SCHEDULER_CONFIGURATION.md` — EventBridge schedule config and overrides.
- `app/lambdas/calculate-ta/TESTS.md` — 47 TA indicator tests.
- `app/lambdas/ai-analysis/README.md` — unit vs E2E test patterns.
- `AWS_PERMISSION.md` — full IAM permission reference.
- `.continue/rules/python-terraform-standards.md` — coding standards.
- `.github/copilot-instructions.md` — extended architecture and workflow details.
