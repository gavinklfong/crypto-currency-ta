import json
import requests
import boto3
from datetime import datetime
from itertools import islice
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CANDLE_INTERVAL = 1  # 1-minute candles (triggered every 1 minute)
KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
DYNAMODB_TABLE_NAME = "crypto-currency-ta-market-data"

events = boto3.client("events")
dynamodb_client = boto3.client("dynamodb", region_name="us-east-2")


def log_info(message, **kwargs):
    logger.info(f"{message} | {json.dumps(kwargs)}")

def log_error(message, **kwargs):
    logger.error(f"{message} | {json.dumps(kwargs)}")

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
                ConditionExpression="attribute_not_exists(SK)"
            )
            written += 1

        except dynamodb_client.exceptions.ConditionalCheckFailedException:
            # Item already exists → skip
            continue

    return written

def validateInput(symbol, start_ts, end_ts):
    if symbol is not None and not isinstance(symbol, str):
        raise ValueError("Symbol must be a string")

    if start_ts is not None:
        try:
            datetime.fromtimestamp(int(start_ts))
        except ValueError:
            raise ValueError("start_ts must be a valid UNIX timestamp")

    if end_ts is not None:
        try:
            datetime.fromtimestamp(int(end_ts))
        except ValueError:
            raise ValueError("end_ts must be a valid UNIX timestamp")
        
    if (start_ts is not None and end_ts is not None) and int(start_ts) > int(end_ts):
        raise ValueError("start_ts cannot be after end_ts")

def find_last_timestamp(ohlc):
    if not ohlc:
        return None
    return max(int(candle[0]) for candle in ohlc)

def lambda_handler(event, context):

    log_info("Lambda triggered", event=json.dumps(event))
    
    # Extract symbol
    if "detail" in event:
        event_data = event["detail"]
    else:
        event_data = event

    # Extract symbol
    symbol = event_data.get("symbol")
    start_ts = event_data.get("start_ts")
    end_ts = event_data.get("end_ts")    


    try:

        validateInput(symbol, start_ts, end_ts)

        params = {
            "pair": symbol,
            "interval": CANDLE_INTERVAL,
            "since": start_ts
        }

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

        # Write the most recent 10 OHLC data points to DynamoDB
        records_written = write_ohlc_to_dynamodb(pair_key, params["interval"], ohlc)
        
        # Find the latest timestamp in the returned OHLC data
        last_timestamp = find_last_timestamp(ohlc)
        if last_timestamp is not None and (end_ts is None or last_timestamp > int(end_ts)):
            log_info("Last timestamp in OHLC data exceeds end_ts", last_timestamp=last_timestamp, end_ts=end_ts)

        else:
            log_info("More OHLC data to be fetched", last_timestamp=last_timestamp, end_ts=end_ts)
            # Emit event to fetch next batch of market data starting from last_timestamp
            events.put_events(
                Entries=[{
                    "Source": "rerun-fetch-market-data",
                    "DetailType": "fetch-market-data",
                    "Detail": json.dumps({
                        "symbol": symbol,
                        "start_ts": last_timestamp,
                        "end_ts": end_ts
                    })
                }]
            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "pair": pair_key,
                    "count": len(ohlc),
                    "records_written_to_dynamodb": records_written
                }
            ),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }