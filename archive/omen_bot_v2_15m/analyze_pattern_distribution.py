import pandas as pd
import numpy as np
import os

def analyze_distributions():
    """
    Analyzes the distribution of outcomes from the saved inter-precursor pattern CSV files.
    """
    print("\n--- Analyzing Pattern Distributions (move_window_hours=6) ---")
    
    # Define the path to the data directory
    # This assumes the script is run from the root of the 'バシャール' project directory
    data_dir = os.path.join('omen_bot', 'data')
    
    # --- 1. Analyze the "Buy to Sell" Pattern ---
    buy_to_sell_path = os.path.join(data_dir, 'inter_precursor_buy_to_sell_move_window_6h.csv')
    try:
        df_bs = pd.read_csv(buy_to_sell_path)
        print("\n--- Pattern: Buy -> Sell ---")
        print(f"Found {len(df_bs)} occurrences.")
        
        # Convert to percentage for easier reading
        df_bs['max_rise_pct'] *= 100
        df_bs['max_fall_pct'] *= 100
        
        print("\nDistribution of Max Rise (%):")
        print(df_bs['max_rise_pct'].describe(percentiles=[.1, .25, .5, .75, .9]))
        
        print("\nDistribution of Max Fall (%):")
        print(df_bs['max_fall_pct'].describe(percentiles=[.1, .25, .5, .75, .9]))

    except FileNotFoundError:
        print(f"\nFile not found: {buy_to_sell_path}")

    # --- 2. Analyze the "Sell to Buy" Pattern ---
    sell_to_buy_path = os.path.join(data_dir, 'inter_precursor_sell_to_buy_move_window_6h.csv')
    try:
        df_sb = pd.read_csv(sell_to_buy_path)
        print("\n\n--- Pattern: Sell -> Buy ---")
        print(f"Found {len(df_sb)} occurrences.")

        # Convert to percentage
        df_sb['max_rise_pct'] *= 100
        df_sb['max_fall_pct'] *= 100

        print("\nDistribution of Max Rise (%):")
        print(df_sb['max_rise_pct'].describe(percentiles=[.1, .25, .5, .75, .9]))

        print("\nDistribution of Max Fall (%):")
        print(df_sb['max_fall_pct'].describe(percentiles=[.1, .25, .5, .75, .9]))

    except FileNotFoundError:
        print(f"\nFile not found: {sell_to_buy_path}")


if __name__ == '__main__':
    analyze_distributions()
