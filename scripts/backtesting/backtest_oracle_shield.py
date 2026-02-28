"""
Oracle Shield: Harmony Grid + Renko Oracle Filter
===================================================
The PROVEN Daily Harmony grid logic (from backtest_sliding_window.py)
with a Renko Volume Lag 'Oracle' gate on entries.

Logic:
  - SELL: Unchanged (grid level crossed upward → take profit, no filter needed)
  - BUY:  Grid level crossed downward AND RSI < limit
          AND a Renko Omen was detected within the last N hours
          (= The Oracle confirms energy accumulation before we commit capital)
          
Comparison Mode: Runs BOTH pure Harmony and Oracle Shield side by side.
"""

import pandas as pd
import numpy as np
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src/engines')))
try:
    from renko_engine import RenkoChart
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/engines')))
    from renko_engine import RenkoChart


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).fillna(50)


def build_omen_lookup(df_1m, brick_size=100, vol_threshold=3.0):
    """
    Build a set of timestamps (rounded to hour) where Renko Omens fired.
    This allows the 1H grid logic to check: 'Was there an Omen this hour?'
    """
    renko = RenkoChart(brick_size=brick_size)
    bricks = renko.process_data(df_1m)
    bricks = renko.calculate_precursors(bricks)
    bricks['timestamp'] = pd.to_datetime(bricks['timestamp'], errors='coerce')
    bricks = bricks.dropna(subset=['timestamp'])
    
    # Omens: High Volume Lag
    omens = bricks[bricks['vol_lag'] > vol_threshold].copy()
    
    # Round to hour for lookup
    omen_hours = set(omens['timestamp'].dt.floor('h'))
    
    # Also include the NEXT few hours as 'afterglow' (omen effect persists)
    expanded = set()
    for ts in omen_hours:
        for h in range(4):  # Omen valid for 4 hours
            expanded.add(ts + pd.Timedelta(hours=h))
    
    return expanded


def run_backtest_with_oracle(closes, rsi_values, grid_size, rsi_limit, 
                              timestamps=None, omen_set=None, fee_rate=0.0006):
    """
    Same as run_backtest_fast but with an Oracle gate on BUY.
    If omen_set is None, behaves identically to pure Harmony (no filter).
    """
    initial_equity = 1000000
    positions = []
    total_realized_profit = 0
    total_fees = 0
    
    grid_levels = np.floor(closes / grid_size).astype(int)
    prev_level = grid_levels[0]
    
    max_drawdown = 0
    peak_equity = initial_equity
    buy_count = 0
    
    for i in range(1, len(closes)):
        price = closes[i]
        rsi = rsi_values[i]
        new_grid_level = grid_levels[i]
        
        # BUY
        if new_grid_level < prev_level:
            diff = prev_level - new_grid_level
            for _ in range(diff):
                if rsi < rsi_limit:
                    # Oracle Gate: Check if omen is active
                    if omen_set is not None:
                        ts = timestamps[i] if timestamps is not None else None
                        if ts is not None and ts not in omen_set:
                            continue  # No omen = Skip this buy
                    
                    positions.append(price)
                    buy_count += 1
                    total_fees += price * fee_rate
                    
        # SELL (No filter - take profits always)
        elif new_grid_level > prev_level:
            diff = new_grid_level - prev_level
            for _ in range(diff):
                if len(positions) > 0:
                    bought_price = positions.pop(0)
                    profit = price - bought_price
                    total_realized_profit += profit
                    total_fees += price * fee_rate
        
        prev_level = new_grid_level
        
        unrealized = sum(price - p for p in positions) if positions else 0
        equity = initial_equity + total_realized_profit - total_fees + unrealized
        if equity > peak_equity:
            peak_equity = equity
        dd = peak_equity - equity
        if dd > max_drawdown:
            max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p for p in positions)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    
    return final_equity, total_realized_profit, total_fees, max_drawdown, buy_count


