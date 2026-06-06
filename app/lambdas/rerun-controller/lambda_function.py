import json
from datetime import datetime, timedelta
from itertools import islice
import logging
import os
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize the EventBridge client
events = boto3.client("events")

DEFAULT_SYMBOLS = ["XXBTZUSD", "XETHZUSD"]
TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

def log_info(message, **kwargs):
    logger.info(f"{message} | {json.dumps(kwargs)}")

def log_error(message, **kwargs):
    logger.error(f"{message} | {json.dumps(kwargs)}")

def validateInput(target, symbol, timeframe, start_date, end_date):
    if symbol is not None and not isinstance(symbol, str):
        raise ValueError("Symbol must be a string")

    if timeframe is not None and timeframe not in TIMEFRAMES:
        raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of {TIMEFRAMES}")

    if start_date is not None:
        try:
            datetime.fromisoformat(start_date)
        except ValueError:
            raise ValueError("start_date must be in ISO format (YYYY-MM-DD)")

    if end_date is not None:
        try:
            datetime.fromisoformat(end_date)
        except ValueError:
            raise ValueError("end_date must be in ISO format (YYYY-MM-DD)")
        
    if (start_date is not None and end_date is not None) and start_date > end_date:
        raise ValueError("start_date cannot be after end_date")

def split_date_range_into_chunks(start_date_str, end_date_str, chunk_size_days=1):
    start_date = datetime.fromisoformat(start_date_str).replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = datetime.fromisoformat(end_date_str).replace(hour=23, minute=59, second=59, microsecond=0)

    chunks = []
    current_start = start_date

    while current_start < end_date:
        current_end = current_start.replace(hour=23, minute=59, second=59, microsecond=0)
        chunks.append((current_start, current_end))
        current_start = current_start + timedelta(days=chunk_size_days)

    return chunks

def process_symbol_timeframe(target, symbol, timeframe, start_date, end_date):
    log_info("Processing symbol", target=target, symbol=symbol, timeframe=timeframe)
    chunks = split_date_range_into_chunks(start_date, end_date)
    for chunk_start, chunk_end in chunks:
        send_event(target, symbol, timeframe, start_date, end_date, chunk_start, chunk_end)

def send_event(target, symbol, timeframe, start_date, end_date, start_ts, end_ts):
    log_info("Sending event for chunk", target=target, symbol=symbol, 
             timeframe=timeframe, 
             chunk_start=start_ts.isoformat(), chunk_end=end_ts.isoformat())
    events.put_events(
        Entries=[{
            "Source": "backfill.controller",
            "DetailType": "backfill.request",
            "Detail": json.dumps({
                "target": target,
                "symbol": symbol,
                "timeframe": timeframe,
                "start_ts": start_ts.timestamp(),
                "end_ts": end_ts.timestamp(),
                "message_group_id": f"{symbol}#{timeframe}",
                "message_dedupe_id": f"{start_date}-{end_date}"
            })
        }]
    )


def lambda_handler(event, context):

    log_info("Lambda triggered", event=json.dumps(event))
    
    # Extract symbols from event (either from detail or directly)
    if "detail" in event:
        # EventBridge format - require symbols in detail
        event_data = event["detail"]
    else:
        # Direct format - try to get symbols, fall back to defaults
        event_data = event

    target = event_data.get("target")
    symbol = event_data.get("symbol")
    timeframe = event_data.get("timeframe")
    start_date = event_data.get("start_date")
    end_date = event_data.get("end_date")

    try:
        validateInput(target, symbol, timeframe, start_date, end_date)

        symbols = [symbol] if symbol else DEFAULT_SYMBOLS
        timeframes = [timeframe] if timeframe else TIMEFRAMES

        # for each symbol, split date range of start date to end date into 1 day chunks, and send a message to EventBridge for each chunk
        for symbol in symbols:
            for timeframe in timeframes:
                process_symbol_timeframe(target, symbol, timeframe, start_date, end_date)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "target": target,
                    "symbols": symbols,
                    "timeframes": timeframes,
                    "start_date": start_date,
                    "end_date": end_date,
                    "count": len(symbols) * len(timeframes),
                }
            ),
        }

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "target": target,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start_date": start_date,
                    "end_date": end_date,
                    "error": str(e)
                }
            ),
        }