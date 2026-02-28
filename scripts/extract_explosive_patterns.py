import pandas as pd
import numpy as np
import os

def extract_explosive_patterns(filepath, output_csv="data/explosive_patterns.csv"):
    """
    Extracts 'Explosive Patterns' for manual inspection and invention.
    Target: 15m candles with > 2.0% range.
    Output: The 12 preceding 5m candles (1 hour context) for each explosion.
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        return

    print(f"Loading 5m data from: {filepath} ...")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # We need to construct 15m candles from 5m data to be precise about the "Explosion"
    # Resample logic: Take every 3 candles
    df.set_index('timestamp', inplace=True)
    df_15m = df.resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    df_15m['range_pct'] = (df_15m['high'] - df_15m['low']) / df_15m['open'] * 100
    
    # Identify Explosions (> 2.0%)
    explosions = df_15m[df_15m['range_pct'] > 2.0].dropna()
    print(f"Total Explosive Events (> 2.0% in 15m): {len(explosions)}")
    
    patterns = []
    
    for ts, row in explosions.iterrows():
        # Get the 12 candles (60 mins) BEFORE the explosion start time
        # Note: 'ts' is the start time of the 15m candle.
        start_time = ts - pd.Timedelta(minutes=60)
        end_time = ts # Exclusive of the explosion itself
        
        precursor_data = df.loc[start_time:end_time].iloc[:-1] # Exclude the start of explosion
        
        if len(precursor_data) < 12: continue
        
        # Normalize data to see the "Shape" (0 to 1 scale based on min/max of the sequence)
        p_min = precursor_data['low'].min()
        p_max = precursor_data['high'].max()
        p_range = p_max - p_min
        
        if p_range == 0: continue
        
        # Store raw data for inspection
        pattern_info = {
            'explosion_time': ts,
            'explosion_size': row['range_pct'],
            'precursor_volatility': precursor_data['high'].max() - precursor_data['low'].min(),
            'precursor_volume_trend': precursor_data['volume'].iloc[-1] / precursor_data['volume'].iloc[0] if precursor_data['volume'].iloc[0] > 0 else 0
        }
        
        patterns.append(pattern_info)

    # Convert to DataFrame
    result_df = pd.DataFrame(patterns)
    
    # Sort by Explosion Size to see the biggest ones first
    result_df.sort_values('explosion_size', ascending=False, inplace=True)
    
    print("\n[Top 10 Largest Explosions & Their Precursor Context]")
    print(f"{'Time':<20} | {'Size(%)':<8} | {'Prec.Volat':<10} | {'Vol Trend':<10}")
    print("-" * 60)
    
    for i in range(10):
        if i >= len(result_df): break
        row = result_df.iloc[i]
        print(f"{row['explosion_time']} | {row['explosion_size']:.2f}%    | {row['precursor_volatility']:.2f}       | {row['precursor_volume_trend']:.2f}x")

    # Save for detailed analysis
    result_df.to_csv(output_csv, index=False)
    print(f"\nSaved pattern list to {output_csv}")
    print("Use this list to visualize specific dates and find the 'Shape'.")

if __name__ == "__main__":
    extract_explosive_patterns("data/bybit_btc_usdt_linear_5m_full.csv")