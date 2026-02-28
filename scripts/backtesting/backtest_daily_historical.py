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
                if len(positions) > 0:
                    bought = positions.pop(0)
                    total_realized_profit += (price - bought)
                    total_fees += price * fee_rate
        prev_level = new_grid_level
        
        unrealized = sum(price - p for p in positions) if positions else 0
        current_eq = initial_equity + total_realized_profit - total_fees + unrealized
        if current_eq > peak_equity: peak_equity = current_eq
        dd = peak_equity - current_eq
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

def run_monthly_walk_forward(df):
    window_rows = 30 # Monthly update
    
    current_base_equity = 1000000
    peak_global_equity = 1000000
    max_global_dd = 0
    
    # Yearly stats container
    yearly_stats = {}
    
    test_start_idx = window_rows
    
    grid_opts = [500, 1000, 2000, 3000, 5000, 10000]
    rsi_opts = [30, 40, 50, 70, 100]
    
    while test_start_idx < len(df):
        test_end_idx = min(test_start_idx + window_rows, len(df))
        
        # Train (Last Month)
        train_start = test_start_idx - window_rows
        train_df = df.iloc[train_start:test_start_idx]
        
        # Optimize
        best_g, best_r = optimize(train_df, grid_opts, rsi_opts)
        
        # Test (Current Month)
        test_df = df.iloc[test_start_idx:test_end_idx]
        closes = test_df['close'].values
        rsis = test_df['rsi'].values
        
        # Determine Year for stats
        current_year = test_df.index[0].year
        if current_year not in yearly_stats:
            yearly_stats[current_year] = {'equity_start': current_base_equity, 'equity_end': 0, 'max_dd': 0, 'peak': current_base_equity}
        
        positions = []
        period_realized = 0
        period_fees = 0
        fee_rate = 0.0006
        
        grid_levels = np.floor(closes / best_g).astype(int)
        prev_level = grid_levels[0]
        
        for i in range(1, len(closes)):
            price = closes[i]
            rsi = rsis[i]
            new_grid_level = grid_levels[i]
            
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
            
            # Global DD
            if equity_now > peak_global_equity: peak_global_equity = equity_now
            dd = peak_global_equity - equity_now
            if dd > max_global_dd: max_global_dd = dd
            
            # Yearly DD
            if equity_now > yearly_stats[current_year]['peak']:
                yearly_stats[current_year]['peak'] = equity_now
            ydd = yearly_stats[current_year]['peak'] - equity_now
            if ydd > yearly_stats[current_year]['max_dd']:
                yearly_stats[current_year]['max_dd'] = ydd

        final_unrealized = sum(closes[-1] - p for p in positions) if positions else 0
        period_net = period_realized - period_fees + final_unrealized
        current_base_equity += period_net
        
        # Update yearly end equity
        yearly_stats[current_year]['equity_end'] = current_base_equity
        
        test_start_idx += window_rows
        
    return current_base_equity, max_global_dd, yearly_stats

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    if not os.path.exists(path): return
    
    print(f"Loading {path}...")
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['rsi'] = calculate_rsi(df['close'])
    
    # Start from 2020-04 (Wait for some data)
    df = df[df.index >= '2020-04-01']
    
    print("\nRunning Historical Test: Daily TF x Monthly Update")
    final, global_dd, yearly = run_monthly_walk_forward(df)
    
    print("\n" + "="*60)
    print(f"{ 'Year':<6} | {'Return':<10} | {'True MaxDD':<12} | {'End Equity':<12}")
    print("-" * 60)
    
    total_ret = (final - 1000000) / 1000000 * 100
    
    for year, stats in yearly.items():
        start = stats['equity_start']
        end = stats['equity_end']
        ret = (end - start) / start * 100
        dd = stats['max_dd']
        print(f"{year:<6} | {ret:>9.2f}% | {dd:>11,.0f} | {end:>11,.0f}")
        
    print("-" * 60)
    print(f"TOTAL  | {total_ret:>9.2f}% | {global_dd:>11,.0f} | {final:>11,.0f}")
    print("="*60)

if __name__ == "__main__":
    main()
