
import pandas as pd
import numpy as np
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src/engines')))
from renko_engine import RenkoChart

def run_renko_backtest(df, brick_size, vol_threshold=3.0, fee_rate=0.0006):
    """
    Backtest the Ura-Mono logic on Renko Bricks.
    Signal: If Volume Lag > threshold, trade the NEXT brick's direction.
    """
    # 1. Generate Bricks
    renko = RenkoChart(brick_size=brick_size)
    renko_df = renko.process_data(df)
    
    if renko_df.empty:
        return 0, 0, 0, 0, 0
    
    # 2. Calculate Precursors
    renko_df = renko.calculate_precursors(renko_df)
    
    # 3. Simulation
    initial_equity = 1000000
    equity = initial_equity
    position = 0 # 1: Long, -1: Short
    entry_price = 0
    
    trades = 0
    total_profit = 0
    total_fees = 0
    
    max_drawdown = 0
    peak = initial_equity
    
    # Logic: 
    # If a brick has 'High Volume Lag' (The Omen), 
    # we take a position on the NEXT brick in the same direction.
    
    for i in range(len(renko_df) - 1):
        current_brick = renko_df.iloc[i]
        next_brick = renko_df.iloc[i+1]
        
        # --- EXIT LOGIC ---
        if position != 0:
            # Simple Exit: If direction changes (Reversal)
            if (position == 1 and next_brick['type'] == 'DOWN') or \
               (position == -1 and next_brick['type'] == 'UP'):
                
                exit_price = next_brick['price']
                profit = (exit_price - entry_price) * position
                total_profit += profit
                total_fees += exit_price * fee_rate
                
                equity += profit - (exit_price * fee_rate)
                position = 0
                trades += 1

        # --- ENTRY LOGIC (The Omens) ---
        if position == 0:
            # If Volume Lag is high, enter on NEXT brick
            if current_brick['vol_lag'] > vol_threshold:
                position = 1 if next_brick['type'] == 'UP' else -1
                entry_price = next_brick['price']
                total_fees += entry_price * fee_rate
                equity -= (entry_price * fee_rate)

        # DD Tracking
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_drawdown:
            max_drawdown = dd

    final_return = (equity - initial_equity) / initial_equity * 100
    return final_return, equity, total_profit, total_fees, max_drawdown, trades

def main():
    file_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    if not os.path.exists(file_path):
        print("Data not found.")
        return

    print("Loading data...")
    df = pd.read_csv(file_path)
    
    # Test multiple brick sizes
    brick_sizes = [50, 100, 200, 500]
    
    print("\n" + "="*60)
    print(f"URA-MONO RENKO BACKTEST (Volume Lag Trigger)")
    print(f"{'Brick':<10} | {'Return':<8} | {'Equity':<12} | {'MaxDD':<8} | {'Trades'}")
    print("-" * 60)
    
    for b in brick_sizes:
        ret, eq, prof, fees, dd, count = run_renko_backtest(df.tail(100000), brick_size=b)
        print(f"{b:<10} | {ret:>7.2f}% | {eq:>12,.0f} | {dd:>8,.0f} | {count}")
    print("="*60)

if __name__ == "__main__":
    main()
