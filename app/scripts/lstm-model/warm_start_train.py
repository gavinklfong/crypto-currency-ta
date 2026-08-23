#!/usr/bin/env python3
"""Daily warm-start retraining for LSTM cryptocurrency price prediction model.

Fetches recent market data from DynamoDB, fine-tunes the existing model with
a small number of epochs, and saves the updated model with a date suffix.
Model and scaler are uploaded to S3 for backup.

Usage:
    # Initial training (cold start) — trains on all DynamoDB data
    python warm_start_train.py --symbol XBTUSD

    # Daily fine-tune (warm start) — fine-tunes on last 30 days
    python warm_start_train.py --symbol XBTUSD --days 30 --epochs 3

    # Dry run — fetch data and preview, no training
    python warm_start_train.py --symbol XBTUSD --dry-run

    # As a module (called from main.py with heartbeat/progress)
    from warm_start_train import run_training
    result = run_training(params, on_progress=callback)
"""

import argparse
import os
import sys
import pickle
import logging
from datetime import datetime, timedelta, timezone

import boto3
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import load_model, Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────

DEFAULT_SYMBOL = "XBTUSD"
DEFAULT_TIMEFRAME = "1m"
DEFAULT_DAYS = 30
DEFAULT_EPOCHS = 3
DEFAULT_BATCH_SIZE = 32
DEFAULT_WINDOW_SIZE = 60
DEFAULT_REGION = "us-east-2"
COLD_START_EPOCHS = 5
TABLE_NAME = "crypto-currency-ta-market-data"
BUCKET_NAME = "crypto-currency-ta-exports"
MODEL_PREFIX = "models/lstm"


# ── Progress Callback ─────────────────────────────────────────────

class TrainingCallback(tf.keras.callbacks.Callback):
    """Reports progress to DynamoDB after each epoch."""

    def __init__(self, total_epochs, on_progress):
        super().__init__()
        self.total_epochs = total_epochs
        self.on_progress = on_progress

    def on_epoch_end(self, epoch, logs=None):
        progress = 80 + int((epoch + 1) / self.total_epochs * 10)
        loss = logs.get("loss", 0)
        self.on_progress(progress, f"Epoch {epoch + 1}/{self.total_epochs} loss: {loss:.4f}")


# ── DynamoDB Data Fetching ────────────────────────────────────────


def fetch_dynamodb_data(symbol, timeframe, days_back, region):
    """Query DynamoDB for market data within the last N days."""
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(TABLE_NAME)

    end_ts = int(datetime.now(tz=timezone.utc).timestamp())
    start_ts = int((datetime.now(tz=timezone.utc) - timedelta(days=days_back)).timestamp())

    start_sk = f"TF#{timeframe}#TS#{start_ts}"
    end_sk = f"TF#{timeframe}#TS#{end_ts}"
    pk = f"PAIR#{symbol}"

    logger.info(
        "Querying DynamoDB: symbol=%s timeframe=%s days=%d range=%d..%d",
        symbol, timeframe, days_back, start_ts, end_ts,
    )

    items = []
    last_evaluated_key = None

    while True:
        query_params = {
            "KeyConditionExpression": "PK = :pk AND SK BETWEEN :start AND :end",
            "ExpressionAttributeValues": {
                ":pk": {"S": pk},
                ":start": {"S": start_sk},
                ":end": {"S": end_sk},
            },
        }

        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = table.query(**query_params)
        page_items = response.get("Items", [])
        items.extend(page_items)
        last_evaluated_key = response.get("LastEvaluatedKey")

        if not last_evaluated_key:
            break

    logger.info("Fetched %d records from DynamoDB", len(items))
    return items


def items_to_dataframe(items):
    """Convert DynamoDB items to a sorted DataFrame."""
    df = pd.DataFrame(items)

    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


# ── Data Preparation ──────────────────────────────────────────────


def prepare_data(data, window_size=60):
    """Scale close price and create sequences for LSTM training."""
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data[["close"]].values)

    X, y = [], []
    for i in range(window_size, len(scaled_data)):
        X.append(scaled_data[i - window_size:i, 0])
        y.append(scaled_data[i, 0])

    X, y = np.array(X), np.array(y)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))

    return X, y, scaler


# ── Model ─────────────────────────────────────────────────────────


