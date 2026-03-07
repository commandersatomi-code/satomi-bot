import pandas as pd
import numpy as np
import os

def calculate_indicators(df, atr_period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean().ffill().bfill()
    return atr

# --- Logic A: Risk-Reward 1:1 (Ishikawa Plan) ---
def run_rr_1to1(closes, atrs, atr_multiplier):
    initial_equity = 1000000 
    positions = []
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    max_drawdown = 0
    peak_equity = initial_equity
    trade_count = 0
    
    # 基準価格（SMAなしの単純なATRトレーリンググリッドを再現）
    # 直近高値からの押し目買いロジックを使用
    reference_high = closes[0]
    
    for i in range(1, len(closes)):
        price = closes[i]
        current_atr = atrs[i]
        
        # 基準更新
        if price > reference_high: reference_high = price
            
        interval = current_atr * atr_multiplier
        entry_target = reference_high - interval
        
        # Buy Logic
        should_buy = False
        if len(positions) == 0:
            if price <= entry_target: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
            
        if should_buy:
            positions.append({'price': price, 'tp': interval, 'sl': interval}) # SL = Interval
            trade_count += 1
            total_fees += price * fee_rate
            
        # Exit Logic (Individual RR 1:1)
        remaining = []
        for pos in positions:
            buy_p = pos['price']
            tp_width = pos['tp']
            sl_width = pos['sl']
            
            # TP Check
            if price >= buy_p + tp_width:
                profit = price - buy_p
                total_realized_profit += profit
                total_fees += price * fee_rate
            # SL Check (New!)
            elif price <= buy_p - sl_width:
                loss = price - buy_p
                total_realized_profit += loss
                total_fees += price * fee_rate
            else:
                remaining.append(pos)
                
        # Reset ref high if all cleared (optional, but good for trend reset)
        if len(positions) > 0 and len(remaining) == 0:
            reference_high = price
            
        positions = remaining
        
        unrealized = sum(price - p['price'] for p in positions)
        equity_now = initial_equity + total_realized_profit - total_fees + unrealized
        
        if equity_now <= 0: return -1, initial_equity, trade_count # Bankrupt
        if equity_now > peak_equity: peak_equity = equity_now
        dd = peak_equity - equity_now
        if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p['price'] for p in positions)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    return final_equity, max_drawdown, trade_count

# --- Logic B: Basket Exit (Bashar Plan) ---
def run_basket_exit(closes, atrs, atr_multiplier, basket_target_ratio=0.5):
    # basket_target_ratio: ATRの何倍の利益が「全体で」出たら決済するか
    # 0.5倍くらいでコツコツ逃げるのが定石
    
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
        entry_target = reference_high - interval
        
        # Buy Logic (Same)
        should_buy = False
        if len(positions) == 0:
            if price <= entry_target: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
            
        if should_buy:
            positions.append({'price': price})
            trade_count += 1
            total_fees += price * fee_rate
            
        # Exit Logic (Total Basket)
        if len(positions) > 0:
            # 現在のポジション全体の含み損益
            current_unrealized = sum(price - p['price'] for p in positions)
            
            # 目標利益（例えば、ポジション数 * ATR * 0.5 とか、固定額とか）
            # ここではシンプルに「ATRの1倍分の利益（金額）」が全体で出たら勝ち逃げする
            # つまり、平均してATR分勝った状態ではなく、合計で「1勝分」の利益が出たら全部切る（救済優先）
            target_profit_amount = current_atr * 1.0 # 1ポジション分のATR利益で全員救う
            
            if current_unrealized >= target_profit_amount:
                # 全決済
                total_realized_profit += current_unrealized
                # 手数料はまとめて計算
                total_fees += sum(price * fee_rate for _ in positions)
                positions = [] # Clear all
                reference_high = price # Reset high
        
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
    df['atr'] = calculate_indicators(df)
    
    # 過去5年でテスト (破綻しやすい期間)
    test_df = df[df.index < '2025-01-25']
    
    closes = test_df['close'].values
    atrs = test_df['atr'].values
    
    # ATR Multiplier 0.8 (Previously Bankrupt)
    m = 0.8
    
    print(f"\n--- Circulation Strategy Showdown (ATR Mult={m}) ---")
    print(f"Period: {test_df.index[0]} to {test_df.index[-1]}")
    print("-" * 65)
    print(f"{ 'Strategy':<20} | {'Return':<10} | {'MaxDD':<12} | {'Trades':<8} | {'Ratio':<6}")
    print("-" * 65)
    
    # 1. Ishikawa Plan (SL = TP)
    fin_sl, dd_sl, tr_sl = run_rr_1to1(closes, atrs, m)
    if fin_sl == -1: str_sl = "BANKRUPT"
    else: str_sl = f"{(fin_sl-1000000)/10000:>8.2f}%"
    
    print(f"{ 'Ishikawa (SL=TP)':<20} | {str_sl} | {dd_sl:>11,.0f} | {tr_sl:>8} | {(dd_sl/(fin_sl-1000000) if fin_sl>1000000 else 9.99):>6.2f}")
    
    # 2. Bashar Plan (Basket Exit)
    fin_bk, dd_bk, tr_bk = run_basket_exit(closes, atrs, m)
    if fin_bk == -1: str_bk = "BANKRUPT"
    else: str_bk = f"{(fin_bk-1000000)/10000:>8.2f}%"
    
    print(f"{ 'Bashar (Basket)':<20} | {str_bk} | {dd_bk:>11,.0f} | {tr_bk:>8} | {(dd_bk/(fin_bk-1000000) if fin_bk>1000000 else 9.99):>6.2f}")
    
    print("-" * 65)

if __name__ == "__main__":
    main()
