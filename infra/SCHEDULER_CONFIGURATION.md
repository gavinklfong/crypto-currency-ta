# EventBridge Scheduler Configuration

## Overview

This document explains the flexible EventBridge scheduling system that allows different Lambda functions to have different schedules for the same timeframe. 

**Key Features:**
- ✅ Global default schedules for timeframes (e.g., "1d" = rate(4 hours) by default)
- ✅ Per-function schedule overrides (e.g., export-data-to-s3 uses "1d" = rate(1 day))
- ✅ Automatic rule deduplication (multiple Lambdas targeting the same {symbol}-{timeframe} with the same schedule share one CloudWatch rule)
- ✅ Automatic conflict detection (errors if different Lambdas target the same {symbol}-{timeframe} with different schedules)
- ✅ Symbol-based targeting for multi-symbol support
- ✅ Event injection (each Lambda receives symbol and timeframe in the event)

## How It Works

### 1. Global Schedule Map
All timeframes map to default schedules in `var.timeframe_schedules` (defined in `variables.tf`):

```hcl
timeframe_schedules = {
  "1m"  = "rate(1 minute)"
  "5m"  = "rate(1 minute)"
  "15m" = "rate(5 minutes)"
  "30m" = "rate(15 minutes)"
  "1h"  = "rate(30 minutes)"
  "4h"  = "rate(1 hour)"
  "1d"  = "rate(4 hours)"    # Default: TA calculation runs every 4 hours
  "1w"  = "rate(1 day)"
}
```

### 2. Per-Function Schedule Overrides
Lambda functions can override the default schedule for specific timeframes using `schedule_overrides`. For example:

```hcl
export_data_to_s3 = {
  function_name = "export-data-to-s3"
  zip_path      = "../.package/deployment-export-data-to-s3.zip"
  timeframes    = ["1d", "1w"]
  schedule_overrides = {
    "1d" = "rate(1 day)"        # Override: export runs once per day
    "1w" = "rate(7 days)"       # Override: export runs once per week
  }
}
```

### 3. Rule Deduplication
Multiple Lambdas can subscribe to the same `{symbol}-{timeframe}` with the same schedule, and they'll share a single CloudWatch Event Rule with multiple targets:

```
Example:
- calculate_ta subscribes to: [XXBTZUSD-1d] with schedule "rate(4 hours)"
- aggregate_timeframe subscribes to: [XXBTZUSD-1d] with schedule "rate(4 hours)"
- export_data_to_s3 subscribes to: [XXBTZUSD-1d] with schedule "rate(1 day)"

Result:
- CloudWatch Rule "XXBTZUSD-1d-4hours" → triggers calculate_ta and aggregate_timeframe
- CloudWatch Rule "XXBTZUSD-1d-1day" → triggers export_data_to_s3
```

### 4. Event Format
Each Lambda receives an event with the symbol and timeframe:

```json
{
  "detail": {
    "symbol": "XXBTZUSD",
    "timeframe": "1d"
  }
}
```

## Configuration

### Symbols
Define which symbols to track in `variables.tf`:

```hcl
variable "symbols" {
  description = "List of trading symbols to track"
  type        = list(string)
  default     = ["XXBTZUSD", "XETHZUSD"]
}
```

Override in `terraform.tfvars`:
```hcl
symbols = ["XXBTZUSD", "XETHZUSD", "XRPZUSD"]
```

### Global Schedules (Timeframe Defaults)
All Lambda functions use the global `timeframe_schedules` by default. Override specific timeframes in `variables.tf`:

```hcl
variable "timeframe_schedules" {
  default = {
    "1m"  = "rate(1 minute)"
    "5m"  = "rate(1 minute)"
    "15m" = "rate(5 minutes)"
    "30m" = "rate(15 minutes)"
    "1h"  = "rate(30 minutes)"
    "4h"  = "rate(1 hour)"
    "1d"  = "rate(4 hours)"
    "1w"  = "rate(1 day)"
  }
}
```

