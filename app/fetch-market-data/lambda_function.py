import json
import requests
import boto3
from datetime import datetime
from itertools import islice


SYMBOL = "XBTUSD"  # Bitcoin/USD       
CANDLE_INTERVAL = 1  # 1-minute candles (triggered every 1 minute)
KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
DYNAMODB_TABLE_NAME = "crypto-currency-ta-market-data"

events = boto3.client("events")
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
    now_ts = int(datetime.now().timestamp())
    timeframe_str = f"{timeframe_minutes}m"
    written = 0

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

        try:
            dynamodb_client.put_item(
                TableName=DYNAMODB_TABLE_NAME,
                Item=item,
                ConditionExpression="attribute_not_exists(PK)"
            )
            written += 1

        except dynamodb_client.exceptions.ConditionalCheckFailedException:
            # Item already exists → skip
            continue

    return written


def lambda_handler(event, context):
    params = {
        "pair": SYMBOL,
        "interval": CANDLE_INTERVAL
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
        records_to_persist = ohlc[-10:]


        # Write the most recent 10 OHLC data points to DynamoDB
        records_written = write_ohlc_to_dynamodb(pair_key, params["interval"], records_to_persist)

        # Emit event for price updated
        events.put_events(
            Entries=[{
                "Source": "market-data-fetcher",
                "DetailType": "market-data-updated",
                "Detail": json.dumps({
                    "pair": pair_key,
                    "timeframe": f"{params['interval']}m",
                    "timestamp": int(records_to_persist[-1][0])  # timestamp of the latest candle
                })
            }]
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "pair": pair_key,
                    "count": len(ohlc),
                    "records_written_to_dynamodb": records_written,
                    "ohlc": records_to_persist,
                }
            ),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }