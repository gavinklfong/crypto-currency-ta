# EventBridge Scheduler Configuration

## Overview
This document explains how to pass cryptocurrency symbols from EventBridge scheduled events to Lambda functions without hardcoding them in the Lambda code.

## How It Works

1. **Terraform Variables**: Define `event_input` in the `lambdas` variable to specify what data should be passed to the Lambda
2. **EventBridge Target**: The `aws_cloudwatch_event_target` uses the `input` parameter to inject the JSON event data
3. **Lambda Handler**: Extract the symbols from the event object

## Configuration

### Default Symbols
The symbols are configured in `variables.tf` in the `lambdas` variable:

```hcl
fetch_market_data = {
  function_name = "fetch-market-data"
  zip_path      = "../.package/deployment-fetch-market-data.zip"
  route_key     = "GET /trigger-fetch-market-data"
  schedule      = "rate(1 minute)"
  event_input = jsonencode({
    detail = {
      symbols = ["BTC/USD", "ETH/USD", "XRP/USD"]
    }
  })
}
```

### Customizing Symbols

#### Option 1: Override in terraform.tfvars
Create or edit `terraform.tfvars`:

```hcl
lambdas = {
  fetch_market_data = {
    function_name = "fetch-market-data"
    zip_path      = "../.package/deployment-fetch-market-data.zip"
    route_key     = "GET /trigger-fetch-market-data"
    schedule      = "rate(1 minute)"
    event_input = jsonencode({
      detail = {
        symbols = ["BTC/USD", "ETH/USD", "XRP/USD", "SOL/USD", "ADA/USD"]
      }
    })
  }
  # ... other Lambda configurations
}
```

#### Option 2: Override via Terraform CLI
```bash
terraform apply -var='lambdas={fetch_market_data={function_name="fetch-market-data",zip_path="../.package/deployment-fetch-market-data.zip",route_key="GET /trigger-fetch-market-data",schedule="rate(1 minute)",event_input=jsonencode({detail={symbols=["BTC/USD","ETH/USD"]}})}}'
```

#### Option 3: Create an environment-specific variables file
Create `production.tfvars`:

```hcl
lambdas = {
  fetch_market_data = {
    function_name = "fetch-market-data"
    zip_path      = "../.package/deployment-fetch-market-data.zip"
    route_key     = "GET /trigger-fetch-market-data"
    schedule      = "rate(1 minute)"
    event_input = jsonencode({
      detail = {
        symbols = ["BTC/USD", "ETH/USD", "XRP/USD"]
      }
    })
  }
  aggregate_timeframe = {
    function_name = "aggregate-timeframe"
    zip_path      = "../.package/deployment-aggregate-timeframe.zip"
    route_key     = "GET /aggregate-timeframe"
    schedule      = "rate(1 minute)"
    event_input = jsonencode({
      detail = {
        pairs = ["BTCUSD", "ETHUSD", "XRPUSD"]
      }
    })
  }
}
```

Then apply with:
```bash
terraform apply -var-file="production.tfvars"
```

## Lambda Handler Implementation

The Lambda functions receive the event in the following format:

```json
{
  "detail": {
    "symbols": ["BTC/USD", "ETH/USD"],
    "pairs": ["BTCUSD", "ETHUSD"]
  }
}
```

### Example: fetch-market-data Lambda
```python
def lambda_handler(event, context):
    # Extract symbols from EventBridge event
    if "detail" in event:
        event_data = event["detail"]
    else:
        event_data = event
    
    symbols = event_data.get("symbols", [])
    
    if not symbols:
        logger.error("No symbols specified in event")
        return {"status": "error", "message": "No symbols specified"}
    
    results = {}
    for symbol in symbols:
        # Process each symbol
        market_data = fetch_data_for_symbol(symbol)
        results[symbol] = market_data
    
    return {"status": "success", "processed": len(symbols), "results": results}
```

### Example: aggregate-timeframe Lambda
```python
def lambda_handler(event, context):
    # Extract pairs from EventBridge event
    if "detail" in event:
        event_data = event["detail"]
    else:
        event_data = event
    
    pairs = event_data.get("pairs", [])
    
    if not pairs:
        logger.error("No pairs specified in event")
        return {"status": "error", "message": "No pairs specified"}
    
    results = {}
    for pair in pairs:
        # Process each pair
        aggregated_data = process_pair(pair)
        results[pair] = aggregated_data
    
    return {"status": "success", "pairs_processed": len(pairs), "results": results}
```

## Event Structure by Lambda

### fetch-market-data
```json
{
  "detail": {
    "symbols": ["BTC/USD", "ETH/USD", "XRP/USD"]
  }
}
```

### aggregate-timeframe
```json
{
  "detail": {
    "pairs": ["BTCUSD", "ETHUSD", "XRPUSD"]
  }
}
```

## Deploying Changes

1. Update the symbols in `terraform.tfvars` or `variables.tf`
2. Validate changes:
   ```bash
   terraform plan
   ```
3. Apply changes:
   ```bash
   terraform apply
   ```

The EventBridge rule will automatically be updated with the new event input.

## Benefits

✅ **No Hardcoding**: Symbols are defined in infrastructure-as-code, not in Lambda code  
✅ **Easy to Update**: Change symbols by updating Terraform variables  
✅ **Environment-Specific**: Use different symbols for dev/staging/prod  
✅ **Scalable**: Add or remove symbols without modifying Lambda function  
✅ **Version Control**: All configuration changes tracked in Git  

## Troubleshooting

### Symbols not received by Lambda
1. Check CloudWatch Logs for the Lambda function
2. Verify the `event_input` in the EventBridge target:
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
