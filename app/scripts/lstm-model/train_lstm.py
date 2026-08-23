import os
import glob
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

def load_data(data_dir):
    """Loads all CSV files from the specified directory and concatenates them."""
    all_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not all_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    
    df_list = []
    for filename in all_files:
        # Based on previous inspection, files do not have headers.
        # Columns: timestamp, open, high, low, close, volume, other
        df = pd.read_csv(filename, header=None, names=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'other'])
        df_list.append(df)
    
    full_df = pd.concat(df_list, ignore_index=True)
    full_df = full_df.sort_values('timestamp')
    return full_df

def prepare_data(data, window_size=60):
    """Scales the 'close' price and creates sequences for LSTM training."""
    scaler = MinMaxScaler(feature_range=(0, 1))
    # We are focusing on predicting the 'close' price
    scaled_data = scaler.fit_transform(data[['close']].values)
    
    X = []
    y = []
    
    for i in range(window_size, len(scaled_data)):
        X.append(scaled_data[i-window_size:i, 0])
        y.append(scaled_data[i, 0])
        
    X, y = np.array(X), np.array(y)
    # Reshape X to be [samples, time steps, features]
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    
    return X, y, scaler

def train_model(X_train, y_train, epochs=10, batch_size=32):
    """Defines and trains the LSTM model."""
    model = Sequential([
        LSTM(units=50, return_sequences=True, input_shape=(60, 1)),  # Layer 1
        Dropout(0.2),                                                 # Dropout 1
        LSTM(units=50, return_sequences=False),                      # Layer 2
        Dropout(0.2),                                                 # Dropout 2
        Dense(units=25),                                              # Hidden
        Dense(units=1)                                                # Output
    ])
    
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(X_train, y_train, batch_size=batch_size, epochs=epochs)
    return model

if __name__ == "__main__":
    # Get the directory where the script is located
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'test')
    MODEL_PATH = os.path.join(BASE_DIR, 'lstm_model.h5')
    
    WINDOW_SIZE = 60
    EPOCHS = 5  # Set low for initial run/verification
    BATCH_SIZE = 32

    try:
        print(f"Loading data from {DATA_DIR}...")
        df = load_data(DATA_DIR)
        print(f"Successfully loaded {len(df)} rows of data.")
        
        print("Preparing sequences for training...")
        X, y, scaler = prepare_data(df, WINDOW_SIZE)
        print(f"Created {len(X)} training samples.")
        
        print("Starting model training...")
        model = train_model(X, y, epochs=EPOCHS, batch_size=BATCH_SIZE)
        
        print(f"Saving trained model to {MODEL_PATH}...")
        model.save(MODEL_PATH)
        print("Training complete and model saved successfully.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
