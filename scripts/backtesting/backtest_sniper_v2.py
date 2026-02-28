"""
Project Ura-Mono: SNIPER LOGIC v2 (次元斬・改)
================================================
Fix from v1: Too many trades (1400+). Not a Sniper.
Root Cause: Omen fires every few minutes.

v2 Changes:
  1. COOLDOWN: After any trade (win or loss), wait N hours before next entry.
  2. STRONGER OMEN: Raise vol_lag threshold to 5.0+ (ultra-rare events only).
  3. CONFLUENCE: Require BOTH Volume Lag AND Squeeze (direction flip) for entry.
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


def compute_omens_v2(df_1m, brick_size, vol_threshold):
    """Generate high-conviction omens with confluence."""
    renko = RenkoChart(brick_size=brick_size)
    bricks = renko.process_data(df_1m)
    bricks = renko.calculate_precursors(bricks)
    bricks['timestamp'] = pd.to_datetime(bricks['timestamp'], errors='coerce')
    bricks = bricks.dropna(subset=['timestamp'])
    
    # Confluence: Volume Lag AND recent squeeze (lots of direction flips)
    confluence = bricks[
        (bricks['vol_lag'] > vol_threshold) & 
        (bricks['squeeze_score'] >= 3)  # At least 3 flips in last 5 bricks
    ][['timestamp', 'type']].copy()
    confluence['omen'] = True
    confluence['omen_dir'] = confluence['type'].apply(lambda x: 1 if x == 'UP' else -1)
    
    return confluence


def run_sniper_v2(df_1m, brick_size=100, vol_threshold=5.0,
                  trailing_atr_mult=6.0, sl_atr_mult=2.0,
                  cooldown_hours=24, fee_rate=0.0006):
    """
    Sniper v2: True sniper with cooldown and confluence filter.
    """
    df = df_1m.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).sort_values('timestamp')
    
    # Indicators
    close = df['close']
    high = df['high']
    low = df['low']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=1440).mean()
    df['sma200'] = close.rolling(window=200).mean()
    
    # Omens (Confluenced)
    omens = compute_omens_v2(df, brick_size, vol_threshold)
    
    # Merge
    df = pd.merge_asof(
        df.sort_values('timestamp'),
        omens[['timestamp', 'omen', 'omen_dir']].sort_values('timestamp'),
        on='timestamp', direction='backward',
        tolerance=pd.Timedelta(minutes=5)  # Tighter window
    )
    df['omen'] = df['omen'].fillna(False)
    df['omen_dir'] = df['omen_dir'].fillna(0)
    
    # Simulation
    initial_equity = 30000.0
    equity = initial_equity
    
    position = 0
    entry_price = 0.0
    stop_loss = 0.0
    trailing_stop = 0.0
    peak_price = 0.0
    entry_atr = 0.0
    last_trade_ts = pd.Timestamp('2000-01-01')
    cooldown_delta = pd.Timedelta(hours=cooldown_hours)
    
    trades = []
    peak_equity = initial_equity
    max_dd = 0.0
    
    prices = df['close'].values
    atrs = df['atr'].values
    smas = df['sma200'].values
    omen_flags = df['omen'].values
    omen_dirs = df['omen_dir'].values
    timestamps = pd.to_datetime(df['timestamp'].values)
    
    warmup = 1440
    
    for i in range(warmup, len(prices)):
        p = prices[i]
        atr = atrs[i]
        sma = smas[i]
        has_omen = omen_flags[i]
        omen_dir = omen_dirs[i]
        ts = timestamps[i]
        
        if np.isnan(atr) or np.isnan(sma):
            continue
        
        # === EXIT ===
        if position != 0:
            if position == 1:
                if p > peak_price:
                    peak_price = p
                    trailing_stop = peak_price - (entry_atr * trailing_atr_mult)
                
                if p <= stop_loss:
                    pnl_pct = (p - entry_price) / entry_price
                    equity = equity * (1 + pnl_pct) - equity * fee_rate
                    trades.append({'ts': ts, 'type': 'SL', 'pnl_pct': pnl_pct, 'dir': 'LONG'})
                    position = 0
                    last_trade_ts = ts
                    
                elif p <= trailing_stop and trailing_stop > entry_price:
                    pnl_pct = (p - entry_price) / entry_price
                    equity = equity * (1 + pnl_pct) - equity * fee_rate
                    trades.append({'ts': ts, 'type': 'TRAIL', 'pnl_pct': pnl_pct, 'dir': 'LONG'})
                    position = 0
                    last_trade_ts = ts
                    
            elif position == -1:
                if p < peak_price:
                    peak_price = p
                    trailing_stop = peak_price + (entry_atr * trailing_atr_mult)
                
                if p >= stop_loss:
                    pnl_pct = (entry_price - p) / entry_price
                    equity = equity * (1 + pnl_pct) - equity * fee_rate
                    trades.append({'ts': ts, 'type': 'SL', 'pnl_pct': pnl_pct, 'dir': 'SHORT'})
                    position = 0
                    last_trade_ts = ts
                    
                elif p >= trailing_stop and trailing_stop < entry_price:
                    pnl_pct = (entry_price - p) / entry_price
                    equity = equity * (1 + pnl_pct) - equity * fee_rate
                    trades.append({'ts': ts, 'type': 'TRAIL', 'pnl_pct': pnl_pct, 'dir': 'SHORT'})
                    position = 0
                    last_trade_ts = ts
        
        # === ENTRY (Sniper: Cooldown + Confluence) ===
        if position == 0 and has_omen:
            # Check cooldown
            if ts - last_trade_ts < cooldown_delta:
                continue
            
            entry_atr = atr
            
            # Follow omen direction (the Renko brick direction at the omen)
            if omen_dir == 1 and p > sma:
                position = 1
                entry_price = p
                stop_loss = p - (atr * sl_atr_mult)
                peak_price = p
                trailing_stop = p - (atr * trailing_atr_mult)
                equity -= equity * fee_rate
                
            elif omen_dir == -1 and p < sma:
                position = -1
                entry_price = p
                stop_loss = p + (atr * sl_atr_mult)
                peak_price = p
                trailing_stop = p + (atr * trailing_atr_mult)
                equity -= equity * fee_rate
        
        # DD tracking
        current_val = equity
        if position == 1:
            current_val = equity * (1 + (p - entry_price) / entry_price)
        elif position == -1:
            current_val = equity * (1 + (entry_price - p) / entry_price)
            
        if current_val > peak_equity:
            peak_equity = current_val
        dd = (peak_equity - current_val) / peak_equity * 100
        if dd > max_dd:
            max_dd = dd
    
    # Close open position
    if position != 0:
        if position == 1:
            pnl_pct = (prices[-1] - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - prices[-1]) / entry_price
        equity = equity * (1 + pnl_pct) - equity * fee_rate
        trades.append({'ts': timestamps[-1], 'type': 'END', 'pnl_pct': pnl_pct, 'dir': 'LONG' if position==1 else 'SHORT'})
    
    final_return = (equity - initial_equity) / initial_equity * 100
    return final_return, equity, max_dd, trades


def main():
    m1_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    if not os.path.exists(m1_path):
        print(f"Error: {m1_path} not found.")
        return
    
    print("Loading 1m data...")
    df = pd.read_csv(m1_path).tail(200000)
    print(f"Loaded {len(df)} rows.")
    
    print("\n" + "="*100)
    print("PROJECT URA-MONO: SNIPER v2 (Cooldown + Confluence)")
    print("="*100)
    
    configs = [
        # (brick, vol_thresh, trail, sl, cooldown_hrs, label)
        (100, 4.0, 5.0, 2.0, 12, "12H Cooldown"),
        (100, 4.0, 5.0, 2.0, 24, "24H Cooldown"),
        (100, 4.0, 8.0, 2.0, 48, "48H Patient"),
        (100, 5.0, 5.0, 2.0, 24, "Ultra Rare Omen"),
        (100, 5.0, 10.0, 3.0, 72, "72H Extreme Sniper"),
        (200, 4.0, 6.0, 3.0, 24, "Wide Brick 24H"),
    ]
    
    print(f"\n{'Label':<22} | {'Return':<8} | {'MaxDD%':<8} | {'Trades':<7} | {'Wins':<5} | {'WR%':<6} | {'AvgWin':<8} | {'AvgLoss':<8} | {'R:R'}")
    print("-" * 110)
    
    for brick, vol_t, trail, sl, cd, label in configs:
        ret, eq, dd, trades = run_sniper_v2(
            df, brick_size=brick, vol_threshold=vol_t,
            trailing_atr_mult=trail, sl_atr_mult=sl,
            cooldown_hours=cd
        )
        
        wins = [t for t in trades if t['pnl_pct'] > 0]
        losses = [t for t in trades if t['pnl_pct'] <= 0]
        wr = len(wins) / len(trades) * 100 if trades else 0
        avg_w = np.mean([t['pnl_pct'] for t in wins]) * 100 if wins else 0
        avg_l = np.mean([t['pnl_pct'] for t in losses]) * 100 if losses else 0
        rr = abs(avg_w / avg_l) if avg_l != 0 else 0
        
        print(f"{label:<22} | {ret:>+7.2f}% | {dd:>7.2f}% | {len(trades):<7} | {len(wins):<5} | {wr:>5.1f}% | {avg_w:>+7.2f}% | {avg_l:>+7.2f}% | {rr:>5.2f}")
    
    print("=" * 110)
    
    # Best candidate detailed log
    print("\n--- Trade Log: 24H Cooldown ---")
    ret, eq, dd, trades = run_sniper_v2(
        df, brick_size=100, vol_threshold=4.0,
        trailing_atr_mult=5.0, sl_atr_mult=2.0, cooldown_hours=24
    )
    for t in trades:
        print(f"  {t['ts']} | {t['dir']:<5} | {t['type']:<5} | PnL: {t['pnl_pct']*100:>+7.3f}%")
    print(f"\nFinal: ¥{eq:,.0f} | Return: {ret:+.2f}% | MaxDD: {dd:.2f}%")


if __name__ == "__main__":
    main()
