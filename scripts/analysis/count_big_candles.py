import pandas as pd
import numpy as np
import os
import sys

def count_big_candles_for_file(filepath, timeframe_name):
    """
    Count the frequency of 'Big Candles' at various thresholds.
    Focus purely on the frequency of occurrence to validate feasibility.
    """
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate Range % (High - Low) / Open
    df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
    
    total_candles = len(df)
    duration_days = (df['timestamp'].max() - df['timestamp'].min()).days
    if duration_days == 0: duration_days = 1
    
    print(f"\n========================================================")
    print(f"   Analysis for: {timeframe_name}")
    print(f"========================================================")
    print(f"Total Data: {total_candles:,} candles over {duration_days:,} days ({duration_days/365.25:.1f} years)")
    print(f"Period: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Thresholds to check
    thresholds = [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
    
    print(f"\n{'-'*70}")
    print(f"{ 'Range > X%':<12} | {'Count':<8} | {'% of Total':<10} | {'Avg Frequency':<25}")
    print(f"{'-'*70}")
    
    for th in thresholds:
        count = (df['range_pct'] > th).sum()
        pct = (count / total_candles) * 100
        
        # Calculate Frequency
        avg_per_day = count / duration_days
        avg_per_week = avg_per_day * 7
        avg_per_month = avg_per_day * 30
        
        freq_str = ""
        if avg_per_day >= 1:
            freq_str = f"{avg_per_day:.1f} times / day"
        elif avg_per_week >= 1:
            freq_str = f"{avg_per_week:.1f} times / week"
        elif count > 0:
            freq_str = f"{avg_per_month:.1f} times / month"
        else:
            freq_str = "Never"
            
        print(f"> {th:5.1f}%     | {count:8,} | {pct:9.2f}% | {freq_str}")
        
    print(f"{'-'*70}")
    print(f"Max Single Candle Move: {df['range_pct'].max():.2f}%")

def main():
    files = [
        ("5-Minute (5m)", "data/bybit_btc_usdt_linear_5m_full.csv"),
        ("15-Minute (15m)", "data/bybit_btcusdt_linear_15m_full.csv"),
        ("1-Hour (1h)", "data/bybit_btcusdt_linear_1h_full.csv"),
    ]
    
    for label, path in files:
        count_big_candles_for_file(path, label)

if __name__ == "__main__":
    main()
