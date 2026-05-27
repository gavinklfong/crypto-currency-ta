import boto3
import json
from datetime import datetime, timedelta, timezone

EVENT_BUS_NAME = "dynamodb-export-bus"
events = boto3.client("events")


# ------------------------------------------------------------
# Determine how many periods to export per timeframe
# ------------------------------------------------------------
def get_period_count(timeframe: str) -> int:
    if timeframe == "4h":
        return 2        # 2 × 4h blocks
    if timeframe == "1d":
        return 2        # 2 × daily blocks
    if timeframe == "1w":
        return 2        # 2 × weekly blocks
    if timeframe == "1M":
        return 1        # 1 × monthly block
    return 2            # default: 2 hourly periods


# ------------------------------------------------------------
# Compute start/end timestamps for each timeframe period
# ------------------------------------------------------------
def get_period_range(timeframe: str, now: datetime, index: int):
    """
    index = 1 means "previous period"
    index = 2 means "two periods ago"
    """

    if timeframe in ["1m", "5m", "15m", "30m", "1h"]:
        # Hourly periods
        start = (now - timedelta(hours=index)).replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)

    elif timeframe == "4h":
        # 4h blocks: 00, 04, 08, 12, 16, 20
        current_block_hour = (now.hour // 4) * 4
        block_start = now.replace(hour=current_block_hour, minute=0, second=0, microsecond=0)
        start = block_start - timedelta(hours=4 * index)
        end = start + timedelta(hours=4)

    elif timeframe == "1d":
        # Daily periods
        start = (now - timedelta(days=index)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

    elif timeframe == "1w":
        # Weekly periods (ISO week)
        # Find Monday of current week
        monday = now - timedelta(days=now.weekday())
        start = (monday - timedelta(weeks=index)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(weeks=1)

    elif timeframe == "1M":
        # Monthly period (previous month only)
        year = now.year
        month = now.month

        # Move to previous month
        month -= index
        while month <= 0:
            month += 12
            year -= 1

        start = datetime(year, month, 1, tzinfo=timezone.utc)

        # Compute next month
        next_month = month + 1
        next_year = year
        if next_month == 13:
            next_month = 1
            next_year += 1

        end = datetime(next_year, next_month, 1, tzinfo=timezone.utc)

    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    return int(start.timestamp()), int(end.timestamp()) - 1


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
    
    - For 4h, 1d:
      * end_ts = last minute of previous day (23:59:59)
      * start_ts = end_ts - 1 day
    """
    if now is None:
        now = datetime.now(timezone.utc)
    
    if timeframe in ["1m", "5m", "15m", "30m", "1h"]:
        # End at last minute of previous hour
        end = (now - timedelta(hours=1)).replace(minute=59, second=59, microsecond=0)
        # Start 2 hours before end
        start = end - timedelta(hours=2)
    
    elif timeframe == "4h":
        # End at last minute of previous day
        end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
        # Start 1 day before end
        start = end - timedelta(days=1)
    
    elif timeframe == "1d":
        # End at last minute of previous day
        end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
        # Start 1 day before end
        start = end - timedelta(days=1)
    
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    
    return int(start.timestamp()), int(end.timestamp())

# ------------------------------------------------------------
# Main Lambda
# ------------------------------------------------------------
def lambda_handler(event, context):

    # Extract symbol + timeframe
    detail = event.get("detail", event)
    symbol = detail.get("symbol")
    timeframe = detail.get("timeframe")

    now = datetime.now(timezone.utc)
    period_count = get_period_count(timeframe)

    entries = []

    # Generate one event per period
    for i in range(1, period_count + 1):
        start_ts, end_ts = get_period_range(timeframe, now, i)

        event_detail = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_ts": start_ts,
            "end_ts": end_ts
        }

        entries.append({
            "Source": "dynamodb.export.scheduler",
            "DetailType": "export-period",
            "Detail": json.dumps(event_detail),
            "EventBusName": EVENT_BUS_NAME
        })

    # EventBridge batching (10 max)
    for i in range(0, len(entries), 10):
        events.put_events(Entries=entries[i:i+10])

    return {
        "status": "scheduled",
        "symbol": symbol,
        "timeframe": timeframe,
        "periods_sent": period_count,
        "events_emitted": len(entries)
    }
