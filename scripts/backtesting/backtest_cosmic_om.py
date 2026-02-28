import pandas as pd
import numpy as np
import os
import sys

# Add src to path for config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
import config

# ==========================================
# 🌀 136.1Hz Cosmic Core: Earth's Orbital Year
# ==========================================
COSMIC_YEAR_DAYS = 365.24219
HOURS_PER_DAY = 24
COSMIC_WINDOW_HOURS = int(COSMIC_YEAR_DAYS * HOURS_PER_DAY)

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def run_backtest_cosmic(closes, rsi_values, grid_pct, rsi_limit, fee_rate=0.0006):
    """
    Backtest tuned to Relative Grid % (Wave) and RSI (Compass).
    """
    initial_equity = 1000000 
    positions = []
    total_realized_profit = 0
    total_fees = 0
    
    # Pre-calculate logarithmic grid levels (5D logic)
    log_base = np.log(1 + grid_pct)
    grid_levels = np.floor(np.log(closes) / log_base).astype(int)
    prev_level = grid_levels[0]
    
    max_drawdown = 0
    peak_equity = initial_equity
    buy_count = 0
    
    for i in range(1, len(closes)):
        price = closes[i]
        rsi = rsi_values[i]
        new_grid_level = grid_levels[i]
        
        # BUY (Cheap Zone)
        if new_grid_level < prev_level:
            diff = prev_level - new_grid_level
            for _ in range(diff):
                if rsi < rsi_limit:
                    positions.append(price)
                    buy_count += 1
                    total_fees += price * fee_rate
                    
        # SELL (Expensive Zone)
        elif new_grid_level > prev_level:
            diff = new_grid_level - prev_level
            for _ in range(diff):
                if len(positions) > 0:
                    bought_price = positions.pop(0) # FIFO
                    profit = price - bought_price
                    total_realized_profit += profit
                    total_fees += price * fee_rate
        
        prev_level = new_grid_level
        
        # Equity Tracking
        unrealized = sum(price - p for p in positions) if positions else 0
        equity = initial_equity + total_realized_profit - total_fees + unrealized
        
        if equity > peak_equity:
            peak_equity = equity
        dd = peak_equity - equity
        if dd > max_drawdown:
            max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p for p in positions) if positions else 0
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    
    return final_equity, total_realized_profit, total_fees, max_drawdown, buy_count

def optimize_cosmic(df, grid_opts, rsi_opts):
    best_score = -np.inf
    best_params = (0.07, 50)
    
    closes = df['close'].values
    rsis = df['rsi'].values
    
    for g in grid_opts:
        for r in rsi_opts:
            eq, prof, fees, dd, buys = run_backtest_cosmic(closes, rsis, g, r)
            
            if buys == 0:
                score = 0
            else:
                net_profit = eq - 1000000
                # Resonance Score: Profit over Drawdown, rewarded for consistent cycles
                score = net_profit / (dd + 1)
            
            if score > best_score:
                best_score = score
                best_params = (g, r)
    return best_params

def main():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/bybit_btc_usdt_linear_1h_full.csv'))
    if not os.path.exists(path):
        print(f"Data not found at {path}")
        return
        
    print(f"🌀 Loading Cosmic Data: {path}...")
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    df['rsi'] = calculate_rsi(df['close'])
    
    print(f"✨ Testing Range: {df.index[0]} ~ {df.index[-1]}")
    print(f"🌌 Cosmic Window: {COSMIC_WINDOW_HOURS} Hours (~365.24 Days)")
    
    grid_opts = [0.03, 0.05, 0.07, 0.10, 0.15, 0.20] # 5D Wave %
    rsi_opts = [30, 40, 50, 60]
    
    # Sliding Window
    current_equity = 1000000
    test_start_idx = COSMIC_WINDOW_HOURS
    peak_global = 1000000
    max_dd_global = 0
    
    print("\nStarting Cosmic Alignment (Sliding 136.1Hz Window)...")
    
    while test_start_idx < len(df):
        test_end_idx = min(test_start_idx + COSMIC_WINDOW_HOURS, len(df))
        
        # Train on Cosmic Year
        train_start = test_start_idx - COSMIC_WINDOW_HOURS
        train_df = df.iloc[train_start:test_start_idx]
        
        best_g, best_r = optimize_cosmic(train_df, grid_opts, rsi_opts)
        
        # Test on Next Period
        test_df = df.iloc[test_start_idx:test_end_idx]
        if len(test_df) < 24: break # Skip too-short tail
        
        closes = test_df['close'].values
        rsis = test_df['rsi'].values
        
        eq, prof, fees, dd, buys = run_backtest_cosmic(closes, rsis, best_g, best_r)
        
        period_ret = (eq - 1000000) / 1000000 * 100
        current_equity += (eq - 1000000)
        
        # Global Metrics
        if current_equity > peak_global: peak_global = current_equity
        dd_curr = peak_global - current_equity
        if dd_curr > max_dd_global: max_dd_global = dd_curr
        
        print(f"  Period {test_df.index[0].date()} ~ {test_df.index[-1].date()} | Grid: {best_g*100:>2.0f}% | RSI: {best_r} | Ret: {period_ret:>+6.2f}%")
        
        test_start_idx += COSMIC_WINDOW_HOURS

    final_ret = (current_equity - 1000000) / 1000000 * 100
    print("\n" + "🌀" * 20)
    print(f"COSOMIZED RESULT (136.1Hz Alignment)")
    print(f"Total Return: {final_ret:.2f}%")
    print(f"Max Drawdown: {(max_dd_global/10000):.2f}%")
    print(f"Final Equity: {current_equity:,.0f} USDT")
    print("🌀" * 20)

if __name__ == "__main__":
    main()
