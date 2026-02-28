import pandas as pd
import numpy as np
import os
import sys

# Add src to path for config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
import config

COSMIC_YEAR_DAYS = 365.24219
HOURS_PER_DAY = 24

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def run_backtest_simple(closes, rsi_values, grid_pct=0.07, rsi_limit=50):
    initial_equity = 1000000 
    positions = []
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    
    log_base = np.log(1 + grid_pct)
    grid_levels = np.floor(np.log(closes) / log_base).astype(int)
    prev_level = grid_levels[0]
    
    peak_equity = initial_equity
    max_drawdown = 0
    
    for i in range(1, len(closes)):
        price = closes[i]
        rsi = rsi_values[i]
        new_grid_level = grid_levels[i]
        
        if new_grid_level < prev_level:
            diff = prev_level - new_grid_level
            for _ in range(diff):
                if rsi < rsi_limit:
                    positions.append(price)
                    total_fees += price * fee_rate
                    
        elif new_grid_level > prev_level:
            diff = new_grid_level - prev_level
            for _ in range(diff):
                if len(positions) > 0:
                    bought_price = positions.pop(0)
                    total_realized_profit += (price - bought_price)
                    total_fees += price * fee_rate
        
        prev_level = new_grid_level
        
        # Equity Tracking
        unrealized = sum(price - p for p in positions) if positions else 0
        equity = initial_equity + total_realized_profit - total_fees + unrealized
        if equity > peak_equity: peak_equity = equity
        max_drawdown = max(max_drawdown, peak_equity - equity)
            
    final_equity = initial_equity + total_realized_profit - total_fees + (sum(closes[-1] - p for p in positions) if positions else 0)
    return final_equity, max_drawdown

def main():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/bybit_btc_usdt_linear_1h_full.csv'))
    if not os.path.exists(path): return
    
    df = pd.read_csv(path)
    df['rsi'] = calculate_rsi(df['close'])
    
    harmonics = [
        ('1/1 (Year)', 1),
        ('1/2 (Half)', 2),
        ('1/4 (Quarter)', 4),
        ('1/12 (Month)', 12),
        ('1/52 (Week)', 52),
        ('1/136.1 (Cosmic Day)', 136.1)
    ]
    
    print(f"🌀 HARMONIC EXPLORER (Frequency Sweep)")
    print(f"{'Harmonic Tier':<20} | {'Window (Days)':<15} | {'Return':<10} | {'MaxDD':<10} | {'Score'}")
    print("-" * 75)
    
    for name, div in harmonics:
        window_days = COSMIC_YEAR_DAYS / div
        window_hours = int(window_days * HOURS_PER_DAY)
        
        if window_hours >= len(df): continue
        
        # Test the most recent window for current resonance
        test_df = df.iloc[-window_hours:]
        final_eq, dd = run_backtest_simple(test_df['close'].values, test_df['rsi'].values)
        
        ret = (final_eq - 1000000) / 1000000 * 100
        dd_pct = (dd / 10000)
        score = ret / (dd_pct + 1)
        
        print(f"{name:<20} | {window_days:>14.2f} | {ret:>+9.2f}% | {dd_pct:>9.2f}% | {score:.2f}")

if __name__ == "__main__":
    main()
