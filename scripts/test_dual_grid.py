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

def run_dual_grid(df, atr_multiplier):
    closes = df['close'].values
    atrs = df['atr'].values
    smas = df['sma'].values
    
    initial_equity = 1000000 
    
    # Positions
    # {price, target, type} type='mean_reversion' or 'trend_follow'
    positions = [] 
    
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    
    max_drawdown = 0
    peak_equity = initial_equity
    trade_count = 0
    
    # 順張り用の「一度エントリーしたら、さらに上がらないと次は入らない」制御
    last_trend_entry_price = 0
    
    for i in range(1, len(closes)):
        price = closes[i]
        current_atr = atrs[i]
        current_sma = smas[i]
        
        if np.isnan(current_sma): continue
        
        interval = current_atr * atr_multiplier
        
        # --- Entry Logic ---
        
        # 1. 逆張り (Mean Reversion)
        # SMAより下に乖離したら買う
        mr_target_price = current_sma - interval
        should_buy_mr = False
        
        # ポジション管理（簡易版：逆張りはナンピンOK）
        mr_positions = [p for p in positions if p['type'] == 'mr']
        if len(mr_positions) == 0:
            if price <= mr_target_price: should_buy_mr = True
        else:
            if price <= mr_positions[-1]['price'] - interval: should_buy_mr = True
            
        if should_buy_mr:
            # 利確目標は「買った幅」戻ること（SMA回帰狙い）
            positions.append({
                'price': price, 
                'target': interval, 
                'type': 'mr'
            })
            trade_count += 1
            total_fees += price * fee_rate

        # 2. 順張り (Trend Follow)
        # SMAより上に乖離したら買う（ブレイクアウト）
        tf_target_price = current_sma + interval
        should_buy_tf = False
        
        # 順張りは「高値更新」的なロジックが必要
        # 単に「SMA+ATR以上なら買う」だと、ずっと買い続けてしまう。
        # 「SMA+ATRを超えた」かつ「前回の順張りエントリーより高い（またはノーポジ）」
        
        tf_positions = [p for p in positions if p['type'] == 'tf']
        
        if price >= tf_target_price:
            if len(tf_positions) == 0:
                # 久しぶりのブレイク
                # 直近で決済した後すぐにまた入らないよう、少しフィルタが必要だが、
                # 今回はシンプルに「SMA+ATR超え」で入る
                should_buy_tf = True
            else:
                # 既に持っているなら、さらに上がったら追撃（ピラミッティング）
                if price >= tf_positions[-1]['price'] + interval:
                    should_buy_tf = True
        
        if should_buy_tf:
            # 利確目標は「さらに伸びること」
            # ここではシンプルにグリッド幅分取れたら利確とする（回転させる）
            positions.append({
                'price': price, 
                'target': interval, # 伸びしろ
                'type': 'tf'
            })
            trade_count += 1
            total_fees += price * fee_rate
            last_trend_entry_price = price

        # --- Exit Logic (共通) ---
        remaining = []
        for pos in positions:
            # 逆張りも順張りも「買った価格 + Target」で利確
            # 逆張り：リバウンド狙い
            # 順張り：トレンド進行狙い
            
            sell_target = pos['price'] + pos['target']
            
            if price >= sell_target:
                profit = price - pos['price']
                total_realized_profit += profit
                total_fees += price * fee_rate
            else:
                remaining.append(pos)
        
        positions = remaining
        
        # Equity Update
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
    
    # 直近1年（2025年〜）
    test_df = df[df.index >= '2025-01-25']
    
    print(f"\n--- Dual Grid (Mean Reversion + Trend Follow) ---")
    print(f"Period: {test_df.index[0].date()} to {test_df.index[-1].date()}")
    print("-" * 65)
    print(f"{ 'ATR Mult':<8} | { 'Return':<10} | { 'MaxDD':<12} | { 'Trades':<8} | { 'Ratio':<6}")
    print("-" * 65)
    
    for m in [1.0, 1.5, 2.0]:
        final, dd, trades = run_dual_grid(test_df, m)
        ret = (final - 1000000) / 1000000 * 100
        ratio = dd / (final - 1000000) if final > 1000000 else 9.99
        print(f"{m:<8} | {ret:>8.2f}% | {dd:>11,.0f} | {trades:>8} | {ratio:>6.2f}")
    
    print("-" * 65)
    print("* Logic: Buy if Price < SMA-Interval (Reversion)")
    print("         Buy if Price > SMA+Interval (Trend Follow)")

if __name__ == "__main__":
    main()
