

import boto3
from botocore.exceptions import ClientError
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple
from decimal import Decimal

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = "crypto-currency-ta-market-data"
table = dynamodb.Table(TABLE_NAME)

# Default symbol if none is provided
LOOKBACK_CANDLES = 10
DEFAULT_SYMBOL = "XBTUSD"  # Bitcoin/USD
DEFAULT_TIMEFRAME = "5m"  # Default aggregation timeframe

# Timeframe configurations (in seconds)
TIMEFRAMES = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
    "1M": 30 * 24 * 60 * 60,  # ~30 days
}

def log_info(message, **kwargs):
    logger.info(f"{message} | {json.dumps(kwargs)}")

def log_error(message, **kwargs):
    logger.error(f"{message} | {json.dumps(kwargs)}")


def to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_decimal(v) for v in obj]
    return obj

def get_candle_timestamp(timestamp: int, timeframe_seconds: int) -> int:
    """Get the bucket timestamp for a given timestamp and timeframe."""
    return (timestamp // timeframe_seconds) * timeframe_seconds

def fetch_1m_candles(pair: str, start_ts: int, end_ts: int) -> List[Dict]:
    """Fetch 1-minute candles from DynamoDB."""
    pk = f"PAIR#{pair}"
    
    resp = table.query(
        KeyConditionExpression="PK = :pk AND SK BETWEEN :sk_start AND :sk_end",
        ExpressionAttributeValues={
            ":pk": pk,
            ":sk_start": f"TF#1m#TS#{start_ts}",
            ":sk_end": f"TF#1m#TS#{end_ts}"
        },
        ScanIndexForward=True,
        ConsistentRead=False
    )
    
    return resp.get("Items", [])

def extract_timestamp_from_sk(sk: str) -> int:
    """Extract integer timestamp from SK format: TF#<tf>#TS#<ts>"""
    parts = sk.split("#")
    if len(parts) >= 4:
        return int(parts[3])
    return None

def aggregate_candles(candles: List[Dict]) -> Dict:
    """Aggregate multiple 1-minute candles into OHLCV + derived metrics."""
    if not candles:
        return None

    # Sort by timestamp to ensure correct open/close
    candles = sorted(candles, key=lambda c: float(c["timestamp"]))

    opens   = [float(c["open"]) for c in candles]
    highs   = [float(c["high"]) for c in candles]
    lows    = [float(c["low"]) for c in candles]
    closes  = [float(c["close"]) for c in candles]
    volumes = [float(c["volume"]) for c in candles]

    # Core OHLCV
    open_price  = opens[0]
    high_price  = max(highs)
    low_price   = min(lows)
    close_price = closes[-1]
    volume_sum  = sum(volumes)

    # Derived metrics
    typical_price = (high_price + low_price + close_price) / 3
    median_price  = (high_price + low_price) / 2

    # VWAP = sum(price * volume) / sum(volume)
    vwap = (
        sum(((h + l + c) / 3) * v for h, l, c, v in zip(highs, lows, closes, volumes))
        / volume_sum
        if volume_sum > 0 else typical_price
    )

    # Heikin-Ashi
    ha_close = (open_price + high_price + low_price + close_price) / 4
    ha_open  = (open_price + close_price) / 2
    ha_high  = max(high_price, ha_open, ha_close)
    ha_low   = min(low_price, ha_open, ha_close)

    return {
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume_sum,
        "typical_price": typical_price,
        "median_price": median_price,
        "vwap": vwap,
        "ha_open": ha_open,
        "ha_high": ha_high,
        "ha_low": ha_low,
        "ha_close": ha_close,
    }

def write_aggregated_candle(pair: str, timeframe: str, timestamp: int, candle_data: Dict):
    pk = f"PAIR#{pair}"
    sk = f"TF#{timeframe}#TS#{timestamp}"

    try:
        candle_data = to_decimal(candle_data)

        table.put_item(
            Item={
                "PK": pk,
                "SK": sk,
                "pair": pair,
                "timeframe": timeframe,
                "timestamp": timestamp,
                "open": candle_data["open"],
                "high": candle_data["high"],
                "low": candle_data["low"],
                "close": candle_data["close"],
                "volume": candle_data["volume"],
                "typical_price": candle_data.get("typical_price"),
                "median_price": candle_data.get("median_price"),
                "vwap": candle_data.get("vwap"),
                "ha_open": candle_data.get("ha_open"),
                "ha_high": candle_data.get("ha_high"),
                "ha_low": candle_data.get("ha_low"),
                "ha_close": candle_data.get("ha_close"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            ConditionExpression="attribute_not_exists(SK)"
        )

        log_info(
            "Aggregated candle inserted",
            pair=pair,
            timeframe=timeframe,
            timestamp=timestamp
        )

    except ClientError as e:
        # Check for ConditionalCheckFailedException
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # Item already exists — skip logging as error
            return

        # Other DynamoDB errors should be logged
        log_error(
            "DynamoDB write failed",
            pair=pair,
            timeframe=timeframe,
            timestamp=timestamp,
            error=str(e)
        )

    except Exception as e:
        # Non-DynamoDB errors
        log_error(
            "Unexpected error writing aggregated candle",
            pair=pair,
            timeframe=timeframe,
            timestamp=timestamp,
            error=str(e)
        )

def process_pair_timeframe(pair: str, timeframe: str, current_time: int):
    """Process aggregation for a specific pair and timeframe."""
    timeframe_seconds = TIMEFRAMES[timeframe]
    
    # Calculate lookback window: last 5 candles + some buffer
    lookback_seconds = timeframe_seconds * (LOOKBACK_CANDLES + 2)
    
    start_ts = current_time - lookback_seconds
    end_ts = current_time
    
    # Fetch 1-minute candles
    candles_1m = fetch_1m_candles(pair, start_ts, end_ts)
    
    log_info(
        "Fetched 1-minute candles",
        pair=pair,
        timeframe=timeframe,
        start_ts=start_ts,
        end_ts=end_ts,
        count=len(candles_1m))

    if not candles_1m:
        log_info(
            "No 1-minute candles found",
            pair=pair,
            timeframe=timeframe,
            start_ts=start_ts,
            end_ts=end_ts
        )
        return 0
    
    # Group candles by aggregation bucket
    buckets = {}
    
    for candle in candles_1m:
        ts = extract_timestamp_from_sk(candle["SK"])
        if ts is None:
            continue
        
        bucket_ts = get_candle_timestamp(ts, timeframe_seconds)
        
        if bucket_ts not in buckets:
            buckets[bucket_ts] = []
        
        buckets[bucket_ts].append(candle)
    
    # Write aggregated candles
    processed_count = 0
    
    log_info(
        "Processing aggregated candles",
        pair=pair,
        timeframe=timeframe,
        buckets_count=len(buckets),
    )

    for bucket_ts in sorted(buckets.keys()):
        candle_group = buckets[bucket_ts]
        
        # Only write complete candles or the most recent incomplete one
        is_current_bucket = (current_time // timeframe_seconds) == (bucket_ts // timeframe_seconds)
        
        # For backfill, we want the last 5 complete candles
        # For the current bucket, we write it anyway
        aggregated = aggregate_candles(candle_group)

        if aggregated:
            write_aggregated_candle(pair, timeframe, bucket_ts, aggregated)
            processed_count += 1
            log_info(
                "Aggregated candle written",
                pair=pair,
                timeframe=timeframe,
                timestamp=bucket_ts,
                candles_in_bucket=len(candle_group)
            )
    
    return processed_count

def lambda_handler(event, context):
    try:
        log_info("Lambda triggered", event=json.dumps(event))

        # Extract symbol
        if "detail" in event:
            event_data = event["detail"]
        else:
            event_data = event

        symbol = event_data.get("symbol", DEFAULT_SYMBOL)
        timeframe = event_data.get("timeframe", DEFAULT_TIMEFRAME)

        if not symbol:
            raise ValueError("No symbol provided in event")

        if not timeframe:
            raise ValueError("No timeframe provided in event")

        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        if timeframe == "1m":
            raise ValueError("1m timeframe cannot be aggregated")

        current_time = int(datetime.now(timezone.utc).timestamp())

        # Process ONLY the requested timeframe
        processed = process_pair_timeframe(symbol, timeframe, current_time)

        return {
            "status": "success",
            "current_time": current_time,
            "symbol_processed": symbol,
            "timeframe_processed": timeframe,
            "candles_written": processed
        }

    except Exception as e:
        log_error("Lambda execution failed", error=str(e), event=event)
        return {
            "status": "error",
            "message": str(e)
        }

