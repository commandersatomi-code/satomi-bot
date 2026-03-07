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

def run_simulation(df, atr_multiplier):
    closes = df['close'].values
    atrs = df['atr'].values
    smas = df['sma'].values
    
    initial_equity = 1000000 
    positions = []
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    max_drawdown = 0
    peak_equity = initial_equity
    trade_count = 0
    
    for i in range(1, len(closes)):
        price = closes[i]
        current_atr = atrs[i]
        current_sma = smas[i]
        if np.isnan(current_sma): continue
        
        interval = current_atr * atr_multiplier
        entry_target = current_sma - interval
        
        should_buy = False
        if len(positions) == 0:
            if price <= entry_target: should_buy = True
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
        positions = remaining
        
        unrealized = sum(price - p['price'] for p in positions)
        equity_now = initial_equity + total_realized_profit - total_fees + unrealized
        
        # 破綻チェック（資産がマイナスになったら終了）
        if equity_now <= 0:
            return -1, initial_equity, trade_count # Bankruptcy
            
        if equity_now > peak_equity: peak_equity = equity_now
        dd = peak_equity - equity_now
        if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p['price'] for p in positions)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    return final_equity, max_drawdown, trade_count

def main():
    path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    atr, sma = calculate_indicators(df)
    df['atr'] = atr
    df['sma'] = sma
    
    past_df = df[df.index < '2025-01-25']
    recent_df = df[df.index >= '2025-01-25']
    
    multipliers = [0.5, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0]
    
    print("\n--- Hyper-Aggression Analysis: 1H ATR Grid ---")
    
    for period_name, data in [("Past 5 Years", past_df), ("Recent 1 Year", recent_df)]:
        print(f"\n=== {period_name} ===")
        print(f"{ 'Mult':<6} | {'Return':<10} | {'MaxDD':<12} | {'Trades':<8}")
        print("-" * 45)
        for m in multipliers:
            final, dd, trades = run_simulation(data, m)
            if final == -1:
                ret_str = "BANKRUPT"
                dd_str = "---"
            else:
                ret_str = f"{(final-1000000)/10000:>8.2f}%"
                dd_str = f"{dd:>11,.0f}"
            
            print(f"{m:<6} | {ret_str} | {dd_str} | {trades:>8}")

if __name__ == "__main__":
    main()
