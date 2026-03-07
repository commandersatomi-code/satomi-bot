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

def run_simulation(df):
    closes = df['close'].values
    atr_shorts = df['atr_short'].values
    atr_longs = df['atr_long'].values
    smas = df['sma'].values
    dates = df.index
    
    initial_equity = 1000000 
    positions = [] 
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    max_drawdown = 0
    peak_equity = initial_equity
    
    # ISHIKAWA MODEL SETTINGS
    base_tp = 14.0
    fixed_sl = 15.0
    entry_mult = 1.2
    
    trade_log = []
    
    for i in range(1, len(closes)):
        price = closes[i]
        curr_atr = atr_shorts[i]
        long_atr = atr_longs[i]
        curr_sma = smas[i]
        
        if np.isnan(curr_sma) or np.isnan(long_atr): continue
        
        vol_ratio = curr_atr / long_atr
        vol_ratio = max(0.5, min(2.0, vol_ratio))
        
        dynamic_tp_mult = base_tp * vol_ratio
        sl_mult = fixed_sl
        
        interval = curr_atr * entry_mult
        tp_width = curr_atr * dynamic_tp_mult
        sl_width = curr_atr * sl_mult
        
        # Entry
        should_buy = False
        if len(positions) == 0:
            if price <= curr_sma - interval: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
            
        if should_buy:
            positions.append({'price': price, 'tp': tp_width, 'sl': sl_width, 'date': dates[i]})
            total_fees += price * fee_rate
            
        # Exit
        remaining = []
        for pos in positions:
            if price >= pos['price'] + pos['tp']:
                profit = price - pos['price']
                total_realized_profit += profit
                total_fees += price * fee_rate
                trade_log.append({'type': 'WIN', 'profit': profit, 'hold_time': i}) # hold_timeは簡易
            elif price <= pos['price'] - pos['sl']:
                loss = price - pos['price']
                total_realized_profit += loss
                total_fees += price * fee_rate
                trade_log.append({'type': 'LOSS', 'profit': loss, 'hold_time': i})
            else:
                remaining.append(pos)
        positions = remaining
        
        unrealized = sum(price - p['price'] for p in positions)
        equity_now = initial_equity + total_realized_profit - total_fees + unrealized
        
        if equity_now <= 0: return -1, 0, 0, 0
        if equity_now > peak_equity: peak_equity = equity_now
        dd = peak_equity - equity_now
        if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p['price'] for p in positions)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    return final_equity, max_drawdown, len(trade_log), trade_log

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
    
    # 全期間テスト (2020-2026)
    # 過去5年と直近1年を分けて表示
    
    periods = [
        ("Past 5 Years (2020-2024)", df[df.index < '2025-01-25']),
        ("Recent 1 Year (2025-2026)", df[df.index >= '2025-01-25'])
    ]
    
    print(f"\n=======================================================")
    print(f"   ISHIKAWA HYBRID GRID: THE FINAL VERDICT")
    print(f"=======================================================")
    print(f"Settings: 1H Timeframe | Entry=1.2 ATR")
    print(f"          TP = Breathing (Base 14.0 * VolRatio)")
    print(f"          SL = Fixed (15.0 ATR)")
    print(f"-------------------------------------------------------")
    
    total_ret_pct = 0
    
    for name, data in periods:
        final, dd, trades_count, logs = run_simulation(data)
        
        print(f"\n>> {name}")
        if final == -1:
            print("   RESULT: BANKRUPT")
        else:
            ret = (final - 1000000) / 1000000 * 100
            ratio = dd / (final - 1000000) if final > 1000000 else 9.99
            
            wins = len([t for t in logs if t['type'] == 'WIN'])
            win_rate = wins / trades_count * 100 if trades_count > 0 else 0
            
            print(f"   Return:    {ret:>8.2f}%")
            print(f"   MaxDD:     {dd:>11,.0f} ({dd/10000:.1f}%)")
            print(f"   Trades:    {trades_count:>8}")
            print(f"   Win Rate:  {win_rate:>8.1f}%")
            print(f"   DD/Ret:    {ratio:>8.2f}")

    print(f"\n=======================================================")

if __name__ == "__main__":
    main()
