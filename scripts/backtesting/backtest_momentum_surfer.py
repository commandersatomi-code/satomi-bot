import pandas as pd
import numpy as np
import os
import sys

def backtest_momentum_surfer(filepath):
    """
    Backtest the 'Momentum Surfer v1.0' Strategy. 
    
    Logic:
    - Entry: First 5m of a 15m period has body > 0.5%.
    - Exit: TP(+1.5%), SL(-1.0%), or Time Limit (15 mins).
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        return

    print(f"Loading data from: {filepath} ...")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # Calculate Metrics
    df['body_pct'] = (df['close'] - df['open']) / df['open'] * 100 # Signed
    
    # Strategy Parameters
    TRIGGER_PCT = 0.5
    TP_PCT = 0.015
    SL_PCT = 0.010
    TIME_LIMIT_CANDLES = 3 # 15 mins
    
    trades = []
    
    # Iterate through the data
    # We need to jump or skip, so simple iteration is safest
    i = 0
    while i < len(df) - TIME_LIMIT_CANDLES:
        current_time = df.index[i]
        
        # 1. Check Time Condition (First 5m of 15m)
        if current_time.minute % 15 != 0: # Assuming data starts at :00, :05...
            i += 1
            continue
            
        # 2. Check Trigger
        body_pct = df.iloc[i]['body_pct']
        current_price = df.iloc[i]['close'] # Entry at close of the trigger candle
        
        if abs(body_pct) >= TRIGGER_PCT:
            direction = 1 if body_pct > 0 else -1
            entry_price = current_price
            
            tp_price = entry_price * (1 + (direction * TP_PCT))
            sl_price = entry_price * (1 - (direction * SL_PCT))
            
            exit_price = entry_price # Default
            exit_reason = "TIME_LIMIT"
            
            # Check the NEXT 3 candles for TP/SL
            for j in range(1, TIME_LIMIT_CANDLES + 1):
                idx = i + j
                if idx >= len(df): break
                
                candle = df.iloc[idx]
                
                # Check High/Low for TP/SL interaction
                if direction == 1: # LONG
                    if candle['low'] <= sl_price:
                        exit_price = sl_price
                        exit_reason = "SL"
                        break
                    elif candle['high'] >= tp_price:
                        exit_price = tp_price
                        exit_reason = "TP"
                        break
                else: # SHORT
                    if candle['high'] >= sl_price:
                        exit_price = sl_price
                        exit_reason = "SL"
                        break
                    elif candle['low'] <= tp_price:
                        exit_price = tp_price
                        exit_reason = "TP"
                        break
                
                # If neither hit, exit price becomes close of this candle (Time Limit update)
                exit_price = candle['close']
            
            # Calculate PnL
            pnl_pct = (exit_price - entry_price) / entry_price * direction * 100
            
            trades.append({
                'entry_time': current_time,
                'type': 'LONG' if direction == 1 else 'SHORT',
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl_pct,
                'reason': exit_reason
            })
            
            # Skip the duration of the trade to avoid overlapping entries
            i += TIME_LIMIT_CANDLES 
        else:
            i += 1

    # --- REPORT ---
    if not trades:
        print("No trades found.")
        return

    results = pd.DataFrame(trades)
    
    total_trades = len(results)
    win_rate = (results['pnl'] > 0).mean() * 100
    avg_pnl = results['pnl'].mean()
    total_return = results['pnl'].sum()
    
    print(f"\n========================================================")
    print(f"   Backtest Result: Momentum Surfer v1.0")
    print(f"========================================================")
    print(f"Data Period: {df.index.min()} to {df.index.max()}")
    print(f"Total Trades: {total_trades:,}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Average PnL per Trade: {avg_pnl:.2f}%")
    print(f"Total Simple Return: {total_return:.2f}%")
    
    print(f"\n[Exit Reasons]")
    print(results['reason'].value_counts(normalize=True) * 100)
    
    # --- EQUITY CURVE SIMULATION ---
    initial_capital = 1000000 # 1 Million JPY
    leverage = 1.0 # Simple 1x for verification
    
    results['equity'] = initial_capital * (1 + results['pnl']/100).cumprod()
    
    final_equity = results['equity'].iloc[-1]
    cagr = (final_equity / initial_capital) ** (365 / ((df.index.max() - df.index.min()).days)) - 1
    
    print(f"\n[Monthly Performance (Last 12 Months)]")
    results.set_index('entry_time', inplace=True)
    monthly = results['pnl'].resample('M').sum().tail(12)
    print(monthly)

if __name__ == "__main__":
    backtest_momentum_surfer("data/bybit_btc_usdt_linear_5m_full.csv")
