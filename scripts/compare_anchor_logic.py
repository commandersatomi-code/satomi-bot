import pandas as pd
import numpy as np
import os

def calculate_indicators(df, atr_period=14, sma_period=20):
    # ATR
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean().ffill().bfill()
    
    # SMA
    sma = close.rolling(window=sma_period).mean()
    
    return atr, sma

def run_simulation(df, atr_multiplier, anchor_type='high'):
    closes = df['close'].values
    atrs = df['atr'].values
    smas = df['sma'].values
    
    initial_equity = 1000000 
    positions = [] # {price, target}
    
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
        current_sma = smas[i]
        
        # 基準価格の決定
        anchor_price = 0
        if anchor_type == 'high':
            if price > reference_high: reference_high = price
            anchor_price = reference_high
        elif anchor_type == 'sma':
            if np.isnan(current_sma): continue
            anchor_price = current_sma
            
        # 買い判定
        interval = current_atr * atr_multiplier
        should_buy = False
        
        # ロジック：基準価格から一定距離離れたら買う
        # SMA基準の場合、SMA自体が下がってくるので、ナンピンの基準としては「最後の取得単価」も併用すべき
        
        entry_target = anchor_price - interval
        
        if len(positions) == 0:
            if price <= entry_target: should_buy = True
        else:
            # ポジションがある場合、最後の取得単価からさらに下がったら買う（ナンピン）
            # これは共通ロジック
            last_price = positions[-1]['price']
            if price <= last_price - interval: should_buy = True
        
        if should_buy:
            positions.append({'price': price, 'target': interval})
            trade_count += 1
            total_fees += price * fee_rate
            
        # 売り判定（共通）
        remaining = []
        for pos in positions:
            if price >= pos['price'] + pos['target']:
                total_realized_profit += (price - pos['price'])
                total_fees += price * fee_rate
            else:
                remaining.append(pos)
        
        # Reference High Reset Logic (Only for 'high' anchor)
        if anchor_type == 'high' and len(remaining) == 0 and len(positions) > 0:
            reference_high = price
            
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
    
    atr, sma = calculate_indicators(df)
    df['atr'] = atr
    df['sma'] = sma
    
    # 2020年〜2025年1月（過去データ）と 2025年〜（直近データ）を分けて表示
    
    split_date = pd.Timestamp('2025-01-25')
    past_df = df[df.index < split_date]
    recent_df = df[df.index >= split_date]
    
    print(f"\n--- Overfitting Check: Anchor Logic Comparison ---")
    print(f"Logic A: Anchor = Recent High (Old)")
    print(f"Logic B: Anchor = SMA20 (New)\n")
    
    for period_name, data in [("Past 5 Years (2020-2024)", past_df), ("Recent 1 Year (2025)", recent_df)]:
        print(f"=== {period_name} ===")
        print(f"{ 'Logic':<15} | {'Mult':<5} | {'Return':<10} | {'MaxDD':<12} | {'Trades':<8}")
        print("-" * 65)
        
        # Test Multiplier 1.5 (Standard)
        m = 1.5
        
        # Logic A (High)
        fin_h, dd_h, tr_h = run_simulation(data, m, 'high')
        ret_h = (fin_h - 1000000) / 1000000 * 100
        print(f"{ 'High Anchor':<15} | {m:<5} | {ret_h:>8.2f}% | {dd_h:>11,.0f} | {tr_h:>8}")
        
        # Logic B (SMA)
        fin_s, dd_s, tr_s = run_simulation(data, m, 'sma')
        ret_s = (fin_s - 1000000) / 1000000 * 100
        print(f"{ 'SMA20 Anchor':<15} | {m:<5} | {ret_s:>8.2f}% | {dd_s:>11,.0f} | {tr_s:>8}")
        
        print("-" * 65)
        
        # Improvement check
        if ret_s > ret_h:
            print(f"-> SMA Logic improved return by {ret_s - ret_h:.2f} points.")
        else:
             print(f"-> High Anchor Logic was better.")
        print("\n")

if __name__ == "__main__":
    main()
