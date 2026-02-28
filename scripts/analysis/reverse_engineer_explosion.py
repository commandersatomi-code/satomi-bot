import pandas as pd
import numpy as np
import os
import sys

def reverse_engineer_explosion(filepath):
    """
    Reverse Engineering the Explosion. 
    
    1. Identify all 'Explosive' candles (Range > 1.0%).
    2. Analyze the 'Precursor' candles (the 5 candles immediately preceding the explosion).
    3. Look for common patterns:
       - Was it silent? (Low volatility)
       - Was there a volume spike?
       - Were there specific candlestick shapes (doji, hammer)?
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        return
    
    print(f"Loading data from: {filepath} ...")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Metrics
    df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
    df['body_pct'] = abs(df['open'] - df['close']) / df['open'] * 100
    df['upper_shadow'] = (df['high'] - df[['open', 'close']].max(axis=1)) / df['open'] * 100
    df['lower_shadow'] = (df[['open', 'close']].min(axis=1) - df['low']) / df['open'] * 100
    df['volume_ma_20'] = df['volume'].rolling(window=20).mean()
    df['vol_ratio'] = df['volume'] / df['volume_ma_20']
    
    # 1. Identify Explosions
    # Definition: Range > 1.0% (Top 1% move)
    EXPLOSION_THRESHOLD = 1.0
    df['is_explosion'] = df['range_pct'] > EXPLOSION_THRESHOLD
    
    explosion_indices = df.index[df['is_explosion']].tolist()
    total_explosions = len(explosion_indices)
    
    print(f"\n--- Reverse Engineering Report: The Precursors of Explosion ---")
    print(f"Total Explosions (> {EXPLOSION_THRESHOLD}%): {total_explosions} instances")
    
    # 2. Analyze Precursors (The candle immediately BEFORE the explosion: t-1)
    # We can also look at t-2, t-3, etc.
    
    precursor_stats = {
        'range_pct': [],
        'body_pct': [],
        'vol_ratio': [],
        'is_silent_01': [],  # Range < 0.1%
        'is_silent_02': [],  # Range < 0.2%
        'upper_shadow': [],
        'lower_shadow': []
    }
    
    # To capture context, let's analyze the 3 candles before explosion
    context_silent_count = [] # How many of the last 3 candles were silent (<0.2%)?
    
    valid_count = 0
    for idx in explosion_indices:
        if idx < 3: continue # Skip start of file
        
        # Immediate Precursor (t-1)
        prev_idx = idx - 1
        p_row = df.iloc[prev_idx]
        
        precursor_stats['range_pct'].append(p_row['range_pct'])
        precursor_stats['body_pct'].append(p_row['body_pct'])
        precursor_stats['vol_ratio'].append(p_row['vol_ratio'])
        precursor_stats['upper_shadow'].append(p_row['upper_shadow'])
        precursor_stats['lower_shadow'].append(p_row['lower_shadow'])
        precursor_stats['is_silent_01'].append(p_row['range_pct'] < 0.1)
        precursor_stats['is_silent_02'].append(p_row['range_pct'] < 0.2)
        
        # Context (t-3 to t-1)
        context = df.iloc[idx-3:idx]
        silent_candles = (context['range_pct'] < 0.2).sum()
        context_silent_count.append(silent_candles)
        
        valid_count += 1

    # --- STATISTICS OF THE PRECURSOR (t-1) ---
    print(f"\n[The Face of the Precursor (Immediate Previous Candle)]")
    print(f"Average Range: {np.mean(precursor_stats['range_pct']):.4f}% (Normal Avg: {df['range_pct'].mean():.4f}%)")
    print(f"Average Body:  {np.mean(precursor_stats['body_pct']):.4f}%")
    print(f"Average Volume Ratio: {np.mean(precursor_stats['vol_ratio']):.2f}x (vs 20MA)")
    
    print(f"\n[Was it Silent?]")
    silent_01_rate = np.mean(precursor_stats['is_silent_01']) * 100
    silent_02_rate = np.mean(precursor_stats['is_silent_02']) * 100
    print(f"Precursor < 0.1% Range: {silent_01_rate:.2f}% of the time")
    print(f"Precursor < 0.2% Range: {silent_02_rate:.2f}% of the time")
    
    # Compare to baseline probability of silence
    base_silent_01 = (df['range_pct'] < 0.1).mean() * 100
    base_silent_02 = (df['range_pct'] < 0.2).mean() * 100
    print(f"(Baseline Probability: <0.1%={base_silent_01:.2f}%, <0.2%={base_silent_02:.2f}%)")
    
    # --- CONTEXT ANALYSIS ---
    print(f"\n[Context (Last 3 Candles before Explosion)]")
    # Histogram of silent candles count
    counts = pd.Series(context_silent_count).value_counts(normalize=True).sort_index() * 100
    print(f"How many candles were 'Quiet' (<0.2%) in the 15 mins before explosion?")
    for k, v in counts.items():
        print(f"  {k} candles: {v:.2f}%")
        
    print("-" * 50)
    print("Insight: Does explosion arise from silence, or from existing volatility?")

if __name__ == "__main__":
    file_path = "data/bybit_btc_usdt_linear_5m_full.csv"
    reverse_engineer_explosion(file_path)