Override in `terraform.tfvars`:
```hcl
timeframe_schedules = {
  "1m"  = "rate(2 minutes)"    # More frequent market data fetches
  "1d"  = "rate(6 hours)"      # Slower TA calculation
  "1w"  = "rate(2 days)"       # Slower weekly aggregation
}
```

### Per-Function Schedule Overrides
Each Lambda can override the global schedules for specific timeframes. For example, export-data-to-s3 uses infrequent schedules:

```hcl
variable "lambdas" {
  default = {
    calculate_ta = {
      function_name = "calculate-ta"
      zip_path      = "../.package/deployment-calculate-ta.zip"
      timeframes    = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
      # No schedule_overrides: uses global timeframe_schedules
    }

    export_data_to_s3 = {
      function_name = "export-data-to-s3"
      zip_path      = "../.package/deployment-export-data-to-s3.zip"
      timeframes    = ["1d", "1w"]
      schedule_overrides = {
        "1d" = "rate(1 day)"      # Override: daily export instead of 4-hourly
        "1w" = "rate(7 days)"     # Override: weekly export instead of daily
      }
    }
  }
}
```

Override per-function schedules in `terraform.tfvars`:

```hcl
lambdas = {
  calculate_ta = {
    function_name = "calculate-ta"
    zip_path      = "../.package/deployment-calculate-ta.zip"
    timeframes    = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    schedule_overrides = {
      "1d" = "cron(0 0 * * ? *)"  # Override: midnight daily only
    }
  }

  export_data_to_s3 = {
    function_name = "export-data-to-s3"
    zip_path      = "../.package/deployment-export-data-to-s3.zip"
    timeframes    = ["1d", "1w"]
    schedule_overrides = {
      "1d" = "cron(0 2 * * ? *)"   # Override: 2 AM UTC daily
      "1w" = "cron(0 0 ? * MON *)" # Override: Monday midnight
    }
  }

  aggregate_timeframe = {
    function_name = "aggregate-timeframe"
    zip_path      = "../.package/deployment-aggregate-timeframe.zip"
    timeframes    = ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    # No schedule_overrides: uses global schedules
  }
}
```

## Adding a New Lambda with Custom Schedules

1. **Add the Lambda function definition** in `variables.tf`:

```hcl
variable "lambdas" {
  default = {
    # ... existing Lambdas ...

    new_export_function = {
      function_name = "new-export-function"
      zip_path      = "../.package/deployment-new-export-function.zip"
      timeframes    = ["1d", "1w", "1mo"]
      schedule_overrides = {
        "1d"  = "rate(1 day)"
        "1w"  = "rate(7 days)"
        "1mo" = "rate(30 days)"
      }
    }
  }
}
```

2. **Add the zip file path** to your build process

3. **Plan and apply**:
```bash
terraform plan
terraform apply
```

Terraform will automatically:
- Create CloudWatch Event Rules for each `{symbol}-{timeframe}` combination
- Attach the new Lambda function to the rules
- Deduplicate rules if the same `{symbol}-{timeframe}` is shared by other Lambdas with the same schedule

## Lambda Handler Implementation

Lambda functions receive events in the following format:

```python
def lambda_handler(event, context):
    # Extract symbol and timeframe from EventBridge event
    symbol = event.get("detail", {}).get("symbol")
    timeframe = event.get("detail", {}).get("timeframe")
    
    if not symbol or not timeframe:
        logger.error("Missing symbol or timeframe in event")
        return {"status": "error", "message": "Missing symbol or timeframe"}
    
    logger.info(f"Processing {symbol} with timeframe {timeframe}")
    
    # Perform Lambda-specific logic
    result = process_data(symbol, timeframe)
    
    return {"status": "success", "symbol": symbol, "timeframe": timeframe, "result": result}
```

## Schedule Override Conflicts

⚠️ **Important**: If two Lambda functions subscribe to the same `{symbol}-{timeframe}` with **different** schedules, Terraform will detect a conflict and fail the plan.

