import pandas as pd
import numpy as np
import os
import sys

def run_backtest(df, start_date, end_date, label):
    """
    Run backtest on a specific slice of data.
    """
    # Slice Data
    mask = (df.index >= start_date) & (df.index <= end_date)
    sub_df = df.loc[mask].copy()
    
    if len(sub_df) == 0:
        print(f"[{label}] No data found.")
        return

    # Strategy Parameters
    TRIGGER_PCT = 0.8
    TP_PCT = 0.006
    SL_PCT = 0.004
    TIME_LIMIT = 2
    
    trades = []
    i = 0
    
    # Simple Loop
    while i < len(sub_df) - TIME_LIMIT:
        current_candle = sub_df.iloc[i]
        
        # 1. Trigger Check
        if abs(current_candle['body_pct']) >= TRIGGER_PCT:
            # REVERSAL: If Up, Short. If Down, Long.
            direction = -1 if current_candle['body_pct'] > 0 else 1
            entry_price = sub_df.iloc[i+1]['open'] # Enter at next Open
            
            tp_price = entry_price * (1 + (direction * TP_PCT))
            sl_price = entry_price * (1 - (direction * SL_PCT))
            
            exit_price = entry_price
            exit_reason = "TIME_LIMIT"
            
            # Check next 2 candles
            for j in range(1, TIME_LIMIT + 1):
                if i + j >= len(sub_df): break
                candle = sub_df.iloc[i + j]
                
                # Check TP/SL
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
                
                exit_price = candle['close']
            
            pnl = (exit_price - entry_price) / entry_price * direction * 100
            trades.append(pnl)
            
            i += TIME_LIMIT # Skip holding period
        else:
            i += 1
            
    # Report
    if not trades:
        print(f"[{label}] No trades.")
        return

    trades = np.array(trades)
    win_rate = np.mean(trades > 0) * 100
    total_return = np.sum(trades)
    avg_pnl = np.mean(trades)
    
    print(f"\n--- {label} ({start_date} ~ {end_date}) ---")
    print(f"Trades: {len(trades)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Avg PnL: {avg_pnl:.4f}%")
    
    return avg_pnl

def verify_robustness(filepath):
    if not os.path.exists(filepath):
        print("File not found.")
        return

    print(f"Loading data: {filepath}")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df['body_pct'] = (df['close'] - df['open']) / df['open'] * 100
    
    print("\n[Robustness Test: Reversal Sniper v1.0]")
    
    # 1. In-Sample (Learning Phase)
    res1 = run_backtest(df, "2020-01-01", "2023-12-31", "In-Sample (2020-2023)")
    
    # 2. Out-of-Sample (Testing Phase)
    res2 = run_backtest(df, "2024-01-01", "2026-12-31", "Out-of-Sample (2024-2026)")
    
    # Conclusion
    if res1 > 0 and res2 > 0:
        print("\n✅ PASSED: Strategy works in both periods.")
        if abs(res1 - res2) < 0.05:
             print("🌟 EXCELLENT: Performance is stable.")
        else:
             print("⚠️ CAUTION: Performance variance is high.")
    else:
        print("\n❌ FAILED: Strategy failed in one or both periods.")

if __name__ == "__main__":
    verify_robustness("data/bybit_btc_usdt_linear_5m_full.csv")
