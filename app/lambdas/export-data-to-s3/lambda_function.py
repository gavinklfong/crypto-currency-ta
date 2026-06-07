import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import io
from datetime import datetime, timezone, timedelta
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = "crypto-currency-ta-market-data"
table = dynamodb.Table(TABLE_NAME)

s3 = boto3.client("s3")
BUCKET_NAME = "crypto-currency-ta-exports"


# ------------------------------------------------------------
# Logging helpers
# ------------------------------------------------------------
def log_info(message, **kwargs):
    logger.info(f"{message} | {json.dumps(kwargs)}")

def log_error(message, **kwargs):
    logger.error(f"{message} | {json.dumps(kwargs)}")


# ------------------------------------------------------------
# DynamoDB Query
# ------------------------------------------------------------
def query_dynamodb(symbol, timeframe, start_ts, end_ts):
    pk = f"PAIR#{symbol}"
    start_sk = f"TF#{timeframe}#TS#{start_ts}"
    end_sk = f"TF#{timeframe}#TS#{end_ts}"
    
    items = []
    last_evaluated_key = None
    
    while True:
        response = perform_query(
            pk=pk,
            start_sk=start_sk,
            end_sk=end_sk,
            last_evaluated_key=last_evaluated_key
        )
        
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        
        if not last_evaluated_key:
            break
    
    return items

def perform_query(pk, start_sk, end_sk, last_evaluated_key=None):
    query_params = {
        "KeyConditionExpression": "PK = :pk AND SK BETWEEN :start AND :end",
        "ExpressionAttributeValues": {
            ":pk": pk,
            ":start": start_sk,
            ":end": end_sk
        }
    }
    
    if last_evaluated_key:
        query_params["ExclusiveStartKey"] = last_evaluated_key
    
    return table.query(**query_params)

# ------------------------------------------------------------
# DataFrame preparation
# ------------------------------------------------------------
def prepare_dataframe(items):
    df = pd.DataFrame(items)

    numeric_cols = [
        "open", "high", "low", "close",
        "ha_open", "ha_high", "ha_low", "ha_close",
        "median_price", "typical_price", "vwap",
        "volume", "timeframe_minutes",
        "ta_rsi14", "ta_ema20"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    expected_cols = [
        "close", "created_at", "ha_close", "ha_high", "ha_low", "ha_open",
        "high", "low", "median_price", "open", "pair", "ta_rsi14", "ta_macd", "ta_ema20", "updated_at", "timeframe",
        "timeframe_minutes", "timestamp", "typical_price", "volume", "vwap"
    ]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    return df


# ------------------------------------------------------------
# Convert DataFrame → Parquet buffer
# ------------------------------------------------------------
def dataframe_to_parquet_buffer(df):
    table_pa = pa.Table.from_pandas(df)
    buffer = io.BytesIO()
    pq.write_table(table_pa, buffer)
    buffer.seek(0)
    return buffer


# ------------------------------------------------------------
# Build S3 key based on timeframe
# ------------------------------------------------------------
def build_s3_key(symbol, timeframe, start_ts):
    dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)

    if timeframe in ["1m", "5m", "15m", "30m", "1h"]:
        date_str = dt.strftime("%Y-%m-%d")
        hour_str = dt.strftime("%H")
        return f"symbol={symbol}/tf={timeframe}/date={date_str}/hour={hour_str}/data.parquet"

    if timeframe == "4h":
        date_str = dt.strftime("%Y-%m-%d")
        return f"symbol={symbol}/tf=4h/date={date_str}/data.parquet"

    if timeframe == "1d":
        date_str = dt.strftime("%Y-%m-%d")
        return f"symbol={symbol}/tf=1d/date={date_str}/data.parquet"

    if timeframe == "1w":
        year, week, _ = dt.isocalendar()
        week_str = f"{year}-W{week:02d}"
        return f"symbol={symbol}/tf=1w/week={week_str}/data.parquet"

    if timeframe == "1M":
        month_str = dt.strftime("%Y-%m")
        return f"symbol={symbol}/tf=1M/month={month_str}/data.parquet"

    raise ValueError(f"Unsupported timeframe: {timeframe}")


# ------------------------------------------------------------
# Write Parquet buffer to S3
# ------------------------------------------------------------
def write_to_s3(buffer, s3_key):
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=buffer.getvalue()
    )