**Example (will cause error):**
```hcl
calculate_ta = {
  timeframes = ["1d"]
  # Uses global: "1d" = "rate(4 hours)"
}

export_data_to_s3 = {
  timeframes = ["1d"]
  schedule_overrides = { "1d" = "rate(1 day)" }  # Different schedule!
}
```

**Result**: Terraform conflict detected for `{symbol}-1d` with schedules `["rate(4 hours)", "rate(1 day)"]`

**Solutions:**
1. Use different timeframes for different functions
2. Make both functions use the same schedule for a given timeframe
3. Move one function to a different symbol subset

## Deploying Changes

### Change Global Timeframe Schedule
```bash
# Edit variables.tf or terraform.tfvars
terraform plan
terraform apply
```

All Lambdas will start using the new schedule for that timeframe, unless they have an override.

### Add a New Symbol
```bash
# Edit variables.tf or terraform.tfvars
symbols = ["XXBTZUSD", "XETHZUSD", "XRPZUSD"]
terraform plan
terraform apply
```

All Lambda × Timeframe combinations will now have rules for the new symbol.

### Override a Specific Lambda's Schedule
```bash
# Edit variables.tf or terraform.tfvars
lambdas = {
  calculate_ta = {
    # ...
    schedule_overrides = { "1d" = "cron(0 0 * * ? *)" }
  }
}
terraform plan
terraform apply
```

Only the `calculate_ta` Lambda will use the custom schedule for "1d"; others use global defaults.

## Troubleshooting

### Lambda not triggering at the right time
1. Check `terraform plan` output to see the actual schedule expression
2. Verify the Lambda is in the correct CloudWatch Event Rule target list
3. Check CloudWatch Logs for Lambda execution
4. Verify IAM permissions: Lambda must have `lambda:InvokeFunction` permission from `events.amazonaws.com`

### Terraform plan shows conflicts
1. Identify which Lambdas are conflicting: `terraform plan | grep -A5 "Schedule conflicts"`
2. Check the schedules for the affected `{symbol}-{timeframe}`
3. Either align the schedules or use different timeframes for different functions

### S3 Export Permissions
The `export-data-to-s3` Lambda needs S3 permissions. These are automatically granted by the `lambda_s3_access` policy in `lambda_functions.tf`:
- `s3:PutObject` — Write export files
- `s3:GetObject` — Read existing exports (if needed)
- `s3:ListBucket` — List bucket contents
- Bucket: `${var.export_bucket_name}` (default: `crypto-currency-ta-exports`)

## Advanced: Cron vs. Rate Expressions

- **Rate expressions** (recommended): `rate(N minutes|hours|days)` — Fixed intervals
  - `rate(4 hours)` — Every 4 hours
  - `rate(1 day)` — Once per day
  
- **Cron expressions**: `cron(minutes hours day month ? day-of-week)` — Specific times
  - `cron(0 0 * * ? *)` — Every day at midnight UTC
  - `cron(0 0 ? * MON *)` — Every Monday at midnight UTC
  - `cron(0/15 * * * ? *)` — Every 15 minutes

Use cron for precise timing; use rate for fixed intervals.

## Summary of Files Changed

- `variables.tf` — Added `schedule_overrides` field to Lambda config; added `export_bucket_name` variable; added `export_data_to_s3` Lambda definition
- `cloudwatch_event_scheduler.tf` — Updated locals to merge global and per-function schedules; added conflict detection
- `lambda_functions.tf` — Added S3 access policy for export Lambda
- `SCHEDULER_CONFIGURATION.md` — This file (updated documentation)
   ```bash
   aws events describe-targets --rule schedule-fetch_market_data --query 'Targets[0].Input'
   ```
3. Ensure the Lambda is decoding the event correctly

### Invalid JSON in event_input
- Use `jsonencode()` in Terraform to properly escape JSON strings
- Avoid manual JSON strings unless properly escaped

### Testing Locally
```python
# Test event structure
test_event = {
    "detail": {
        "symbols": ["BTC/USD", "ETH/USD"]
    }
}

# Call Lambda directly
from lambda_function import lambda_handler
result = lambda_handler(test_event, None)
print(result)
```
