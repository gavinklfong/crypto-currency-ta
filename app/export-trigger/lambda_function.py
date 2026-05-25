import boto3
import json
from datetime import datetime, timedelta, timezone

EVENT_BUS_NAME = "dynamodb-export-bus"

# 🔧 CONFIG: number of past full hours to export
HOUR_WINDOW = 2

# 🔧 CONFIG: symbols to export
SYMBOLS = ["XXBTXUSD", "XETHZUSD"]


events = boto3.client("events")

def lambda_handler(event, context):

    # Extract symbol
    if "detail" in event:
        event_data = event["detail"]
    else:
        event_data = event

    timeframe = event_data.get("timeframe")

    now = datetime.now(timezone.utc)

    # Floor to the current hour (e.g., 05:15 → 05:00)
    current_hour = now.replace(minute=0, second=0, microsecond=0)

    entries = []

    # Loop over the number of hours defined in HOUR_WINDOW
    for i in range(1, HOUR_WINDOW + 1):
        start_hour = current_hour - timedelta(hours=i)
        end_hour = start_hour + timedelta(hours=1)

        start_ts = int(start_hour.timestamp())
        end_ts = int(end_hour.timestamp()) - 1

        for symbol in SYMBOLS:
            detail = {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_ts": start_ts,
                "end_ts": end_ts
            }

            entries.append({
                "Source": "dynamodb.export.scheduler",
                "DetailType": "export-hour",
                "Detail": json.dumps(detail),
                "EventBusName": EVENT_BUS_NAME
            })

    # EventBridge allows max 10 entries per call
    for i in range(0, len(entries), 10):
        events.put_events(Entries=entries[i:i+10])

    return {
        "status": "scheduled",
        "hours_sent": HOUR_WINDOW,
        "symbols": len(SYMBOLS),
        "timeframe": timeframe,
        "events_emitted": len(entries)
    }
