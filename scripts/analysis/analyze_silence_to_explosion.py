import pandas as pd
import numpy as np
import os
import sys

def analyze_silence_to_explosion(filepath):
    """
    Backtest the 'Silence to Explosion' hypothesis. 
    
    Hypothesis:
    - If 5m candle range is extremely low (< 0.1%) for 3 consecutive candles,
    - An explosion (high volatility) is likely to follow immediately.
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        return
    
    print(f"Loading 5m data from: {filepath} ...")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate Range %
    df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
    df['body_pct'] = abs(df['open'] - df['close']) / df['open'] * 100
    
    # --- DEFINE SILENCE ---
    # Threshold: Range < 0.1% (Based on Median 0.15%)
    silence_threshold = 0.1
    
    df['is_silent'] = df['range_pct'] < silence_threshold
    
    # Check for 3 consecutive silent candles
    # We shift to look back: Current is quiet, Prev is quiet, Prev-Prev is quiet
    df['silence_3_candles'] = (
        df['is_silent'] & 
        df['is_silent'].shift(1) & 
        df['is_silent'].shift(2)
    )
    
    # The "Trigger" is the completion of the 3rd silent candle.
    # We want to see what happens in the NEXT candle (t+1) and next 3 candles (t+1 to t+3).
    
    # --- OUTCOME METRICS ---
    # 1. Next Candle Volatility (Absolute Move)
    df['next_range_pct'] = df['range_pct'].shift(-1)
    
    # 2. Next 3 Candles Max Move (Highest High - Lowest Low over next 3 / Current Close)
    # Using rolling window on reversed data or shifting
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=3)
    df['next_3_max'] = df['high'].rolling(window=indexer).max().shift(-1)
    df['next_3_min'] = df['low'].rolling(window=indexer).min().shift(-1)
    df['next_3_range_pct'] = (df['next_3_max'] - df['next_3_min']) / df['close'] * 100

    # Filter for Triggers
    events = df[df['silence_3_candles']].copy()
    
    total_candles = len(df)
    total_events = len(events)
    
    print(f"\n--- Analysis Results: Silence (3 candles < {silence_threshold}%) -> Explosion ---")
    print(f"Total Candles: {total_candles:,}")
    print(f"Silence Events Found: {total_events:,}")
    print(f"Frequency: Once every {total_candles / total_events:.1f} candles ({total_candles / total_events / 12:.1f} hours)")
    
    # --- STATS OF THE NEXT CANDLE ---
    avg_next_move = events['next_range_pct'].mean()
    median_next_move = events['next_range_pct'].median()
    
    # Compare with baseline
    baseline_avg = df['range_pct'].mean()
    
    print(f"\n[Immediate Reaction (Next 5m Candle)]")
    print(f"Baseline Avg Move: {baseline_avg:.4f}%")
    print(f"After Silence Avg: {avg_next_move:.4f}%  (Multiplier: x{avg_next_move/baseline_avg:.2f})")
    print(f"After Silence Median: {median_next_move:.4f}%")
    
    # Probability of Explosion (> 0.5% and > 1.0%)
    prob_05 = (events['next_range_pct'] > 0.5).sum() / total_events * 100
    prob_10 = (events['next_range_pct'] > 1.0).sum() / total_events * 100
    
    print(f"Probability of > 0.5% move: {prob_05:.2f}% (Baseline: {(df['range_pct']>0.5).mean()*100:.2f}%)")
    print(f"Probability of > 1.0% move: {prob_10:.2f}% (Baseline: {(df['range_pct']>1.0).mean()*100:.2f}%)")

    # --- STATS OF NEXT 15 MINUTES (3 Candles) ---
    avg_3_move = events['next_3_range_pct'].mean()
    prob_3_10 = (events['next_3_range_pct'] > 1.0).sum() / total_events * 100
    
    print(f"\n[Short-Term Trend (Next 15m / 3 Candles)]")
    print(f"Avg Max Range: {avg_3_move:.4f}%")
    print(f"Probability of > 1.0% trend: {prob_3_10:.2f}%")

    # --- TOP EXAMPLES ---
    print(f"\n[Top 5 Explosions after Silence]")
    events.sort_values('next_range_pct', ascending=False, inplace=True)
    print(events[['timestamp', 'close', 'range_pct', 'next_range_pct', 'next_3_range_pct']].head(5))

if __name__ == "__main__":
    file_path = "data/bybit_btc_usdt_linear_5m_full.csv"
    analyze_silence_to_explosion(file_path)