# ------------------------------------------------------------
# Generate time range for a given timeframe
# Returns (start_ts, end_ts) as Unix timestamps
# ------------------------------------------------------------
def get_timeframe_range(timeframe: str, now: datetime = None) -> tuple:
    """
    Generate start and end timestamps for a given timeframe.
    
    Args:
        timeframe: One of "1m", "5m", "15m", "30m", "1h", "4h", "1d"
        now: Reference datetime (defaults to current UTC time)
    
    Returns:
        Tuple of (start_ts, end_ts) as Unix timestamps (integers)
    
    Logic:
    - For 1m, 5m, 15m, 30m, 1h:
      * end_ts = last minute of previous hour (HH:59:59)
      * start_ts = end_ts - 2 hours
      For example, if now is 2024-05-25 14:30:00 UTC:
        - end_ts = 2024-05-25 13:59:59 UTC
        - start_ts = 2024-05-25 11:00:00 UTC
    
    - For 4h:
      * end_ts = last minute of previous day (23:59:59)
      * start_ts = start of that day (00:00:00)
        For example, if now is 2024-05-25 14:30:00 UTC:
        - end_ts = 2024-05-24 23:59:59 UTC
        - start_ts = 2024-05-24 00:00:00 UTC
      
    - For 1d:
      * end_ts = last minute of previous day (23:59:59)
      * start_ts = start of end_ts - 1 day (00:00:00)
        For example, if now is 2024-05-25 14:30:00 UTC:
        - end_ts = 2024-05-24 23:59:59 UTC
        - start_ts = 2024-05-23 00:00:00 UTC
    """
    if now is None:
        now = datetime.now(timezone.utc)
        print(f"Current UTC time: {now.isoformat()}")
    
    if timeframe in ["1m", "5m", "15m", "30m", "1h"]:
        # End at last minute of previous hour
        end = (now - timedelta(hours=1)).replace(minute=59, second=59, microsecond=0)
        # Start 2 hours before end
        start = (end - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    
    elif timeframe == "4h":
        # End at last minute of previous day
        end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
        # Start 1 day before end
        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    
    elif timeframe == "1d":
        # End at last minute of previous day
        end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
        # Start 1 day before end
        start = (end - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    
    return int(start.timestamp()), int(end.timestamp())


def split_time_period(start_ts, end_ts, timeframe):
    # Convert timestamps to datetime objects
    start_dt = datetime.fromtimestamp(start_ts)
    end_dt = datetime.fromtimestamp(end_ts)
    
    # Define time unit and interval based on timeframe
    if timeframe in ['1m', '5m', '15m', '30m', '1h']:
        # For 1-hour, 5-min, 15-min, and 30-min intervals, use hourly intervals
        time_unit = timedelta(hours=1)
    elif timeframe == '4h':
        # For 4-hour intervals, use daily intervals
        time_unit = timedelta(days=1)
    elif timeframe in ['1d']:
        # For daily intervals, use daily intervals
        time_unit = timedelta(days=1)
    else:
        raise ValueError("Unsupported timeframe")
    
    # Initialize result list
    time_periods = []
    
    # Generate time periods
    current_start = start_dt
    while current_start < end_dt:
        current_end = min(current_start + time_unit - timedelta(seconds=1), end_dt)
        time_periods.append({
            'start_ts': int(current_start.timestamp()),
            'end_ts': int(current_end.timestamp())
        })
        current_start += time_unit
    
    return time_periods

def export_data_to_s3(symbol, timeframe, start_ts, end_ts):
    log_info("Starting export time period", symbol=symbol, timeframe=timeframe, 
             start_ts=datetime.fromtimestamp(start_ts).isoformat(), 
             end_ts=datetime.fromtimestamp(end_ts).isoformat())

    items = query_dynamodb(symbol, timeframe, start_ts, end_ts)
    if not items:
        log_info("No data found", symbol=symbol, timeframe=timeframe)
        return {"status": "empty"}

    df = prepare_dataframe(items)
    buffer = dataframe_to_parquet_buffer(df)
    s3_key = build_s3_key(symbol, timeframe, start_ts)

    write_to_s3(buffer, s3_key)

    log_info("Export completed", symbol=symbol, timeframe=timeframe, s3_key=s3_key)

# ------------------------------------------------------------
# Main Lambda Handler
# ------------------------------------------------------------
def lambda_handler(event, context):

    log_info("Lambda triggered", event=json.dumps(event))

    # Extract event data from different event sources
    event_data = {}
    
    # SQS event
    if "Records" in event:
        record = event["Records"][0]
        body = json.loads(record["body"])
        event_data = body
    # EventBridge event
    elif "detail" in event:
        event_data = event["detail"]
    # Direct invocation
    else:
        event_data = event

    # Extract parameters
    symbol = event_data.get("symbol")
    timeframe = event_data.get("timeframe")
    
    # Handle both string and numeric types for timestamps
    start_ts_raw = event_data.get("start_ts")
    end_ts_raw = event_data.get("end_ts")
    
    start_ts = None
    end_ts = None
    
    if start_ts_raw is not None:
        start_ts = int(float(start_ts_raw))
    
    if end_ts_raw is not None:
        end_ts = int(float(end_ts_raw))

    if not symbol:
        raise ValueError("No symbol provided in event")
    if not timeframe:
        raise ValueError("No timeframe provided in event")

    # Use provided timestamps or generate from timeframe
    if start_ts is None or end_ts is None:
        start_ts, end_ts = get_timeframe_range(timeframe)

    log_info("Starting export", symbol=symbol, timeframe=timeframe, 
             start_ts=datetime.fromtimestamp(start_ts).isoformat(), 
             end_ts=datetime.fromtimestamp(end_ts).isoformat())

    split_time_periods = split_time_period(start_ts, end_ts, timeframe)

    for period in split_time_periods:
        export_data_to_s3(symbol, timeframe, period['start_ts'], period['end_ts'])

    return {"status": "ok", "symbol": symbol, "timeframe": timeframe, 
            "periods_exported": len(split_time_periods)}
