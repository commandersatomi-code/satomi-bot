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

def run_metabolic_simulation(df, atr_multiplier, sl_multiplier):
    closes = df['close'].values
    atrs = df['atr'].values
    smas = df['sma'].values
    
    initial_equity = 1000000 
    positions = [] # {price, tp_width, sl_width}
    
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
        sl_width = current_atr * sl_multiplier
        
        # --- Entry Logic (SMA Anchor) ---
        should_buy = False
        if len(positions) == 0:
            if price <= current_sma - interval: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
            
        if should_buy:
            positions.append({'price': price, 'tp': interval, 'sl': sl_width})
            trade_count += 1
            total_fees += price * fee_rate
            
        # --- Exit Logic (Individual TP/SL) ---
        remaining = []
        for pos in positions:
            buy_p = pos['price']
            # 利確：Entry + interval
            if price >= buy_p + pos['tp']:
                total_realized_profit += (price - buy_p)
                total_fees += price * fee_rate
            # 損切：Entry - sl_width (7.0 ATR)
            elif price <= buy_p - pos['sl']:
                total_realized_profit += (price - buy_p)
                total_fees += price * fee_rate
            else:
                remaining.append(pos)
        positions = remaining
        
        # Equity Update
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
    
    atr, sma = calculate_indicators(df)
    df['atr'] = atr
    df['sma'] = sma
    
    past_df = df[df.index < '2025-01-25']
    recent_df = df[df.index >= '2025-01-25']
    
    print("\n--- Metabolic Grid Performance: SL = 7.0 ATR ---")
    
    for period_name, data in [("Past 5 Years", past_df), ("Recent 1 Year", recent_df)]:
        print(f"\n=== {period_name} ===")
        # ATR Mult 1.0 (Hyper-aggressive)
        m = 1.0
        sl_m = 7.0
        
        final, dd, trades = run_metabolic_simulation(data, m, sl_m)
        
        if final == -1:
            print("BANKRUPT")
        else:
            ret = (final - 1000000) / 1000000 * 100
            print(f"Return: {ret:>8.2f}%")
            print(f"MaxDD:  {dd:>11,.0f}")
            print(f"Trades: {trades:>8}")
            print(f"Ratio:  {(dd/(final-1000000) if final>1000000 else 9.99):>8.2f}")

if __name__ == "__main__":
    main()
