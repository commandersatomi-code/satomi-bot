import pandas as pd
import numpy as np
import os
import sys

def analyze_continuation_probability(filepath, label):
    """
    Analyze the probability of price continuation based on candle body size.
    
    Question: "If current candle moves X%, what is the probability the NEXT candle continues in the same direction?"
    """
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate Body Size (%)
    # Body = (Close - Open) / Open * 100
    df['body_pct'] = (df['close'] - df['open']) / df['open'] * 100
    df['abs_body'] = abs(df['body_pct'])
    df['direction'] = np.sign(df['body_pct']) # 1 for Up, -1 for Down
    
    # Calculate NEXT Candle's Return
    df['next_close'] = df['close'].shift(-1)
    df['next_return'] = (df['next_close'] - df['close']) / df['close'] * 100
    
    # Did it continue? (Same sign)
    df['is_continuation'] = (np.sign(df['next_return']) == df['direction']) & (df['next_return'] != 0)
    
    print(f"\n========================================================")
    print(f"   Continuation Analysis: {label}")
    print(f"========================================================")
    print(f"Total Candles: {len(df):,}")
    
    # Define Bins for Body Size (e.g., 0.0-0.1, 0.1-0.2, ... up to >2.0)
    bins = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0, 100.0]
    labels = [f"{bins[i]}%-{bins[i+1]}%" for i in range(len(bins)-1)]
    labels[-1] = "> 2.0%"
    
    df['bin'] = pd.cut(df['abs_body'], bins=bins, labels=labels, right=False)
    
    # Group by Bin and Calculate Stats
    stats = df.groupby('bin', observed=False).agg(
        count=('body_pct', 'count'),
        win_rate=('is_continuation', 'mean'),
        avg_next_return=('next_return', 'mean'), # Simple return (mix of pos/neg)
        avg_continuation_mag=('next_return', lambda x: abs(x).mean()) # Magnitude of next move
    )
    
    # Display Result
    print(f"{ 'Body Size':<12} | {'Count':<8} | {'Win Rate (Continuation)':<25} | {'Next Candle Mag':<15}")
    print("-" * 75)
    
    for idx, row in stats.iterrows():
        win_rate = row['win_rate'] * 100
        # Determine "Edge"
        edge_str = ""
        if win_rate > 52: edge_str = ">> TREND"
        if win_rate < 48: edge_str = "<< REVERT"
        
        print(f"{idx:<12} | {row['count']:8,} | {win_rate:6.2f}% {edge_str:<10} | {row['avg_continuation_mag']:.4f}%")

def main():
    files = [
        ("5-Minute (5m)", "data/bybit_btc_usdt_linear_5m_full.csv"),
        ("15-Minute (15m)", "data/bybit_btcusdt_linear_15m_full.csv"),
        ("1-Hour (1h)", "data/bybit_btcusdt_linear_1h_full.csv"),
    ]
    
    for label, path in files:
        analyze_continuation_probability(path, label)

if __name__ == "__main__":
    main()
