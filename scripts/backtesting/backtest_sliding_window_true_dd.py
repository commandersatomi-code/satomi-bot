import pandas as pd
import numpy as np
import os

# ==========================================
# 1. バックテスト用コアロジック
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
    
    # Pre-calculate grid levels
    grid_levels = np.floor(closes / grid_size).astype(int)
    prev_level = grid_levels[0]
    
    max_drawdown = 0
    peak_equity = initial_equity
    buy_count = 0
    
    # Track equity curve for DD calculation
    # Only need to return max_dd from this specific run
    
    for i in range(1, len(closes)):
        price = closes[i]
        rsi = rsi_values[i]
        new_grid_level = grid_levels[i]
        
        # BUY
        if new_grid_level < prev_level:
            diff = prev_level - new_grid_level
            for _ in range(diff):
                if rsi < rsi_limit:
                    positions.append(price)
                    buy_count += 1
                    total_fees += price * fee_rate
                    
        # SELL
        elif new_grid_level > prev_level:
            diff = new_grid_level - prev_level
            for _ in range(diff):
                if len(positions) > 0:
                    bought_price = positions.pop(0)
                    profit = price - bought_price
                    total_realized_profit += profit
                    total_fees += price * fee_rate
        
        prev_level = new_grid_level
        
        # DD Check (Every Step)
        unrealized = 0
        if positions:
             unrealized = sum(price - p for p in positions)
        
        current_equity = initial_equity + total_realized_profit - total_fees + unrealized
        
        if current_equity > peak_equity:
            peak_equity = current_equity
        
        dd = peak_equity - current_equity
        if dd > max_drawdown:
            max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p for p in positions)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    
    return final_equity, total_realized_profit, total_fees, max_drawdown, buy_count

# ==========================================
# 2. スライディングウィンドウ
# ==========================================
def optimize(df, grid_opts, rsi_opts):
    best_score = -np.inf
    best_params = (1000, 100)
    
    closes = df['close'].values
    rsis = df['rsi'].values
    
    for g in grid_opts:
        for r in rsi_opts:
            eq, prof, fees, dd, buys = run_backtest_fast(closes, rsis, g, r)
            if buys == 0: score = 0
            else: score = (eq - 1000000) / (dd + 1)
            
            if score > best_score:
                best_score = score
                best_params = (g, r)
    return best_params

