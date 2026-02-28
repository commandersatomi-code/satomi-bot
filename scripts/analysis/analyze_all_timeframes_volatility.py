import pandas as pd
import numpy as np
import os
import sys

def analyze_single_timeframe(df, label):
    """
    Calculate and print statistics for a single dataframe.
    """
    # Calculate Percent Range (Range % = (High - Low) / Open * 100)
    df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
    
    mean_val = df['range_pct'].mean()
    median_val = df['range_pct'].median()
    max_val = df['range_pct'].max()
    
    # Percentiles
    p90 = np.percentile(df['range_pct'], 90)
    p95 = np.percentile(df['range_pct'], 95)
    p99 = np.percentile(df['range_pct'], 99)
    
    print(f"\n=== {label} Volatility Analysis ===")
    print(f"Data Count: {len(df):,} candles")
    print(f"Period: {df['timestamp'].min()} - {df['timestamp'].max()}")
    print("-" * 30)
    print(f"Average Move (Mean):   {mean_val:.4f}%")
    print(f"Typical Move (Median): {median_val:.4f}%")
    print("-" * 30)
    print(f"[Thresholds for 'Big Moves']")
    print(f"Top 10%  (> {p90:.4f}%): occurs once every ~10 candles")
    print(f"Top 5%   (> {p95:.4f}%): occurs once every ~20 candles")
    print(f"Top 1%   (> {p99:.4f}%): occurs once every ~100 candles (The Explosion)")
    print("-" * 30)
    print(f"Largest Move Recorded: {max_val:.4f}% on {df.loc[df['range_pct'].idxmax(), 'timestamp']}")
    
    return {
        'label': label,
        'mean': mean_val,
        'median': median_val,
        'top_1_pct': p99
    }

def main():
    base_dir = "data"
    files = [
        ("5-Minute (5m)", "bybit_btc_usdt_linear_5m_full.csv"),
        ("15-Minute (15m)", "bybit_btcusdt_linear_15m_full.csv"), 
        ("1-Hour (1h)", "bybit_btcusdt_linear_1h_full.csv"),
    ]
    
    # Handle filename variation for 15m (btcusdt vs btc_usdt)
    if not os.path.exists(os.path.join(base_dir, files[1][1])):
        files[1] = ("15-Minute (15m)", "bybit_btc_usdt_linear_15m_full.csv")

    summary_stats = []

    for label, filename in files:
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            try:
                # Read only necessary columns to save memory/time
                df = pd.read_csv(filepath, usecols=['timestamp', 'open', 'high', 'low'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                stats = analyze_single_timeframe(df, label)
                summary_stats.append(stats)
            except Exception as e:
                print(f"Error analyzing {label}: {e}")
        else:
            print(f"Warning: File not found for {label} at {filepath}")

    # --- Comparative Summary ---
    print("\n\n################################################")
    print("###       CROSS-TIMEFRAME COMPARISON         ###")
    print("################################################")
    print(f"{ 'Timeframe':<15} | { 'Median Move':<12} | { 'Top 1% (Explosion)':<20}")
    print("-" * 55)
    for s in summary_stats:
        print(f"{s['label']:<15} | {s['median']:.4f}%      | > {s['top_1_pct']:.4f}%")
    print("-" * 55)
    print("Insight: To catch a 1h explosion on a 5m chart, you need a sustained run.")

if __name__ == "__main__":
    main()
