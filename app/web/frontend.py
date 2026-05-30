import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import boto3
import s3fs
from datetime import datetime, timedelta, timezone

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("Market Data Viewer (S3 + DynamoDB Catch-up)")

symbol = st.sidebar.text_input("Symbol", "XXBTZUSD")
timeframe = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"])

start_date = st.sidebar.date_input(
    "Start Date",
    datetime.now(timezone.utc).date() - timedelta(days=0)
)
end_date = st.sidebar.date_input(
    "End Date",
    datetime.now(timezone.utc).date()
)

# -----------------------------
# S3 Loader
# -----------------------------
@st.cache_data
def load_s3_range(symbol, timeframe, start_date, end_date):
    fs = s3fs.S3FileSystem()
    all_dfs = []

    current = pd.to_datetime(start_date).date()
    end_date = pd.to_datetime(end_date).date()

    while current <= end_date:
        # Loop through 24 hours
        for hour in range(24):
            hour_str = f"{hour:02d}"

            s3_path = (
                f"crypto-currency-ta-exports/"
                f"symbol={symbol}/tf={timeframe}/date={current}/hour={hour_str}/data.parquet"
            )

            if fs.exists(s3_path):
                with fs.open(s3_path, "rb") as f:
                    df = pd.read_parquet(f)
                    all_dfs.append(df)

        current += timedelta(days=1)

    if not all_dfs:
        return pd.DataFrame()

    df = pd.concat(all_dfs).sort_values("timestamp")
    df = normalize_timestamp(df)
    return df

def normalize_timestamp(df):
    if "timestamp" not in df.columns:
        raise ValueError("S3 file missing 'timestamp' column")

    # Convert Decimal → int
    df["timestamp"] = df["timestamp"].apply(lambda x: int(x) if not isinstance(x, int) else x)

    # Detect milliseconds vs seconds
    sample = df["timestamp"].iloc[0]
    if sample > 1e12:  # milliseconds
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    else:              # seconds
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

    return df


# -----------------------------
# DynamoDB Catch-up Loader
# -----------------------------
@st.cache_data
def load_dynamodb_after(symbol, timeframe, last_ts):
    dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
    table = dynamodb.Table("crypto-currency-ta-market-data")

    pk = f"PAIR#{symbol}"
    sk_prefix = f"TF#{timeframe}#TS#"

    # Query SK >= last_ts
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(pk)
        & boto3.dynamodb.conditions.Key("SK").gte(f"{sk_prefix}{last_ts}")
    )

    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(pk)
            & boto3.dynamodb.conditions.Key("SK").gte(f"{sk_prefix}{last_ts}"),
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))

    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items)

    # Extract timestamp from SK
    df["timestamp"] = df["SK"].str.extract(r"TS#(\d+)").astype(int)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

    # Convert numeric fields
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)

    return df.sort_values("timestamp")


# -----------------------------
# Load S3 Data
# -----------------------------
df_s3 = load_s3_range(symbol, timeframe, start_date, end_date)

if df_s3.empty:
    st.warning("No S3 data found for this range.")
    st.stop()

# -----------------------------
# Load DynamoDB Catch-up
# -----------------------------
last_ts = int(df_s3["timestamp"].max().timestamp())
df_ddb = load_dynamodb_after(symbol, timeframe, last_ts)

# Merge
df = pd.concat([df_s3, df_ddb]).drop_duplicates(subset=["timestamp"])
df = df.sort_values("timestamp")

# -----------------------------
# Plot Candlestick
# -----------------------------
fig = go.Figure(
    data=[
        go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
        )
    ]
)

fig.update_layout(
    title=f"{symbol} — {timeframe} candles",
    height=600,
    xaxis_rangeslider_visible=False,
)

st.plotly_chart(fig, width='stretch')
