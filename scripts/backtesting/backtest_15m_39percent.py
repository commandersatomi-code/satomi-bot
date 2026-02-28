import pandas as pd
import numpy as np

def load_data(filepath):
    print(f"Loading data from {filepath}...")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    return df

def calculate_indicators(df):
    # Volume SMA 20
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['vol_mult'] = df['volume'] / df['volume_sma']
    
    # SMA 200
    df['sma_200'] = df['close'].rolling(window=200).mean()
    
    # Range Pct (High - Low) / Open
    df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
    
    # RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def run_backtest_15m(df, tp_pct=0.05, sl_pct=0.03):
    initial_equity = 1000000
    equity = initial_equity
    
    positions = [] # list of dict {'type': 'long'|'short', 'price': 123, 'tp': 130, 'sl': 110, 'time': ts}
    trades = []
    
    closes = df['close'].values
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    times = df.index
    
    # Pre-calc columns to arrays for speed
    sma200 = df['sma_200'].values
    range_pct = df['range_pct'].values
    vol_mult = df['vol_mult'].values
    rsi = df['rsi'].values
    
    # We need at least 200 bars for SMA and 3 prior bars for logic
    start_idx = 205
    
    print("Running Backtest...")
    
    for i in range(start_idx, len(df)):
        current_time = times[i]
        
        # --- Check Exits ---
        # Assuming we check OHLC of current candle for exits
        # Conservative: check Low for Long SL, High for Long TP?
        # Standard: Check if touched.
        
        active_positions = []
        for pos in positions:
            p_type = pos['type']
            entry = pos['price']
            tp = pos['tp']
            sl = pos['sl']
            
            pnl = 0
            exit_reason = None
            
            if p_type == 'LONG':
                if lows[i] <= sl:
                    pnl = (sl - entry) / entry
                    exit_reason = 'SL'
                elif highs[i] >= tp:
                    pnl = (tp - entry) / entry
                    exit_reason = 'TP'
            elif p_type == 'SHORT':
                if highs[i] >= sl:
                    pnl = (entry - sl) / entry
                    exit_reason = 'SL'
                elif lows[i] <= tp:
                    pnl = (entry - tp) / entry
                    exit_reason = 'TP'
            
            if exit_reason:
                equity *= (1 + pnl)
                trades.append({
                    'time': current_time,
                    'type': p_type,
                    'exit': exit_reason,
                    'pnl': pnl,
                    'equity': equity
                })
            else:
                active_positions.append(pos)
        
        positions = active_positions
        
        # --- Entry Logic ---
        # "Running Start" check on *previous* 3 candles
        # i is current candle
        # p1 is i-1
        # p2 is i-2
        # p3 is i-3
        
        p1_idx = i - 1
        p2_idx = i - 2
        p3_idx = i - 3
        
        # Condition 1: Increasing Range
        is_increasing_range = (range_pct[p1_idx] > range_pct[p2_idx]) and (range_pct[p2_idx] > range_pct[p3_idx])
        
        # Condition 2: Increasing Volume
        is_increasing_volume = (vol_mult[p1_idx] > vol_mult[p2_idx]) and (vol_mult[p2_idx] > vol_mult[p3_idx])
        
        if is_increasing_range and is_increasing_volume:
            entry_price = opens[i] # Enter at Open of current candle
            sma_val = sma200[p1_idx] # Compare against p1's SMA or current open vs p1 SMA? Code matches "entry_price > p1['sma_200']"
            
            is_uptrend = entry_price > sma_val
            is_downtrend = entry_price < sma_val
            
            # RSI Check
            rsi_p1 = rsi[p1_idx]
            rsi_p2 = rsi[p2_idx]
            rsi_p3 = rsi[p3_idx]
            
            signal = None
            
            # Limit 1 position at a time for simplicity? 
            # Or allow multiple? "The 39% Runner" implies a specific focused trade. 
            # Let's assume single position for clearer results.
            if len(positions) == 0:
                if is_uptrend and (rsi_p1 >= 50 and rsi_p2 >= 50 and rsi_p3 >= 50):
                    signal = "LONG"
                    tp_price = entry_price * (1 + tp_pct)
                    sl_price = entry_price * (1 - sl_pct)
                    
                elif is_downtrend and (rsi_p1 <= 47 and rsi_p2 <= 47 and rsi_p3 <= 47):
                    signal = "SHORT"
                    tp_price = entry_price * (1 - tp_pct)
                    sl_price = entry_price * (1 + sl_pct)
                
                if signal:
                    positions.append({
                        'type': signal,
                        'price': entry_price,
                        'tp': tp_price,
                        'sl': sl_price,
                        'time': current_time
                    })
                    # print(f"Entry {signal} at {current_time} Price: {entry_price}")

    return equity, trades

def main():
    data_path = 'data/bybit_btcusdt_linear_15m_full.csv'
    df = load_data(data_path)
    df = calculate_indicators(df)
    
    # Split data to find the "39%" period
    # Usually "39%" in a filename implies a specific backtest result on recent data.
    # Let's run year by year.
    
    years = df.index.year.unique()
    
    print(f"\n--- 15m Strategy Reproduction (TP=5%, SL=3%) ---")
    
    total_trades_all = 0
    
    for year in years:
        sub_df = df[df.index.year == year]
        if len(sub_df) < 500: continue
        
        final_eq, trades = run_backtest_15m(sub_df)
        ret = (final_eq - 1000000) / 1000000 * 100
        total_trades = len(trades)
        wins = len([t for t in trades if t['pnl'] > 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        print(f"Year {year}: Return {ret:>6.2f}% | Trades: {total_trades:>3} | WinRate: {win_rate:>5.1f}%")
        total_trades_all += total_trades

    # Also run last 365 days
    last_date = df.index[-1]
    start_365 = last_date - pd.Timedelta(days=365)
    last_year_df = df[df.index >= start_365]
    
    final_eq, trades = run_backtest_15m(last_year_df)
    ret = (final_eq - 1000000) / 1000000 * 100
    total_trades = len(trades)
    wins = len([t for t in trades if t['pnl'] > 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    print(f"\nLast 365 Days: Return {ret:>6.2f}% | Trades: {total_trades:>3} | WinRate: {win_rate:>5.1f}%")

if __name__ == "__main__":
    main()
