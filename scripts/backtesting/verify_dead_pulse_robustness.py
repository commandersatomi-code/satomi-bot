import pandas as pd
import numpy as np
import os

def run_backtest_period(df, start_date, end_date, label):
    """Runs the Dead Pulse backtest on a specific period."""
    sub_df = df.loc[start_date:end_date].copy()
    if len(sub_df) == 0:
        print(f"[{label}] No data.")
        return None

    # --- Strategy Parameters ---
    SILENCE_THRESHOLD = 0.05
    SILENCE_DURATION = 3
    TRIGGER_THRESHOLD = 0.2
    TP_PCT = 0.020
    SL_PCT = 0.005
    TIME_LIMIT = 6 # 30 mins
    
    # Identify Silence
    sub_df['is_silent'] = (sub_df['high'] - sub_df['low']) / sub_df['open'] * 100 < SILENCE_THRESHOLD
    sub_df['silence_confirmed'] = sub_df['is_silent'].rolling(window=SILENCE_DURATION).sum() == SILENCE_DURATION
    sub_df['ready_to_trigger'] = sub_df['is_silent'].shift(1).fillna(False)
    
    trades = []
    i = 0
    while i < len(sub_df) - TIME_LIMIT:
        if sub_df.iloc[i]['ready_to_trigger']:
            body_pct = (sub_df.iloc[i]['close'] - sub_df.iloc[i]['open']) / sub_df.iloc[i]['open'] * 100
            
            if abs(body_pct) >= TRIGGER_THRESHOLD:
                direction = 1 if body_pct > 0 else -1
                entry_price = sub_df.iloc[i]['close']
                
                tp_p = entry_price * (1 + (direction * TP_PCT))
                sl_p = entry_price * (1 - (direction * SL_PCT))
                
                exit_price = entry_price
                exit_reason = "TIME_LIMIT"
                
                for j in range(1, TIME_LIMIT + 1):
                    if i + j >= len(sub_df): break
                    c = sub_df.iloc[i + j]
                    if direction == 1: # LONG
                        if c['low'] <= sl_p: exit_price, exit_reason = sl_p, "SL"; break
                        elif c['high'] >= tp_p: exit_price, exit_reason = tp_p, "TP"; break
                    else: # SHORT
                        if c['high'] >= sl_p: exit_price, exit_reason = sl_p, "SL"; break
                        elif c['low'] <= tp_p: exit_price, exit_reason = tp_p, "TP"; break
                    exit_price = c['close']
                
                pnl = (exit_price - entry_price) / entry_price * direction * 100
                trades.append(pnl)
                i += TIME_LIMIT
                continue
        i += 1
    
    if not trades:
        print(f"[{label}] No trades triggered.")
        return 0
    
    trades = np.array(trades)
    win_rate = np.mean(trades > 0) * 100
    avg_pnl = np.mean(trades)
    total_ret = np.sum(trades)
    
    print(f"\n--- {label} ({start_date} to {end_date}) ---")
    print(f"Trades: {len(trades)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Avg PnL: {avg_pnl:.4f}%")
    print(f"Total Simple Return: {total_ret:.2f}%")
    return avg_pnl

def main():
    path = "data/bybit_btc_usdt_linear_5m_full.csv"
    if not os.path.exists(path): return
    
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    print("========================================================")
    print("   Robustness Test: Dead Pulse Hunter")
    print("========================================================")
    
    # 1. In-Sample (2020-2023)
    res_in = run_backtest_period(df, "2020-01-01", "2023-12-31", "In-Sample (Learning)")
    
    # 2. Out-of-Sample (2024-2026)
    res_out = run_backtest_period(df, "2024-01-01", "2026-12-31", "Out-of-Sample (Testing)")
    
    if res_in is not None and res_out is not None:
        if res_in > 0 and res_out > 0:
            print("\n✅ SUCCESS: The strategy holds up in the test period!")
        else:
            print("\n❌ FAILED: The strategy does not perform consistently.")

if __name__ == "__main__":
    main()
