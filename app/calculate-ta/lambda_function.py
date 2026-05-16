import boto3
import decimal
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = "crypto-currency-ta-market-data"
table = dynamodb.Table(TABLE_NAME)

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
    if "start_ts" in event and "end_ts" in event:
        return calculate_range(
            event["pair"],
            event["timeframe"],
            event["start_ts"],
            event["end_ts"]
        )

    return calculate_single(event)

# ============================================================
# SINGLE-CANDLE MODE
# ============================================================

def calculate_single(event):
    pair = event["pair"]
    timeframe = event["timeframe"]
    timestamp = event["timestamp"]

    # ----------------------------------------------------
    # 1. Fetch last 200 candles up to this timestamp
    # ----------------------------------------------------
    items = fetch_last_n_candles(pair, timeframe, timestamp, n=200)

    if not items:
        raise RuntimeError(f"MARKET_DATA_NOT_AVAILABLE, ts:{timestamp}")

    # ----------------------------------------------------
    # 2. Check if the target timestamp exists in the window
    # ----------------------------------------------------
    last_item = items[-1]  # chronological order
    sk = last_item["SK"]
    _, _, _, ts_str = sk.split("#")
    last_ts = int(ts_str)

    if last_ts != timestamp:
        raise RuntimeError(f"TARGET_TIMESTAMP_NOT_AVAILABLE, ts:{timestamp}, last_available_ts:{last_ts}")

    # ----------------------------------------------------
    # 3. Compute TA
    # ----------------------------------------------------
    closes = [float(i["close"]) for i in items]
    ta = compute_all_ta(closes)

    # ----------------------------------------------------
    # 4. Write TA into DynamoDB
    # ----------------------------------------------------
    write_ta_to_dynamodb(pair, timeframe, timestamp, ta)

    return {
        "pair": pair,
        "timeframe": timeframe,
        "timestamp": timestamp,
        "ta_written": ta
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
