import pandas as pd
import numpy as np
import os

# ==========================================
# 1. バックテスト用コアロジック (高速版)
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
        
        # DD Check
        unrealized = 0
        if positions:
             unrealized = sum(price - p for p in positions)
        
        equity = initial_equity + total_realized_profit - total_fees + unrealized
        if equity > peak_equity:
            peak_equity = equity
        dd = peak_equity - equity
        if dd > max_drawdown:
            max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p for p in positions)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    
    return final_equity, total_realized_profit, total_fees, max_drawdown, buy_count

# ==========================================
# 2. スライディングウィンドウ最適化
# ==========================================
def optimize(df, grid_opts, rsi_opts):
    best_score = -np.inf
    best_params = (1000, 100)
    
    closes = df['close'].values
    rsis = df['rsi'].values
    
    for g in grid_opts:
        for r in rsi_opts:
            eq, prof, fees, dd, buys = run_backtest_fast(closes, rsis, g, r)
            
            if buys == 0:
                score = 0
            else:
                net_profit = eq - 1000000
                score = net_profit / (dd + 1)
            
            if score > best_score:
                best_score = score
                best_params = (g, r)
    return best_params

def run_sliding_window(df, window_days):
    rows_per_day = 24 # 1H data
    window_rows = window_days * rows_per_day
    
    current_equity = 1000000
    
    test_start_idx = window_rows
    
    print(f"  Running Sliding Window: {window_days} Days...")
    
    total_profit_accum = 0
    total_fees_accum = 0
    max_dd_global = 0
    peak_global = 1000000
    total_trades = 0
    
    grid_opts = [500, 1000, 2000, 3000, 5000]
    rsi_opts = [30, 40, 50, 70, 100]
    
    while test_start_idx < len(df):
        test_end_idx = min(test_start_idx + window_rows, len(df))
        
        # Train
        train_start = test_start_idx - window_rows
        train_df = df.iloc[train_start:test_start_idx]
        
        best_g, best_r = optimize(train_df, grid_opts, rsi_opts)
        
        # Test
        test_df = df.iloc[test_start_idx:test_end_idx]
        closes = test_df['close'].values
        rsis = test_df['rsi'].values
        
        eq, prof, fees, dd, buys = run_backtest_fast(closes, rsis, best_g, best_r)
        
        # Period Result
        period_net = eq - 1000000
        current_equity += period_net
        
        total_profit_accum += prof
        total_fees_accum += fees
        total_trades += buys
        
        # Global DD
        if current_equity > peak_global:
            peak_global = current_equity
        dd_curr = peak_global - current_equity
        if dd_curr > max_dd_global:
            max_dd_global = dd_curr
        
        test_start_idx += window_rows
        
    return current_equity, total_profit_accum, total_fees_accum, max_dd_global, total_trades

def main():
    path = 'data/bybit_btc_usdt_linear_1h_full.csv'
    if not os.path.exists(path):
        print("Data not found.")
        return
        
    print(f"Loading {path}...")
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    # print("Resampling to 1H...")
    # df = df.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
    # df.dropna(inplace=True)
    
    df['rsi'] = calculate_rsi(df['close'])
    
    # Use full data range
    # start_date = '2023-01-01'
    # df = df[df.index >= start_date]
    print(f"Testing Data: {df.index[0]} ~ {df.index[-1]} ({len(df)} rows)")
    
    windows = [
        ('Yearly', 360),
        ('Quarterly', 90),
        ('Monthly', 30),
        ('Weekly', 7),
        ('3 Days', 3),
        ('1 Day', 1)
    ]
    
    summary = []
    
    for name, days in windows:
        final_eq, prof, fees, dd, trades = run_sliding_window(df, days)
        ret = (final_eq - 1000000) / 1000000 * 100
        summary.append({
            'Window': name,
            'Return': ret,
            'FinalEquity': final_eq,
            'MaxDD': dd,
            'Trades': trades
        })
        
    print("\n" + "="*80)
    print(f"{'Window':<10} | {'Return':<8} | {'Final Equity':<15} | {'MaxDD':<12} | {'Trades':<8}")
    print("-" * 80)
    for s in summary:
        print(f"{s['Window']:<10} | {s['Return']:>7.2f}% | {s['FinalEquity']:>15,.0f} | {s['MaxDD']:>12,.0f} | {s['Trades']:>8}")
    print("="*80)

if __name__ == "__main__":
    main()
