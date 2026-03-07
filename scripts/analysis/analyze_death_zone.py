import pandas as pd
import numpy as np
import os

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def run_simulation_with_logs(df, rsi_limit):
    # RSI固定、Grid最適化のロジックを再現しつつ、日々の資産推移を記録
    window_days = 30
    window_rows = 30
    current_base_equity = 1000000
    test_start_idx = window_rows
    
    daily_equity_log = [] # {date, equity}
    trades_log = [] # {date, type, price, profit}
    
    grid_opts = [500, 1000, 2000, 3000, 5000, 10000]
    
    while test_start_idx < len(df):
        test_end_idx = min(test_start_idx + window_rows, len(df))
        
        # Train (Optimize Grid)
        train_df = df.iloc[test_start_idx - window_rows : test_start_idx]
        best_g = 2000
        best_score = -np.inf
        
        # 簡易最適化
        closes_tr = train_df['close'].values
        rsis_tr = train_df['rsi'].values
        for g in grid_opts:
            # 高速化のため簡易DD計算
            # (実際はここでrun_backtest_fast相当の処理)
            pass
            # 今回は「なぜ死んだか」の特定が目的なので、
            # 最適化ロジックの影響を排除するため、あえてGrid=2000固定で比較しても良いが、
            # 以前の結果(Monthly Opt)を再現するため、ロジックを入れる必要がある。
            # 簡略化して固定Grid=2000で比較します（変数を減らすため）。
        
        best_g = 2000 # 死のゾーン分析のため固定
        
        # Test
        test_df = df.iloc[test_start_idx : test_end_idx]
        closes = test_df['close'].values
        rsis = test_df['rsi'].values
        dates = test_df.index
        
        positions = [] 
        period_realized = 0
        period_fees = 0
        fee_rate = 0.0006
        grid_levels = np.floor(closes / best_g).astype(int)
        if len(grid_levels) == 0: break
        prev_level = grid_levels[0]
        
        for i in range(1, len(closes)):
            price = closes[i]
            rsi = rsis[i]
            date = dates[i]
            new_grid_level = grid_levels[i]
            
            if new_grid_level < prev_level:
                diff = prev_level - new_grid_level
                for _ in range(diff):
                    if rsi < rsi_limit:
                        positions.append(price)
                        trades_log.append({'Date': date, 'Type': 'BUY', 'Price': price})
                        period_fees += price * fee_rate
            elif new_grid_level > prev_level:
                diff = new_grid_level - prev_level
                for _ in range(diff):
                    if positions:
                        bought = positions.pop(0)
                        profit = price - bought
                        period_realized += profit
                        period_fees += price * fee_rate
                        trades_log.append({'Date': date, 'Type': 'SELL', 'Price': price, 'Profit': profit})
            
            prev_level = new_grid_level
            
            unrealized = sum(price - p for p in positions)
            equity_now = current_base_equity + period_realized - period_fees + unrealized
            daily_equity_log.append({'Date': date, 'Equity': equity_now})
        
        final_unrealized = sum(closes[-1] - p for p in positions)
        period_net_profit = period_realized - period_fees + final_unrealized
        current_base_equity += period_net_profit
        test_start_idx += window_rows
        
    return pd.DataFrame(daily_equity_log), pd.DataFrame(trades_log)

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['rsi'] = calculate_rsi(df['close'])
    
    # 分析期間 (前回と同じ)
    split_date = df.index[-1] - pd.Timedelta(days=365)
    analysis_df = df[df.index < split_date]
    
    targets = [40, 42, 48]
    
    print("\n--- Death Zone Forensics (Grid=2000 Fixed) ---")
    
    for rsi in targets:
        print(f"\nAnalyzing RSI < {rsi}...")
        eq_df, tr_df = run_simulation_with_logs(analysis_df, rsi)
        
        # Calculate MaxDD and when it happened
        eq_df['Peak'] = eq_df['Equity'].cummax()
        eq_df['DD'] = eq_df['Peak'] - eq_df['Equity']
        max_dd_row = eq_df.loc[eq_df['DD'].idxmax()]
        
        final_eq = eq_df.iloc[-1]['Equity']
        ret = (final_eq - 1000000) / 1000000 * 100
        
        print(f"  Return: {ret:.2f}%")
        print(f"  MaxDD: {max_dd_row['DD']:,.0f} on {max_dd_row['Date'].date()}")
        print(f"  Equity at DD: {max_dd_row['Equity']:,.0f}")
        
        # DD発生付近のトレード状況
        dd_date = max_dd_row['Date']
        around_dd = tr_df[(tr_df['Date'] >= dd_date - pd.Timedelta(days=30)) & 
                          (tr_df['Date'] <= dd_date)]
        
        buys = len(around_dd[around_dd['Type'] == 'BUY'])
        print(f"  Buys in 30 days before DD: {buys}")
        if buys > 0:
            avg_price = around_dd[around_dd['Type'] == 'BUY']['Price'].mean()
            print(f"  Avg Buy Price: {avg_price:,.0f}")

if __name__ == "__main__":
    main()
