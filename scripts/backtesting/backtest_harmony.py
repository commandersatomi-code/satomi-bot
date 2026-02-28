import pandas as pd
import numpy as np
import datetime

def load_data(filepath):
    print(f"Loading data from {filepath}...")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    return df

def run_backtest(df, window, sigma):
    # Prepare indicators
    df = df.copy()
    df['MA'] = df['close'].rolling(window=window).mean()
    df['Std'] = df['close'].rolling(window=window).std()
    df['Upper'] = df['MA'] + (df['Std'] * sigma)
    df['Lower'] = df['MA'] - (df['Std'] * sigma)
    
    # Logic
    position = 0 # 0: None, 1: Long, -1: Short
    entry_price = 0
    trades = []
    equity = [1000000] # Initial capital
    
    # Iterating (simple but effective for this state-based logic)
    # Optimizing speed by converting to numpy arrays
    closes = df['close'].values
    uppers = df['Upper'].values
    lowers = df['Lower'].values
    mas = df['MA'].values
    times = df.index
    
    current_equity = 1000000
    
    for i in range(len(df)):
        if np.isnan(uppers[i]):
            continue
            
        close = closes[i]
        upper = uppers[i]
        lower = lowers[i]
        ma = mas[i]
        time = times[i]
        
        # Logic from Harmony.py
        
        # BUY Entry (Reversion)
        if position == 0 and close < lower:
            position = 1
            entry_price = close
            # print(f"LONG at {time} : {close}")
            
        # SELL Entry (Reversion)
        elif position == 0 and close > upper:
            position = -1
            entry_price = close
            # print(f"SHORT at {time} : {close}")
            
        # EXIT Long
        elif position == 1 and close >= ma:
            pnl = (close - entry_price) / entry_price
            current_equity *= (1 + pnl)
            trades.append({'type': 'long_exit', 'pnl': pnl, 'time': time})
            position = 0
            
        # EXIT Short
        elif position == -1 and close <= ma:
            pnl = (entry_price - close) / entry_price
            current_equity *= (1 + pnl)
            trades.append({'type': 'short_exit', 'pnl': pnl, 'time': time})
            position = 0
            
    return current_equity, trades

def optimize(train_df):
    windows = [10, 20, 30, 40, 50, 60]
    sigmas = [1.5, 2.0, 2.5, 3.0, 3.5]
    
    best_perf = -np.inf
    best_params = (20, 2.0)
    
    print("\n--- Training (Optimization) ---")
    for w in windows:
        for s in sigmas:
            final_equity, trades = run_backtest(train_df, w, s)
            return_pct = (final_equity - 1000000) / 1000000 * 100
            print(f"Params: Window={w}, Sigma={s} -> Return: {return_pct:.2f}%")
            
            if return_pct > best_perf:
                best_perf = return_pct
                best_params = (w, s)
                
    return best_params

def main():
    data_path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = load_data(data_path)
    
    # Split data (Last 1 year for test)
    last_date = df.index[-1]
    split_date = last_date - pd.Timedelta(days=365)
    
    train_df = df[df.index < split_date]
    test_df = df[df.index >= split_date]
    
    print(f"Data Loaded. Total rows: {len(df)}")
    print(f"Training Data: {train_df.index[0]} to {train_df.index[-1]}")
    print(f"Test Data: {test_df.index[0]} to {test_df.index[-1]}")
    
    # Optimize
    best_w, best_s = optimize(train_df)
    print(f"\nBest Parameters found: Window={best_w}, Sigma={best_s}")
    
    # Test
    print("\n--- Testing (Validation) ---")
    final_equity, trades = run_backtest(test_df, best_w, best_s)
    
    # Analysis
    total_trades = len(trades)
    wins = len([t for t in trades if t['pnl'] > 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    total_return = (final_equity - 1000000) / 1000000 * 100
    
    print(f"Test Results for Harmony Bot (Last 1 Year):")
    print(f"Final Equity: {final_equity:,.0f} (Start: 1,000,000)")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.2f}%")

if __name__ == "__main__":
    main()
