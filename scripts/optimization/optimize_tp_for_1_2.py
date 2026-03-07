import pandas as pd
import numpy as np
import os

def calculate_indicators(df, atr_period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean().ffill().bfill()
    return atr

def analyze_optimal_tp(df, atr_multiplier):
    closes = df['close'].values
    atrs = df['atr'].values
    trades = []
    last_entry_price = closes[0]
    sl_threshold = 7.0 
    
    for i in range(1, len(closes) - 2000): 
        price = closes[i]
        current_atr = atrs[i]
        interval = current_atr * atr_multiplier
        if price > last_entry_price:
            last_entry_price = price
            continue
        if price <= last_entry_price - interval:
            entry_price = price
            sl_price = entry_price - (current_atr * sl_threshold)
            valid_max_profit = 0
            future_prices = closes[i+1 : i+2000]
            for future_price in future_prices:
                if future_price <= sl_price: break 
                profit = future_price - entry_price
                if profit > 0:
                    p_atr = profit / current_atr
                    if p_atr > valid_max_profit: valid_max_profit = p_atr
            trades.append(valid_max_profit)
            last_entry_price = entry_price

    best_tp = 0
    best_exp = -np.inf
    tp_candidates = np.arange(1.0, 15.5, 0.5) # 15倍までで十分
    
    print(f"\n--- Optimization for ATR {atr_multiplier} Entry ---")
    print(f"{ 'TP (ATR)':<10} | { 'Win Rate':<10} | {'Expectancy'}")
    print("-" * 40)
    
    for tp in tp_candidates:
        wins = sum(1 for x in trades if x >= tp)
        win_rate = wins / len(trades)
        expectancy = (win_rate * tp) - ((1-win_rate) * sl_threshold)
        if tp % 2.0 == 0 or expectancy > best_exp:
            print(f"{tp:<10.1f} | {win_rate*100:>9.1f}% | {expectancy:>10.2f}")
        if expectancy > best_exp:
            best_exp = expectancy
            best_tp = tp
            
    return best_tp

def main():
    path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['atr'] = calculate_indicators(df)
    
    # 過去5年で最適値を算出
    test_df = df[df.index < '2025-01-25']
    best_tp = analyze_optimal_tp(test_df, 1.2)
    print(f"\nOptimal TP for 1.2 Entry: {best_tp} ATR")

if __name__ == "__main__":
    main()
