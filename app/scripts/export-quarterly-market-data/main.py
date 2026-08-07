#!/usr/bin/env python3
"""
CLI script to export quarterly market data from DynamoDB to S3 as Parquet files.

Each timeframe is exported as a separate Parquet file per symbol per quarter.

Usage (local):
    PYTHONPATH=../../layers/common-utils python main.py '{"symbol":"XBTUSD","time_period":"2026_Q1"}' --job-id JOB_ID

Usage (via EventBridge / launch-ec2-job):
    Send an event like the following to trigger the job on an EC2 worker:

    {
      "source": "my.crypto.ta.app",
      "detail-type": "start-long-running-job",
      "detail": {
        "job_script_name": "export-quarterly-market-data",
        "job_payload": "{\"symbol\":\"XBTUSD\",\"time_period\":\"2026_Q1\"}",
        "instance_type": "large"
      }
    }

S3 key format: <symbol>/<yyyy-QQ>/tf=<timeframe>/data.parquet
(e.g., XBTUSD/2026-Q1/tf=5m/data.parquet)
"""
import sys
import json
import logging
import argparse
from datetime import datetime, timezone
from typing import Tuple

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import io

from common.job_status_client import JobStatusClient, HeartbeatThread

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# DynamoDB connection
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = "crypto-currency-ta-market-data"
table = dynamodb.Table(TABLE_NAME)

# S3 connection
s3 = boto3.client("s3")
BUCKET_NAME = "crypto-currency-ta-exports"

# Quarter mappings: (start_month, end_day_month, end_day)
QUARTER_INFO = {
    "Q1": (1, 3, 31),   # Jan 1 - Mar 31
    "Q2": (4, 6, 30),   # Apr 1 - Jun 30
    "Q3": (7, 9, 30),   # Jul 1 - Sep 30
    "Q4": (10, 12, 31), # Oct 1 - Dec 31
}

# Supported timeframes
SUPPORTED_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]


# ------------------------------------------------------------
# Logging helpers
# ------------------------------------------------------------
def log_info(message, **kwargs):
    logger.info(f"{message} | {json.dumps(kwargs)}")


def log_error(message, **kwargs):
    logger.error(f"{message} | {json.dumps(kwargs)}")


# ------------------------------------------------------------
# Time Period Parsing
# ------------------------------------------------------------
def parse_quarter(time_period: str) -> Tuple[int, int]:
    """
    Parse a quarterly time period string (e.g., "2026_Q1") into
    start and end Unix timestamps.

    Args:
        time_period: String in format "<year>_Q<quarter>", e.g., "2026_Q1"

    Returns:
        Tuple of (start_ts, end_ts) as Unix timestamps

    Raises:
        ValueError: If the format is invalid or quarter number is out of range
    """
    time_period = time_period.strip()

    if "_" not in time_period:
        raise ValueError(f"Invalid time period format: '{time_period}'. Expected format: YYYY_QQ (e.g., 2026_Q1)")

    parts = time_period.rsplit("_", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid time period format: '{time_period}'. Expected format: YYYY_QQ (e.g., 2026_Q1)")

    year_str, quarter_str = parts

    # Validate year
    try:
        year = int(year_str)
    except ValueError:
        raise ValueError(f"Invalid year in time period: '{year_str}'. Expected a 4-digit year.")

    if len(year_str) != 4:
        raise ValueError(f"Year must be 4 digits: '{year_str}'")

    # Validate quarter
    if quarter_str not in QUARTER_INFO:
        raise ValueError(f"Invalid quarter: '{quarter_str}'. Expected Q1, Q2, Q3, or Q4.")

    start_month, end_month, end_day = QUARTER_INFO[quarter_str]

    # Calculate start timestamp (first second of first day of quarter)
    start_dt = datetime(year, start_month, 1, 0, 0, 0, tzinfo=timezone.utc)
    start_ts = int(start_dt.timestamp())

    # Calculate end timestamp (last second of last day of quarter)
    end_dt = datetime(year, end_month, end_day, 23, 59, 59, tzinfo=timezone.utc)
    end_ts = int(end_dt.timestamp())

    log_info("Parsed quarter", time_period=time_period, year=year, quarter=quarter_str,
             start_dt=start_dt.isoformat(), end_dt=datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat())

    return start_ts, end_ts


# ------------------------------------------------------------
# DynamoDB Query
# ------------------------------------------------------------
def query_dynamodb(symbol: str, timeframe: str, start_ts: int, end_ts: int) -> list:
    """Query DynamoDB for market data within a time range."""
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
            last_evaluated_key=last_evaluated_key,
        )

        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")

        if not last_evaluated_key:
            break

    return items


