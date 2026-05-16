import boto3
import decimal
from datetime import datetime, timezone
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = "crypto-currency-ta-market-data"
table = dynamodb.Table(TABLE_NAME)

def log_info(message, **kwargs):
    logger.info(f"{message} | {kwargs}")

def log_error(message, **kwargs):
    logger.error(f"{message} | {kwargs}")

def D(x):
    return decimal.Decimal(str(x)) if x is not None else None

# ============================================================
# TA CALCULATIONS
# ============================================================

def compute_ema(values, period):
    k = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema

def compute_rsi(values, period=14):
    if len(values) < period + 1:
        return None

    window = values[-(period + 1):]
    gains, losses = [], []

    for i in range(1, len(window)):
        diff = window[i] - window[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_macd(values, fast=12, slow=26, signal=9):
    if len(values) < slow + signal:
        return None, None, None

    ema_fast = compute_ema(values[-(slow+signal):], fast)
    ema_slow = compute_ema(values[-(slow+signal):], slow)
    macd_line = ema_fast - ema_slow

    macd_hist = []
    for i in range(len(values) - (slow + signal), len(values)):
        ef = compute_ema(values[:i], fast)
        es = compute_ema(values[:i], slow)
        macd_hist.append(ef - es)

    signal_line = compute_ema(macd_hist, signal)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram

# ============================================================
# COMMON LOGIC
# ============================================================

def fetch_last_n_candles(pair, timeframe, timestamp, n=200):
    """Fetch last N candles up to and including timestamp."""
    pk = f"PAIR#{pair}"
    sk_upper = f"TF#{timeframe}#TS#{timestamp}"

    resp = table.query(
        KeyConditionExpression="PK = :pk AND SK <= :sk_upper",
        ExpressionAttributeValues={
            ":pk": pk,
            ":sk_upper": sk_upper
        },
        ScanIndexForward=False,
        Limit=n,
        ConsistentRead=True
    )

    return list(reversed(resp["Items"]))

def extract_timestamp_from_sk(sk):
    """Extract integer timestamp from SK."""
    _, _, _, ts_str = sk.split("#")
    return int(ts_str)

def compute_all_ta(closes):
    """Compute RSI, MACD, EMA20 and return TA dict."""
    rsi = compute_rsi(closes)
    macd_line, signal_line, histogram = compute_macd(closes)
    ema20 = compute_ema(closes[-20:], 20) if len(closes) >= 20 else None

    return {
        "rsi14": D(rsi),
        "macd": {
            "line": D(macd_line),
            "signal": D(signal_line),
            "histogram": D(histogram)
        },
        "ema20": D(ema20),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

def write_ta_to_dynamodb(pair, timeframe, timestamp, ta):
    pk = f"PAIR#{pair}"
    sk = f"TF#{timeframe}#TS#{timestamp}"

    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET ta = :ta",
        ExpressionAttributeValues={":ta": ta}
    )

# ============================================================
# MAIN LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):
    # SQS event
    if "Records" in event:
        record = event["Records"][0]
        body = json.loads(record["body"])
        
        # EventBridge event is inside "detail"
        event_data = body.get("detail", {})
    else:
        # Direct invocation (manual)
        event_data = event

    # Check if range calculation is requested
    if "start_ts" in event_data and "end_ts" in event_data:
        return calculate_range(
            event_data["pair"],
            event_data["timeframe"],
            event_data["start_ts"],
            event_data["end_ts"]
        )

    return calculate_single(event_data)

# ============================================================
# SINGLE-CANDLE MODE
# ============================================================

def calculate_single(event):
    pair = event["pair"]
    timeframe = event["timeframe"]
    timestamp = int(event["timestamp"])

    # ----------------------------------------------------
    # 1. Fetch last 200 candles ONCE
    # ----------------------------------------------------
    window = fetch_last_n_candles(pair, timeframe, timestamp, n=200)
    log_info("Fetched candles", count=len(window), pair=pair, timeframe=timeframe)

    if not window:
        raise RuntimeError(f"MARKET_DATA_NOT_AVAILABLE, ts:{timestamp}")

    # ----------------------------------------------------
    # 2. Extract the last 10 candles from this single window
    # ----------------------------------------------------
    last_10 = window[-10:] if len(window) >= 10 else window
    last_10_timestamps = [extract_timestamp_from_sk(i["SK"]) for i in last_10]

    log_info("Processing last 10 candles", timestamps=last_10_timestamps)

    # ----------------------------------------------------
    # 3. For each of the last 10 timestamps:
    #    - Use the SAME window
    #    - Slice the window up to that timestamp
    #    - Compute TA
    #    - Persist TA
    # ----------------------------------------------------
    results = []

    # Pre-extract closes for performance
    closes_all = [float(i["close"]) for i in window]

    # Build a mapping: timestamp → index in window
    index_by_ts = {extract_timestamp_from_sk(i["SK"]): idx for idx, i in enumerate(window)}

    for ts in last_10_timestamps:
        idx = index_by_ts[ts]

        # Slice closes up to this candle
        closes = closes_all[: idx + 1]

        ta = compute_all_ta(closes)
        write_ta_to_dynamodb(pair, timeframe, ts, ta)

        log_info("TA written", pair=pair, timeframe=timeframe, timestamp=ts)

        results.append({
            "timestamp": ts,
            "ta": ta
        })

    return {
        "pair": pair,
        "timeframe": timeframe,
        "processed": len(results),
        "details": results
    }

# ============================================================
# RANGE RE-CALCULATION MODE
# ============================================================

def calculate_range(pair, timeframe, start_ts, end_ts):
    pk = f"PAIR#{pair}"

    resp = table.query(
        KeyConditionExpression="PK = :pk AND SK BETWEEN :sk_start AND :sk_end",
        ExpressionAttributeValues={
            ":pk": pk,
            ":sk_start": f"TF#{timeframe}#TS#{start_ts}",
            ":sk_end": f"TF#{timeframe}#TS#{end_ts}"
        },
        ScanIndexForward=True,
        ConsistentRead=True
    )

    candles = resp["Items"]

    for item in candles:
        ts = extract_timestamp_from_sk(item["SK"])
        window = fetch_last_n_candles(pair, timeframe, ts, n=200)
        closes = [float(c["close"]) for c in window]

        ta = compute_all_ta(closes)
        write_ta_to_dynamodb(pair, timeframe, ts, ta)

    return {
        "pair": pair,
        "timeframe": timeframe,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "status": "range recalculated"
    }
