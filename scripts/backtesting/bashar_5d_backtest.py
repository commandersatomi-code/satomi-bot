"""
🌀 Bashar_5D Final Verification
===============================
Period:
  Train: 2020-01-01 ~ 2025-02-14 (Development)
  Test:  2025-02-15 ~ Present    (Validation/Unknown)

Logic:
  - 1H SMA200
  - Grid 7%
  - Size 8% x 4
  - Long Only, No SL
"""
import pandas as pd
import numpy as np

# --- Configuration ---
SMA_PERIOD = 200
GRID_PCT = 0.07
POS_SIZE_PCT = 0.08
MAX_POS = 4
FEE = 0.0006

HOLDOUT_START = '2025-02-15'

def run_backtest(df, period_name):
    closes = df['close'].values
    sma = df['sma200'].values
    dates = df.index
    
    init = 1000000
    equity = init
    positions = [] # {price, size}
    
    peak = init
    mdd = 0
    
    wins = 0; losses = 0; trades = 0
    
    log_base = np.log(1 + GRID_PCT)
    def glv(p): return int(np.log(max(p, 1)) / log_base)
    
    last_grid = glv(closes[0])
    
    history = []
    
    for i in range(1, len(closes)):
        p = closes[i]
        ma = sma[i]
        t = dates[i]
        
        if np.isnan(ma): continue
        
        curr_grid = glv(p)
        prev_grid = glv(closes[i-1])
        
        # BUY Logic
        if curr_grid < last_grid:
            # Must be below SMA200
            if p < ma:
                levels = last_grid - curr_grid
                for _ in range(levels):
                    if len(positions) >= MAX_POS: continue
                    
                    # Size calculation
                    # Market value of positions
                    pos_val = sum(x['s']*(1+(p-x['p'])/x['p']) for x in positions)
                    total_val = equity + pos_val
                    
                    invest = total_val * POS_SIZE_PCT
                    
                    if equity >= invest and invest > 0:
                        equity -= invest
                        positions.append({'p':p, 's':invest, 't':t})
                        trades += 1
                        history.append({'t':t, 'type':'BUY', 'price':p, 'size':invest})

        # SELL Logic
        elif curr_grid > last_grid:
            # Must be above SMA200
            if p > ma:
                levels = curr_grid - last_grid
                for _ in range(levels):
                    if positions:
                        pos = positions.pop(0)
                        pnl = pos['s']*((p-pos['p'])/pos['p']) - pos['s']*FEE*2
                        equity += pos['s'] + pnl
                        trades += 1
                        if pnl > 0: wins += 1
                        else: losses += 1
                        history.append({'t':t, 'type':'SELL', 'price':p, 'pnl':pnl, 'ret':pnl/pos['s']})
        
        last_grid = curr_grid
        
        # DD Check
        pos_val = sum(x['s']*(1+(p-x['p'])/x['p']) for x in positions)
        curr_total = equity + pos_val
        if curr_total > peak: peak = curr_total
        dd = peak - curr_total
        if dd > mdd: mdd = dd

    # End
    pos_val = sum(x['s']*(1+(closes[-1]-x['p'])/x['p']) for x in positions)
    final = equity + pos_val
    ret = (final - init) / init * 100
    mdd_pct = mdd / init * 100
    wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
    bh = (closes[-1] / closes[0] - 1) * 100
    
    print(f"\n  [{period_name}] {dates[0].date()} ~ {dates[-1].date()}")
    print(f"  Return: {ret:>+7.2f}%  (B&H: {bh:>+7.2f}%)")
    print(f"  MaxDD:  {mdd_pct:>7.2f}%")
    print(f"  Trades: {trades:>5}  (WinRate: {wr:.1f}%)")
    print(f"  Held:   {len(positions)} positions")
    
    if period_name == "TEST (Unknown)":
        print("\n  --- Trade Log (Test Period) ---")
        for h in history:
            if h['type'] == 'SELL':
                print(f"  {h['t']} SELL {h['price']:,.0f} (+{h['ret']*100:.1f}%)")
            elif h['type'] == 'BUY':
                print(f"  {h['t']} BUY  {h['price']:,.0f}")
                
    return ret, mdd_pct

# --- Main ---
print("Loading...")
df = pd.read_csv('data/bybit_btc_usdt_linear_15m_full.csv')
df['timestamp'] = pd.to_datetime(df['timestamp']); df.set_index('timestamp',inplace=True); df.sort_index(inplace=True)
df['sma200'] = df['close'].rolling(SMA_PERIOD).mean()
df.dropna(inplace=True)

print(f"🌀 Bashar_5D Verification (15m)")
print(f"   Config: 15m SMA{SMA_PERIOD}, Grid {GRID_PCT*100}%, Size {POS_SIZE_PCT*100}% x {MAX_POS}")

# 1. Train
train_df = df[df.index < HOLDOUT_START]
run_backtest(train_df, "TRAIN (Past)")

# 2. Test
test_df = df[df.index >= HOLDOUT_START]
run_backtest(test_df, "TEST (Unknown)")

print("\nDONE")
