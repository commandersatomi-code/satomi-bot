import pandas as pd
import numpy as np
import os
import sys

def profile_first_5m_simple(path_15m, path_5m):
    """
    Profile the 'First 5m Candle' of a large 15m Explosion.
    Focus on SIMPLE, ROBUST metrics to avoid overfitting.
    """
    print(f"\n========================================================")
    print(f"   Simple Profiling: First 5m of >1.5% 15m Candle")
    print(f"========================================================")
    
    if not os.path.exists(path_15m) or not os.path.exists(path_5m):
        print("Error: File not found.")
        return

    # Load 15m Data
    df_15 = pd.read_csv(path_15m)
    df_15['timestamp'] = pd.to_datetime(df_15['timestamp'])
    df_15['range_pct'] = (df_15['high'] - df_15['low']) / df_15['open'] * 100
    
    # Target: 15m Candle > 1.5% Range
    # (A robust 'Big Move', not extremely rare, but profitable)
    explosions = df_15[df_15['range_pct'] > 1.5].copy()
    print(f"Total 15m Explosions (>1.5%): {len(explosions):,}")
    
    # Load 5m Data
    df_5 = pd.read_csv(path_5m)
    df_5['timestamp'] = pd.to_datetime(df_5['timestamp'])
    df_5.set_index('timestamp', inplace=True)
    
    # Simple Metrics
    first_5m_ranges = []
    
    for idx, row in explosions.iterrows():
        start_time = row['timestamp']
        if start_time in df_5.index:
            c5 = df_5.loc[start_time]
            r_pct = (c5['high'] - c5['low']) / c5['open'] * 100
            first_5m_ranges.append(r_pct)
            
    # --- ROBUST STATISTICS ---
    # We use percentiles to find the "Minimum Viable Trigger"
    # If we set the trigger too high, we miss too many opportunities.
    # If too low, we get noise.
    # Let's see the distribution.
    
    ranges = np.array(first_5m_ranges)
    
    print(f"\n[Distribution of First 5m Range]")
    print(f"Mean:   {np.mean(ranges):.4f}%")
    print(f"Median: {np.median(ranges):.4f}%")
    
    print(f"\n[Potential Triggers (Percentiles)]")
    # If we want to catch 90% of these explosions, what is the minimum 5m move we need to see?
    p10 = np.percentile(ranges, 10) 
    print(f"To catch 90% of explosions, Trigger >= {p10:.4f}%")
    
    # To catch 75%
    p25 = np.percentile(ranges, 25)
    print(f"To catch 75% of explosions, Trigger >= {p25:.4f}%")
    
    # To catch 50% (The strongest ones)
    p50 = np.percentile(ranges, 50)
    print(f"To catch 50% of explosions, Trigger >= {p50:.4f}%")
    
    # Compare with Noise Level (Baseline 5m Median)
    print(f"\n(Reference: Normal 5m Median Range is ~0.15%)")

if __name__ == "__main__":
    profile_first_5m_simple(
        path_15m="data/bybit_btcusdt_linear_15m_full.csv",
        path_5m="data/bybit_btc_usdt_linear_5m_full.csv"
    )
