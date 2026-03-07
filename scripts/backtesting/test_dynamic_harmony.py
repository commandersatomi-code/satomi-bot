import pandas as pd
import numpy as np
import os

def calculate_indicators(df, atr_period=14, sma_period=20, long_atr_period=100):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    
    # 短期ATR（今の歩幅）
    atr_short = tr.rolling(window=atr_period).mean().ffill().bfill()
    
    # 長期ATR（普段の歩幅）
    atr_long = tr.rolling(window=long_atr_period).mean().ffill().bfill()
    
    sma = close.rolling(window=sma_period).mean()
    
    return atr_short, atr_long, sma

def run_dynamic_simulation(df, base_tp, base_sl):
    closes = df['close'].values
    atr_shorts = df['atr_short'].values
    atr_longs = df['atr_long'].values
    smas = df['sma'].values
    
    initial_equity = 1000000 
    positions = [] # {price, tp, sl}
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    max_drawdown = 0
    peak_equity = initial_equity
    trade_count = 0
    
    entry_mult = 1.2 # Entry is fixed at 1.2 * Current ATR
    
    for i in range(1, len(closes)):
        price = closes[i]
        curr_atr = atr_shorts[i]
        long_atr = atr_longs[i]
        curr_sma = smas[i]
        
        if np.isnan(curr_sma) or np.isnan(long_atr): continue
        
        # 変動係数 (Volatility Ratio)
        # 今が普段よりどれくらい元気か？
        # 元気なら 1.5倍、静かなら 0.8倍のようになる
        vol_ratio = curr_atr / long_atr
        
        # 極端な値を防ぐためのキャップ（0.5倍 〜 2.0倍 の範囲に収める）
        vol_ratio = max(0.5, min(2.0, vol_ratio))
        
        # 動的なTP/SL
        # 元気な時はTPを伸ばし、静かな時は手前で利確する
        dynamic_tp_mult = base_tp * vol_ratio
        dynamic_sl_mult = base_sl * vol_ratio 
        
        # SLも変動させるべきか？
        # 「静かな時ほど狭いSLで切られる」のはノイズ死のリスクがあるが、
        # 「静かな時は大怪我もしにくい」ので理にはかなっている。
        # 今回は両方変動させる（縮尺を変えるイメージ）。
        
        interval = curr_atr * entry_mult
        tp_width = curr_atr * dynamic_tp_mult
        sl_width = curr_atr * dynamic_sl_mult
        
        # Entry
        should_buy = False
        if len(positions) == 0:
            if price <= curr_sma - interval: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
            
        if should_buy:
            positions.append({'price': price, 'tp': tp_width, 'sl': sl_width})
            trade_count += 1
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
        
        if equity_now <= 0: return -1, initial_equity, trade_count
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
    
    # 指標計算
    atr_s, atr_l, sma = calculate_indicators(df)
    df['atr_short'] = atr_s
    df['atr_long'] = atr_l
    df['sma'] = sma
    
    past_df = df[df.index < '2025-01-25']
    recent_df = df[df.index >= '2025-01-25']
    
    # Base Settings (Fixed values were TP=14.0, SL=15.0)
    base_tp = 14.0
    base_sl = 15.0
    
    print(f"\n--- Dynamic Harmony (Breathing TP/SL) ---")
    print(f"Base TP={base_tp}, Base SL={base_sl}, Modulated by ATR Ratio")
    print("-" * 65)
    
    for period_name, data in [("Past 5 Years", past_df), ("Recent 1 Year", recent_df)]:
        final, dd, trades = run_dynamic_simulation(data, base_tp, base_sl)
        
        if final == -1:
            print(f"=== {period_name} ===\nBANKRUPT")
        else:
            ret = (final - 1000000) / 1000000 * 100
            ratio = dd / (final - 1000000) if final > 1000000 else 9.99
            
            print(f"=== {period_name} ===")
            print(f"Return: {ret:>8.2f}%")
            print(f"MaxDD:  {dd:>11,.0f} ({dd/10000:.1f}%)")
            print(f"Trades: {trades:>8}")
            print(f"Ratio:  {ratio:>8.2f}")

if __name__ == "__main__":
    main()
