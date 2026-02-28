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
    
    print("Collecting trade data for optimization...")
    
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
            
            # SLに触れる前に到達できた最大ATRを計測
            valid_max_profit = 0
            
            future_prices = closes[i+1 : i+2000]
            
            for future_price in future_prices:
                if future_price <= sl_price:
                    break 
                
                profit = future_price - entry_price
                if profit > 0:
                    p_atr = profit / current_atr
                    if p_atr > valid_max_profit:
                        valid_max_profit = p_atr
            
            trades.append(valid_max_profit)
            last_entry_price = entry_price

    print(f"Total Trades: {len(trades)}")
    
    print("\n--- Theoretical Optimization: Best TP Level ---")
    print(f"{ 'TP (ATR)':<10} | {'Win Rate':<10} | {'Expectancy':<12} | {'Score'}")
    print("-" * 50)
    
    best_tp = 0
    best_exp = -np.inf
    
    tp_candidates = np.arange(1.0, 20.5, 0.5)
    
    for tp in tp_candidates:
        wins = sum(1 for x in trades if x >= tp)
        loss_rate = 1.0 - (wins / len(trades))
        expectancy = ((wins / len(trades)) * tp) - (loss_rate * sl_threshold)
        
        # なだらかさを確認するため、全データを表示に近い形で出力
        if tp % 1.0 == 0 or expectancy > best_exp:
             flag = '*' if expectancy > best_exp else ''
             print(f"{tp:<10.1f} | {wins/len(trades)*100:>9.1f}% | {expectancy:>12.2f} | {flag}")
        
        if expectancy > best_exp:
            best_exp = expectancy
            best_tp = tp
            
    print("-" * 50)
    print(f"OPTIMAL TP: {best_tp:.1f} ATR")
    print(f"Max Expectancy: {best_exp:.2f} ATR per trade")

def main():
    path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['atr'] = calculate_indicators(df)
    
    test_df = df[df.index < '2025-01-25']
    
    analyze_optimal_tp(test_df, 1.0) 

if __name__ == "__main__":
    main()
