import csv
import time
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

DYNAMODB_TABLE_NAME = "crypto-currency-ta-market-data"
dynamodb = boto3.client("dynamodb", region_name="us-east-2")


def batch_write(items):
    """Write up to 25 items with retry for unprocessed items."""
    request = {DYNAMODB_TABLE_NAME: [{"PutRequest": {"Item": item}} for item in items]}

    while True:
        response = dynamodb.batch_write_item(RequestItems=request)
        unprocessed = response.get("UnprocessedItems", {})

        if not unprocessed or DYNAMODB_TABLE_NAME not in unprocessed:
            break

        print("Retrying unprocessed:", len(unprocessed[DYNAMODB_TABLE_NAME]))
        request = unprocessed
        time.sleep(0.25)


def build_item(pair, timeframe_minutes, row):
    """
    Row format expected:
    [timestamp, open, high, low, close, vwap, volume]
    """
    timestamp = int(row[0])
    open_p = float(row[1])
    high_p = float(row[2])
    low_p = float(row[3])
    close_p = float(row[4])
    vwap = float(row[5])
    volume = float(row[6])

    now_ts = int(datetime.now().timestamp())
    timeframe_str = f"{timeframe_minutes}m"

    return {
        "PK": {"S": f"PAIR#{pair}"},
        "SK": {"S": f"TF#{timeframe_str}#TS#{timestamp}"},
        "pair": {"S": pair},
        "timeframe_minutes": {"N": str(timeframe_minutes)},
        "timestamp": {"N": str(timestamp)},
        "open": {"N": str(open_p)},
        "high": {"N": str(high_p)},
        "low": {"N": str(low_p)},
        "close": {"N": str(close_p)},
        "vwap": {"N": str(vwap)},
        "volume": {"N": str(volume)},
        "created_at": {"N": str(now_ts)},
    }


def import_csv_to_dynamodb(csv_path, pair, timeframe_minutes):
    batch = []
    total_written = 0

    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header

        for row in reader:
            item = build_item(pair, timeframe_minutes, row)
            batch.append(item)

            if len(batch) == 25:
                batch_write(batch)
                total_written += len(batch)
                print(f"Batch write completed. Total records written: {total_written}")
                batch = []

        # final flush
        if batch:
            batch_write(batch)
            total_written += len(batch)

    print(f"Import complete. Total records written: {total_written}")


if __name__ == "__main__":
    # Example usage
    import_csv_to_dynamodb(
        csv_path="XBTUSD_1.csv",
        pair="XXBTZUSD",
        timeframe_minutes=1
    )
