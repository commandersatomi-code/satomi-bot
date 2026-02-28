"""
Project Ura-Mono: SNIPER v3 (次元斬・真打)
=============================================
Key Insight from v2:
  R:R is excellent (4.45x). But Win Rate ~15-20% turns winners into net loss.
  
v3 Fix: MOMENTUM CONFIRMATION
  Instead of entering on any Omen, wait for:
  1. An Omen fires (Volume Lag + Squeeze)
  2. THEN wait for 3 consecutive Renko bricks in the SAME direction
     = The "explosion" has STARTED. Now ride it.
  This sacrifices some profit (late entry) but dramatically improves Win Rate.
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


def run_sniper_v3(df_1m, brick_size=100, vol_threshold=4.0,
                  consecutive_bricks=3, trailing_atr_mult=5.0, sl_atr_mult=2.0,
                  cooldown_hours=24, fee_rate=0.0006):
    """
    Sniper v3: Momentum Confirmed Entry.
    ENTRY:
      1. Renko Omen fires (Volume Lag > threshold + Squeeze)
      2. Then, N consecutive bricks form in the SAME direction
      3. Enter in that direction, with SMA trend confirmation
    EXIT:
      Trailing Stop (ATR-based) or Hard SL
    """
    df = df_1m.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).sort_values('timestamp')
    
    # ATR + SMA
    close = df['close']
    high = df['high']
    low = df['low']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=1440).mean()
    df['sma200'] = close.rolling(window=200).mean()
    
    # Renko: Full brick analysis
    renko = RenkoChart(brick_size=brick_size)
    bricks = renko.process_data(df)
    bricks = renko.calculate_precursors(bricks)
    bricks['timestamp'] = pd.to_datetime(bricks['timestamp'], errors='coerce')
    bricks = bricks.dropna(subset=['timestamp'])
    
    # Find momentum-confirmed omens:
    # Where Vol Lag is high AND followed by N consecutive same-direction bricks
    confirmed_signals = []
    
    for i in range(len(bricks) - consecutive_bricks):
        brick = bricks.iloc[i]
        
        # Check if this brick is an omen
        if brick['vol_lag'] <= vol_threshold:
            continue
        if brick['squeeze_score'] < 2:  # Some compression
            continue
            
        # Check next N bricks for same direction
        subsequent = bricks.iloc[i+1 : i+1+consecutive_bricks]
        directions = subsequent['type'].values
        
        if len(directions) < consecutive_bricks:
            continue
            
        if all(d == 'UP' for d in directions):
            confirmed_signals.append({
                'timestamp': subsequent.iloc[-1]['timestamp'],  # Enter after confirmation
                'direction': 1,
                'confirmed': True
            })
        elif all(d == 'DOWN' for d in directions):
            confirmed_signals.append({
                'timestamp': subsequent.iloc[-1]['timestamp'],
                'direction': -1,
                'confirmed': True
            })
    
    if not confirmed_signals:
        return 0, 30000, 0, []
    
    signals_df = pd.DataFrame(confirmed_signals)
    
    # Merge signals to 1m data
    df = pd.merge_asof(
        df.sort_values('timestamp'),
        signals_df[['timestamp', 'direction', 'confirmed']].sort_values('timestamp'),
        on='timestamp', direction='backward',
        tolerance=pd.Timedelta(minutes=5)
    )
    df['confirmed'] = df['confirmed'].fillna(False)
    df['sig_dir'] = df['direction'].fillna(0)
    
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
    sig_flags = df['confirmed'].values
    sig_dirs = df['sig_dir'].values
    timestamps = pd.to_datetime(df['timestamp'].values)
    
    warmup = 1440
    
    for i in range(warmup, len(prices)):
        p = prices[i]
        atr = atrs[i]
        sma = smas[i]
        has_signal = sig_flags[i]
        sig_dir = sig_dirs[i]
        ts = timestamps[i]
        
        if np.isnan(atr) or np.isnan(sma):
            continue
        
        # EXIT
        if position != 0:
            if position == 1:
                if p > peak_price:
                    peak_price = p
                    trailing_stop = peak_price - (entry_atr * trailing_atr_mult)
                
                if p <= stop_loss:
                    pnl = (p - entry_price) / entry_price
                    equity = equity * (1 + pnl) - equity * fee_rate
                    trades.append({'ts': ts, 'type': 'SL', 'pnl': pnl, 'dir': 'LONG'})
                    position = 0
                    last_trade_ts = ts
                elif p <= trailing_stop and trailing_stop > entry_price:
                    pnl = (p - entry_price) / entry_price
                    equity = equity * (1 + pnl) - equity * fee_rate
                    trades.append({'ts': ts, 'type': 'TRAIL', 'pnl': pnl, 'dir': 'LONG'})
                    position = 0
                    last_trade_ts = ts
                    
            elif position == -1:
                if p < peak_price:
                    peak_price = p
                    trailing_stop = peak_price + (entry_atr * trailing_atr_mult)
                
                if p >= stop_loss:
                    pnl = (entry_price - p) / entry_price
                    equity = equity * (1 + pnl) - equity * fee_rate
                    trades.append({'ts': ts, 'type': 'SL', 'pnl': pnl, 'dir': 'SHORT'})
                    position = 0
                    last_trade_ts = ts
                elif p >= trailing_stop and trailing_stop < entry_price:
                    pnl = (entry_price - p) / entry_price
                    equity = equity * (1 + pnl) - equity * fee_rate
                    trades.append({'ts': ts, 'type': 'TRAIL', 'pnl': pnl, 'dir': 'SHORT'})
                    position = 0
                    last_trade_ts = ts
        
        # ENTRY (Momentum Confirmed)
        if position == 0 and has_signal:
            if ts - last_trade_ts < cooldown_delta:
                continue
            
            entry_atr = atr
            
            # Direction from confirmed signal + SMA check
            if sig_dir == 1 and p > sma:
                position = 1
                entry_price = p
                stop_loss = p - (atr * sl_atr_mult)
                peak_price = p
                trailing_stop = p - (atr * trailing_atr_mult)
                equity -= equity * fee_rate
            elif sig_dir == -1 and p < sma:
                position = -1
                entry_price = p
                stop_loss = p + (atr * sl_atr_mult)
                peak_price = p
                trailing_stop = p + (atr * trailing_atr_mult)
                equity -= equity * fee_rate
        
        # DD
        cv = equity
        if position == 1: cv = equity * (1 + (p - entry_price) / entry_price)
        elif position == -1: cv = equity * (1 + (entry_price - p) / entry_price)
        if cv > peak_equity: peak_equity = cv
        dd = (peak_equity - cv) / peak_equity * 100
        if dd > max_dd: max_dd = dd
    
    # Close open
    if position != 0:
        pnl = ((prices[-1] - entry_price) / entry_price) if position == 1 else ((entry_price - prices[-1]) / entry_price)
        equity = equity * (1 + pnl) - equity * fee_rate
        trades.append({'ts': timestamps[-1], 'type': 'END', 'pnl': pnl, 'dir': 'L' if position==1 else 'S'})
    
    return (equity - initial_equity) / initial_equity * 100, equity, max_dd, trades


def main():
    m1_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    if not os.path.exists(m1_path): return
    
    print("Loading 1m data...")
    df = pd.read_csv(m1_path).tail(200000)
    print(f"Loaded {len(df)} rows.")
    
    print("\n" + "="*110)
    print("PROJECT URA-MONO: SNIPER v3 (Momentum Confirmed)")
    print("="*110)
    
    configs = [
        # (brick, vol, consec_bricks, trail, sl, cooldown, label)
        (100, 3.0, 2, 5.0, 2.0, 12, "2-Brick Confirm 12H"),
        (100, 3.0, 3, 5.0, 2.0, 12, "3-Brick Confirm 12H"),
        (100, 3.0, 3, 5.0, 2.0, 24, "3-Brick Confirm 24H"),
        (100, 3.0, 3, 8.0, 2.0, 24, "3-Brick Patient 24H"),
        (100, 4.0, 2, 5.0, 2.0, 24, "Ultra Omen 2-Brick"),
        (100, 3.0, 4, 5.0, 2.0, 24, "4-Brick Confirm 24H"),
        (200, 3.0, 3, 6.0, 3.0, 24, "Wide 3-Brick 24H"),
    ]
    
    print(f"\n{'Label':<24} | {'Return':<8} | {'DD%':<7} | {'#Tr':<5} | {'Win':<4} | {'WR%':<6} | {'AvgW':<7} | {'AvgL':<7} | {'R:R'}")
    print("-" * 110)
    
    for brick, vol, consec, trail, sl, cd, label in configs:
        ret, eq, dd, trades = run_sniper_v3(
            df, brick_size=brick, vol_threshold=vol,
            consecutive_bricks=consec, trailing_atr_mult=trail, sl_atr_mult=sl,
            cooldown_hours=cd
        )
        
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        wr = len(wins) / len(trades) * 100 if trades else 0
        avg_w = np.mean([t['pnl'] for t in wins]) * 100 if wins else 0
        avg_l = np.mean([t['pnl'] for t in losses]) * 100 if losses else 0
        rr = abs(avg_w / avg_l) if avg_l != 0 else 0
        
        print(f"{label:<24} | {ret:>+7.2f}% | {dd:>6.2f}% | {len(trades):<5} | {len(wins):<4} | {wr:>5.1f}% | {avg_w:>+6.2f}% | {avg_l:>+6.2f}% | {rr:>4.2f}")
    
    print("=" * 110)
    
    # Best config detail
    print("\n--- BEST CONFIG DETAIL ---")
    ret, eq, dd, trades = run_sniper_v3(
        df, brick_size=100, vol_threshold=3.0,
        consecutive_bricks=3, trailing_atr_mult=5.0, sl_atr_mult=2.0,
        cooldown_hours=24
    )
    for t in trades:
        print(f"  {t['ts']} | {t['dir']:<5} | {t['type']:<5} | PnL: {t['pnl']*100:>+7.3f}%")
    print(f"\n¥{eq:,.0f} (¥30,000 start) | Return: {ret:+.2f}% | MaxDD: {dd:.2f}%")


if __name__ == "__main__":
    main()
