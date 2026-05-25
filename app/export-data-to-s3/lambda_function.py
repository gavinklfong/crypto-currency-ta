import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import io
from datetime import datetime, timezone
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = "crypto-currency-ta-market-data"
table = dynamodb.Table(TABLE_NAME)

s3 = boto3.client("s3")
BUCKET_NAME = "crypto-currency-ta-market-data-export"


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
    end_sk   = f"TF#{timeframe}#TS#{end_ts}"

    resp = table.query(
        KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ":pk": pk,
            ":start": start_sk,
            ":end": end_sk
        }
    )

    return resp.get("Items", [])


# ------------------------------------------------------------
# DataFrame preparation
# ------------------------------------------------------------
def prepare_dataframe(items):
    df = pd.DataFrame(items)

    numeric_cols = [
        "open", "high", "low", "close",
        "ha_open", "ha_high", "ha_low", "ha_close",
        "median_price", "typical_price", "vwap",
        "volume", "timeframe_minutes"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    expected_cols = [
        "close", "created_at", "ha_close", "ha_high", "ha_low", "ha_open",
        "high", "low", "median_price", "open", "pair", "ta", "timeframe",
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
        block_hour = (dt.hour // 4) * 4
        block_str = f"{block_hour:02d}"
        date_str = dt.strftime("%Y-%m-%d")
        return f"symbol={symbol}/tf=4h/date={date_str}/block={block_str}/data.parquet"

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
# Main Lambda Handler
# ------------------------------------------------------------
def lambda_handler(event, context):

    detail = event["detail"]
    symbol = detail["symbol"]
    timeframe = detail["timeframe"]
    start_ts = detail["start_ts"]
    end_ts = detail["end_ts"]

    log_info("Starting export", symbol=symbol, timeframe=timeframe, start_ts=start_ts, end_ts=end_ts)

    items = query_dynamodb(symbol, timeframe, start_ts, end_ts)
    if not items:
        log_info("No data found", symbol=symbol, timeframe=timeframe)
        return {"status": "empty"}

    df = prepare_dataframe(items)
    buffer = dataframe_to_parquet_buffer(df)
    s3_key = build_s3_key(symbol, timeframe, start_ts)

    write_to_s3(buffer, s3_key)

    log_info("Export completed", symbol=symbol, timeframe=timeframe, s3_key=s3_key)

    return {"status": "ok", "s3_key": s3_key}
