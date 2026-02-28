
import pandas as pd
import numpy as np
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src/engines')))
try:
    from renko_engine import RenkoChart
except ImportError:
    # Fallback
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/engines')))
    from renko_engine import RenkoChart

def run_renko_backtest_refined(df, brick_size, vol_threshold=2.5, fee_rate=0.0006):
    """
    Refined Ura-Mono Backtest with robust timestamp handling.
    """
    # 1. Clean and Prepare underlying data
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])
    df['ema_trend'] = df['close'].ewm(span=200).mean()
    
    # 2. Generate Bricks
    renko = RenkoChart(brick_size=brick_size)
    renko_df = renko.process_data(df)
    
    if renko_df.empty:
        return 0, 0, 0, 0, 0, 0
        
    # Ensure renko_df timestamp is also datetime
    renko_df['timestamp'] = pd.to_datetime(renko_df['timestamp'], errors='coerce')
    renko_df = renko_df.dropna(subset=['timestamp'])
    
    # 3. Merge Trend Filter
    # Need to sort both for merge_asof
    renko_df = renko_df.sort_values('timestamp')
    trend_data = df[['timestamp', 'ema_trend']].sort_values('timestamp')
    
    renko_df = pd.merge_asof(renko_df, trend_data, on='timestamp')
    
    # 4. Calculate Precursors
    renko_df = renko.calculate_precursors(renko_df)
    
    # 5. Simulation
    initial_equity = 1000000
    equity = initial_equity
    position = 0
    entry_price = 0
    
    trades = 0
    total_profit = 0
    total_fees = 0
    max_drawdown = 0
    peak = initial_equity
    
    for i in range(len(renko_df) - 1):
        curr = renko_df.iloc[i]
        nxt = renko_df.iloc[i+1]
        
        # EXIT
        if position != 0:
            if (position == 1 and nxt['type'] == 'DOWN') or \
               (position == -1 and nxt['type'] == 'UP'):
                
                exit_price = nxt['price']
                profit = (exit_price - entry_price) * position
                total_profit += profit
                total_fees += exit_price * fee_rate
                equity += profit - (exit_price * fee_rate)
                position = 0
                trades += 1

        # ENTRY
        if position == 0:
            if curr['vol_lag'] > vol_threshold:
                trend_dir = 1 if curr['price'] > curr['ema_trend'] else -1
                
                if nxt['type'] == 'UP' and trend_dir == 1:
                    position = 1
                    entry_price = nxt['price']
                elif nxt['type'] == 'DOWN' and trend_dir == -1:
                    position = -1
                    entry_price = nxt['price']
                
                if position != 0:
                    total_fees += entry_price * fee_rate
                    equity -= (entry_price * fee_rate)

        if equity > peak: peak = equity
        dd = peak - equity
        if dd > max_drawdown: max_drawdown = dd

    final_return = (equity - initial_equity) / initial_equity * 100
    return final_return, equity, total_profit, total_fees, max_drawdown, trades

def main():
    file_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    if not os.path.exists(file_path):
        print("Data not found.")
        return
        
    print("Loading data...")
    df = pd.read_csv(file_path).tail(200000)
    
    brick_sizes = [30, 50, 80, 100]
    
    print("\n" + "="*80)
    print(f"URA-MONO REFINED BACKTEST (Trend Filtered)")
    print(f"{'Brick':<10} | {'Return':<8} | {'Equity':<15} | {'MaxDD':<10} | {'Trades'}")
    print("-" * 80)
    
    for b in brick_sizes:
        ret, eq, prof, fees, dd, count = run_renko_backtest_refined(df, brick_size=b)
        print(f"{b:<10} | {ret:>7.2f}% | {eq:>15,.0f} | {dd:>10,.0f} | {count}")
    print("="*80)

if __name__ == "__main__":
    main()