def run_sliding_window_true_dd(df, window_days, tf_name):
    if tf_name == '5m': rows_per_day = 288
    elif tf_name == '15m': rows_per_day = 96
    elif tf_name == '1h': rows_per_day = 24
    elif tf_name == '4h': rows_per_day = 6
    elif tf_name == 'Daily': rows_per_day = 1
    elif tf_name == 'Weekly': rows_per_day = 1/7
    elif tf_name == 'Monthly': rows_per_day = 1/30
    else: rows_per_day = 24
    
    window_rows = int(window_days * rows_per_day)
    if window_rows < 5: window_rows = 5
    
    # Global state tracking across windows
    current_base_equity = 1000000 # The equity at the start of each window
    peak_global_equity = 1000000
    max_global_dd = 0
    total_trades_global = 0
    
    test_start_idx = window_rows
    
    grid_opts = [500, 1000, 2000, 3000, 5000, 10000]
    rsi_opts = [30, 40, 50, 70, 100]
    
    while test_start_idx < len(df):
        test_end_idx = min(test_start_idx + window_rows, len(df))
        
        # Train
        train_start = test_start_idx - window_rows
        train_df = df.iloc[train_start:test_start_idx]
        
        if len(train_df) < 5:
            test_start_idx += window_rows
            continue

        best_g, best_r = optimize(train_df, grid_opts, rsi_opts)
        
        # Test
        test_df = df.iloc[test_start_idx:test_end_idx]
        closes = test_df['close'].values
        rsis = test_df['rsi'].values
        
        # To calculate TRUE DD, we need to simulate step-by-step within the window
        # but starting from the current_base_equity
        
        # Re-implement step logic here or modify run_backtest_fast to accept start_equity?
        # Let's modify logic inline for clarity and global state tracking
        
        positions = [] 
        # Note: In true sliding window, we might carry positions. 
        # But here we assume "fresh start" (close all) at each re-optimization for simplicity.
        
        period_realized = 0
        period_fees = 0
        fee_rate = 0.0006
        
        grid_levels = np.floor(closes / best_g).astype(int)
        prev_level = grid_levels[0]
        
        for i in range(1, len(closes)):
            price = closes[i]
            rsi = rsis[i]
            new_grid_level = grid_levels[i]
            
            # Logic
            if new_grid_level < prev_level:
                diff = prev_level - new_grid_level
                for _ in range(diff):
                    if rsi < best_r:
                        positions.append(price)
                        total_trades_global += 1
                        period_fees += price * fee_rate
            elif new_grid_level > prev_level:
                diff = new_grid_level - prev_level
                for _ in range(diff):
                    if positions:
                        bought = positions.pop(0)
                        period_realized += (price - bought)
                        period_fees += price * fee_rate
            
            prev_level = new_grid_level
            
            # Global Equity Calculation (at this step)
            unrealized = sum(price - p for p in positions)
            equity_now = current_base_equity + period_realized - period_fees + unrealized
            
            if equity_now > peak_global_equity:
                peak_global_equity = equity_now
            
            dd = peak_global_equity - equity_now
            if dd > max_global_dd:
                max_global_dd = dd
        
        # End of Window: Close all positions (Virtual Settlement)
        final_unrealized = sum(closes[-1] - p for p in positions)
        period_net_profit = period_realized - period_fees + final_unrealized
        
        current_base_equity += period_net_profit
        test_start_idx += window_rows
        
    return current_base_equity, max_global_dd, total_trades_global

def main():
    datasets = [
        ('15m', 'data/bybit_btcusdt_linear_15m_full.csv'),
        ('1h', 'data/bybit_btcusdt_linear_1h_full.csv'),
        ('4h', 'data/bybit_btc_usdt_linear_4h_full.csv'),
        ('Daily', 'data/bybit_btc_usdt_linear_daily_full.csv'),
        ('Weekly', 'data/bybit_btc_usdt_linear_W_full.csv'),
    ]
    
    windows = [
        ('3 Days', 3),
        ('Weekly', 7),
        ('Monthly', 30),
        ('Quarterly', 90),
        ('Yearly', 360)
    ]
    
    results = []
    
    for tf_name, path in datasets:
        if not os.path.exists(path): continue
        
        print(f"Processing {tf_name}...")
        df = pd.read_csv(path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        df['rsi'] = calculate_rsi(df['close'])
        
        start_date = '2023-01-01'
        df = df[df.index >= start_date]
        
        if len(df) < 50: continue
            
        best_ret = -np.inf
        best_win = ""
        
        for w_name, w_days in windows:
            if tf_name in ['Daily', 'Weekly'] and w_days < 30: continue
            if tf_name in ['Weekly'] and w_days < 90: continue
                
            final, dd, trades = run_sliding_window_true_dd(df, w_days, tf_name)
            ret = (final - 1000000) / 1000000 * 100
            
            results.append({
                'TF': tf_name,
                'Window': w_name,
                'Return': ret,
                'TrueMaxDD': dd
            })
            
            if ret > best_ret:
                best_ret = ret
                best_win = w_name
                
        print(f"  Best Window for {tf_name}: {best_win} ({best_ret:.2f}%)")

    print("\n" + "="*70)
    print(f"{ 'TF':<8} | { 'Window':<10} | { 'Return':<8} | { 'True MaxDD':<12}")
    print("-" * 70)
    for r in results:
        print(f"{r['TF']:<8} | {r['Window']:<10} | {r['Return']:>7.2f}% | {r['TrueMaxDD']:>11,.0f}")
    print("="*70)

if __name__ == "__main__":
    main()
