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

def run_fast_sim(closes, atr_shorts, atr_longs, smas, entry_m, tp_base, sl_fixed):
    initial_equity = 1000000 
    positions = [] 
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    max_drawdown = 0
    peak_equity = initial_equity
    
    for i in range(1, len(closes)):
        price = closes[i]
        curr_atr = atr_shorts[i]
        long_atr = atr_longs[i]
        curr_sma = smas[i]
        if np.isnan(curr_sma) or np.isnan(long_atr): continue
        
        vol_ratio = max(0.5, min(2.0, curr_atr / long_atr))
        interval = curr_atr * entry_m
        tp_w = curr_atr * (tp_base * vol_ratio)
        sl_w = curr_atr * sl_fixed
        
        should_buy = False
        if len(positions) == 0:
            if price <= curr_sma - interval: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
        if should_buy:
            positions.append({'price': price, 'tp': tp_w, 'sl': sl_w})
            total_fees += price * fee_rate
            
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
            
    final_equity = initial_equity + total_realized_profit - total_fees + sum(closes[-1]-p['price'] for p in positions)
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
    
    # 半減期ベースの1年刻み
    periods = [
        ("Year 1: Post-Halving 3 (2020/05-2021/05)", "2020-05-11", "2021-05-11"),
        ("Year 2: Post-Halving 3 (2021/05-2022/05)", "2021-05-11", "2022-05-11"),
        ("Year 3: Post-Halving 3 (2022/05-2023/05)", "2022-05-11", "2023-05-11"),
        ("Year 4: Post-Halving 3 (2023/05-2024/04)", "2023-05-11", "2024-04-20"),
        ("Year 1: Post-Halving 4 (2024/04-2025/04)", "2024-04-20", "2025-04-20"),
        ("Latest: Current Status (2025/04-2026/01)", "2025-04-20", "2026-01-25")
    ]
    
    entry_opts = [1.2, 1.5, 1.8]
    tp_opts = [5.0, 10.0, 15.0]
    sl_opts = [10.0, 15.0, 20.0]
    
    print(f"\n--- Halving Cycle Precision Scan (1 Year Windows) ---")
    
    for name, start, end in periods:
        data = df[(df.index >= start) & (df.index < end)]
        if len(data) < 100: continue
            
        best_cfg = None
        best_score = -np.inf
        
        closes = data['close'].values
        as_ = data['atr_short'].values
        al_ = data['atr_long'].values
        sm_ = data['sma'].values
        
        for e in entry_opts:
            for tp in tp_opts:
                for sl in sl_opts:
                    final, dd = run_fast_sim(closes, as_, al_, sm_, e, tp, sl)
                    if final == -1: continue
                    ret = (final - 1000000) / 1000000 * 100
                    score = ret / (dd / 10000) if dd > 5000 else ret
                    
                    if score > best_score:
                        best_score = score
                        best_cfg = (e, tp, sl, ret, dd)
        
        print(f"\n>> {name}")
        if best_cfg:
            e, tp, sl, ret, dd = best_cfg
            print(f"   Best: Entry={e}, TP={tp}, SL={sl}")
            print(f"   Perf: Return={ret:>6.2f}%, MaxDD={dd:>8,.0f}")
        else:
            print("   No viable configuration found.")

if __name__ == "__main__":
    main()
