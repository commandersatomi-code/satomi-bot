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
    buy_count = 0
    
    for i in range(1, len(closes)):
        new_grid_level = grid_levels[i]
        if new_grid_level != prev_level:
            price = closes[i]
            rsi = rsi_values[i]
            
            if new_grid_level < prev_level:
                diff = prev_level - new_grid_level
                for _ in range(diff):
                    if rsi < rsi_limit:
                        positions.append(price)
                        buy_count += 1
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
            equity_now = initial_equity + total_realized_profit - total_fees + unrealized
            if equity_now > peak_equity: peak_equity = equity_now
            dd = peak_equity - equity_now
            if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p for p in positions) if positions else 0
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    return final_equity, total_realized_profit, total_fees, max_drawdown, buy_count

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

def run_sliding_window_1m(df, window_hours):
    rows_per_hour = 60
    window_rows = int(window_hours * rows_per_hour)
    
    current_base_equity = 1000000
    peak_global_equity = 1000000
    max_global_dd = 0
    
    # Test from 2025-01-01 to Present (Last ~1 year)
    start_date = pd.Timestamp('2025-01-01')
    if start_date not in df.index:
         test_start_idx = window_rows
    else:
         test_start_idx = df.index.get_indexer([start_date], method='nearest')[0]
         if test_start_idx < window_rows: test_start_idx = window_rows
    
    grid_opts = [500, 1000, 2000, 3000, 5000]
    rsi_opts = [30, 40, 50, 70]
    
    print(f"  Testing Window: {window_hours} Hours...")
    
    while test_start_idx < len(df):
        test_end_idx = min(test_start_idx + window_rows, len(df))
        
        train_start = test_start_idx - window_rows
        train_df = df.iloc[train_start:test_start_idx]
        best_g, best_r = optimize(train_df, grid_opts, rsi_opts)
        
        test_df = df.iloc[test_start_idx:test_end_idx]
        closes = test_df['close'].values
        rsis = test_df['rsi'].values
        
        positions = []
        period_realized = 0
        period_fees = 0
        fee_rate = 0.0006
        
        grid_levels = np.floor(closes / best_g).astype(int)
        prev_level = grid_levels[0]
        
        for i in range(1, len(closes)):
            new_grid_level = grid_levels[i]
            if new_grid_level != prev_level:
                price = closes[i]
                rsi = rsis[i]
                
                if new_grid_level < prev_level:
                    diff = prev_level - new_grid_level
                    for _ in range(diff):
                        if rsi < best_r:
                            positions.append(price)
                            period_fees += price * fee_rate
                elif new_grid_level > prev_level:
                    diff = new_grid_level - prev_level
                    for _ in range(diff):
                        if positions:
                            bought = positions.pop(0)
                            period_realized += (price - bought)
                            period_fees += price * fee_rate
                prev_level = new_grid_level
                
                unrealized = sum(price - p for p in positions) if positions else 0
                equity_now = current_base_equity + period_realized - period_fees + unrealized
                if equity_now > peak_global_equity: peak_global_equity = equity_now
                dd = peak_global_equity - equity_now
                if dd > max_global_dd: max_global_dd = dd
        
        final_unrealized = sum(closes[-1] - p for p in positions) if positions else 0
        period_net = period_realized - period_fees + final_unrealized
        current_base_equity += period_net
        test_start_idx += window_rows
        
    return current_base_equity, max_global_dd

def main():
    path = 'data/bybit_btcusdt_linear_1m_full.csv'
    if not os.path.exists(path): return
    
    print(f"Loading {path}...")
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    print("Calculating RSI...")
    df['rsi'] = calculate_rsi(df['close'])
    
    # 2025年以降のデータでテストするために、少し前から読み込む
    df = df[df.index >= '2024-10-01'] 
    
    windows_hours = [12, 24, 36, 48, 72]
    
    print("\n" + "="*50)
    print(f"{ 'Window (H)':<10} | { 'Return':<10} | { 'True MaxDD':<12}")
    print("-" * 50)
    
    for h in windows_hours:
        final, dd = run_sliding_window_1m(df, h)
        ret = (final - 1000000) / 1000000 * 100
        print(f"{h:<10} | {ret:>9.2f}% | {dd:>11,.0f}")
        
    print("="*50)

if __name__ == "__main__":
    main()
