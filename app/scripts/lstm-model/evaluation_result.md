
Evaluation Results

Metrics (5,000 samples, April 2024 data)

┌────────┬─────────┐
│ Metric │ Value   │
├────────┼─────────┤
│ RMSE   │ $129.57 │
├────────┼─────────┤
│ MAE    │ $92.80  │
├────────┼─────────┤
│ MAPE   │ 0.14%   │
├────────┼─────────┤
│ R²     │ 0.9945  │
└────────┴─────────┘

Sample Predictions (last 10 timesteps)

┌────────────┬────────────┬─────────┬───────┐
│ Actual     │ Predicted  │ Error   │ %Err  │
├────────────┼────────────┼─────────┼───────┤
│ $66,132.70 │ $66,294.97 │ $162.27 │ 0.25% │
├────────────┼────────────┼─────────┼───────┤
│ $66,174.80 │ $66,278.91 │ $104.11 │ 0.16% │
├────────────┼────────────┼─────────┼───────┤
│ $66,181.80 │ $66,265.19 │ $83.39  │ 0.13% │
├────────────┼────────────┼─────────┼───────┤
│ ...        │ ...        │ ...     │ ...   │
├────────────┼────────────┼─────────┼───────┤
│ $66,219.80 │ $66,241.50 │ $21.70  │ 0.03% │
└────────────┴────────────┴─────────┴───────┘

What the Script Does

1. Load Data — Reads CSVs from  test/ , mirrors training pipeline
2. Prepare Sequences — Creates sequences with window=60 (same as training)
3. Load Model — Loads the  .h5  model and prints architecture summary
4. Generate Predictions — Runs inference on test sequences
5. Compute Metrics — RMSE, MAE, MAPE, R² on unscaled data
6. Visualize — Saves  prediction_vs_actual.png  and  residual_histogram.png 
7. Sample Output — Shows last 10 predictions with error analysis

Usage

# Full dataset (all 10.4M rows — slow on CPU)
python evaluate_model.py

# Sample subset for quick evaluation
python evaluate_model.py --sample-size 5000

# Custom model path and data directory
python evaluate_model.py --model my_model.h5 --data-dir ./custom_data

The model performs very well on this time period with R² = 0.9945 and only 0.14% MAPE. To evaluate on different periods, you can specify different CSV files in the data directory.