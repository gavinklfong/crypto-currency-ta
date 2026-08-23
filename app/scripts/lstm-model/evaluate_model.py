#!/usr/bin/env python3
"""Evaluate a trained LSTM model against historical market data.

Mirrors the training pipeline to generate predictions and compute
performance metrics (RMSE, MAE, MAPE, R²) with visualisations.
Usage:
    python evaluate_model.py                    # uses default model & data
    python evaluate_model.py --model my_model.h5 --epochs 5
"""

import argparse
import os
import sys
import glob
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf
from tensorflow.keras.models import load_model

warnings.filterwarnings("ignore")


# ── Data Loading (identical to training) ──────────────────────────

def load_data(data_dir):
    """Load & concat all CSVs, sort by timestamp."""
    all_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not all_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    df_list = []
    for filename in all_files:
        df = pd.read_csv(
            filename,
            header=None,
            names=["timestamp", "open", "high", "low", "close", "volume", "other"],
        )
        df_list.append(df)
    full_df = pd.concat(df_list, ignore_index=True)
    full_df["timestamp"] = pd.to_datetime(full_df["timestamp"], unit="s")
    full_df = full_df.sort_values("timestamp").reset_index(drop=True)
    return full_df


# ── Preparation (identical to training) ──────────────────────────

def prepare_data(data, window_size=60):
    """Scale close price & create sequences. Returns X, y, scaler."""
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data[["close"]].values)

    X, y = [], []
    for i in range(window_size, len(scaled_data)):
        X.append(scaled_data[i - window_size : i, 0])
        y.append(scaled_data[i, 0])

    X, y = np.array(X), np.array(y)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    return X, y, scaler


# ── Metrics ────────────────────────────────────────────────────────

def compute_metrics(y_true, y_pred):
    """Return dict of common regression metrics on unscaled data."""
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    r2 = r2_score(y_true, y_pred)
    return {
        "RMSE": rmse,
        "MAE": mae,
        "MAPE (%)": round(mape, 2),
        "R²": round(r2, 4),
    }


# ── Visualization ─────────────────────────────────────────────────

def plot_predictions(y, y_pred_scaled, window_size=60):
    """Plot actual vs predicted (scaled close price) over time."""
    plt.figure(figsize=(16, 6))
    plt.plot(
        range(len(y)),
        y,
        label="Actual",
        color="steelblue",
        linewidth=0.8,
    )
    plt.plot(
        range(len(y_pred_scaled)),
        y_pred_scaled,
        label="Predicted",
        color="crimson",
        linewidth=0.8,
    )
    plt.title("LSTM Close-Price Prediction vs Actual")
    plt.xlabel("Timestep (window_size=60 offset)")
    plt.ylabel("Scaled Close Price")
    plt.legend()
    plt.tight_layout()
    plt.savefig("prediction_vs_actual.png", dpi=150)
    print("Saved prediction_vs_actual.png")


def plot_residuals(y_true, y_pred):
    """Histogram of prediction residuals."""
    residuals = y_true - y_pred
    plt.figure(figsize=(10, 5))
    plt.hist(residuals, bins=100, color="steelblue", edgecolor="white", alpha=0.8)
    plt.axvline(residuals.mean(), color="crimson", linestyle="--", linewidth=1.2)
    plt.title("Prediction Residual Distribution")
    plt.xlabel("Residual (USD)")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig("residual_histogram.png", dpi=150)
    print("Saved residual_histogram.png")


def plot_training_history(model_path):
    """Plot loss curves from model training history if available."""
    history = model_path.get("history", None)
    if history is None:
        print("No training history available — skipping history plot.")
        return
    plt.figure(figsize=(10, 4))
    plt.plot(history.history["loss"], label="Training Loss", color="steelblue")
    plt.title("Training Loss Over Epochs")
    plt.xlabel("Epoch")
    plt.ylabel("MSE Loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig("training_history.png", dpi=150)
    print("Saved training_history.png")


# ── Main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate a trained LSTM model.")
    parser.add_argument(
        "--model",
        default=None,
        help="Path to the .h5 model file (default: lstm_model.h5 in script dir)",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory containing CSV data files (default: ./test)",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=60,
        help="Sequence window size (default: 60)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Use only the first N data rows for evaluation (faster)",
    )
    args = parser.parse_args()

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MODEL_PATH = args.model or os.path.join(BASE_DIR, "lstm_model.h5")
    DATA_DIR = args.data_dir or os.path.join(BASE_DIR, "test")

    print("=" * 60)
    print(" LSTM Model Evaluation")
    print("=" * 60)

    # 1. Load data
    print(f"\n[1/5] Loading data from {DATA_DIR} ...")
    df = load_data(DATA_DIR)
    if args.sample_size:
        df = df.head(args.sample_size)
    print(f"  Loaded {len(df)} rows  "
          f"({df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]})")
    print(f"  Close price range: ${df['close'].min():.2f} – ${df['close'].max():.2f}")

    # 2. Prepare sequences
    print(f"\n[2/5] Preparing sequences (window={args.window_size}) ...")
    X, y, scaler = prepare_data(df, args.window_size)
    print(f"  Created {len(X)} samples")

    # 3. Load model
    print(f"\n[3/5] Loading model from {MODEL_PATH} ...")
    model = load_model(MODEL_PATH)
    model.summary(print_fn=lambda x: print(f"  {x}"))

    # 4. Predict & evaluate
    print(f"\n[4/5] Generating predictions ...")
    y_pred_scaled = model.predict(X, verbose=0).flatten()

    # Inverse-transform to original scale for metrics
    # y is the true values, y_pred_scaled is the predicted values
    y_true_original = scaler.inverse_transform(y.reshape(-1, 1)).flatten()
    y_pred_original = scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()

    metrics = compute_metrics(y_true_original, y_pred_original)
    print(f"\n  ┌───────────────┬──────────────┐")
    print(f"  │ Metric        │ Value        │")
    print(f"  ├───────────────┼──────────────┤")
    for k, v in metrics.items():
        bar = "█" * min(int(abs(v)) % 20, 18) if k != "R²" else ""
        print(f"  │ {k:<12}│ {str(v):>8}  {bar}│")
    print(f"  └───────────────┴──────────────┘")

    # 5. Visualise
    print(f"\n[5/5] Generating visualisations ...")
    plot_predictions(y, y_pred_scaled, args.window_size)
    plot_residuals(y_true_original, y_pred_original)

    # 6. Sample predictions
    print(f"\n  Sample predictions (last 10 timesteps):")
    print(f"  {'Actual':>12}  {'Predicted':>12}  {'Error':>10}  {'%Err':>8}")
    print(f"  {'─' * 46}")
    for i in range(len(y) - 10, len(y)):
        actual = y_true_original[i]
        predicted = y_pred_original[i]
        error = abs(actual - predicted)
        pct = (error / actual) * 100
        print(f"  {actual:>12.2f}  {predicted:>12.2f}  {error:>10.2f}  {pct:>7.2f}%")

    print(f"\n{'=' * 60}")
    print(" Evaluation complete.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
