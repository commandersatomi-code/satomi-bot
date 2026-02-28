import pandas as pd
import numpy as np
import os

def calculate_indicators(df, atr_period=14, sma_period=20):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean().ffill().bfill()
    sma = close.rolling(window=sma_period).mean()
    return atr, sma

def run_simulation(closes, atrs, smas, tp_mult, sl_mult):
    initial_equity = 1000000 
    positions = []
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    max_drawdown = 0
    peak_equity = initial_equity
    atr_multiplier = 1.2 # Entry Fixed
    
    for i in range(1, len(closes)):
        price = closes[i]
        current_atr = atrs[i]
        current_sma = smas[i]
        if np.isnan(current_sma): continue
        
        interval = current_atr * atr_multiplier
        tp_width = current_atr * tp_mult
        sl_width = current_atr * sl_mult
        
        # Entry
        should_buy = False
        if len(positions) == 0:
            if price <= current_sma - interval: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
            
        if should_buy:
            positions.append({'price': price, 'tp': tp_width, 'sl': sl_width})
            total_fees += price * fee_rate
            
        # Exit
        remaining = []
        for pos in positions:
            if price >= pos['price'] + pos['tp']:
                total_realized_profit += (price - pos['price'])
                total_fees += price * fee_rate
            elif price <= pos['price'] - pos['sl']:
                total_realized_profit += (price - pos['price']) # Loss
                total_fees += price * fee_rate
            else:
                remaining.append(pos)
        positions = remaining
        
        unrealized = sum(price - p['price'] for p in positions)
        equity_now = initial_equity + total_realized_profit - total_fees + unrealized
        
        if equity_now <= 0: return -1, 0 # Bankrupt
        if equity_now > peak_equity: peak_equity = equity_now
        dd = peak_equity - equity_now
        if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p['price'] for p in positions)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    return final_equity, max_drawdown

def main():
    path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    atr, sma = calculate_indicators(df)
    df['atr'] = atr
    df['sma'] = sma
    
    # 過去5年で最適化
    test_df = df[df.index < '2025-01-25']
    
    closes = test_df['close'].values
    atrs = test_df['atr'].values
    smas = test_df['sma'].values
    
    tp_mult = 14.0 # Fixed based on previous optimization
    sl_candidates = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 15.0]
    
    print(f"\n--- SL Optimization (Entry=1.2, TP=14.0) ---")
    print(f"{ 'SL (ATR)':<10} | {'Return':<10} | {'MaxDD':<12} | {'Ratio':<8}")
    print("-" * 50)
    
    for sl in sl_candidates:
        final, dd = run_simulation(closes, atrs, smas, tp_mult, sl)
        
        if final == -1:
            print(f"{sl:<10.1f} | BANKRUPT   | ---          | ---")
        else:
            ret = (final - 1000000) / 1000000 * 100
            ratio = dd / (final - 1000000) if final > 1000000 else 9.99
            print(f"{sl:<10.1f} | {ret:>8.2f}% | {dd:>11,.0f} | {ratio:>8.2f}")

if __name__ == "__main__":
    main()
