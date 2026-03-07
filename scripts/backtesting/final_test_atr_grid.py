import pandas as pd
import numpy as np
import os

def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean().ffill().bfill()

def run_simulation(df, atr_multiplier):
    closes = df['close'].values
    atrs = df['atr'].values
    initial_equity = 1000000 
    positions = []
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    max_drawdown = 0
    peak_equity = initial_equity
    trade_count = 0
    reference_high = closes[0]
    
    for i in range(1, len(closes)):
        price = closes[i]
        current_atr = atrs[i]
        if price > reference_high: reference_high = price
        
        interval = current_atr * atr_multiplier
        should_buy = False
        if len(positions) == 0:
            if price <= reference_high - interval: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
        
        if should_buy:
            positions.append({'price': price, 'target': interval})
            trade_count += 1
            total_fees += price * fee_rate
            
        remaining = []
        for pos in positions:
            if price >= pos['price'] + pos['target']:
                total_realized_profit += (price - pos['price'])
                total_fees += price * fee_rate
            else:
                remaining.append(pos)
        
        if len(remaining) == 0 and len(positions) > 0: reference_high = price
        positions = remaining
        
        unrealized = sum(price - p['price'] for p in positions)
        equity_now = initial_equity + total_realized_profit - total_fees + unrealized
        if equity_now > peak_equity: peak_equity = equity_now
        dd = peak_equity - equity_now
        if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p['price'] for p in positions)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    return final_equity, max_drawdown, trade_count

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['atr'] = calculate_atr(df)
    
    # 【重要】直近1年間（未知のデータ）
    test_start = '2025-01-25'
    test_df = df[df.index >= test_start]
    
    print(f"\n--- FINAL TEST: The Last 1 Year (Unseen Data) ---")
    print(f"Period: {test_df.index[0].date()} to {test_df.index[-1].date()}")
    print("-" * 60)
    print(f"{ 'ATR Mult':<8} | {'Return':<10} | {'MaxDD':<12} | {'Trades':<8}")
    print("-" * 60)
    
    for m in [1.0, 1.5, 2.0]:
        final, dd, trades = run_simulation(test_df, m)
        ret = (final - 1000000) / 1000000 * 100
        print(f"{m:<8} | {ret:>8.2f}% | {dd:>11,.0f} | {trades:>8}")
    print("-" * 60)

if __name__ == "__main__":
    main()
