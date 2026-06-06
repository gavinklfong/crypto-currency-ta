import boto3
import decimal
from datetime import datetime, timezone
import logging
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MIN_REQUIRED = 20  # tune this: e.g., 20 for EMA20, 15 for RSI(14)+1, etc.

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
        log_info("Not enough data to compute RSI", values_count=len(values), required=period+1)
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
        log_info("Not enough data to compute MACD", values_count=len(values), required=slow+signal)
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
        ConsistentRead=False
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
        "ta_rsi14": D(rsi),
        "ta_macd": {
            "line": D(macd_line),
            "signal": D(signal_line),
            "histogram": D(histogram)
        },
        "ta_ema20": D(ema20),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

def write_ta_to_dynamodb(pair, timeframe, timestamp, ta):
    pk = f"PAIR#{pair}"
    sk = f"TF#{timeframe}#TS#{timestamp}"

    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET ta_rsi14 = :rsi, ta_macd = :macd, ta_ema20 = :ema, updated_at = :ts",
        ExpressionAttributeValues={
            ":rsi": ta.get("ta_rsi14"),
            ":macd": ta.get("ta_macd"),
            ":ema": ta.get("ta_ema20"),
            ":ts": ta.get("updated_at")
        }
    )

# ============================================================
# MAIN LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):

    log_info("Lambda triggered", event=json.dumps(event))

    # SQS event
    if "Records" in event:
        record = event["Records"][0]
        body = json.loads(record["body"])
        
        # EventBridge event is inside "detail"
        event_data = body.get("detail", {})
    else:
        if "detail" in event:
            event_data = event["detail"]    
        else:
            # Direct invocation (manual)
            event_data = event

    # Check if range calculation is requested
    if "start_ts" in event_data and "end_ts" in event_data:
        return calculate_range(
            event_data["symbol"],
            event_data["timeframe"],
            event_data["start_ts"],
            event_data["end_ts"]
        )

    return calculate_single(event_data)

# ============================================================
# SINGLE-CANDLE MODE
# ============================================================

def to_float_safe(val):
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    try:
        return float(val)
    except Exception:
        return None

def extract_closes(window):
    closes = []
    bad = []
    for it in window:
        sk = it.get("SK")
        if "close" not in it:
            bad.append({"sk": sk, "reason": "missing_close"})
            continue
        f = to_float_safe(it.get("close"))
        if f is None:
            bad.append({"sk": sk, "reason": "invalid_close", "value": it.get("close")})
            continue
        closes.append(f)
    return closes, bad

def calculate_single(event):
    pair = event["symbol"]
    timeframe = event["timeframe"]
    timestamp = int(datetime.now(timezone.utc).timestamp())

    # 1) fetch window
    window = fetch_last_n_candles(pair, timeframe, timestamp, n=200)
    log_info("Fetched candles", count=len(window), pair=pair, timeframe=timeframe)

    # 2) extract closes defensively
    closes_all, bad_items = extract_closes(window)
    if bad_items:
        log_info("Some items missing/invalid close", valid_count=len(closes_all), bad_count=len(bad_items), bad_sample=bad_items[:3])

    # 3) quit early if not enough history
    if len(closes_all) < MIN_REQUIRED:
        log_info("Insufficient history for TA, quitting", pair=pair, timeframe=timeframe,
                 available=len(closes_all), required=MIN_REQUIRED)
        # Optional: mark item in DynamoDB or emit metric here if you want observability
        return {
            "pair": pair,
            "timeframe": timeframe,
            "processed": 0,
            "status": "insufficient_history",
            "available_closes": len(closes_all)
        }

    # 4) proceed with TA computation (unchanged)
    last_window = window[-10:] if len(window) >= 10 else window
    last_timestamps = [extract_timestamp_from_sk(i["SK"]) for i in last_window]
    closes_all_floats = closes_all  # already floats
    index_by_ts = {extract_timestamp_from_sk(i["SK"]): idx for idx, i in enumerate(window)}

    results = []
    for ts in last_timestamps:
        idx = index_by_ts[ts]
        closes = closes_all_floats[: idx + 1]
        ta = compute_all_ta(closes)
        if not ta:
            log_info("Skipping TA update due to insufficient history for this timestamp", timestamp=ts)
            continue

        write_ta_to_dynamodb(pair, timeframe, ts, ta)
        # log_info("TA written", pair=pair, timeframe=timeframe, timestamp=ts)
        results.append({"timestamp": ts, "ta": ta})

    log_info("TA calculation completed", pair=pair, timeframe=timeframe, processed_count=len(results))
    return {"pair": pair, "timeframe": timeframe, "processed": len(results), "details": results}


# ============================================================
# RANGE RE-CALCULATION MODE
# ============================================================

def calculate_range(pair, timeframe, start_ts, end_ts):
    pk = f"PAIR#{pair}"

    # ----------------------------------------------------
    # 1. Fetch all candles in the range
    # ----------------------------------------------------
    resp = table.query(
        KeyConditionExpression="PK = :pk AND SK BETWEEN :sk_start AND :sk_end",
        ExpressionAttributeValues={
            ":pk": pk,
            ":sk_start": f"TF#{timeframe}#TS#{start_ts}",
            ":sk_end": f"TF#{timeframe}#TS#{end_ts}"
        },
        ScanIndexForward=True,
        ConsistentRead=False
    )

    candles = resp["Items"]
    if not candles:
        return {
            "pair": pair,
            "timeframe": timeframe,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "status": "no candles found"
        }

    # Extract timestamps
    timestamps = [extract_timestamp_from_sk(i["SK"]) for i in candles]

    # ----------------------------------------------------
    # 2. Fetch a single large window up to end_ts
    # ----------------------------------------------------
    window = fetch_last_n_candles(pair, timeframe, end_ts, n=2000)
    closes_all = [float(i["close"]) for i in window]

    # Map timestamp → index in window
    index_by_ts = {extract_timestamp_from_sk(i["SK"]): idx for idx, i in enumerate(window)}

    # ----------------------------------------------------
    # 3. Update TA columns for each candle
    # ----------------------------------------------------
    processed = 0

    for candle in candles:
        ts = extract_timestamp_from_sk(candle["SK"])
        if ts not in index_by_ts:
            continue

        idx = index_by_ts[ts]
        closes = closes_all[: idx + 1]

        ta = compute_all_ta(closes)

        # Update TA columns using dedicated function
        write_ta_to_dynamodb(pair, timeframe, ts, ta)
        processed += 1

    return {
        "pair": pair,
        "timeframe": timeframe,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "processed": processed,
        "status": "range recalculated (update mode)"
    }
