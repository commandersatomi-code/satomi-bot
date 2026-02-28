
import pandas as pd
import numpy as np
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src/engines')))
from renko_engine import RenkoChart

def run_hybrid_backtest(df_daily, df_1m, brick_size=50, vol_threshold=2.5, grid_size=2000, fee_rate=0.0006):
    """
    Hybrid Oracle Logic:
    1. Grid: Defined by grid_size (e.g., every 2000 USDT)
    2. Filter: Only enter if a Renko 'Yellow Star' (Volume Lag) happens near the grid level.
    """
    # --- 1. Renko Omens (Oracle) ---
    print("  Generating Renko Oracle signals...")
    renko = RenkoChart(brick_size=brick_size)
    renko_bricks = renko.process_data(df_1m)
    renko_bricks = renko.calculate_precursors(renko_bricks)
    
    # Extract 'Star' timestamps (High Volume Lag)
    stars = renko_bricks[renko_bricks['vol_lag'] > vol_threshold].copy()
    stars['omen'] = True
    
    # --- 2. Simulation Setup ---
    initial_equity = 1000000
    equity = initial_equity
    positions = [] # List of entry prices
    
    total_profit = 0
    total_fees = 0
    max_drawdown = 0
    peak = initial_equity
    trades = 0
    
    # We use Daily data for the general "Grid" feel but 1m for precise entries
    # Filter 1m data to match Daily range
    start_date = df_daily['timestamp'].min()
    df_1m_filtered = df_1m[df_1m['timestamp'] >= start_date].copy()
    
    # Map Omens to 1m data
    df_1m_filtered = pd.merge_asof(
        df_1m_filtered.sort_values('timestamp'),
        stars[['timestamp', 'omen']].sort_values('timestamp'),
        on='timestamp',
        direction='backward',
        tolerance=pd.Timedelta(minutes=5) # Omen is valid for 5 mins
    )
    df_1m_filtered['omen'] = df_1m_filtered['omen'].fillna(False)

    print(f"  Starting Simulation on {len(df_1m_filtered)} bars...")
    
    # Pre-calc grid levels
    closes = df_1m_filtered['close'].values
    omens = df_1m_filtered['omen'].values
    
    last_grid_level = np.floor(closes[0] / grid_size)
    
    for i in range(1, len(closes)):
        price = closes[i]
        has_omen = omens[i]
        current_grid_level = np.floor(price / grid_size)
        
        # --- ENTRY (Grid + Omen) ---
        # If price crosses a grid level DOWNWARD AND we have an Omen (Delayed Sound)
        if current_grid_level < last_grid_level:
            if has_omen:
                # BUY (Long Only for this prototype)
                positions.append(price)
                total_fees += price * fee_rate
                equity -= (price * fee_rate)
        
        # --- EXIT (Harmony / Simple Grid) ---
        # Exit if price crosses a grid level UPWARD
        elif current_grid_level > last_grid_level:
            if positions:
                # Close oldest position (FIFO)
                bought_price = positions.pop(0)
                profit = price - bought_price
                total_profit += profit
                total_fees += price * fee_rate
                equity += profit - (price * fee_rate)
                trades += 1
        
        last_grid_level = current_grid_level
        
        # Floating Equity for DD
        unrealized = sum(price - p for p in positions)
        total_val = equity + unrealized
        
        if total_val > peak: peak = total_val
        dd = peak - total_val
        if dd > max_drawdown: max_drawdown = dd

    final_return = (equity + sum(closes[-1] - p for p in positions) - initial_equity) / initial_equity * 100
    return final_return, equity, total_profit, total_fees, max_drawdown, trades

def main():
    daily_path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    m1_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    
    if not os.path.exists(daily_path) or not os.path.exists(m1_path):
        print("Data missing.")
        return
        
    print("Loading Data (This may take a moment)...")
    df_daily = pd.read_csv(daily_path)
    df_daily['timestamp'] = pd.to_datetime(df_daily['timestamp'])
    
    # Load 1m data (Last 300,000 for realistic but fast test)
    df_1m = pd.read_csv(m1_path).tail(300000)
    df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'])
    
    print("\n" + "="*80)
    print(f"HYBRID ORACLE BACKTEST (Harmony Grid + Renko Omens)")
    print(f"{'Grid':<10} | {'Brick':<8} | {'Return':<8} | {'Equity':<15} | {'MaxDD':<10} | {'Trades'}")
    print("-" * 80)
    
    grid_sizes = [1000, 2000, 3000]
    brick_sizes = [50, 100]
    
    for g in grid_sizes:
        for b in brick_sizes:
            ret, eq, prof, fees, dd, count = run_hybrid_backtest(df_daily, df_1m, brick_size=b, grid_size=g)
            print(f"{g:<10} | {b:<8} | {ret:>7.2f}% | {eq:>15,.0f} | {dd:>10,.0f} | {count}")
    print("="*80)

if __name__ == "__main__":
    main()
