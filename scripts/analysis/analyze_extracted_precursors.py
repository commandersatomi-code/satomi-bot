import pandas as pd
import numpy as np
import os

def analyze_extracted_precursors(file_path: str):
    """
    Reads the CSV of precursor/move pairs and calculates summary statistics
    for the precursor candles, grouped by the direction of the large move.
    """
    print(f"--- Statistically Analyzing Precursors from: {file_path} ---")

    try:
        df = pd.read_csv(file_path, parse_dates=['precursor_timestamp', 'timestamp'])

        # Add helper columns for precursor candle color
        df['precursor_is_bullish'] = df['precursor_close'] > df['precursor_open']
        df['precursor_is_bearish'] = df['precursor_close'] < df['precursor_open']
        
        # Separate into rises and falls
        rises_df = df[df['move_change_pct'] >= 10].copy()
        falls_df = df[df['move_change_pct'] <= -10].copy()

        print("\n" + "="*60)
        print("           ANALYSIS OF PRECURSORS BEFORE LARGE RISES")
        print("="*60)
        if not rises_df.empty:
            print(f"\nFound {len(rises_df)} precursors to analyze.")
            
            print("\n--- Precursor Body Ratio (precursor_body_ratio) ---")
            print(rises_df['precursor_body_ratio'].describe())
            
            print("\n--- Precursor Volume Multiplier (precursor_vol_mult) ---")
            print(rises_df['precursor_vol_mult'].describe())

            print("\n--- Precursor Candle Color Distribution ---")
            color_counts = rises_df[['precursor_is_bullish', 'precursor_is_bearish']].sum()
            color_counts['doji'] = len(rises_df) - color_counts.sum()
            color_pct = (color_counts / len(rises_df)) * 100
            print(color_counts.rename(index={'precursor_is_bullish': 'Bullish', 'precursor_is_bearish': 'Bearish'}))
            print("\nPercentage:")
            print(color_pct.rename(index={'precursor_is_bullish': 'Bullish', 'precursor_is_bearish': 'Bearish'}).round(2))
        else:
            print("No large rise events to analyze.")


        print("\n" + "="*60)
        print("           ANALYSIS OF PRECURSORS BEFORE LARGE FALLS")
        print("="*60)
        if not falls_df.empty:
            print(f"\nFound {len(falls_df)} precursors to analyze.")
            
            print("\n--- Precursor Body Ratio (precursor_body_ratio) ---")
            print(falls_df['precursor_body_ratio'].describe())
            
            print("\n--- Precursor Volume Multiplier (precursor_vol_mult) ---")
            print(falls_df['precursor_vol_mult'].describe())

            print("\n--- Precursor Candle Color Distribution ---")
            color_counts = falls_df[['precursor_is_bullish', 'precursor_is_bearish']].sum()
            color_counts['doji'] = len(falls_df) - color_counts.sum()
            print(color_counts.rename(index={'precursor_is_bullish': 'Bullish', 'precursor_is_bearish': 'Bearish'}))
            print("\nPercentage:")
            print(color_pct.rename(index={'precursor_is_bullish': 'Bullish', 'precursor_is_bearish': 'Bearish'}).round(2))
        else:
            print("No large fall events to analyze.")
            
        print("\n--- Analysis Complete ---")

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    analyze_extracted_precursors('daily_large_move_precursors.csv')