def perform_query(pk: str, start_sk: str, end_sk: str, last_evaluated_key=None) -> dict:
    """Execute a single DynamoDB query page."""
    query_params = {
        "KeyConditionExpression": "PK = :pk AND SK BETWEEN :start AND :end",
        "ExpressionAttributeValues": {
            ":pk": pk,
            ":start": start_sk,
            ":end": end_sk,
        },
    }

    if last_evaluated_key:
        query_params["ExclusiveStartKey"] = last_evaluated_key

    return table.query(**query_params)


# ------------------------------------------------------------
# DataFrame preparation
# ------------------------------------------------------------
def prepare_dataframe(items: list) -> pd.DataFrame:
    """Convert DynamoDB items to a pandas DataFrame with numeric coercion."""
    df = pd.DataFrame(items)

    numeric_cols = [
        "open", "high", "low", "close",
        "ha_open", "ha_high", "ha_low", "ha_close",
        "median_price", "typical_price", "vwap",
        "volume", "timeframe_minutes",
        "ta_rsi14", "ta_ema20",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    expected_cols = [
        "close", "created_at", "ha_close", "ha_high", "ha_low", "ha_open",
        "high", "low", "median_price", "open", "pair", "ta_rsi14",
        "ta_macd", "ta_ema20", "updated_at", "timeframe",
        "timeframe_minutes", "timestamp", "typical_price", "volume", "vwap",
    ]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    return df


# ------------------------------------------------------------
# Convert DataFrame → Parquet buffer
# ------------------------------------------------------------
def dataframe_to_parquet_buffer(df: pd.DataFrame) -> io.BytesIO:
    """Convert a pandas DataFrame to a Parquet buffer."""
    table_pa = pa.Table.from_pandas(df)
    buffer = io.BytesIO()
    pq.write_table(table_pa, buffer)
    buffer.seek(0)
    return buffer


# ------------------------------------------------------------
# Build S3 key: <symbol>/<yyyy-QQ>/tf=<timeframe>/data.parquet
# ------------------------------------------------------------
def build_s3_key(symbol: str, time_period: str, timeframe: str) -> str:
    """Build S3 key for per-timeframe quarterly export.

    Args:
        symbol: Market symbol (e.g., XBTUSD)
        time_period: Quarter string (e.g., 2026_Q1)
        timeframe: Timeframe identifier (e.g., 5m, 1h)

    Returns:
        S3 key path like XBTUSD/2026-Q1/tf=5m/data.parquet
    """
    time_period = time_period.strip()
    year_str, quarter_str = time_period.rsplit("_", 1)
    return f"{symbol}/{year_str}-{quarter_str}/tf={timeframe}/data.parquet"


# ------------------------------------------------------------
# Write Parquet buffer to S3
# ------------------------------------------------------------
def write_to_s3(buffer: io.BytesIO, s3_key: str) -> None:
    """Write Parquet buffer to S3."""
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=buffer.getvalue(),
    )


# ------------------------------------------------------------
# Get all supported timeframes
# ------------------------------------------------------------
def get_all_timeframes() -> list:
    """Return list of all supported timeframes."""
    return SUPPORTED_TIMEFRAMES


