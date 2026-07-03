import boto3
import json
import logging
import decimal
from datetime import datetime, timezone, timedelta
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
bedrock_runtime = boto3.client("bedrock-runtime")

TABLE_NAME = "crypto-currency-ta-market-data"
table = dynamodb.Table(TABLE_NAME)

def log_info(message, **kwargs):
    logger.info(f"{message} | {json.dumps(kwargs)}")

def log_error(message, **kwargs):
    logger.error(f"{message} | {json.dumps(kwargs)}")

def D(x):
    return Decimal(str(x)) if x is not None else None

def fetch_data(pair, timeframe, lookback_minutes=60):
    """Fetch 1-minute market data and TAs for the last N minutes."""
    end_ts = int(datetime.now(timezone.utc).timestamp())
    start_ts = end_ts - (lookback_minutes * 60)
    
    pk = f"PAIR#{pair}"
    sk_start = f"TF#{timeframe}#TS#{start_ts}"
    sk_end = f"TF#{timeframe}#TS#{end_ts}"
    
    query_params = {
        "KeyConditionExpression": "PK = :pk AND SK BETWEEN :sk_start AND :sk_end",
        "ExpressionAttributeValues": {
            ":pk": pk,
            ":sk_start": sk_start,
            ":sk_end": sk_end
        },
        "ScanIndexForward": True
    }
    
    response = table.query(**query_params)
    items = response.get("Items", [])
    
    # Sort by timestamp to be sure
    items.sort(key=lambda x: int(x["SK"].split("#")[-1]))
    return items

def call_bedrock(prompt):
    """Call AWS Bedrock with the prompt."""
    model_id = "anthropic.claude-3-haiku-20240307-v1:0" # Using Haiku for speed/cost
    
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }
        ]
    })

    try:
        response = bedrock_runtime.invoke_model(
            body=body,
            modelId=model_id,
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response.get("body").read())
        return response_body["content"][0]["text"]
    except Exception as e:
        log_error("Bedrock invocation failed", error=str(e))
        return f"Error calling Bedrock: {str(e)}"

def lambda_handler(event, context):
    log_info("AI Analysis Lambda triggered", event=json.dumps(event))
    
    # Handle different event sources
    event_data = {}
    if "Records" in event:
        event_data = json.loads(event["Records"][0]["body"])
    elif "detail" in event:
        event_data = event["detail"]
    else:
        event_data = event

    symbol = event_data.get("symbol")
    timeframe = event_data.get("timeframe", "1m") # We need 1m data

    if not symbol:
        return {"status": "error", "message": "No symbol provided"}

    # 1. Fetch 1-minute data
    # Note: The user asked for 'last 1 hour 1-minute market data and TAs'
    # So we query the 1m timeframe
    data = fetch_data(symbol, "1m", lookback_minutes=60)
    
    if not data:
        return {"status": "error", "message": f"No 1m data found for {symbol}"}

    # 2. Prepare data for prompt
    # We want to include OHLCV and TAs if they exist in the 1m records 
    # (though TAs are usually on larger timeframes, they might be present if 1m also has them)
    # Or maybe the user meant 'fetch 1m data AND the TAs from the corresponding larger timeframe'
    # But let's stick to the 1m data requested.
    
    data_summary = []
    for item in data:
        # Extracting key values safely
        ts = item.get("SK", "").split("#")[-1]
        ts_dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        row = {
            "time": ts_dt,
            "open": float(item.get("open", 0)),
            "high": float(item.get("high", 0)),
            "low": float(item.get("low", 0)),
            "close": float(item.get("close", 0)),
            "volume": float(item.get("volume", 0)),
        }
        
        # Include TAs if present in the 1m records (e.g. if they were calculated for 1m)
        if "ta_rsi14" in item: row["rsi"] = float(item["ta_rsi14"])
        if "ta_ema20" in item: row["ema20"] = float(item["ta_ema20"])
        if "ta_macd" in item:
            macd = item["ta_macd"]
            row["macd_line"] = float(macd.get("line", 0))
            row["macd_signal"] = float(macd.get("signal", 0))
            row["macd_hist"] = float(macd.get("histogram", 0))
            
        data_summary.append(row)

    prompt = f"""
    Analyze the following 1-minute cryptocurrency market data for {symbol} for the last hour.
    Provide a brief technical analysis including trend, momentum, and potential support/resistance levels.

    Data:
    {json.dumps(data_summary, indent=2)}
    """

    # 3. Call Bedrock
    analysis_result = call_bedrock(prompt)

    # 4. Print result to console (CloudWatch Logs)
    print("--- AI ANALYSIS RESULT ---")
    print(analysis_result)
    print("---------------------------")

    return {
        "status": "success",
        "symbol": symbol,
        "analysis": analysis_result
    }
