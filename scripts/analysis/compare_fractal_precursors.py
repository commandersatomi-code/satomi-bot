import pandas as pd
import numpy as np
import os
import sys

def analyze_precursor_relationship(parent_path, child_path, parent_label, child_label, explosion_threshold_pct):
    """
    Analyze the relationship between a Parent Candle Explosion and its Child Candles Precursors.
    
    Ex: Parent=15m, Child=5m.
    1. Find Parent candles with Range > explosion_threshold_pct.
    2. Look at the Child candles that corresponds to the time IMMEDIATELY BEFORE the Parent candle.
       (The 'Precursor' phase).
    """
    print(f"\n========================================================")
    print(f"   Analyzing: {child_label} (Precursor) -> {parent_label} (Explosion)")
    print(f"========================================================")
    
    if not os.path.exists(parent_path) or not os.path.exists(child_path):
        print("Error: File not found.")
        return

    # Load Data
    p_df = pd.read_csv(parent_path)
    p_df['timestamp'] = pd.to_datetime(p_df['timestamp'])
    p_df['range_pct'] = (p_df['high'] - p_df['low']) / p_df['open'] * 100
    
    c_df = pd.read_csv(child_path)
    c_df['timestamp'] = pd.to_datetime(c_df['timestamp'])
    c_df['range_pct'] = (c_df['high'] - c_df['low']) / c_df['open'] * 100
    c_df['body_pct'] = abs(c_df['open'] - c_df['close']) / c_df['open'] * 100
    c_df['volume_ma'] = c_df['volume'].rolling(20).mean()
    c_df['vol_ratio'] = c_df['volume'] / c_df['volume_ma']
    
    # Identify Explosions in Parent
    # We use the threshold (e.g., 1.0% or 2.0%)
    explosions = p_df[p_df['range_pct'] > explosion_threshold_pct]
    print(f"Target: Parent Candles > {explosion_threshold_pct}% Range")
    print(f"Total Explosions Found: {len(explosions):,}")
    
    # Analyze Precursors in Child
    # Logic: If Parent candle starts at T, we want to look at Child candles ending at T (or just before T).
    # Actually, "Precursor" means the time BEFORE the explosion.
    # So if 15m candle starts at 10:00, we look at 5m candles at 09:45, 09:50, 09:55.
    
    precursor_stats = {
        'avg_range': [],
        'avg_vol_ratio': [],
        'silent_count': 0, # How many times was the child candle 'Silent' (<0.1%)
        'total_child_candles': 0
    }
    
    # Optimization: Create a lookup or set index for faster access
    c_df.set_index('timestamp', inplace=True)
    
    # Child interval duration (e.g., 5 min or 15 min)
    if '5m' in child_label:
        lookback_delta = pd.Timedelta(minutes=5)
        num_lookback = 3 # Look at last 3 candles (15 mins before)
    elif '15m' in child_label:
        lookback_delta = pd.Timedelta(minutes=15)
        num_lookback = 4 # Look at last 4 candles (1 hour before)
    
    count_valid = 0
    
    for idx, row in explosions.iterrows():
        start_time = row['timestamp']
        
        # Gather child candles immediately BEFORE start_time
        # e.g., if explosion starts at 10:00, we want 09:55, 09:50, 09:45...
        
        current_stats_range = []
        current_stats_vol = []
        
        for i in range(1, num_lookback + 1):
            target_time = start_time - (lookback_delta * i)
            if target_time in c_df.index:
                child_row = c_df.loc[target_time]
                current_stats_range.append(child_row['range_pct'])
                current_stats_vol.append(child_row['vol_ratio'])
                
                if child_row['range_pct'] < 0.1: # Silence definition
                    precursor_stats['silent_count'] += 1
                
                precursor_stats['total_child_candles'] += 1
        
        if current_stats_range:
            precursor_stats['avg_range'].append(np.mean(current_stats_range))
            precursor_stats['avg_vol_ratio'].append(np.mean(current_stats_vol))
            count_valid += 1

    # --- REPORT ---
    print(f"\n[Precursor Profile (Immediate {num_lookback} candles before Explosion)]")
    
    avg_pre_range = np.mean(precursor_stats['avg_range'])
    avg_pre_vol = np.mean(precursor_stats['avg_vol_ratio'])
    silence_rate = (precursor_stats['silent_count'] / precursor_stats['total_child_candles']) * 100 if precursor_stats['total_child_candles'] > 0 else 0
    
    print(f"Average Range: {avg_pre_range:.4f}%")
    print(f"Average Vol Ratio: {avg_pre_vol:.2f}x")
    print(f"Silence Rate (<0.1%): {silence_rate:.2f}%")
    
    # Baseline comparison
    base_range = c_df['range_pct'].mean()
    base_silence = (c_df['range_pct'] < 0.1).mean() * 100
    
    print(f"\n(Baseline for {child_label}: AvgRange={base_range:.4f}%, SilenceRate={base_silence:.2f}%)")
    
    # Signal Quality (Deviation from baseline)
    print(f"\n[Signal Clarity Score]")
    range_diff = (avg_pre_range / base_range)
    print(f"Volatility Pre-signal: {range_diff:.2f}x normal activity")
    print(f"Is it quieter than usual? {'YES' if silence_rate > base_silence else 'NO'}")

def main():
    # 1. Compare 5m Precursors -> 15m Explosion (>1.0%)
    analyze_precursor_relationship(
        parent_path="data/bybit_btcusdt_linear_15m_full.csv",
        child_path="data/bybit_btc_usdt_linear_5m_full.csv",
        parent_label="15m",
        child_label="5m",
        explosion_threshold_pct=1.0
    )
    
    # 2. Compare 15m Precursors -> 1h Explosion (>2.0%)
    analyze_precursor_relationship(
        parent_path="data/bybit_btcusdt_linear_1h_full.csv",
        child_path="data/bybit_btcusdt_linear_15m_full.csv",
        parent_label="1h",
        child_label="15m",
        explosion_threshold_pct=2.0
    )

if __name__ == "__main__":
    main()