# ------------------------------------------------------------
# Export all timeframes for a symbol into separate Parquet files
# ------------------------------------------------------------
def export_quarter(symbol: str, time_period: str, start_ts: int, end_ts: int) -> dict:
    """
    Query DynamoDB for each timeframe, write a separate Parquet file per timeframe.

    Args:
        symbol: Market symbol (e.g., XBTUSD)
        time_period: Quarter string (e.g., 2026_Q1)
        start_ts: Quarter start timestamp
        end_ts: Quarter end timestamp

    Returns:
        Dict with status, metadata, and per-timeframe details
    """
    timeframes = get_all_timeframes()
    all_records = 0
    timeframe_details = {}

    for timeframe in timeframes:
        log_info("Querying timeframe", symbol=symbol, timeframe=timeframe)
        items = query_dynamodb(symbol, timeframe, start_ts, end_ts)
        if not items:
            log_info("No data for timeframe", symbol=symbol, timeframe=timeframe)
            continue

        df = prepare_dataframe(items)
        buffer = dataframe_to_parquet_buffer(df)
        s3_key = build_s3_key(symbol, time_period, timeframe)
        write_to_s3(buffer, s3_key)

        all_records += len(items)
        timeframe_details[timeframe] = {
            "records": len(items),
            "s3_key": s3_key,
        }
        log_info(
            "Timeframe exported",
            symbol=symbol,
            timeframe=timeframe,
            records=len(items),
            s3_key=s3_key,
        )

    if not timeframe_details:
        log_info("No data found for any timeframe", symbol=symbol, time_period=time_period)
        return {
            "status": "empty",
            "symbol": symbol,
            "time_period": time_period,
            "total_records": 0,
            "timeframes_exported": 0,
        }

    log_info(
        "Quarter exported",
        symbol=symbol,
        time_period=time_period,
        total_records=all_records,
        timeframe_details=timeframe_details,
    )

    return {
        "status": "ok",
        "symbol": symbol,
        "time_period": time_period,
        "total_records": all_records,
        "timeframes_exported": len(timeframe_details),
        "timeframe_details": timeframe_details,
    }


# ------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------
def main():
    """CLI entry point for quarterly market data export."""
    parser = argparse.ArgumentParser(description="Export quarterly market data from DynamoDB to S3")
    parser.add_argument("params", type=str, help="JSON string with 'symbol' and 'time_period' fields")
    parser.add_argument("--job-id", type=str, default=None, help="Job ID for heartbeat tracking")

    # Parse args (the JSON params must come first)
    args, remaining = parser.parse_known_args()

    job_id = args.job_id

    # Parse JSON input
    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as e:
        log_error("Invalid JSON input", error=str(e))
        sys.exit(1)

    # Validate required fields
    symbol = params.get("symbol")
    time_period = params.get("time_period")

    if not symbol:
        log_error("Missing required field: symbol")
        sys.exit(1)

    if not time_period:
        log_error("Missing required field: time_period")
        sys.exit(1)

    # Parse quarter time period
    try:
        start_ts, end_ts = parse_quarter(time_period)
    except ValueError as e:
        log_error(str(e))
        sys.exit(1)

    log_info("Starting quarterly export", symbol=symbol, time_period=time_period)

    client = JobStatusClient()

    try:
        # Start the heartbeat thread
        heartbeat_thread = HeartbeatThread(client, job_id, interval=30)
        heartbeat_thread.start()

        try:
            # Export all timeframes into a single file
            result = export_quarter(symbol, time_period, start_ts, end_ts)
        finally:
            # Ensure heartbeat thread is stopped even if export fails or is interrupted
            heartbeat_thread.stop()
            heartbeat_thread.join()

        if result["status"] == "empty":
            print(f"No data found for {symbol} {time_period}")
        else:
            print(
                f"Successfully exported {result['total_records']} records for {symbol} {time_period} "
                f"({result['timeframes_exported']} timeframes)"
            )
            for tf, details in result["timeframe_details"].items():
                print(f"  tf={tf}: {details['records']} records -> {details['s3_key']}")

    except Exception as e:
        log_error("Export failed", symbol=symbol, time_period=time_period, error=str(e))
        try:
            if job_id:
                client.fail_job(job_id, str(e))
        except Exception as client_err:
            log_error("Failed to report job failure", error=str(client_err))
        sys.exit(1)


if __name__ == "__main__":
    main()
