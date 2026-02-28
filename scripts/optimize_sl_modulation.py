import pandas as pd
import numpy as np
import os

def calculate_indicators(df, atr_period=14, sma_period=20, long_atr_period=100):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr_short = tr.rolling(window=atr_period).mean().ffill().bfill()
    atr_long = tr.rolling(window=long_atr_period).mean().ffill().bfill()
    sma = close.rolling(window=sma_period).mean()
    return atr_short, atr_long, sma

def run_simulation(df, sl_mod_factor):
    # sl_mod_factor: ボラティリティ比率に対するSLの感度
    # 0.0 = 完全固定（比率無視）
    # 1.0 = TPと同じように完全に連動
    # 0.5 = 半分の感度で連動
    
    closes = df['close'].values
    atr_shorts = df['atr_short'].values
    atr_longs = df['atr_long'].values
    smas = df['sma'].values
    
    initial_equity = 1000000 
    positions = [] 
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    max_drawdown = 0
    peak_equity = initial_equity
    
    base_tp = 14.0
    base_sl = 15.0
    entry_mult = 1.2
    
    for i in range(1, len(closes)):
        price = closes[i]
        curr_atr = atr_shorts[i]
        long_atr = atr_longs[i]
        curr_sma = smas[i]
        
        if np.isnan(curr_sma) or np.isnan(long_atr): continue
        
        # 変動比率（中心は1.0）
        raw_ratio = curr_atr / long_atr
        capped_ratio = max(0.5, min(2.0, raw_ratio))
        
        # TPは素直に連動 (1.0倍)
        tp_mult = base_tp * capped_ratio
        
        # SLは係数を使って連動度合いを調整
        # 1.0 + (比率 - 1.0) * 感度
        # 例：比率1.5, 感度0.5 -> 1.0 + 0.5*0.5 = 1.25倍
        sl_ratio = 1.0 + (capped_ratio - 1.0) * sl_mod_factor
        
        # 負にならないよう安全策
        sl_ratio = max(0.1, sl_ratio)
        sl_mult = base_sl * sl_ratio
        
        interval = curr_atr * entry_mult
        tp_width = curr_atr * tp_mult
        sl_width = curr_atr * sl_mult
        
        # Entry
        should_buy = False
        if len(positions) == 0:
            if price <= curr_sma - interval: should_buy = True
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
                total_realized_profit += (price - pos['price'])
                total_fees += price * fee_rate
            else:
                remaining.append(pos)
        positions = remaining
        
        unrealized = sum(price - p['price'] for p in positions)
        equity_now = initial_equity + total_realized_profit - total_fees + unrealized
        
        if equity_now <= 0: return -1, 0
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
    
    atr_s, atr_l, sma = calculate_indicators(df)
    df['atr_short'] = atr_s
    df['atr_long'] = atr_l
    df['sma'] = sma
    
    past_df = df[df.index < '2025-01-25']
    
    print(f"\n--- Optimizing SL Modulation Factor (Past 5 Years) ---")
    print(f"{ 'SL Factor':<10} | {'Return':<10} | {'MaxDD':<12} | {'Ratio':<8}")
    print("-" * 55)
    
    # 0.0 (固定) から 1.0 (完全連動)、さらに 1.5 (過剰反応) まで
    factors = [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2]
    
    for f in factors:
        final, dd = run_simulation(past_df, f)
        if final == -1:
            print(f"{f:<10.1f} | BANKRUPT")
        else:
            ret = (final - 1000000) / 1000000 * 100
            ratio = dd / (final - 1000000) if final > 1000000 else 9.99
            print(f"{f:<10.1f} | {ret:>8.2f}% | {dd:>11,.0f} | {ratio:>8.2f}")

if __name__ == "__main__":
    main()
