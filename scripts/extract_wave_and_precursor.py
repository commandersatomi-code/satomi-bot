
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta

def calculate_indicators(df):
    """Calculates body_ratio and vol_mult for the dataframe."""
    df['body_size'] = abs(df['close'] - df['open'])
    df['high_low_range'] = df['high'] - df['low']
    # Avoid division by zero for doji candles
    df['body_ratio'] = df['body_size'] / df['high_low_range'].replace(0, np.nan)
    
    # Volume multiplier based on a 20-period SMA
    vol_sma = df['volume'].rolling(window=20, min_periods=1).mean()
    df['vol_mult'] = df['volume'] / vol_sma.replace(0, np.nan)
    return df

def extract_waves_and_precursors(file_path: str, threshold: float):
    """
    Finds large price moves and extracts the candle immediately preceding them,
    saving the pairs to a new CSV file for analysis.
    """
    print(f"--- Extracting Large Waves & Precursors from: {file_path} ---")
    
    try:
        # 1. Load data and apply training data rule
        df = pd.read_csv(file_path, parse_dates=['timestamp'])
        
        # We need to calculate indicators on the full dataset before splitting,
        # to ensure the rolling means are accurate.
        df = calculate_indicators(df)

        split_date = datetime.now() - timedelta(days=365)
        training_df = df[df['timestamp'] < split_date].copy()
        
        if training_df.empty:
            print("No training data available.")
            return

        # 2. Calculate the change for each candle
        training_df['move_change_pct'] = 100 * (training_df['close'] - training_df['open']) / training_df['open']

        # 3. Get the precursor candle's data using shift(1)
        precursor_cols = {
            'timestamp': 'precursor_timestamp',
            'open': 'precursor_open',
            'high': 'precursor_high',
            'low': 'precursor_low',
            'close': 'precursor_close',
            'volume': 'precursor_volume',
            'body_ratio': 'precursor_body_ratio',
            'vol_mult': 'precursor_vol_mult'
        }
        precursor_df = training_df[precursor_cols.keys()].shift(1).rename(columns=precursor_cols)

        # 4. Combine the original data with the precursor data
        combined_df = pd.concat([precursor_df, training_df], axis=1)

        # 5. Filter for the large moves
        large_moves_df = combined_df[abs(combined_df['move_change_pct']) >= threshold].copy()
        
        # Clean up columns for the final output
        output_cols = list(precursor_cols.values()) + [
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'move_change_pct'
        ]
        final_df = large_moves_df[output_cols]

        # 6. Save the results to a new CSV
        output_file = 'daily_large_move_precursors.csv'
        print(f"Found {len(final_df)} large move events (≥ +/-{threshold}%).")
        print(f"Saving precursor/move pairs to {output_file}...")
        final_df.to_csv(output_file, index=False, float_format='%.4f')

        print(f"\n--- Extraction Complete ---")
        print(f"Data saved to {output_file}. You can now observe this file.")

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    extract_waves_and_precursors(
        file_path='data/bybit_btc_usdt_linear_daily_full.csv',
        threshold=10.0
    )