def build_model(input_shape):
    """Build the LSTM model architecture — matches train_lstm.py exactly."""
    model = Sequential([
        LSTM(units=50, return_sequences=True, input_shape=input_shape),
        Dropout(0.2),
        LSTM(units=50, return_sequences=False),
        Dropout(0.2),
        Dense(units=25),
        Dense(units=1),
    ])

    model.compile(optimizer="adam", loss="mean_squared_error")
    return model


def compute_metrics(y_true, y_pred):
    """Compute regression metrics on unscaled data."""
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    mae = np.mean(np.abs(y_true - y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

    return {
        "RMSE": round(rmse, 2),
        "MAE": round(mae, 2),
        "MAPE": round(mape, 2),
        "R2": round(r2, 4),
    }


# ── S3 Upload ─────────────────────────────────────────────────────


def upload_to_s3(local_path, s3_key):
    """Upload a file to S3."""
    s3 = boto3.client("s3")
    s3.upload_file(local_path, BUCKET_NAME, s3_key)
    logger.info("Uploaded s3://%s/%s", BUCKET_NAME, s3_key)


# ── Core Training ─────────────────────────────────────────────────


def _parse_cli_args():
    parser = argparse.ArgumentParser(description="Warm-start LSTM retraining script.")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Market symbol (e.g., XBTUSD)")
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME, help="Timeframe (default: 1m)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Days of recent data for fine-tune")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS, help="Fine-tune epochs (default: 3)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Training batch size")
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE, help="Sequence window size")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    parser.add_argument("--dry-run", action="store_true", help="Fetch data only, no training")
    return parser.parse_args()