def run_sliding_window_comparison(df_1h, omen_set, window_days):
    """Run sliding window for BOTH pure Harmony and Oracle Shield."""
    rows_per_day = 24
    window_rows = window_days * rows_per_day
    
    # Pure Harmony state
    pure_equity = 1000000
    pure_peak = 1000000
    pure_max_dd = 0
    pure_total_trades = 0
    
    # Oracle Shield state
    oracle_equity = 1000000
    oracle_peak = 1000000
    oracle_max_dd = 0
    oracle_total_trades = 0
    
    grid_opts = [500, 1000, 2000, 3000, 5000]
    rsi_opts = [30, 40, 50, 70, 100]
    
    test_start_idx = window_rows
    
    timestamps_arr = df_1h.index.values if hasattr(df_1h.index, 'values') else None
    # Convert to pandas Timestamps for omen lookup
    if timestamps_arr is not None:
        ts_series = pd.to_datetime(df_1h.index).floor('h')
    
    while test_start_idx < len(df_1h):
        test_end_idx = min(test_start_idx + window_rows, len(df_1h))
        
        # Train (same for both)
        train_start = test_start_idx - window_rows
        train_df = df_1h.iloc[train_start:test_start_idx]
        
        # Optimize on pure Harmony (no oracle in training)
        best_score = -np.inf
        best_params = (1000, 100)
        train_closes = train_df['close'].values
        train_rsis = train_df['rsi'].values
        
        for g in grid_opts:
            for r in rsi_opts:
                eq, prof, fees, dd, buys = run_backtest_with_oracle(
                    train_closes, train_rsis, g, r)
                if buys == 0:
                    score = 0
                else:
                    score = (eq - 1000000) / (dd + 1)
                if score > best_score:
                    best_score = score
                    best_params = (g, r)
        
        best_g, best_r = best_params
        
        # Test Period
        test_df = df_1h.iloc[test_start_idx:test_end_idx]
        test_closes = test_df['close'].values
        test_rsis = test_df['rsi'].values
        test_ts = pd.to_datetime(test_df.index).floor('h')
        test_ts_arr = test_ts.values
        
        # Convert to set-compatible timestamps
        test_timestamps = [pd.Timestamp(t) for t in test_ts_arr]
        
        # PURE Harmony
        eq_p, prof_p, fees_p, dd_p, buys_p = run_backtest_with_oracle(
            test_closes, test_rsis, best_g, best_r,
            timestamps=None, omen_set=None)
        
        pure_net = eq_p - 1000000
        pure_equity += pure_net
        pure_total_trades += buys_p
        if pure_equity > pure_peak: pure_peak = pure_equity
        dd_c = pure_peak - pure_equity
        if dd_c > pure_max_dd: pure_max_dd = dd_c
        
        # ORACLE Shield
        eq_o, prof_o, fees_o, dd_o, buys_o = run_backtest_with_oracle(
            test_closes, test_rsis, best_g, best_r,
            timestamps=test_timestamps, omen_set=omen_set)
        
        oracle_net = eq_o - 1000000
        oracle_equity += oracle_net
        oracle_total_trades += buys_o
        if oracle_equity > oracle_peak: oracle_peak = oracle_equity
        dd_c = oracle_peak - oracle_equity
        if dd_c > oracle_max_dd: oracle_max_dd = dd_c
        
        test_start_idx += window_rows
        
    return {
        'pure': {
            'equity': pure_equity,
            'return': (pure_equity - 1000000) / 1000000 * 100,
            'max_dd': pure_max_dd,
            'trades': pure_total_trades
        },
        'oracle': {
            'equity': oracle_equity,
            'return': (oracle_equity - 1000000) / 1000000 * 100,
            'max_dd': oracle_max_dd,
            'trades': oracle_total_trades
        }
    }


def main():
    h1_path = 'data/bybit_btc_usdt_linear_1h_full.csv'
    m1_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    
    if not os.path.exists(h1_path) or not os.path.exists(m1_path):
        print("Data files not found.")
        return
    
    # Load 1H data
    print("Loading 1H data...")
    df_1h = pd.read_csv(h1_path)
    df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'])
    df_1h.set_index('timestamp', inplace=True)
    df_1h.sort_index(inplace=True)
    df_1h['rsi'] = calculate_rsi(df_1h['close'])
    print(f"  1H: {df_1h.index[0]} ~ {df_1h.index[-1]} ({len(df_1h)} rows)")
    
    # Load 1m data and build Omen lookup
    print("Loading 1m data and building Renko Oracle...")
    df_1m = pd.read_csv(m1_path)
    df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'], errors='coerce')
    df_1m = df_1m.dropna(subset=['timestamp'])
    print(f"  1m: {df_1m['timestamp'].min()} ~ {df_1m['timestamp'].max()} ({len(df_1m)} rows)")
    
    # Build Omen lookup for different thresholds
    omen_configs = [
        (100, 3.0, "Oracle (Vol>3.0)"),
        (100, 4.0, "Oracle (Vol>4.0)"),
        (100, 5.0, "Oracle (Vol>5.0)"),
        (200, 3.0, "Oracle (Brick200)"),
    ]
    
    # Sliding Window configs
    window_configs = [
        ('Monthly', 30),
        ('Quarterly', 90),
        ('Yearly', 360),
    ]
    
    print("\n" + "="*100)
    print("ORACLE SHIELD: Harmony Grid + Renko Oracle Filter")
    print("="*100)
    
    for w_name, w_days in window_configs:
        print(f"\n--- Window: {w_name} ({w_days} days) ---")
        print(f"{'Strategy':<25} | {'Return':<8} | {'MaxDD':<12} | {'Trades':<8} | {'DD Reduction'}")
        print("-" * 85)
        
        # Pure Harmony (baseline)
        result_baseline = run_sliding_window_comparison(df_1h, set(), w_days)
        pure = result_baseline['pure']
        print(f"{'Pure Harmony':<25} | {pure['return']:>+7.2f}% | {pure['max_dd']:>12,.0f} | {pure['trades']:>8} | (baseline)")
        
        # Oracle variations
        for brick, vol_t, label in omen_configs:
            omen_set = build_omen_lookup(df_1m, brick_size=brick, vol_threshold=vol_t)
            result = run_sliding_window_comparison(df_1h, omen_set, w_days)
            oracle = result['oracle']
            
            dd_reduction = ((pure['max_dd'] - oracle['max_dd']) / pure['max_dd'] * 100) if pure['max_dd'] > 0 else 0
            
            print(f"{label:<25} | {oracle['return']:>+7.2f}% | {oracle['max_dd']:>12,.0f} | {oracle['trades']:>8} | {dd_reduction:>+6.1f}%")
    
    print("=" * 100)


if __name__ == "__main__":
    main()
