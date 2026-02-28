import pandas as pd
import numpy as np
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def analyze_frequency(file_path):
    """
    Analyzes the frequency of price movements of different ranges.
    """
    logging.info(f"--- Starting Price Movement Frequency Analysis ---")
    logging.info(f"Loading data from: {file_path}")

    # --- Load Data ---
    try:
        df = pd.read_csv(file_path, parse_dates=['timestamp'], index_col='timestamp')
        logging.info(f"Data loaded. Analyzing {len(df)} candles.")
    except FileNotFoundError:
        logging.error(f"Error: Price data not found at {file_path}.")
        return

    # --- Calculate Price Change ---
    df['price_change_pct'] = ((df['close'] - df['open']) / df['open']) * 100
    logging.info("Calculated price change percentage.")

    # --- Define Ranges and Count Frequencies ---
    bins = np.arange(-5.0, 5.5, 0.5)
    labels = [f"{i:.1f}% to {i+0.5:.1f}%" for i in bins[:-1]]
    
    df['range'] = pd.cut(df['price_change_pct'], bins=bins, labels=labels, right=False)
    
    frequency_counts = df['range'].value_counts().sort_index()
    
    total_candles = len(df)
    frequency_percentage = (frequency_counts / total_candles) * 100

    # --- Print Results ---
    logging.info("\n--- Price Movement Frequency Distribution ---")
    
    results_df = pd.DataFrame({
        'Range': frequency_counts.index,
        'Frequency': frequency_counts.values,
        'Percentage (%)': frequency_percentage.values.round(2)
    })
    
    print(results_df.to_string(index=False))
    
    logging.info("\n--- Analysis Finished ---")


if __name__ == '__main__':
    # Assuming the data file is in the root data directory
    DATA_FILE = 'data/bybit_btc_usdt_linear_1h_full.csv'
    analyze_frequency(DATA_FILE)
