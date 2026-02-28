import pandas as pd
import numpy as np
import sys
import os

# パスを解決するために親ディレクトリを追加
sys.path.append(os.getcwd())

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def run_backtest_fast(closes, rsi_values, grid_size, rsi_limit, fee_rate=0.0006):
    # 最適化用なので高速化のため履歴は取らない簡易版
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

def optimize(df, grid_opts, rsi_opts):
    best_score = -np.inf
    best_params = (1000, 100)
    closes = df['close'].values
    rsis = df['rsi'].values
    
    for g in grid_opts:
        for r in rsi_opts:
            eq, dd, buys = run_backtest_fast(closes, rsis, g, r)
            if buys == 0: score = -999999
            else: score = (eq - 1000000) / (dd + 1)
            
            if score > best_score:
                best_score = score
                best_params = (g, r)
    return best_params

def run_simulation_with_history(df, window_days):
    rows_per_day = 1
    window_rows = int(window_days * rows_per_day)
    
    test_start_idx = window_rows
    grid_opts = [500, 1000, 2000, 3000, 5000, 10000]
    rsi_opts = [30, 40, 50, 70, 100]
    
    history = []
    positions = [] # {price: float, date: datetime}
    
    # グローバルな損益計算用
    total_realized = 0
    total_fees = 0
    fee_rate = 0.0006
    
    while test_start_idx < len(df):
        test_end_idx = min(test_start_idx + window_rows, len(df))
        
        # 1. 過去のデータで最適化
        train_df = df.iloc[test_start_idx - window_rows : test_start_idx]
        best_g, best_r = optimize(train_df, grid_opts, rsi_opts)
        
        # 2. 直近のデータでテスト実行
        test_df = df.iloc[test_start_idx : test_end_idx]
        
        closes = test_df['close'].values
        rsis = test_df['rsi'].values
        dates = test_df.index
        
        grid_levels = np.floor(closes / best_g).astype(int)
        if len(grid_levels) == 0: break
        prev_level = grid_levels[0]
        
        for i in range(1, len(closes)):
            price = closes[i]
            rsi = rsis[i]
            date = dates[i]
            new_grid_level = grid_levels[i]
            
            # BUY
            if new_grid_level < prev_level:
                diff = prev_level - new_grid_level
                for _ in range(diff):
                    if rsi < best_r:
                        positions.append({'price': price, 'date': date})
                        total_fees += price * fee_rate
                        history.append({
                            'Date': date,
                            'Type': 'BUY',
                            'Price': price,
                            'Profit': np.nan,
                            'RSI_Limit': best_r,
                            'Grid_Size': best_g
                        })
            
            # SELL
            elif new_grid_level > prev_level:
                diff = new_grid_level - prev_level
                for _ in range(diff):
                    if positions:
                        bought = positions.pop(0)
                        profit = price - bought['price']
                        total_realized += profit
                        total_fees += price * fee_rate
                        
                        history.append({
                            'Date': date,
                            'Type': 'SELL',
                            'Price': price,
                            'Profit': profit,
                            'Hold_Days': (date - bought['date']).days,
                            'RSI_Limit': best_r,
                            'Grid_Size': best_g
                        })
            
            prev_level = new_grid_level
            
        test_start_idx += window_rows
        
    return pd.DataFrame(history)

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    if not os.path.exists(path):
        print("Data file not found.")
        return

    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['rsi'] = calculate_rsi(df['close'])
    
    # 2023年以降でテスト
    test_df = df[df.index >= '2023-01-01']
    
    print("Generating trade history...")
    history_df = run_simulation_with_history(test_df, 30)
    
    if history_df.empty:
        print("No trades found.")
        return

    # 見やすく整形
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', 1000)
    
    print("\n--- Trade History (Daily + Monthly Opt) ---")
    print(history_df[['Date', 'Type', 'Price', 'Profit', 'Hold_Days']].to_string(index=False))
    
    total_profit = history_df['Profit'].sum()
    print("\n" + "="*40)
    print(f"Total Realized Profit (Points): {total_profit:,.2f}")
    print(f"Total Trades: {len(history_df[history_df['Type'] == 'BUY'])} Buys, {len(history_df[history_df['Type'] == 'SELL'])} Sells")
    print("="*40)

if __name__ == "__main__":
    main()
