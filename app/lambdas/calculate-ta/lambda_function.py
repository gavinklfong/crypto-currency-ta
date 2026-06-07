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
        if i <= 0:  # Skip if slice would be empty
            continue
        ef = compute_ema(values[:i], fast)
        es = compute_ema(values[:i], slow)
        macd_hist.append(ef - es)

    if not macd_hist:  # If no valid histogram entries, return None
        return None, None, None

    signal_line = compute_ema(macd_hist, signal)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram

# ============================================================
# COMMON LOGIC
# ============================================================

def fetch_last_n_candles(pair, timeframe, timestamp, n=200):
    """Fetch last N candles up to and including timestamp, with pagination support."""
    pk = f"PAIR#{pair}"
    sk_upper = f"TF#{timeframe}#TS#{timestamp}"
    
    all_items = []
    last_evaluated_key = None
    
    while len(all_items) < n:
        query_params = {
            "KeyConditionExpression": "PK = :pk AND SK <= :sk_upper",
            "ExpressionAttributeValues": {
                ":pk": pk,
                ":sk_upper": sk_upper
            },
            "ScanIndexForward": False,
            "Limit": n - len(all_items),  # Only fetch remaining items needed
            "ConsistentRead": False
        }
        
        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key
        
        resp = table.query(**query_params)
        all_items.extend(resp.get("Items", []))
        
        last_evaluated_key = resp.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break  # No more items to fetch
    
    # Return only the first n items, reversed to chronological order
    return list(reversed(all_items[:n]))

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

    # Extract event data from different event sources
    event_data = {}
    
    # SQS event
    if "Records" in event:
        record = event["Records"][0]
        body = json.loads(record["body"])
        event_data = body
    # EventBridge event
    elif "detail" in event:
        event_data = event["detail"]
    # Direct invocation
    else:
        event_data = event

    # Extract parameters
    symbol = event_data.get("symbol")
    timeframe = event_data.get("timeframe")
    
    # Handle both string and numeric types for timestamps
    start_ts_raw = event_data.get("start_ts")
    end_ts_raw = event_data.get("end_ts")
    
    start_ts = None
    end_ts = None
    
    if start_ts_raw is not None:
        start_ts = int(float(start_ts_raw))
    
    if end_ts_raw is not None:
        end_ts = int(float(end_ts_raw))

    # Check if range calculation is requested
    if start_ts is not None and end_ts is not None:
        return calculate_range(
            symbol,
            timeframe,
            start_ts,
            end_ts
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

    log_info("Fetched candles for range", pair=pair, timeframe=timeframe, start_ts=start_ts, end_ts=end_ts, count=len(resp["Items"]))

    candles = resp["Items"]
    if not candles:
        return {
            "pair": pair,
            "timeframe": timeframe,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "status": "no candles found"
        }

    # ----------------------------------------------------
    # 2. Fetch a single large window up to end_ts
    # ----------------------------------------------------
    # Fetch enough candles to cover entire range + TA history requirements
    # TA calculations (especially MACD) need ~35 data points minimum
    TA_MIN_HISTORY = 35
    num_candles_in_range = len(candles)
    fetch_count = num_candles_in_range + TA_MIN_HISTORY
    window = fetch_last_n_candles(pair, timeframe, end_ts, n=fetch_count)
    log_info("Fetched window for range calculation", pair=pair, timeframe=timeframe, end_ts=end_ts, requested_count=fetch_count, actual_count=len(window))

    # Extract closes defensively
    closes_all, bad_items = extract_closes(window)
    if bad_items:
        log_info("Some items missing/invalid close", valid_count=len(closes_all), bad_count=len(bad_items), bad_sample=bad_items[:3])
    
    # Quit early if not enough history
    if len(closes_all) < MIN_REQUIRED:
        log_info("Insufficient history for TA in range, quitting", pair=pair, timeframe=timeframe,
                 available=len(closes_all), required=MIN_REQUIRED)
        return {
            "pair": pair,
            "timeframe": timeframe,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "status": "insufficient_history",
            "available_closes": len(closes_all)
        }

    # Map timestamp → index in window
    index_by_ts = {extract_timestamp_from_sk(i["SK"]): idx for idx, i in enumerate(window)}

    # TA_MIN_HISTORY is the minimum data points needed for all TA calculations
    # MACD needs slow + signal = 26 + 9 = 35; RSI needs 15; EMA20 needs 20
    TA_MIN_HISTORY = 35
    
    # ----------------------------------------------------
    # 3. Update TA columns for each candle
    # ----------------------------------------------------
    processed = 0

    for candle in candles:
        ts = extract_timestamp_from_sk(candle["SK"])
        if ts not in index_by_ts:
            continue

        idx = index_by_ts[ts]
        # Skip candles without sufficient prior history for TA (need TA_MIN_HISTORY items total)
        if idx < TA_MIN_HISTORY - 1:
            log_info("Skipping candle in range due to insufficient history for TA", timestamp=ts, index_in_window=idx)
            continue

        closes = closes_all[: idx + 1]

        ta = compute_all_ta(closes)

        # Update TA columns using dedicated function
        log_info("Writing TA to DynamoDB for candle in range", pair=pair, timeframe=timeframe, timestamp=ts)
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
