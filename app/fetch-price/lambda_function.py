import json
import requests
import boto3
from datetime import datetime

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
TIMESTREAM_DATABASE = "crypto-price-database"
TIMESTREAM_TABLE = "price-data"

timestream_client = boto3.client("timestream-write", region_name="us-east-2")


def write_ohlc_to_timestream(pair, interval, ohlc_data):
    """Write OHLC data to Timestream"""
    records = []
    current_time_ms = str(int(datetime.now().timestamp() * 1000))

    for candle in ohlc_data:
        timestamp = str(int(candle[0]))  # Kraken timestamp in seconds
        open_price = candle[1]
        high_price = candle[2]
        low_price = candle[3]
        close_price = candle[4]
        vwap = candle[5]
        volume = candle[6]

        # Create a record for each OHLC metric
        for metric_name, metric_value in [
            ("open", open_price),
            ("high", high_price),
            ("low", low_price),
            ("close", close_price),
            ("vwap", vwap),
            ("volume", volume),
        ]:
            records.append(
                {
                    "Dimensions": [
                        {"Name": "pair", "Value": pair},
                        {"Name": "interval", "Value": str(interval)},
                        {"Name": "metric", "Value": metric_name},
                    ],
                    "MeasureName": "price",
                    "MeasureValue": str(metric_value),
                    "MeasureValueType": "DOUBLE",
                    "Time": timestamp,
                    "TimeUnit": "SECONDS",
                }
            )

    # Write records in batches (Timestream has a batch size limit)
    batch_size = 100
    records_written = 0

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            timestream_client.write_records(
                DatabaseName=TIMESTREAM_DATABASE,
                TableName=TIMESTREAM_TABLE,
                Records=batch,
            )
            records_written += len(batch)
        except Exception as e:
            print(f"Error writing batch to Timestream: {str(e)}")
            raise

    return records_written


def lambda_handler(event, context):
    params = {
        "pair": "XBTUSD",  # Bitcoin/USD
        "interval": 60,  # 1-hour candles
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

        # Write OHLC data to Timestream
        records_written = write_ohlc_to_timestream(pair_key, params["interval"], ohlc)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "pair": pair_key,
                    "count": len(ohlc),
                    "records_written_to_timestream": records_written,
                    "ohlc": ohlc,
                }
            ),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
