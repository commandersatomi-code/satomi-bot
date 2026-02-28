"""
Oracle Shield: Walk-Forward Performance Evaluation
=====================================================
Runs sliding window optimization with TRAIN/TEST split reporting.
Shows per-window results so we can see overfitting potential.
"""

import pandas as pd
import numpy as np
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src/engines')))
from renko_engine import RenkoChart


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).fillna(50)


def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def build_omen_lookup(df_1m, brick_size=100, vol_threshold=5.0):
    renko = RenkoChart(brick_size=brick_size)
    bricks = renko.process_data(df_1m)
    bricks = renko.calculate_precursors(bricks)
    bricks['timestamp'] = pd.to_datetime(bricks['timestamp'], errors='coerce')
    bricks = bricks.dropna(subset=['timestamp'])
    
    omens = bricks[bricks['vol_lag'] > vol_threshold].copy()
    omen_hours = set(omens['timestamp'].dt.floor('h'))
    
    expanded = set()
    for ts in omen_hours:
        for h in range(4):
            expanded.add(ts + pd.Timedelta(hours=h))
    
    return expanded


def run_backtest_with_atr(closes, highs, lows, rsi_values, grid_size, rsi_limit,
                          atr_values, atr_long_values,
                          timestamps=None, omen_set=None, fee_rate=0.0006,
                          atr_tp_mult=10.0, atr_sl_mult=7.0):
    """
    Enhanced backtest with ATR-based asymmetric TP/SL (breathing).
    """
    initial_equity = 1000000
    positions = []  # list of dicts: {price, tp, sl, size}
    total_realized_pnl = 0
    total_fees = 0
    
    grid_levels = np.floor(closes / grid_size).astype(int)
    prev_level = grid_levels[0]
    
    max_drawdown = 0
    peak_equity = initial_equity
    buy_count = 0
    sell_count = 0
    tp_count = 0
    sl_count = 0
    
    MAX_POS = 5
    POS_SIZE_PCT = 0.20
    
    cash = initial_equity
    
    for i in range(1, len(closes)):
        price = closes[i]
        rsi = rsi_values[i]
        atr = atr_values[i] if not np.isnan(atr_values[i]) else 500
        atr_l = atr_long_values[i] if not np.isnan(atr_long_values[i]) else atr
        new_grid_level = grid_levels[i]
        
        # --- Check TP/SL for existing positions ---
        active = []
        for pos in positions:
            tp_price = pos['price'] + pos['tp']
            sl_price = pos['price'] - pos['sl']
            
            if price >= tp_price:
                pnl = (price - pos['price']) / pos['price']
                pnl_amt = pos['size'] * pnl - pos['size'] * fee_rate * 2
                cash += pos['size'] + pnl_amt
                total_realized_pnl += pnl_amt
                tp_count += 1
            elif price <= sl_price:
                pnl = (price - pos['price']) / pos['price']
                pnl_amt = pos['size'] * pnl - pos['size'] * fee_rate * 2
                cash += pos['size'] + pnl_amt
                total_realized_pnl += pnl_amt
                sl_count += 1
            else:
                active.append(pos)
        positions = active
        
        # --- BUY Logic ---
        if new_grid_level < prev_level:
            diff = prev_level - new_grid_level
            for _ in range(diff):
                if rsi >= rsi_limit:
                    continue
                if omen_set is not None:
                    ts = timestamps[i] if timestamps is not None else None
                    if ts is not None and ts not in omen_set:
                        continue
                if len(positions) >= MAX_POS:
                    continue
                    
                floating = sum(pos['size'] * ((price - pos['price']) / pos['price']) for pos in positions)
                total_val = cash + floating
                invest = total_val * POS_SIZE_PCT
                
                if cash >= invest:
                    vol_ratio = max(0.5, min(2.0, atr / atr_l))
                    tp = atr * atr_tp_mult * vol_ratio
                    sl = atr * atr_sl_mult
                    
                    cash -= invest
                    positions.append({'price': price, 'tp': tp, 'sl': sl, 'size': invest})
                    buy_count += 1
                    total_fees += invest * fee_rate
        
        # --- SELL (Grid Up) ---
        elif new_grid_level > prev_level:
            diff = new_grid_level - prev_level
            for _ in range(diff):
                if len(positions) > 0:
                    pos = positions.pop(0)
                    pnl = (price - pos['price']) / pos['price']
                    pnl_amt = pos['size'] * pnl - pos['size'] * fee_rate * 2
                    cash += pos['size'] + pnl_amt
                    total_realized_pnl += pnl_amt
                    sell_count += 1
        
        prev_level = new_grid_level
        
        # Equity tracking
        floating = sum(pos['size'] * ((price - pos['price']) / pos['price']) for pos in positions)
        equity = cash + floating
        if equity > peak_equity:
            peak_equity = equity
        dd = peak_equity - equity
        if dd > max_drawdown:
            max_drawdown = dd
    
    # Close remaining
    for pos in positions:
        pnl = (closes[-1] - pos['price']) / pos['price']
        pnl_amt = pos['size'] * pnl - pos['size'] * fee_rate * 2
        cash += pos['size'] + pnl_amt
        total_realized_pnl += pnl_amt
    
    final_equity = cash
    return {
        'equity': final_equity,
        'return_pct': (final_equity - initial_equity) / initial_equity * 100,
        'max_dd': max_drawdown,
        'max_dd_pct': max_drawdown / initial_equity * 100,
        'buys': buy_count,
        'sells': sell_count,
        'tp_hits': tp_count,
        'sl_hits': sl_count,
        'total_trades': buy_count
    }


