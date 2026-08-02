#!/usr/bin/env python3
"""
CLI script to export quarterly market data from DynamoDB to S3 as Parquet files.

Usage:
    PYTHONPATH=../../layers/common-utils python main.py '{"timeframe":"1m","symbol":"XBTUSD","time_period":"2026_Q1"}'
"""
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import io

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
# Build S3 key based on timeframe
# ------------------------------------------------------------
def build_s3_key(symbol: str, timeframe: str, start_ts: int) -> str:
    """Build S3 key path based on timeframe partitioning."""
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

    raise ValueError(f"Unsupported timeframe: {timeframe}")


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
# Split time period into manageable chunks
# ------------------------------------------------------------
def split_time_period(start_ts: int, end_ts: int, timeframe: str) -> list:
    """
    Split a large time range into smaller chunks for incremental export.

    Args:
        start_ts: Start timestamp
        end_ts: End timestamp
        timeframe: Candle timeframe (determines chunk size)

    Returns:
        List of dicts with 'start_ts' and 'end_ts' for each chunk
    """
    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)

    # Define time unit and interval based on timeframe
    if timeframe in ["1m", "5m", "15m", "30m", "1h"]:
        time_unit = timedelta(hours=1)
    elif timeframe in ["4h", "1d", "1w"]:
        time_unit = timedelta(days=1)
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    time_periods = []
    current_start = start_dt

    while current_start < end_dt:
        current_end = min(current_start + time_unit - timedelta(seconds=1), end_dt)
        time_periods.append(
            {
                "start_ts": int(current_start.timestamp()),
                "end_ts": int(current_end.timestamp()),
            }
        )
        current_start += time_unit

    return time_periods


# ------------------------------------------------------------
# Export a single time period chunk
# ------------------------------------------------------------
def export_chunk(symbol: str, timeframe: str, start_ts: int, end_ts: int) -> dict:
    """
    Export a single time period chunk: query DynamoDB, prepare data, write to S3.

    Returns:
        Dict with status and metadata
    """
    log_info(
        "Exporting chunk",
        symbol=symbol,
        timeframe=timeframe,
        start_ts=datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat(),
        end_ts=datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat(),
    )

    items = query_dynamodb(symbol, timeframe, start_ts, end_ts)

    if not items:
        log_info("No data found for chunk", symbol=symbol, timeframe=timeframe)
        return {"status": "empty", "symbol": symbol, "timeframe": timeframe}

    df = prepare_dataframe(items)
    buffer = dataframe_to_parquet_buffer(df)
    s3_key = build_s3_key(symbol, timeframe, start_ts)
    write_to_s3(buffer, s3_key)

    log_info(
        "Chunk exported",
        symbol=symbol,
        timeframe=timeframe,
        s3_key=s3_key,
        records=len(items),
    )

    return {"status": "ok", "symbol": symbol, "timeframe": timeframe, "s3_key": s3_key, "records": len(items)}


# ------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------
def main():
    """CLI entry point for quarterly market data export."""
    if len(sys.argv) < 2:
        log_error("Missing input JSON argument")
        print("Usage: PYTHONPATH=../../layers/common-utils python main.py '{\"timeframe\":\"1m\",\"symbol\":\"XBTUSD\",\"time_period\":\"2026_Q1\"}'", file=sys.stderr)
        sys.exit(1)

    # Parse JSON input
    try:
        params = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        log_error("Invalid JSON input", error=str(e))
        sys.exit(1)

    # Validate required fields
    timeframe = params.get("timeframe")
    symbol = params.get("symbol")
    time_period = params.get("time_period")

    if not timeframe:
        log_error("Missing required field: timeframe")
        sys.exit(1)

    if not symbol:
        log_error("Missing required field: symbol")
        sys.exit(1)

    if not time_period:
        log_error("Missing required field: time_period")
        sys.exit(1)

    # Validate timeframe
    if timeframe not in SUPPORTED_TIMEFRAMES:
        log_error("Unsupported timeframe", timeframe=timeframe, supported=SUPPORTED_TIMEFRAMES)
        sys.exit(1)

    # Parse quarter time period
    try:
        start_ts, end_ts = parse_quarter(time_period)
    except ValueError as e:
        log_error(str(e))
        sys.exit(1)

    log_info("Starting quarterly export", symbol=symbol, timeframe=timeframe, time_period=time_period)

    # Split into chunks
    chunks = split_time_period(start_ts, end_ts, timeframe)
    total_chunks = len(chunks)

    log_info(f"Will export {total_chunks} chunk(s)", symbol=symbol, timeframe=timeframe)

    # Export each chunk
    ok_count = 0
    empty_count = 0
    failed_chunks = []

    for i, chunk in enumerate(chunks, 1):
        log_info(f"Processing chunk {i}/{total_chunks}")

        try:
            result = export_chunk(symbol, timeframe, chunk["start_ts"], chunk["end_ts"])
            if result["status"] == "ok":
                ok_count += 1
            elif result["status"] == "empty":
                empty_count += 1
        except Exception as e:
            log_error(f"Failed to export chunk {i}", error=str(e))
            failed_chunks.append({"chunk": i, "error": str(e)})

    # Summary
    log_info(
        "Export completed",
        symbol=symbol,
        timeframe=timeframe,
        time_period=time_period,
        total_chunks=total_chunks,
        exported_ok=ok_count,
        empty_chunks=empty_count,
        failed_chunks=len(failed_chunks),
    )

    if failed_chunks:
        log_error("Failed chunks", failed=failed_chunks)
        sys.exit(1)
    else:
        print(f"Successfully exported {ok_count} chunk(s), {empty_count} empty chunk(s) for {symbol} {timeframe} {time_period}")


if __name__ == "__main__":
    main()
