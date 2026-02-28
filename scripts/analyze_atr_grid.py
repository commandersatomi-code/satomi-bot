import pandas as pd
import numpy as np
import os

def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr.fillna(method='bfill')

def run_atr_grid_simulation(df, atr_multiplier):
    # RSIなし、ATR連動グリッド
    
    closes = df['close'].values
    atrs = df['atr'].values
    
    initial_equity = 1000000 
    
    # Position構造: {'price': float, 'target_profit': float}
    positions_detailed = []
    
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    
    max_drawdown = 0
    peak_equity = initial_equity
    trade_count = 0
    
    # 基準価格（最初は始値）
    reference_price = closes[0]
    
    # 初期の間隔（最初のATRに基づく）
    current_interval = atrs[0] * atr_multiplier
    
    for i in range(1, len(closes)):
        price = closes[i]
        current_atr = atrs[i]
        
        # 1. 買い判定
        # 基準より「今のATRに基づいた間隔」下がったら買う
        # 間隔は常に最新のATRで更新され続ける（呼吸するように）
        
        # ※ここでの工夫：
        # 「ポジションを持つたびに間隔を再計算」するか、「日々ATRに合わせて間隔を変える」か
        # 自然なのは「日々変わる」こと。
        # reference_price（前回の基準）から、今のATR * 倍率 分下がったら買う
        
        dynamic_interval = current_atr * atr_multiplier
        
        if price <= reference_price - dynamic_interval:
            buy_price = price
            target_profit = dynamic_interval # 利確幅もその時のボラティリティに合わせる
            
            positions_detailed.append({'price': buy_price, 'target_profit': target_profit})
            trade_count += 1
            total_fees += buy_price * fee_rate
            
            reference_price = buy_price
            
        # 2. 売り判定
        remaining_positions = []
        for pos in positions_detailed:
            buy_p = pos['price']
            target = pos['target_profit']
            sell_target = buy_p + target
            
            if price >= sell_target:
                profit = price - buy_p
                total_realized_profit += profit
                total_fees += price * fee_rate
            else:
                remaining_positions.append(pos)
        
        # ポジションが減った場合の基準価格リセット
        if len(remaining_positions) < len(positions_detailed):
            if len(remaining_positions) == 0:
                reference_price = price
            else:
                last_pos = remaining_positions[-1]
                reference_price = last_pos['price']
                
        positions_detailed = remaining_positions
        
        # Equity Update
        unrealized = sum(price - p['price'] for p in positions_detailed)
        current_equity = initial_equity + total_realized_profit - total_fees + unrealized
        
        if current_equity > peak_equity: peak_equity = current_equity
        dd = peak_equity - current_equity
        if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p['price'] for p in positions_detailed)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    
    return final_equity, max_drawdown, trade_count

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    # ATR計算
    df['atr'] = calculate_atr(df)
    
    # 2020年〜2025年1月までのデータ
    split_date = df.index[-1] - pd.Timedelta(days=365)
    analysis_df = df[df.index < split_date]
    
    multipliers = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]
    
    print(f"\n--- ATR-Based Breathing Grid Analysis ---")
    print(f"Period: {analysis_df.index[0].date()} to {analysis_df.index[-1].date()}")
    print(f"{ 'ATR Mult':<8} | {'Return':<10} | {'MaxDD':<12} | {'Trades':<8} | {'DD/Ret Ratio':<12}")
    print("-" * 65)
    
    for m in multipliers:
        final, dd, trades = run_atr_grid_simulation(analysis_df, m)
        ret_pct = (final - 1000000) / 1000000 * 100
        ratio = dd / (final - 1000000) if final > 1000000 else 9.99
        
        print(f"{m:<8} | {ret_pct:>8.2f}% | {dd:>11,.0f} | {trades:>8} | {ratio:>11.2f}")
    
    print("-" * 65)
    print("* ATR 1.0 means grid size equals daily average volatility")

if __name__ == "__main__":
    main()