def run_training(params, on_progress=None):
    """Run warm-start training.

    Called by main.py with heartbeat context, or by CLI directly.

    Args:
        params: dict with symbol, timeframe, days, epochs, batch_size, window_size, region, dry_run
        on_progress: optional callable(progress: int, detail: str) -> None

    Returns:
        dict with training results (metrics, mode, epochs, etc.)
    """
    symbol = params.get("symbol", DEFAULT_SYMBOL)
    timeframe = params.get("timeframe", DEFAULT_TIMEFRAME)
    days_back = params.get("days", DEFAULT_DAYS)
    epochs = params.get("epochs", DEFAULT_EPOCHS)
    batch_size = params.get("batch_size", DEFAULT_BATCH_SIZE)
    window_size = params.get("window_size", DEFAULT_WINDOW_SIZE)
    region = params.get("region", DEFAULT_REGION)
    dry_run = params.get("dry_run", False)

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MODEL_DIR = BASE_DIR
    MODEL_PATH = os.path.join(MODEL_DIR, "lstm_model.h5")
    SCALER_PATH = os.path.join(MODEL_DIR, "lstm_scaler.pkl")

    def _progress(progress, detail):
        logger.info("Progress %d%% — %s", progress, detail)
        if on_progress:
            on_progress(progress, detail)

    # ── Step 1: Fetch data ──────────────────────────────────────
    logger.info("=" * 60)
    logger.info("LSTM Warm-Start Training")
    logger.info("=" * 60)

    _progress(10, "Initializing job")
    _progress(25, "Fetching market data from DynamoDB")
    items = fetch_dynamodb_data(symbol, timeframe, days_back, region)

    if not items:
        raise ValueError("No data fetched from DynamoDB.")

    df = items_to_dataframe(items)
    logger.info("Data range: %s to %s (%d rows)", df["timestamp"].min(), df["timestamp"].max(), len(df))

    if dry_run:
        _progress(30, "Dry run — previewing data")
        logger.info("Dry run — previewing last 5 rows:")
        print(df.tail().to_string(index=False))
        logger.info("Dry run complete.")
        return {"dry_run": True, "rows": len(df)}

    # ── Step 2: Prepare sequences ──────────────────────────────
    _progress(40, "Preparing data sequences")
    X, y, scaler = prepare_data(df, window_size)
    logger.info("Prepared %d sequences (window=%d)", len(X), window_size)

    if len(X) == 0:
        raise ValueError("No sequences created. Check window size vs data length.")

    # ── Step 3: Determine mode (cold start vs warm start) ──────
    _progress(50, "Determining training mode (cold/warm start)")
    model_exists = os.path.exists(MODEL_PATH)

    if model_exists:
        logger.info("Existing model found — WARM START (fine-tuning)")
        model = load_model(MODEL_PATH)
        model.summary(print_fn=lambda x: logger.info("  %s"))
        mode = "warm"
    else:
        logger.info("No existing model — COLD START (training from scratch)")
        model = build_model(input_shape=(X.shape[1], X.shape[2]))
        model.summary(print_fn=lambda x: logger.info("  %s"))
        mode = "cold"
        epochs = COLD_START_EPOCHS

    _progress(65, "Building LSTM model")

    # ── Step 4: Train ──────────────────────────────────────────
    logger.info("Training: mode=%s epochs=%d batch_size=%d", mode, epochs, batch_size)

    _progress(80, f"Training model (epoch 1/{epochs})")
    callback = TrainingCallback(epochs, on_progress)
    history = model.fit(
        X, y,
        batch_size=batch_size,
        epochs=epochs,
        verbose=1,
        callbacks=[callback],
    )

    final_loss = history.history["loss"][-1]
    logger.info("Final training loss: %.6f", final_loss)

    # ── Step 5: Evaluate on training data ──────────────────────
    _progress(90, "Evaluating model on training data")
    logger.info("Computing evaluation metrics...")
    y_pred_scaled = model.predict(X, verbose=0).flatten()
    y_true_original = scaler.inverse_transform(y.reshape(-1, 1)).flatten()
    y_pred_original = scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()

    metrics = compute_metrics(y_true_original, y_pred_original)
    logger.info("Metrics: %s", metrics)

    print(f"\n{'─' * 60}")
    print(f"  {'Metric':<10} │ {'Value':>10}")
    print(f"  {'─' * 22}")
    for k, v in metrics.items():
        print(f"  {k:<10} │ {v:>10}")
    print(f"{'─' * 60}\n")

    # ── Step 6: Save model + scaler (local + S3) ───────────────
    _progress(95, "Saving model and uploading to S3")
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M")
    model_save_name = f"lstm_model_{mode}_{timestamp}.h5"
    scaler_save_name = f"lstm_scaler_{timestamp}.pkl"

    local_model_path = os.path.join(MODEL_DIR, model_save_name)
    local_scaler_path = os.path.join(MODEL_DIR, "lstm_scaler.pkl")

    logger.info("Saving model to %s", local_model_path)
    model.save(local_model_path)

    logger.info("Saving scaler to %s", local_scaler_path)
    with open(local_scaler_path, "wb") as f:
        pickle.dump(scaler, f)

    s3_model_key = f"{MODEL_PREFIX}/{symbol}/{model_save_name}"
    upload_to_s3(local_model_path, s3_model_key)

    s3_scaler_key = f"{MODEL_PREFIX}/{symbol}/{scaler_save_name}"
    upload_to_s3(local_scaler_path, s3_scaler_key)

    # ── Step 7: Summary ────────────────────────────────────────
    _progress(100, "Training complete")
    logger.info("=" * 60)
    logger.info("Training complete!")
    logger.info("  Mode:        %s", mode)
    logger.info("  Model file:  %s", model_save_name)
    logger.info("  Scaler file: lstm_scaler.pkl")
    logger.info("  Epochs:      %d", epochs)
    logger.info("  Final loss:  %.6f", final_loss)
    logger.info("  Records:     %d", len(df))
    logger.info("  Model S3:    s3://%s/%s", BUCKET_NAME, s3_model_key)
    logger.info("  Scaler S3:   s3://%s/%s", BUCKET_NAME, s3_scaler_key)
    logger.info("=" * 60)

    return {
        "mode": mode,
        "model_file": model_save_name,
        "epochs": epochs,
        "final_loss": final_loss,
        "rows": len(df),
        "metrics": metrics,
        "s3_model_key": s3_model_key,
        "s3_scaler_key": s3_scaler_key,
    }


# ── Main (CLI) ────────────────────────────────────────────────────


def main():
    args = _parse_cli_args()

    params = {
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "days": args.days,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "window_size": args.window_size,
        "region": args.region,
        "dry_run": args.dry_run,
    }

    try:
        result = run_training(params)
    except Exception as e:
        logger.error("Training failed: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
