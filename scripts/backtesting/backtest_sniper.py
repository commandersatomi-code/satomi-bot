"""
Project Ura-Mono: SNIPER LOGIC (次元斬)
========================================
Philosophy:
  - NOT a grid. NOT a scalper. A SNIPER.
  - Wait for the Oracle (Renko Volume Lag) to confirm an 'Energy Explosion'.
  - Enter ONE focused position.
  - Hold until the explosion plays out (ATR * N trailing stop).
  - Spend most of the time in CASH (Zero Drawdown).

Key Metrics:
  - Win Rate doesn't matter. What matters is: Avg Win >> Avg Loss.
  - Target: Few trades, massive R:R (Risk:Reward).
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


def compute_renko_omens(df_1m, brick_size, vol_threshold):
    """Generate Renko bricks and identify 'Omen' timestamps."""
    renko = RenkoChart(brick_size=brick_size)
    bricks = renko.process_data(df_1m)
    bricks = renko.calculate_precursors(bricks)
    bricks['timestamp'] = pd.to_datetime(bricks['timestamp'], errors='coerce')
    bricks = bricks.dropna(subset=['timestamp'])
    
    # Omen = Volume Lag exceeds threshold
    omens = bricks[bricks['vol_lag'] > vol_threshold][['timestamp']].copy()
    omens['omen'] = True
    return omens, bricks


def run_sniper_backtest(df_1m, brick_size=100, vol_threshold=3.0,
                        trailing_atr_mult=5.0, sl_atr_mult=2.0,
                        fee_rate=0.0006):
    """
    Sniper Logic:
      ENTRY: Renko Omen detected + Price trending (above/below SMA200)
             -> Enter LONG (above SMA) or SHORT (below SMA)
      EXIT:  Trailing Stop = ATR * trailing_atr_mult from peak profit
             OR Hard Stop Loss = ATR * sl_atr_mult from entry
      SIZE:  100% of equity (Single concentrated bet)
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
    df['atr'] = tr.rolling(window=1440).mean()  # 1-day ATR on 1m bars
    df['sma200'] = close.rolling(window=200).mean()
    
    # Renko Omens
    omens, _ = compute_renko_omens(df, brick_size, vol_threshold)
    
    # Merge omens
    df = pd.merge_asof(
        df.sort_values('timestamp'),
        omens.sort_values('timestamp'),
        on='timestamp', direction='backward',
        tolerance=pd.Timedelta(minutes=15)
    )
    df['omen'] = df['omen'].fillna(False)
    
    # Simulation
    initial_equity = 30000.0  # 3万円スタート
    equity = initial_equity
    
    position = 0       # 0=flat, 1=long, -1=short
    entry_price = 0.0
    stop_loss = 0.0
    trailing_stop = 0.0
    peak_price = 0.0
    entry_atr = 0.0
    
    trades = []
    equity_curve = []
    
    peak_equity = initial_equity
    max_dd = 0.0
    
    prices = df['close'].values
    atrs = df['atr'].values
    smas = df['sma200'].values
    omen_flags = df['omen'].values
    timestamps = df['timestamp'].values
    
    warmup = 1440  # Skip first day for ATR warmup
    
    for i in range(warmup, len(prices)):
        p = prices[i]
        atr = atrs[i]
        sma = smas[i]
        has_omen = omen_flags[i]
        ts = timestamps[i]
        
        if np.isnan(atr) or np.isnan(sma):
            continue
        
        # === EXIT LOGIC ===
        if position != 0:
            # Update trailing stop
            if position == 1:  # Long
                if p > peak_price:
                    peak_price = p
                    trailing_stop = peak_price - (entry_atr * trailing_atr_mult)
                
                # Check exits
                if p <= stop_loss:
                    # Hard SL hit
                    pnl_pct = (p - entry_price) / entry_price
                    fee = equity * fee_rate
                    equity = equity * (1 + pnl_pct) - fee
                    trades.append({'ts': ts, 'type': 'SL', 'pnl_pct': pnl_pct, 'dir': 'LONG'})
                    position = 0
                    
                elif p <= trailing_stop and trailing_stop > entry_price:
                    # Trailing stop (only if in profit)
                    pnl_pct = (p - entry_price) / entry_price
                    fee = equity * fee_rate
                    equity = equity * (1 + pnl_pct) - fee
                    trades.append({'ts': ts, 'type': 'TRAIL', 'pnl_pct': pnl_pct, 'dir': 'LONG'})
                    position = 0
                    
            elif position == -1:  # Short
                if p < peak_price:
                    peak_price = p
                    trailing_stop = peak_price + (entry_atr * trailing_atr_mult)
                
                if p >= stop_loss:
                    pnl_pct = (entry_price - p) / entry_price
                    fee = equity * fee_rate
                    equity = equity * (1 + pnl_pct) - fee
                    trades.append({'ts': ts, 'type': 'SL', 'pnl_pct': pnl_pct, 'dir': 'SHORT'})
                    position = 0
                    
                elif p >= trailing_stop and trailing_stop < entry_price:
                    pnl_pct = (entry_price - p) / entry_price
                    fee = equity * fee_rate
                    equity = equity * (1 + pnl_pct) - fee
                    trades.append({'ts': ts, 'type': 'TRAIL', 'pnl_pct': pnl_pct, 'dir': 'SHORT'})
                    position = 0
        
        # === ENTRY LOGIC (Sniper: Wait for the Oracle) ===
        if position == 0 and has_omen:
            entry_atr = atr
            
            if p > sma:
                # LONG
                position = 1
                entry_price = p
                stop_loss = p - (atr * sl_atr_mult)
                peak_price = p
                trailing_stop = p - (atr * trailing_atr_mult)
                fee = equity * fee_rate
                equity -= fee
                
            elif p < sma:
                # SHORT
                position = -1
                entry_price = p
                stop_loss = p + (atr * sl_atr_mult)
                peak_price = p
                trailing_stop = p + (atr * trailing_atr_mult)
                fee = equity * fee_rate
                equity -= fee
        
        # Equity tracking
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
        
        equity_curve.append(current_val)
    
    # Close any open position at end
    if position != 0:
        if position == 1:
            pnl_pct = (prices[-1] - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - prices[-1]) / entry_price
        equity = equity * (1 + pnl_pct) - equity * fee_rate
        trades.append({'ts': timestamps[-1], 'type': 'END', 'pnl_pct': pnl_pct, 'dir': 'LONG' if position==1 else 'SHORT'})
    
    final_return = (equity - initial_equity) / initial_equity * 100
    
    return final_return, equity, max_dd, trades, equity_curve


