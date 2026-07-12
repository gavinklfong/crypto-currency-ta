import sys
import time
import datetime
import pandas as pd
import numpy as np

def run_ta(symbol, timeframe):
    print(f"[{datetime.datetime.now()}] Starting TA job for {symbol} with timeframe {timeframe}...")
    
    # Simulate fetching data
    print(f"[{datetime.datetime.now()}] Fetching market data for {symbol}...")
    time.sleep(5)
    
    # Create dummy data
    data = {
        'timestamp': pd.date_range(start=datetime.datetime.now() - datetime.timedelta(hours=24), periods=100, freq='T'),
        'close': np.random.uniform(30000, 40000, 100)
    }
    df = pd.DataFrame(data)
    
    # Calculate EMA
    print(f"[{datetime.datetime.now()}] Calculating EMA...")
    df['ema'] = df['close'].ewm(span=20, adjust=False).mean()
    
    print(f"[{datetime.datetime.now()}] TA calculation complete!")
    print(df.tail())

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 ta_job.py <symbol> <timeframe>")
        sys.exit(1)
    run_ta(sys.argv[1], sys.argv[2])
