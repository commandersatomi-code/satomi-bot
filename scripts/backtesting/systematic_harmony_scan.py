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
    trade_count = 0
    
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
        
        # Entry
        should_buy = False
        if len(positions) == 0:
            if price <= curr_sma - interval: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
        if should_buy:
            positions.append({'price': price, 'tp': tp_w, 'sl': sl_w})
            total_fees += price * fee_rate
            trade_count += 1
            
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
        if equity_now <= 0: return -1, 0, 0
        if equity_now > peak_equity: peak_equity = equity_now
        dd = peak_equity - equity_now
        if dd > max_drawdown: max_drawdown = dd
            
    final_equity = initial_equity + total_realized_profit - total_fees + sum(closes[-1]-p['price'] for p in positions)
    return final_equity, max_drawdown, trade_count

def main():
    path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    atr_s, atr_l, sma = calculate_indicators(df)
    
    # 全期間 (2020-2026) でのタフな最適化
    closes = df['close'].values
    atr_shorts = atr_s.values
    atr_longs = atr_l.values
    smas = sma.values
    
    entry_range = np.arange(1.2, 2.1, 0.2) # 1.2, 1.4, 1.6, 1.8, 2.0
    tp_range = [5.0, 10.0, 15.0]
    sl_range = [10.0, 15.0, 20.0]
    
    print(f"\n--- Systematic Harmony Scan (1H All-Time) ---")
    print(f"{'Entry':<6} | {'TP':<5} | {'SL':<5} | {'Return':<10} | {'MaxDD':<10} | {'Trades':<6} | {'Score'}")
    print("-" * 70)
    
    results = []
    
    for e in entry_range:
        best_e_score = -np.inf
        best_e_config = None
        
        for tp in tp_range:
            for sl in sl_range:
                final, dd, tr = run_fast_sim(closes, atr_shorts, atr_longs, smas, e, tp, sl)
                
                if final == -1: continue
                
                ret = (final - 1000000) / 1000000 * 100
                score = ret / (dd / 10000) if dd > 0 else ret
                
                # 表示（各Entryの試行を簡潔に）
                # print(f"{e:.1f} | {tp:>4.1f} | {sl:>4.1f} | {ret:>8.2f}% | {dd:>10,.0f} | {tr:>6}")
                
                if score > best_e_score:
                    best_e_score = score
                    best_e_config = (e, tp, sl, ret, dd, tr, score)
        
        if best_e_config:
            e, tp, sl, ret, dd, tr, sc = best_e_config
            print(f"{e:.1f}    | {tp:>4.1f} | {sl:>4.1f} | {ret:>8.2f}% | {dd:>9,.0f} | {tr:>6} | {sc:.2f}")
            results.append(best_e_config)

if __name__ == "__main__":
    main()
