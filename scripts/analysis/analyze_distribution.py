
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta

def analyze_distribution(file_path):
    """
    Analyzes the distribution of price changes for a given dataset,
    including counting candles within specified percentage ranges.

    Args:
        file_path (str): The path to the CSV file.
    """
    print(f"--- Analyzing: {file_path} ---")
    
    try:
        # Load the data
        df = pd.read_csv(file_path)

        # Ensure required columns exist
        required_columns = ['timestamp', 'open', 'close']
        if not all(col in df.columns for col in required_columns):
            print(f"Error: Missing one of the required columns: {required_columns}")
            return

        # Convert open_time to datetime objects
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # --- Data Splitting Rule ---
        # Exclude the last year of data for testing
        split_date = datetime.now() - timedelta(days=365)
        training_df = df[df['timestamp'] < split_date].copy()
        
        if training_df.empty:
            print("No data available before the one-year cutoff date.")
            return

        # Calculate the percentage change from open to close
        training_df['change_pct'] = ((training_df['close'] - training_df['open']) / training_df['open']) * 100

        # Define the percentiles to calculate
        percentiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
        
        # Calculate the distribution
        dist = training_df['change_pct'].quantile(percentiles)

        # Print the results
        print("Distribution of Open-to-Close Percentage Change (Training Data):")
        for p in percentiles:
            print(f"{p*100: >3.0f}th percentile: {dist.loc[p]: >7.4f}%")
        print("-" * (len(file_path) + 14))
        print("\n")

        # --- New: Analyze movement counts ---
        print("--- Candle Movement Counts (Open-to-Close Percentage Change) ---")
        bins = [-np.inf, -5, -4, -3, -2, -1, -0.5, 0, 0.5, 1, 2, 3, 4, 5, np.inf]
        labels = [
            "< -5%",
            "-5% to -4%",
            "-4% to -3%",
            "-3% to -2%",
            "-2% to -1%",
            "-1% to -0.5%",
            "-0.5% to 0%",
            "0% to 0.5%",
            "0.5% to 1%",
            "1% to 2%",
            "2% to 3%",
            "3% to 4%",
            "4% to 5%",
            "> 5%"
        ]

        training_df['change_bin'] = pd.cut(training_df['change_pct'], bins=bins, labels=labels, right=False)
        movement_counts = training_df['change_bin'].value_counts().sort_index()
        movement_percentages = training_df['change_bin'].value_counts(normalize=True).sort_index() * 100

        print(f"{'Movement Range':<20} | {'Count':<10} | {'Percentage':<10}")
        print("-" * 45)
        for label in labels:
            count = movement_counts.get(label, 0)
            percentage = movement_percentages.get(label, 0.0)
            print(f"{label:<20} | {count:<10} | {percentage:<9.2f}%")
        print("-" * 45)
        print("\n")


    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze the distribution of price changes from a CSV file.")
    parser.add_argument("file", type=str, help="Path to the input CSV file.")
    args = parser.parse_args()
    analyze_distribution(args.file)