def run_walkforward(df_1h, omen_set, window_days, atr_tp=10.0, atr_sl=7.0):
    """Walk-forward optimization with per-window train/test reporting."""
    rows_per_day = 24
    window_rows = window_days * rows_per_day
    
    grid_opts = [500, 1000, 2000, 3000, 5000]
    rsi_opts = [30, 40, 50, 70, 100]
    
    closes_all = df_1h['close'].values
    highs_all = df_1h['high'].values
    lows_all = df_1h['low'].values
    rsi_all = df_1h['rsi'].values
    atr_all = df_1h['atr'].values
    atr_long_all = df_1h['atr_long'].values
    ts_floor = pd.to_datetime(df_1h.index).floor('h')
    
    window_results = []
    
    # Cumulative tracking
    pure_equity = 1000000
    oracle_equity = 1000000
    pure_peak = 1000000
    oracle_peak = 1000000
    pure_max_dd = 0
    oracle_max_dd = 0
    
    test_start_idx = window_rows
    window_num = 0
    
    while test_start_idx < len(df_1h):
        window_num += 1
        test_end_idx = min(test_start_idx + window_rows, len(df_1h))
        train_start = test_start_idx - window_rows
        
        # --- TRAIN ---
        train_c = closes_all[train_start:test_start_idx]
        train_h = highs_all[train_start:test_start_idx]
        train_l = lows_all[train_start:test_start_idx]
        train_r = rsi_all[train_start:test_start_idx]
        train_atr = atr_all[train_start:test_start_idx]
        train_atr_l = atr_long_all[train_start:test_start_idx]
        
        best_score = -np.inf
        best_params = (2000, 50)
        best_train = None
        
        for g in grid_opts:
            for r in rsi_opts:
                res = run_backtest_with_atr(
                    train_c, train_h, train_l, train_r, g, r,
                    train_atr, train_atr_l,
                    atr_tp_mult=atr_tp, atr_sl_mult=atr_sl)
                if res['buys'] == 0:
                    score = 0
                else:
                    score = res['return_pct'] / (res['max_dd_pct'] + 1)
                if score > best_score:
                    best_score = score
                    best_params = (g, r)
                    best_train = res
        
        best_g, best_r = best_params
        
        # --- TEST (Pure Harmony — no Oracle) ---
        test_c = closes_all[test_start_idx:test_end_idx]
        test_h = highs_all[test_start_idx:test_end_idx]
        test_l = lows_all[test_start_idx:test_end_idx]
        test_r = rsi_all[test_start_idx:test_end_idx]
        test_atr = atr_all[test_start_idx:test_end_idx]
        test_atr_l = atr_long_all[test_start_idx:test_end_idx]
        
        pure_test = run_backtest_with_atr(
            test_c, test_h, test_l, test_r, best_g, best_r,
            test_atr, test_atr_l,
            timestamps=None, omen_set=None,
            atr_tp_mult=atr_tp, atr_sl_mult=atr_sl)
        
        # --- TEST (Oracle Shield) ---
        test_ts_arr = ts_floor[test_start_idx:test_end_idx].values
        test_timestamps = [pd.Timestamp(t) for t in test_ts_arr]
        
        oracle_test = run_backtest_with_atr(
            test_c, test_h, test_l, test_r, best_g, best_r,
            test_atr, test_atr_l,
            timestamps=test_timestamps, omen_set=omen_set,
            atr_tp_mult=atr_tp, atr_sl_mult=atr_sl)
        
        # Track cumulative
        pure_net = pure_test['equity'] - 1000000
        pure_equity += pure_net
        if pure_equity > pure_peak: pure_peak = pure_equity
        dd = pure_peak - pure_equity
        if dd > pure_max_dd: pure_max_dd = dd
        
        oracle_net = oracle_test['equity'] - 1000000
        oracle_equity += oracle_net
        if oracle_equity > oracle_peak: oracle_peak = oracle_equity
        dd = oracle_peak - oracle_equity
        if dd > oracle_max_dd: oracle_max_dd = dd
        
        period_start = df_1h.index[test_start_idx]
        period_end = df_1h.index[min(test_end_idx - 1, len(df_1h) - 1)]
        
        window_results.append({
            'window': window_num,
            'period': f"{str(period_start)[:10]} ~ {str(period_end)[:10]}",
            'best_grid': best_g,
            'best_rsi': best_r,
            'train_return': best_train['return_pct'] if best_train else 0,
            'train_dd': best_train['max_dd_pct'] if best_train else 0,
            'pure_test_return': pure_test['return_pct'],
            'pure_test_dd': pure_test['max_dd_pct'],
            'pure_trades': pure_test['buys'],
            'oracle_test_return': oracle_test['return_pct'],
            'oracle_test_dd': oracle_test['max_dd_pct'],
            'oracle_trades': oracle_test['buys'],
            'oracle_tp': oracle_test['tp_hits'],
            'oracle_sl': oracle_test['sl_hits'],
        })
        
        test_start_idx += window_rows
    
    return window_results, {
        'pure': {'equity': pure_equity, 'return': (pure_equity - 1000000) / 1000000 * 100, 'max_dd': pure_max_dd},
        'oracle': {'equity': oracle_equity, 'return': (oracle_equity - 1000000) / 1000000 * 100, 'max_dd': oracle_max_dd}
    }


