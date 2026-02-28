
import pandas as pd
import numpy as np
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src/engines')))
try:
    from renko_engine import RenkoChart
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/engines')))
    from renko_engine import RenkoChart

def run_hybrid_backtest_v3(df_1m, brick_size=100, vol_threshold=2.5, entry_m=1.0, tp_m=2.0, fee_rate=0.0006):
    df_1m = df_1m.copy()
    df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'], errors='coerce')
    df_1m = df_1m.dropna(subset=['timestamp'])
    
    high = df_1m['high']
    low = df_1m['low']
    close = df_1m['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    df_1m['atr'] = tr.rolling(window=1440).mean()
    df_1m['sma'] = close.rolling(window=200).mean()
    
    renko = RenkoChart(brick_size=brick_size)
    renko_bricks = renko.process_data(df_1m)
    renko_bricks = renko.calculate_precursors(renko_bricks)
    renko_bricks['timestamp'] = pd.to_datetime(renko_bricks['timestamp'], errors='coerce')
    renko_bricks = renko_bricks.dropna(subset=['timestamp'])
    
    stars = renko_bricks[renko_bricks['vol_lag'] > vol_threshold].copy()
    stars['omen'] = True
    
    # Ensure sorted for merge_asof
    df_1m = df_1m.sort_values('timestamp')
    stars = stars.sort_values('timestamp')
    
    df_sim = pd.merge_asof(
        df_1m,
        stars[['timestamp', 'omen']],
        on='timestamp', direction='backward', tolerance=pd.Timedelta(minutes=15)
    )
    df_sim['omen'] = df_sim['omen'].fillna(False)
    
    initial_equity = 30000 
    equity = initial_equity
    positions = [] 
    
    peak = initial_equity
    max_dd_val = 0
    trades = 0
    
    prices = df_sim['close'].values
    atrs = df_sim['atr'].values
    smas = df_sim['sma'].values
    omens = df_sim['omen'].values
    
    for i in range(1440, len(prices)):
        p = prices[i]
        atr = atrs[i]
        sma = smas[i]
        omen = omens[i]
        
        # EXIT
        active_pos = []
        for b_price, tp_price in positions:
            if p >= tp_price:
                pnl = (p - b_price) / b_price
                equity += (initial_equity * 0.2) * (1 + pnl - fee_rate * 2)
                trades += 1
            elif p < b_price * 0.90:
                pnl = (p - b_price) / b_price
                equity += (initial_equity * 0.2) * (1 + pnl - fee_rate * 2)
                trades += 1
            else:
                active_pos.append((b_price, tp_price))
        positions = active_pos
        
        # ENTRY
        if len(positions) < 5 and not np.isnan(sma) and p < sma:
            if omen:
                can_entry = True
                if positions:
                    last_e = positions[-1][0]
                    if p > last_e - (atr * entry_m): can_entry = False
                
                if can_entry:
                    size = initial_equity * 0.2
                    equity -= size
                    tp = p + (atr * tp_m)
                    positions.append((p, tp))

        # DD
        unrealized = sum((p - pos[0]) / pos[0] * (initial_equity * 0.2) for pos in positions)
        total_val = equity + unrealized
        if total_val > peak: peak = total_val
        dd_amt = peak - total_val
        if dd_amt > max_dd_val: max_dd_val = dd_amt

    final_val = equity + sum((prices[-1]-pos[0])/pos[0]*(initial_equity*0.2) for pos in positions)
    return (final_val - initial_equity) / initial_equity * 100, (max_dd_val / peak * 100), trades

def main():
    m1_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    if not os.path.exists(m1_path): return
    df = pd.read_csv(m1_path).tail(100000)
    
    print("\n" + "="*80)
    print(f"HYBRID ORACLE v3 (Final Stable)")
    print(f"{'Entry_M':<10} | {'TP_M':<8} | {'Return':<8} | {'MaxDD%':<10} | {'Trades'}")
    print("-" * 80)
    
    # Test slightly more aggressive TP to capture 'explosions'
    configs = [(1.5, 3.0), (2.0, 5.0), (1.0, 6.0)]
    for e_m, t_m in configs:
        ret, dd, count = run_hybrid_backtest_v3(df, entry_m=e_m, tp_m=t_m)
        print(f"{e_m:<10} | {t_m:<8} | {ret:>7.2f}% | {dd:>10.2f}% | {count}")
    print("="*80)

if __name__ == "__main__":
    main()
