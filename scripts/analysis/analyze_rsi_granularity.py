import pandas as pd
import numpy as np
import os

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
        price = closes[i]
        rsi = rsi_values[i]
        new_grid_level = grid_levels[i]
        
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
        eq = initial_equity + total_realized_profit - total_fees + unrealized
        if eq > peak_equity: peak_equity = eq
        dd = peak_equity - eq
        if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p for p in positions) if positions else 0
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    return final_equity, max_drawdown, buy_count

def optimize_grid_only(df, fixed_rsi_limit):
    grid_opts = [500, 1000, 2000, 3000, 5000, 10000]
    best_score = -np.inf
    best_grid = 2000
    closes = df['close'].values
    rsis = df['rsi'].values
    for g in grid_opts:
        eq, dd, buys = run_backtest_fast(closes, rsis, g, fixed_rsi_limit)
        if buys == 0: score = -999999
        else: score = (eq - 1000000) / (dd + 1)
        if score > best_score:
            best_score = score
            best_grid = g
    return best_grid

def run_simulation_fixed_rsi(df, rsi_limit):
    window_days = 30
    window_rows = 30
    current_base_equity = 1000000
    peak_global_equity = 1000000
    max_global_dd = 0
    total_trades = 0
    test_start_idx = window_rows
    
    while test_start_idx < len(df):
        test_end_idx = min(test_start_idx + window_rows, len(df))
        train_df = df.iloc[test_start_idx - window_rows : test_start_idx]
        best_g = optimize_grid_only(train_df, rsi_limit)
        test_df = df.iloc[test_start_idx : test_end_idx]
        closes = test_df['close'].values
        rsis = test_df['rsi'].values
        positions = [] 
        period_realized = 0
        period_fees = 0
        fee_rate = 0.0006
        grid_levels = np.floor(closes / best_g).astype(int)
        if len(grid_levels) == 0: break
        prev_level = grid_levels[0]
        
        for i in range(1, len(closes)):
            price = closes[i]
            rsi = rsis[i]
            new_grid_level = grid_levels[i]
            if new_grid_level < prev_level:
                diff = prev_level - new_grid_level
                for _ in range(diff):
                    if rsi < rsi_limit:
                        positions.append(price)
                        total_trades += 1
                        period_fees += price * fee_rate
            elif new_grid_level > prev_level:
                diff = new_grid_level - prev_level
                for _ in range(diff):
                    if positions:
                        bought = positions.pop(0)
                        period_realized += (price - bought)
                        period_fees += price * fee_rate
            prev_level = new_grid_level
            unrealized = sum(price - p for p in positions)
            equity_now = current_base_equity + period_realized - period_fees + unrealized
            if equity_now > peak_global_equity: peak_global_equity = equity_now
            dd = peak_global_equity - equity_now
            if dd > max_global_dd: max_global_dd = dd
        
        final_unrealized = sum(closes[-1] - p for p in positions)
        period_net_profit = period_realized - period_fees + final_unrealized
        current_base_equity += period_net_profit
        test_start_idx += window_rows
        
    return current_base_equity, max_global_dd, total_trades

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['rsi'] = calculate_rsi(df['close'])
    
    # 分析期間 (前回と同じ)
    split_date = df.index[-1] - pd.Timedelta(days=365)
    analysis_df = df[df.index < split_date]
    
    # 40〜50を細かく刻む
    rsi_limits = [40, 42, 44, 46, 48, 50]
    
    print(f"\n--- Granular Analysis: RSI 40 to 50 ---")
    print(f"{ 'RSI <':<6} | { 'Return':<10} | { 'MaxDD':<12} | { 'Trades':<8} | { 'DD/Ret Ratio':<12}")
    print("-" * 65)
    
    for rsi in rsi_limits:
        final, dd, trades = run_simulation_fixed_rsi(analysis_df, rsi)
        ret_pct = (final - 1000000) / 1000000 * 100
        ratio = dd / (final - 1000000) if final > 1000000 else 9.99
        print(f"{rsi:<6} | {ret_pct:>8.2f}% | {dd:>11,.0f} | {trades:>8} | {ratio:>11.2f}")
    
    print("-" * 65)

if __name__ == "__main__":
    main()
