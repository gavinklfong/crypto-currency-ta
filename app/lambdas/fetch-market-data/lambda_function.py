import json
import requests
import requests.exceptions
import boto3
from datetime import datetime
from itertools import islice
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_result,
)

logger = logging.getLogger(__name__)

DEFAULT_SYMBOL = "XBTUSD"  # Bitcoin/USD
CANDLE_INTERVAL = 1  # 1-minute candles (triggered every 1 minute)
KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
DYNAMODB_TABLE_NAME = "crypto-currency-ta-market-data"

dynamodb_client = boto3.client("dynamodb", region_name="us-east-2")


def _is_http_429(response):
    """Return True if the response is an HTTP 429 (rate limited)."""
    return getattr(response, "status_code", None) == 429


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=(
        retry_if_exception_type((
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RetryError,
        ))
        | retry_if_exception_type(requests.exceptions.HTTPError)
        | retry_if_result(_is_http_429)
    ),
    before_sleep=lambda retry_state: logger.warning(
        "Kraken API request failed (attempt %d/5): %s — retrying in %.1fs",
        retry_state.attempt_number,
        retry_state.outcome.exception() if retry_state.outcome.failed else retry_state.outcome.result().status_code,
        retry_state.next_action.sleep,
    ),
    reraise=True,
)
def _fetch_ohlc_from_kraken(pair, interval):
    """Fetch OHLC data from Kraken API with automatic retry and backoff."""
    logger.info("Fetching OHLC for pair=%s interval=%s", pair, interval)
    response = requests.get(
        KRAKEN_OHLC_URL,
        params={"pair": pair, "interval": interval},
        timeout=10,
    )
    # Raise HTTPError for non-429 errors so tenacity can retry them
    response.raise_for_status()
    return response


def log_info(message, **kwargs):
    logger.info(f"{message} | {json.dumps(kwargs)}")

def log_error(message, **kwargs):
    logger.error(f"{message} | {json.dumps(kwargs)}")

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
                ConditionExpression="attribute_not_exists(SK)"
            )
            written += 1

        except dynamodb_client.exceptions.ConditionalCheckFailedException:
            # Item already exists → skip
            continue

    return written


def lambda_handler(event, context):

    log_info("Lambda triggered", event=json.dumps(event))
    
    # Extract symbols from event (either from detail or directly)
    if "detail" in event:
        # EventBridge format - require symbols in detail
        event_data = event["detail"]
        symbol = event_data.get("symbol")
    else:
        # Direct format - try to get symbols, fall back to defaults
        event_data = event
        symbol = event_data.get("symbol", DEFAULT_SYMBOL)


    params = {
        "pair": symbol,
        "interval": CANDLE_INTERVAL
    }

    try:
        kraken_response = _fetch_ohlc_from_kraken(params["pair"], params["interval"])
        data = kraken_response.json()

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
        latest_candle_ts = int(records_to_persist[-1][0]) if records_to_persist else None

        log_info("Records written to DynamoDB", pair=pair_key, timestamp=latest_candle_ts, count=records_written)

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