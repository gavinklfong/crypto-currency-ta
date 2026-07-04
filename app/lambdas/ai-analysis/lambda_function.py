import os
import boto3
import json
import logging
import decimal
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
bedrock_runtime = boto3.client("bedrock-runtime")

TABLE_NAME = "crypto-currency-ta-market-data"
table = dynamodb.Table(TABLE_NAME)

MODEL_ID = os.environ.get("LLM_MODEL_ID", "google.gemma-3-4b-it")

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
    
    print(f"Fetching data for {pk} from {sk_start} to {sk_end} (last {lookback_minutes} minutes)")

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

    # Your Bedrock client expects the Chat Completions schema
    body = json.dumps({
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1000
    })

    try:
        response = bedrock_runtime.invoke_model(
            body=body,
            modelId=MODEL_ID,
            accept="application/json",
            contentType="application/json"
        )

        response_body = json.loads(response.get("body").read())

        # print(f"Bedrock response: {json.dumps(response_body, indent=2)}")

        # Extract the OpenAI-style response
        return response_body["choices"][0]["message"]["content"]

    except Exception as e:
        log_error("Bedrock invocation failed", error=str(e))
        raise Exception(f"Bedrock invocation failed: {str(e)}")

def send_to_slack(text: str):
    webhook = os.environ["SLACK_WEBHOOK_URL"]
    data = json.dumps({"text": text}).encode("utf-8")

    req = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")

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
    print(f"Fetched {len(data)} records for {symbol} 1m data")

    if not data:
        return {"status": "error", "message": "No 1m data found"}

    # 2. Prepare data for prompt
    # We want to include OHLCV and TAs if they exist in the 1m records 
    # (though TAs are usually on larger timeframes, they might be present if 1m also has them)
    # Or maybe the user meant 'fetch 1m data AND the TAs from the corresponding larger timeframe'
    # But let's stick to the 1m data requested.
    
    data_summary = []
    for item in data:
        # Extracting key values safely
        sk_parts = item.get("SK", "").split("#")
        timestamp_str = sk_parts[-1]
        # Attempt to find the numeric timestamp part, assuming it's the last sequence of digits
        ts_dt = datetime.fromtimestamp(int(timestamp_str.lstrip("TS")), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
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
At the very top of your response, output a Slack‑bold subject line formatted EXACTLY as:
*Market Summary of [pair] time range [start] - [end]*
Replace [pair], [start], and [end] with the actual values provided in the DATA section.

This subject line must appear BEFORE the section titles.
Do not format it as a heading.
Do not add any text before or after it.

Analyze the following 1-minute cryptocurrency market data for the last hour.
Provide a brief technical analysis including trend, momentum, and potential support/resistance levels.

Respond only using the following sections, each formatted EXACTLY as shown:
*Market Summary*
*Technical Indicators*
*Pattern Recognition*
*Bias & Risk*
*Final Outlook*

Do not alter the section titles.
Do not include any text outside these sections.

OUTPUT SPECIFICATION
- Begin your response directly with the analysis.
- Do not acknowledge the request.
- Do not use conversational language.

Formatting Rules (Slack mrkdwn only):

Allowed:
*bold*
_italic_
> block quotes
- bullet lists
`inline code`
```code blocks```

Forbidden (strict):
**double-asterisk bold**
__double-underscore bold__
Any bold using two characters on each side
Any bold that is not Slack-style single-asterisk bold
Markdown headings (#, ##, ###, ####, etc.)
Tables
HTML tags
Markdown links ([text](url))
Images
Any formatting not listed as allowed

Additional strict rules:
- Bullet points MUST NOT contain double-asterisk bold. Use Slack bold only: *RSI*, *MACD*, *EMA20*, etc.
- Indicator names MUST use Slack bold only.
- Section titles MUST be Slack bold exactly as shown.
- Do not add decorative separators or extra blank lines.
- Do not wrap indicator names in any formatting except Slack bold.

DATA:
    {json.dumps(data_summary, indent=2)}
    """

    # print("--- Prompt to Bedrock ---")
    # print(prompt)

    try:
        analysis_result = call_bedrock(prompt)
        send_to_slack(analysis_result)
    except Exception as e:
        log_error("Bedrock analysis failed", error=str(e))
        return {
            "status": "error",
            "message": "Error calling Bedrock"
        }

    # 4. Print result to console (CloudWatch Logs)
    print("--- AI ANALYSIS RESULT ---")
    print(analysis_result)
    print("---------------------------")

    return {
        "status": "success",
        "symbol": symbol,
        "analysis": analysis_result
    }
