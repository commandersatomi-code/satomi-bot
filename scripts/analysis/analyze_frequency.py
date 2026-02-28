import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta, timezone

def analyze_frequency(file_path: str):
    """
    Analyzes the frequency of specific price change thresholds in a dataset.
    """
    print(f"--- Analyzing Frequency for: {file_path} ---")
    
    try:
        # Load data and apply training data rule
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Standardize timestamp to UTC to handle both naive and aware datetimes
        if df['timestamp'].dt.tz is None:
            # If naive, assume UTC and localize
            df['timestamp'] = df['timestamp'].dt.tz_localize('utc')
        else:
            # If already aware, convert to UTC
            df['timestamp'] = df['timestamp'].dt.tz_convert('utc')

        split_date = datetime.now(timezone.utc) - timedelta(days=365)
        training_df = df[df['timestamp'] < split_date].copy()
        
        if training_df.empty:
            print("No training data available for this timeframe.")
            print("-" * 50)
            return

        # Calculate percentage change
        training_df['change_pct'] = ((training_df['close'] - training_df['open']) / training_df['open']) * 100
        
        total_candles = len(training_df)
        if total_candles == 0:
            print("No data in the training period.")
            print("-" * 50)
            return

        # Define thresholds
        thresholds = [0.5, 1.0, 2.0, 3.0, 5.0]
        
        print("\n--- Frequencies of Price Changes ---")
        
        # Negative thresholds
        print("\n--- Negative Changes (≤) ---")
        for t in sorted(thresholds):
            count = training_df[training_df['change_pct'] <= -t].shape[0]
            frequency = (count / total_candles) * 100
            print(f"Frequency of change ≤ {-t:>4.1f}%: {frequency:>7.4f}%  ({count}/{total_candles} candles)")

        # Positive thresholds
        print("\n--- Positive Changes (≥) ---")
        for t in sorted(thresholds):
            count = training_df[training_df['change_pct'] >= t].shape[0]
            frequency = (count / total_candles) * 100
            print(f"Frequency of change ≥ {t:>4.1f}%:  {frequency:>7.4f}%  ({count}/{total_candles} candles)")
            
        # Max changes
        max_up = training_df['change_pct'].max()
        max_down = training_df['change_pct'].min()
        print("\n--- Maximum Observed Change ---")
        print(f"Max Rise:  {max_up:.4f}%")
        print(f"Max Drop:  {max_down:.4f}%")

        print("-" * 50)

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze the frequency of price changes in a dataset.")
    parser.add_argument("file", type=str, help="Path to the input CSV file.")
    args = parser.parse_args()
    analyze_frequency(args.file)
