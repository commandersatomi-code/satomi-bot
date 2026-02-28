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

def run_simulation_with_logging(df, atr_multiplier):
    closes = df['close'].values
    atrs = df['atr'].values
    smas = df['sma'].values
    times = df.index
    
    initial_equity = 1000000 
    positions = []
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    max_drawdown = 0
    peak_equity = initial_equity
    
    # ログ用
    equity_log = [] # {date, equity, drawdown, positions_count}
    trades_log = [] # {date, type, price}
    
    for i in range(1, len(closes)):
        price = closes[i]
        date = times[i]
        current_atr = atrs[i]
        current_sma = smas[i]
        
        if np.isnan(current_sma): continue
        
        interval = current_atr * atr_multiplier
        entry_target = current_sma - interval
        
        should_buy = False
        if len(positions) == 0:
            if price <= entry_target: should_buy = True
        else:
            if price <= positions[-1]['price'] - interval: should_buy = True
            
        if should_buy:
            positions.append({'price': price, 'target': interval, 'date': date})
            trades_log.append({'date': date, 'type': 'BUY', 'price': price})
            total_fees += price * fee_rate
            
        remaining = []
        for pos in positions:
            if price >= pos['price'] + pos['target']:
                profit = price - pos['price']
                total_realized_profit += profit
                total_fees += price * fee_rate
                trades_log.append({'date': date, 'type': 'SELL', 'price': price, 'profit': profit})
            else:
                remaining.append(pos)
        positions = remaining
        
        unrealized = sum(price - p['price'] for p in positions)
        equity_now = initial_equity + total_realized_profit - total_fees + unrealized
        
        if equity_now > peak_equity: peak_equity = equity_now
        dd = peak_equity - equity_now
        
        equity_log.append({
            'date': date,
            'equity': equity_now,
            'drawdown': dd,
            'positions_count': len(positions),
            'price': price
        })
        
        # 破綻チェック
        if equity_now <= 0:
            print(f"\n!!! BANKRUPTCY DETECTED !!!")
            print(f"Date: {date}")
            print(f"Price: {price}")
            print(f"Positions Held: {len(positions)}")
            if len(positions) > 0:
                print(f"Avg Buy Price: {sum(p['price'] for p in positions)/len(positions):.2f}")
                print(f"Deepest Loss Position: Bought at {positions[0]['price']} on {positions[0]['date']}")
            
            return pd.DataFrame(equity_log), pd.DataFrame(trades_log), True

    return pd.DataFrame(equity_log), pd.DataFrame(trades_log), False

def main():
    path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    atr, sma = calculate_indicators(df)
    df['atr'] = atr
    df['sma'] = sma
    
    # 過去5年でテスト
    test_df = df[df.index < '2025-01-25']
    
    print("\n--- Autopsy Report: 1H ATR Grid (Mult=0.8) ---")
    eq_log, tr_log, bankrupt = run_simulation_with_logging(test_df, 0.8)
    
    if bankrupt:
        # 破綻直前の動きを分析
        last_date = eq_log.iloc[-1]['date']
        start_date = last_date - pd.Timedelta(days=30)
        
        death_spiral = eq_log[(eq_log['date'] >= start_date) & (eq_log['date'] <= last_date)]
        
        print(f"\n--- Death Spiral Analysis (Last 30 Days) ---")
        print(f"Period: {start_date} to {last_date}")
        print(f"Peak Equity before Crash: {death_spiral['equity'].max():,.0f}")
        print(f"Price Drop: {death_spiral['price'].iloc[0]:,.0f} -> {death_spiral['price'].iloc[-1]:,.0f}")
        print(f"Max Positions Held: {death_spiral['positions_count'].max()}")
        
        # 致命傷となった買いトレード
        fatal_trades = tr_log[(tr_log['date'] >= start_date) & (tr_log['type'] == 'BUY')]
        print(f"Number of BUYs in Death Spiral: {len(fatal_trades)}")

if __name__ == "__main__":
    main()