def main():
    m1_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    if not os.path.exists(m1_path):
        print(f"Error: {m1_path} not found.")
        return
    
    print("Loading 1m data...")
    df = pd.read_csv(m1_path)
    # Use a large sample for meaningful results
    df = df.tail(200000)
    print(f"Loaded {len(df)} rows.")
    
    print("\n" + "="*80)
    print("PROJECT URA-MONO: SNIPER LOGIC (次元斬)")
    print("="*80)
    
    # Test configurations
    configs = [
        # (brick, vol_thresh, trail_mult, sl_mult, label)
        (100, 3.0, 5.0, 2.0, "Conservative Sniper"),
        (100, 2.5, 8.0, 2.0, "Patient Sniper"),
        (100, 3.0, 10.0, 3.0, "Ultra Patient"),
        ( 50, 3.0, 5.0, 1.5, "Tight SL Sniper"),
        (200, 2.5, 6.0, 3.0, "Wide Brick Sniper"),
    ]
    
    print(f"\n{'Label':<22} | {'Return':<8} | {'MaxDD%':<8} | {'Trades':<7} | {'Wins':<5} | {'WinRate':<8} | {'AvgWin':<8} | {'AvgLoss'}")
    print("-" * 100)
    
    for brick, vol_t, trail, sl, label in configs:
        ret, eq, dd, trades, _ = run_sniper_backtest(
            df, brick_size=brick, vol_threshold=vol_t,
            trailing_atr_mult=trail, sl_atr_mult=sl
        )
        
        wins = [t for t in trades if t['pnl_pct'] > 0]
        losses = [t for t in trades if t['pnl_pct'] <= 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_win = np.mean([t['pnl_pct'] for t in wins]) * 100 if wins else 0
        avg_loss = np.mean([t['pnl_pct'] for t in losses]) * 100 if losses else 0
        
        print(f"{label:<22} | {ret:>+7.2f}% | {dd:>7.2f}% | {len(trades):<7} | {len(wins):<5} | {win_rate:>6.1f}% | {avg_win:>+7.2f}% | {avg_loss:>+7.2f}%")
    
    print("=" * 100)
    
    # Detailed trade log for the best config
    print("\n--- Detailed Trade Log (Conservative Sniper) ---")
    ret, eq, dd, trades, curve = run_sniper_backtest(
        df, brick_size=100, vol_threshold=3.0,
        trailing_atr_mult=5.0, sl_atr_mult=2.0
    )
    
    for t in trades[:20]:  # First 20 trades
        print(f"  {t['ts']} | {t['dir']:<5} | {t['type']:<5} | PnL: {t['pnl_pct']*100:>+7.3f}%")
    
    if len(trades) > 20:
        print(f"  ... and {len(trades)-20} more trades")
    
    print(f"\nFinal Equity: ¥{eq:,.0f} (Start: ¥30,000)")
    print(f"Total Return: {ret:+.2f}%")
    print(f"Max Drawdown: {dd:.2f}%")


if __name__ == "__main__":
    main()
