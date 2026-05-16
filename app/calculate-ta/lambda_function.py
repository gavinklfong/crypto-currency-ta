import boto3
import decimal
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = "crypto-currency-ta-market-data"
table = dynamodb.Table(TABLE_NAME)

def D(x):
    return decimal.Decimal(str(x))

# -----------------------------
# TA CALCULATIONS
# -----------------------------

def compute_ema(values, period):
    k = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema

def compute_rsi(values, period=14):
    # Need exactly period + 1 values to compute RSI for the last candle
    if len(values) < period + 1:
        return None

    # Slice only the last (period + 1) closes
    window = values[-(period + 1):]

    gains = []
    losses = []

    # Compute gains/losses for the window
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

# -----------------------------
# MAIN LAMBDA HANDLER
# -----------------------------

def lambda_handler(event, context):
    pair = event["pair"]
    timeframe = event["timeframe"]
    timestamp = event["timestamp"]

    pk = f"PAIR#{pair}"

    # -----------------------------------------
    # UPDATED QUERY: fetch latest 200 candles
    # -----------------------------------------
    resp = table.query(
        KeyConditionExpression=(
            "PK = :pk AND SK <= :sk_upper"
        ),
        ExpressionAttributeValues={
            ":pk": f"PAIR#{pair}",
            ":sk_upper": f"TF#{timeframe}#TS#{timestamp}"
        },
        ScanIndexForward=False,   # newest → oldest
        Limit=200,                # only fetch last 200
        ConsistentRead=True
    )

    # Reverse to chronological order
    items = list(reversed(resp["Items"]))

    if not items:
        return {"error": "No OHLC data found"}

    closes = [float(i["close"]) for i in items]

    # Compute indicators
    rsi = compute_rsi(closes)
    macd_line, signal_line, histogram = compute_macd(closes)
    ema20 = compute_ema(closes[-20:], 20) if len(closes) >= 20 else None

    ta = {
        "rsi14": D(rsi) if rsi is not None else None,
        "macd": {
            "line": D(macd_line) if macd_line else None,
            "signal": D(signal_line) if signal_line else None,
            "histogram": D(histogram) if histogram else None
        },
        "ema20": D(ema20) if ema20 else None,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    # Write TA into the latest candle item
    sk = f"TF#{timeframe}#TS#{timestamp}"

    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET ta = :ta",
        ExpressionAttributeValues={":ta": ta}
    )

    return {
        "pair": pair,
        "timeframe": timeframe,
        "timestamp": timestamp,
        "ta_written": ta
    }
