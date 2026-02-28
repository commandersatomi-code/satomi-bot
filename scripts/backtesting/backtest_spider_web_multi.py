import pandas as pd
import numpy as np
import os

# ---------------------------------------------------------
# Core Logic (Same as before)
# ---------------------------------------------------------
def run_spider_backtest(df, grid_size):
    initial_equity = 1000000 
    positions = []
    total_profit = 0
    closes = df['close'].values
    
    if len(closes) == 0:
        return initial_equity, 0, 0
        
    current_grid_level = int(closes[0] // grid_size)
    max_drawdown = 0
    peak_equity = initial_equity
    
    # Speed optimization: Pre-calculate grid levels
    grid_levels = np.floor(closes / grid_size).astype(int)
    
    # Iterate
    # Note: To simulate strictly, we should check High/Low, but for 'close' based logic:
    prev_level = grid_levels[0]
    
    for i in range(1, len(closes)):
        price = closes[i]
        new_grid_level = grid_levels[i]
        
        if new_grid_level < prev_level:
            # Drop down -> Buy
            # Difference in levels determines how many buys?
            # Simple version: 1 buy per level drop
            diff = prev_level - new_grid_level
            for _ in range(diff):
                 positions.append(price) # Approximate entry at close
            
        elif new_grid_level > prev_level:
            # Rise up -> Sell
            diff = new_grid_level - prev_level
            for _ in range(diff):
                if len(positions) > 0:
                    bought_price = positions.pop(0) # FIFO
                    profit = price - bought_price
                    total_profit += profit
        
        prev_level = new_grid_level
        
        # Calculate Stats occasionally or at end?
        # Doing it every step is slow for 5m data (years of data).
        # We will approximate MaxDD calculation to peak periods if needed,
        # but for accuracy let's do a simplified DD check:
        
        # Only check DD if price is lower than average position price (optimization)
        if len(positions) > 0:
            current_val = initial_equity + total_profit + sum(price - p for p in positions)
            if current_val > peak_equity:
                peak_equity = current_val
            dd = peak_equity - current_val
            if dd > max_drawdown:
                max_drawdown = dd
        else:
            current_val = initial_equity + total_profit
            if current_val > peak_equity:
                peak_equity = current_val

    final_value = initial_equity + total_profit + sum([closes[-1] - p for p in positions])
    return final_value, total_profit, max_drawdown

# ---------------------------------------------------------
# Multi-Timeframe Runner
# ---------------------------------------------------------
def load_data(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return None
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    return df

def process_timeframe(name, filepath, grid_sizes):
    df = load_data(filepath)
    if df is None:
        return
    
    # Split Last 1 Year
    last_date = df.index[-1]
    split_date = last_date - pd.Timedelta(days=365)
    train_df = df[df.index < split_date]
    test_df = df[df.index >= split_date]
    
    print(f"\n[{name}] Training ({len(train_df)} rows) -> Testing ({len(test_df)} rows)")
    
    # Optimize
    best_grid = 5000
    best_score = -np.inf
    
    for gs in grid_sizes:
        final_val, realized, max_dd = run_spider_backtest(train_df, gs)
        # Score = Profit / (MaxDD + 1) -> Stability focused
        score = realized / (max_dd + 1)
        if score > best_score:
            best_score = score
            best_grid = gs
            
    print(f"[{name}] Best Grid: {best_grid} (Train Score: {best_score:.4f})")
    
    # Test
    final_val, realized, max_dd = run_spider_backtest(test_df, best_grid)
    ret_pct = (final_val - 1000000) / 1000000 * 100
    
    return {
        'Timeframe': name,
        'Best Grid': best_grid,
        'Return (%)': ret_pct,
        'Profit (JPY)': realized,
        'Max DD (JPY)': max_dd,
        'Final Equity': final_val
    }

def main():
    # Files
    datasets = [
        ("5m", "data/bybit_btc_usdt_linear_5m_full.csv"),
        ("15m", "data/bybit_btcusdt_linear_15m_full.csv"),
        ("1h", "data/bybit_btcusdt_linear_1h_full.csv"),
        ("4h", "data/bybit_btc_usdt_linear_4h_full.csv"),
        ("Daily", "data/bybit_btc_usdt_linear_daily_full.csv"),
    ]
    
    # Grid sizes to search
    grid_sizes = [500, 1000, 2000, 3000, 5000, 10000]
    
    results = []
    
    for name, path in datasets:
        res = process_timeframe(name, path, grid_sizes)
        if res:
            results.append(res)
            
    # Display Summary
    print("\n" + "="*80)
    print(f"{ 'Timeframe':<10} | { 'Grid Size':<10} | { 'Return':<10} | { 'Realized Profit':<18} | { 'Max Drawdown':<15}")
    print("-" * 80)
    
    for r in results:
        print(f"{r['Timeframe']:<10} | {r['Best Grid']:<10} | {r['Return (%)']:>9.2f}% | {r['Profit (JPY)']:>18,.0f} | {r['Max DD (JPY)']:>15,.0f}")
    print("="*80)

if __name__ == "__main__":
    main()
