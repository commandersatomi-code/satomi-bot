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

def run_simulation(df, rsi_limit, strategy_name):
    # RSI計算
    closes = df['close'].values
    rsi_values = df['rsi'].values
    
    # 簡易最適化（Monthly）を入れると時間がかかるため、
    # フェアな比較のために、ここでも「Grid=2000固定」で基礎体力を比較します。
    # Grid幅が同じ条件で、RSIフィルターの有無がどう効くかを見ます。
    
    grid_size = 2000
    initial_equity = 1000000 
    positions = []
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    
    grid_levels = np.floor(closes / grid_size).astype(int)
    prev_level = grid_levels[0]
    
    max_drawdown = 0
    peak_equity = initial_equity
    
    trade_count = 0
    
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
                    trade_count += 1
                    total_fees += price * fee_rate
                    
        # SELL
        elif new_grid_level > prev_level:
            diff = new_grid_level - prev_level
            for _ in range(diff):
                if positions:
                    bought = positions.pop(0)
                    total_realized_profit += (price - bought)
                    total_fees += price * fee_rate
        
        prev_level = new_grid_level
        
        # DD Check
        unrealized = sum(price - p for p in positions) if positions else 0
        current_equity = initial_equity + total_realized_profit - total_fees + unrealized
        
        if current_equity > peak_equity: peak_equity = current_equity
        dd = peak_equity - current_equity
        if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p for p in positions) if positions else 0
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    
    ret_pct = (final_equity - 1000000) / 1000000 * 100
    
    print(f"{strategy_name:<20} | {ret_pct:>8.2f}% | {max_drawdown:>11,.0f} | {trade_count:>8}")

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['rsi'] = calculate_rsi(df['close'])
    
    # 2020年〜2025年1月までのデータで検証
    split_date = df.index[-1] - pd.Timedelta(days=365)
    analysis_df = df[df.index < split_date]
    
    print(f"\n--- RSI vs No RSI (Pure Grid) Comparison ---")
    print(f"Period: {analysis_df.index[0].date()} to {analysis_df.index[-1].date()}")
    print("-" * 60)
    print(f"{'Strategy':<20} | {'Return':<10} | {'MaxDD':<12} | {'Trades':<8}")
    print("-" * 60)
    
    # 1. With RSI Filter (Limit < 60)
    run_simulation(analysis_df, 60, "RSI < 60 (Loose)")
    
    # 2. No RSI Filter (Pure Grid)
    run_simulation(analysis_df, 100, "No RSI (Pure Grid)")
    
    print("-" * 60)

if __name__ == "__main__":
    main()
