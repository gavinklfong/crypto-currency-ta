import json
import requests
import boto3
from datetime import datetime
from itertools import islice

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
DYNAMODB_TABLE_NAME = "crypto-currency-ta-market-data"

dynamodb_client = boto3.client("dynamodb", region_name="us-east-2")


def chunked(iterable, size=25):
    """Yield successive chunks of size N from iterable."""
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            break
        yield batch


def write_ohlc_to_dynamodb(pair, timeframe_minutes, ohlc_data):
    """Bulk write OHLC data to DynamoDB using batch_write_item."""
    
    items = []
    now_ts = int(datetime.now().timestamp())
    timeframe_str = f"{timeframe_minutes}m"

    # Build all items first
    for candle in ohlc_data:
        timestamp = int(candle[0])
        open_price = float(candle[1])
        high_price = float(candle[2])
        low_price = float(candle[3])
        close_price = float(candle[4])
        vwap = float(candle[5])
        volume = float(candle[6])

        pk = f"PAIR#{pair}"
        sk = f"TF#{timeframe_str}#TS#{timestamp}"

        item = {
            "PK": {"S": pk},
            "SK": {"S": sk},
            "pair": {"S": pair},
            "timeframe_minutes": {"N": str(timeframe_minutes)},
            "timestamp": {"N": str(timestamp)},
            "open": {"N": str(open_price)},
            "high": {"N": str(high_price)},
            "low": {"N": str(low_price)},
            "close": {"N": str(close_price)},
            "vwap": {"N": str(vwap)},
            "volume": {"N": str(volume)},
            "created_at": {"N": str(now_ts)},
        }

        items.append({"PutRequest": {"Item": item}})

    # Batch write in chunks of 25
    total_written = 0

    for batch in chunked(items, 25):
        request_items = {DYNAMODB_TABLE_NAME: batch}

        while True:
            response = dynamodb_client.batch_write_item(RequestItems=request_items)

            # Retry unprocessed items
            unprocessed = response.get("UnprocessedItems", {})
            if unprocessed and DYNAMODB_TABLE_NAME in unprocessed:
                request_items = unprocessed
            else:
                break

        total_written += len(batch)

    return total_written

def lambda_handler(event, context):
    params = {
        "pair": "XBTUSD",  # Bitcoin/USD
        "interval": 1,  # 1-minute candles (triggered every 1 minute)
    }

    try:
        response = requests.get(KRAKEN_OHLC_URL, params=params, timeout=10)
        data = response.json()

        if data.get("error"):
            return {
                "statusCode": 500,
                "body": json.dumps({"error": data["error"]}),
            }

        # Kraken returns a dict with the pair name as the key
        pair_key = list(data["result"].keys())[0]
        ohlc = data["result"][pair_key]

        # Write OHLC data to DynamoDB
        records_written = write_ohlc_to_dynamodb(pair_key, params["interval"], ohlc)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "pair": pair_key,
                    "count": len(ohlc),
                    "records_written_to_dynamodb": records_written,
                    "ohlc": ohlc,
                }
            ),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }