import pandas as pd
import numpy as np
import os

# ==========================================
# 1. 指標計算 & 高速バックテストロジック
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def run_backtest_core(closes, rsi_values, grid_size, rsi_limit, fee_rate=0.0006):
    initial_equity = 1000000 
    positions = [] # List of entry prices
    total_realized_profit = 0
    total_fees = 0
    
    current_grid_level = int(closes[0] // grid_size)
    max_drawdown = 0
    peak_equity = initial_equity
    
    buy_count = 0
    
    # Pre-calculation for speed
    grid_levels = np.floor(closes / grid_size).astype(int)
    
    prev_level = grid_levels[0]
    
    for i in range(1, len(closes)):
        price = closes[i]
        rsi = rsi_values[i]
        new_grid_level = grid_levels[i]
        
        # BUY Logic
        if new_grid_level < prev_level:
            diff = prev_level - new_grid_level
            for _ in range(diff):
                if rsi < rsi_limit:
                    positions.append(price)
                    buy_count += 1
                    # Fee on Entry
                    total_fees += price * fee_rate
                    
        # SELL Logic
        elif new_grid_level > prev_level:
            diff = new_grid_level - prev_level
            for _ in range(diff):
                if len(positions) > 0:
                    bought_price = positions.pop(0)
                    trade_profit = price - bought_price
                    # Fee on Exit
                    exit_fee = price * fee_rate
                    total_fees += exit_fee
                    
                    total_realized_profit += trade_profit
        
        prev_level = new_grid_level
        
        # --- DD Calculation (Approximate: Check only when equity likely drops) ---
        # To be accurate and fast, we check DD every step or skip some. 
        # Let's check every step but optimized.
        
        unrealized = 0
        if len(positions) > 0:
            # Vectorized sum is faster? No, list sum is fast enough for small lists
            # For huge lists, maintain running sum
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
# 2. Walk-Forward Analysis (Yearly)
# ==========================================
def optimize_params(df, grid_options, rsi_options):
    best_score = -np.inf
    best_params = (1000, 100)
    
    closes = df['close'].values
    rsis = df['rsi'].values
    
    for g in grid_options:
        for r in rsi_options:
            eq, prof, fees, dd, buys = run_backtest_core(closes, rsis, g, r)
            
            if buys == 0:
                score = 0
            else:
                # Score: Profit / (MaxDD + 1)
                # But we also want to avoid huge fees killing us? 
                # Equity result already includes fees.
                net_profit = eq - 1000000
                score = net_profit / (dd + 1)
                
            if score > best_score:
                best_score = score
                best_params = (g, r)
                
    return best_params

def process_year(year, prev_year_df, current_year_df, timeframe_name):
    # 1. Optimize on Previous Year (Training)
    grid_opts = [500, 1000, 2000, 3000, 5000]
    rsi_opts = [30, 40, 50, 70, 100]
    
    best_g, best_r = optimize_params(prev_year_df, grid_opts, rsi_opts)
    
    # 2. Test on Current Year
    closes = current_year_df['close'].values
    rsis = current_year_df['rsi'].values
    
    eq, prof, fees, dd, buys = run_backtest_core(closes, rsis, best_g, best_r)
    ret_pct = (eq - 1000000) / 1000000 * 100
    
    return {
        'Year': year,
        'Timeframe': timeframe_name,
        'Return': ret_pct,
        'Profit': prof,
        'Fees': fees,
        'MaxDD': dd,
        'Trades': buys,
        'Params': f"G={best_g}, R<{best_r}"
    }

def main():
    files = {
        '5m': 'data/bybit_btc_usdt_linear_5m_full.csv',
        '15m': 'data/bybit_btcusdt_linear_15m_full.csv',
        '1h': 'data/bybit_btcusdt_linear_1h_full.csv',
        # '1m': 'data/bybit_btcusdt_linear_1m_full.csv' # Uncomment when ready
    }
    
    results = []
    
    for tf, path in files.items():
        if not os.path.exists(path):
            continue
            
        print(f"Processing {tf}...")
        df = pd.read_csv(path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        df['rsi'] = calculate_rsi(df['close'])
        
        # Years to test: 2021, 2022, 2023, 2024, 2025 (partial)
        years = [2021, 2022, 2023, 2024, 2025]
        
        for year in years:
            # Define periods
            start_test = f"{year}-01-01"
            end_test = f"{year}-12-31"
            
            start_train = f"{year-1}-01-01"
            end_train = f"{year-1}-12-31"
            
            train_df = df[start_train:end_train]
            test_df = df[start_test:end_test]
            
            if len(train_df) < 1000 or len(test_df) < 100:
                print(f"  Skipping {year} (insufficient data)")
                continue
                
            res = process_year(year, train_df, test_df, tf)
            results.append(res)
            print(f"  {year}: {res['Return']:.2f}% ({res['Params']})")

    # Display Summary Table
    print("\n" + "="*90)
    print(f"{'Year':<6} | {'TF':<4} | {'Return':<8} | {'Profit':<10} | {'Fees':<10} | {'MaxDD':<10} | {'Trades':<6} | {'Params'}")
    print("-" * 90)
    
    for r in results:
        print(f"{r['Year']:<6} | {r['Timeframe']:<4} | {r['Return']:>7.2f}% | {r['Profit']:>9.0f} | {r['Fees']:>9.0f} | {r['MaxDD']:>9.0f} | {r['Trades']:>6} | {r['Params']}")
    print("="*90)

if __name__ == "__main__":
    main()
