import pandas as pd
import numpy as np
import os

def display_quiet_explosions(filepath, pattern_path="data/explosive_patterns.csv"):
    """
    Find and display the 'Quiet Explosions'.
    Target:
    - Explosion: 15m Candle Range > 2.0%
    - Precursor: Lowest volatility in the preceding hour.
    """
    if not os.path.exists(filepath) or not os.path.exists(pattern_path):
        print("File not found.")
        return

    # Load Patterns
    patterns = pd.read_csv(pattern_path)
    # Filter: Ensure explosion is significant (> 2.0%)
    patterns = patterns[patterns['explosion_size'] > 2.0]
    
    # Sort by Precursor Volatility (Ascending) -> Find the Quietest ones
    quietest = patterns.sort_values('precursor_volatility', ascending=True).head(5)
    
    print(f"\n========================================================")
    print(f"   Invention Lab: Top 5 Explosions from Pure Silence")
    print(f"========================================================")

    # Load 5m Data to show context
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    for idx, row in quietest.iterrows():
        ts = pd.to_datetime(row['explosion_time'])
        
        # Get 1 hour context (12 candles)
        start_time = ts - pd.Timedelta(minutes=60)
        end_time = ts - pd.Timedelta(minutes=5) # Up to the candle before explosion
        
        context = df.loc[start_time:end_time]
        
        if context.empty: continue
        
        print(f"\n[Case: {ts}] 💥 Explosion: {row['explosion_size']:.2f}%")
        print(f"Precursor Volatility (High-Low): {row['precursor_volatility']:.2f}")
        
        print(f"{ 'Time':<20} | {'Open':<8} | {'Close':<8} | {'Range%':<6} | {'Vol'}")
        print("-" * 65)
        
        base_price = context.iloc[0]['open']
        
        for t, c in context.iterrows():
            r_pct = (c['high'] - c['low']) / c['open'] * 100
            # Show relative price to base to see the "Shape" easier
            rel_close = c['close'] - base_price
            print(f"{t} | {c['open']:.1f}  | {c['close']:.1f}  | {r_pct:5.2f}% | {c['volume']:.0f}")
            
        print("-" * 65)
        print("Note the rhythm. Is it compressing? Is volume dying?")

if __name__ == "__main__":
    display_quiet_explosions("data/bybit_btc_usdt_linear_5m_full.csv")