def main():
    h1_path = 'data/bybit_btc_usdt_linear_1h_full.csv'
    m1_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    
    print("Loading 1H data...")
    df_1h = pd.read_csv(h1_path)
    df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'])
    df_1h.set_index('timestamp', inplace=True)
    df_1h.sort_index(inplace=True)
    df_1h['rsi'] = calculate_rsi(df_1h['close'])
    df_1h['atr'] = calculate_atr(df_1h)
    df_1h['atr_long'] = calculate_atr(df_1h, 100)
    print(f"  1H: {df_1h.index[0]} ~ {df_1h.index[-1]} ({len(df_1h)} rows)")
    
    print("Loading 1m data and building Renko Oracle...")
    df_1m = pd.read_csv(m1_path)
    df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'], errors='coerce')
    df_1m = df_1m.dropna(subset=['timestamp'])
    print(f"  1m: {df_1m['timestamp'].min()} ~ {df_1m['timestamp'].max()} ({len(df_1m)} rows)")
    
    omen_set = build_omen_lookup(df_1m, brick_size=100, vol_threshold=5.0)
    print(f"  Omens: {len(omen_set)} hours with active omens")
    
    window_configs = [
        ('Quarterly', 90),
        ('Yearly', 360),
    ]
    
    for w_name, w_days in window_configs:
        print(f"\n{'='*120}")
        print(f"  WALK-FORWARD: {w_name} ({w_days}-day windows) | ATR TP×10 SL×7 | Oracle Vol>5.0")
        print(f"{'='*120}")
        
        results, summary = run_walkforward(df_1h, omen_set, w_days)
        
        # Print per-window detail
        print(f"\n{'Win':>3} | {'Period':<25} | {'Grid':>5} | {'RSI':>3} | "
              f"{'Train%':>8} | {'TrainDD':>7} | "
              f"{'Pure%':>8} | {'PureDD':>7} | {'PT':>3} | "
              f"{'Oracle%':>8} | {'OraDD':>7} | {'OT':>3} | {'TP':>3} | {'SL':>3}")
        print("-" * 140)
        
        for r in results:
            print(f"{r['window']:>3} | {r['period']:<25} | {r['best_grid']:>5} | {r['best_rsi']:>3} | "
                  f"{r['train_return']:>+7.2f}% | {r['train_dd']:>6.2f}% | "
                  f"{r['pure_test_return']:>+7.2f}% | {r['pure_test_dd']:>6.2f}% | {r['pure_trades']:>3} | "
                  f"{r['oracle_test_return']:>+7.2f}% | {r['oracle_test_dd']:>6.2f}% | {r['oracle_trades']:>3} | "
                  f"{r['oracle_tp']:>3} | {r['oracle_sl']:>3}")
        
        # Summary
        p = summary['pure']
        o = summary['oracle']
        dd_reduction = ((p['max_dd'] - o['max_dd']) / p['max_dd'] * 100) if p['max_dd'] > 0 else 0
        
        print(f"\n{'--- CUMULATIVE SUMMARY ---':^120}")
        print(f"  Pure Harmony:  Return={p['return']:+.2f}%  MaxDD={p['max_dd']:,.0f}")
        print(f"  Oracle Shield: Return={o['return']:+.2f}%  MaxDD={o['max_dd']:,.0f}  DD Reduction={dd_reduction:+.1f}%")
    
    print(f"\n{'='*120}")
    print("DONE")


if __name__ == "__main__":
    main()
