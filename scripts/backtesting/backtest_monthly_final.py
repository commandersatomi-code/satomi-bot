import pandas as pd
import numpy as np
import os

# ==========================================
# Core Logic (True DD Version)
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def run_backtest_fast(closes, rsi_values, grid_size, rsi_limit, fee_rate=0.0006):
    initial_equity = 1000000 
    positions = []
    total_realized_profit = 0
    total_fees = 0
    grid_levels = np.floor(closes / grid_size).astype(int)
    prev_level = grid_levels[0]
    max_drawdown = 0
    peak_equity = initial_equity
    
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
                if positions:
                    bought = positions.pop(0)
                    total_realized_profit += (price - bought)
                    total_fees += price * fee_rate
        prev_level = new_grid_level
        unrealized = sum(price - p for p in positions) if positions else 0
        eq = initial_equity + total_realized_profit - total_fees + unrealized
        if eq > peak_equity: peak_equity = eq
        dd = peak_equity - eq
        if dd > max_drawdown: max_drawdown = dd
        
    final_unrealized = sum(closes[-1] - p for p in positions) if positions else 0
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    return final_equity, max_drawdown

def main():
    path = 'data/bybit_btc_usdt_linear_M_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['rsi'] = calculate_rsi(df['close'])
    
    # Test on Full History from 2020 to 2026
    # For Monthly, Sliding Window is not practical due to small data.
    # We test best static params to see potential.
    grid_opts = [5000, 10000, 20000]
    rsi_opts = [40, 50, 70, 100]
    
    print("\n--- Monthly Timeframe Backtest (2020-2026) ---")
    print(f"{'Grid':<8} | {'RSI <':<6} | {'Return':<8} | {'True MaxDD':<12}")
    print("-" * 45)
    
    for g in grid_opts:
        for r in rsi_opts:
            final, dd = run_backtest_fast(df['close'].values, df['rsi'].values, g, r)
            ret = (final - 1000000) / 1000000 * 100
            print(f"{g:<8} | {r:<6} | {ret:>7.2f}% | {dd:>11,.0f}")

if __name__ == "__main__":
    main()
