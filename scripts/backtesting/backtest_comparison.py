import pandas as pd
import numpy as np
import sys
import os

# ==========================================
# 共通設定 / Common Config
# ==========================================
INITIAL_CAPITAL = 30000.0  # 3万円スタート
FEE_RATE = 0.0006         # 0.06% (Taker)
START_DATE = '2023-01-01'

# ==========================================
# 1. データ読み込み / Data Loader
# ==========================================
def load_and_prep_data(filepath, start_date):
    print(f"Loading {filepath}...")
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return None
    
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    return df

# ==========================================
# 2. 1H ロジック (Ishikawa Hybrid)
# ==========================================
def run_1h_simulation(df):
    # --- Indicators ---
    # ATR Short (14), ATR Long (100), SMA (20)
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr_short = tr.rolling(window=14).mean().ffill().bfill()
    atr_long = tr.rolling(window=100).mean().ffill().bfill()
    sma = close.rolling(window=20).mean()
    
    # --- Settings (Latest Scan) ---
    ENTRY_M = 1.8
    TP_BASE = 10.0
    SL_FIXED = 10.0
    
    # --- Simulation ---
    # Slice Data
    df_sim = df[df.index >= START_DATE].copy()
    start_idx_offset = len(df) - len(df_sim)
    
    equity = INITIAL_CAPITAL
    positions = [] # List of dicts
    trades = []
    
    # Pre-calc arrays
    closes = df['close'].values
    atr_s = atr_short.values
    atr_l = atr_long.values
    smas = sma.values
    times = df.index
    
    # Max Positions (Grid Safety)
    MAX_POSITIONS = 5
    POS_SIZE_PCT = 0.20 # 20% of Equity per position
    
    peak_equity = equity
    max_dd = 0

    print("Running 1H Simulation...")
    
    # Iterate over sliced range
    for i in range(start_idx_offset, len(df)):
        current_time = times[i]
        price = closes[i]
        curr_atr = atr_s[i]
        long_atr = atr_l[i]
        curr_sma = smas[i]
        
        if np.isnan(curr_sma): continue

        # --- Check Exits ---
        active_positions = []
        for pos in positions:
            p_price = pos['price']
            tp_price = p_price + pos['tp']
            sl_price = p_price - pos['sl']
            p_size = pos['size'] # Amount invested
            
            # Hit TP? (Long Only)
            if price >= tp_price:
                # Profit
                raw_pnl_pct = (price - p_price) / p_price
                net_pnl_amt = (p_size * raw_pnl_pct) - (p_size * FEE_RATE * 2) # Fee Entry+Exit
                equity += net_pnl_amt + p_size # Return capital + profit
                trades.append({'time': current_time, 'pnl': raw_pnl_pct, 'type': 'TP'})
                
            # Hit SL?
            elif price <= sl_price:
                # Loss
                raw_pnl_pct = (price - p_price) / p_price
                net_pnl_amt = (p_size * raw_pnl_pct) - (p_size * FEE_RATE * 2)
                equity += net_pnl_amt + p_size
                trades.append({'time': current_time, 'pnl': raw_pnl_pct, 'type': 'SL'})
                
            else:
                active_positions.append(pos)
        
        positions = active_positions
        
        # --- Update Equity & Drawdown ---
        # Calculate floating equity
        floating_pnl = 0
        current_invested = 0
        for pos in positions:
            current_invested += pos['size']
            floating_pnl += pos['size'] * ((price - pos['price']) / pos['price'])
            
        total_value = equity + floating_pnl # positions removed from equity when opened? No, I subtracted below.
        # Wait, standardizing arithmetic:
        # equity = Cash. Positions = Invested.
        # Total Value = Cash + Current Value of Positions.
        
        # Logic fix: When opening, subtract from equity (Cash).
        
        if total_value > peak_equity: peak_equity = total_value
        dd = peak_equity - total_value
        if dd > max_dd: max_dd = dd
        
        # --- Entry Logic ---
        vol_ratio = max(0.5, min(2.0, curr_atr / long_atr))
        interval = curr_atr * ENTRY_M
        
        should_buy = False
        if len(positions) < MAX_POSITIONS:
            # First Entry or Averaging
            if len(positions) == 0:
                if price <= curr_sma - interval: should_buy = True
            else:
                # Add if dropped by interval
                last_price = positions[-1]['price']
                if price <= last_price - interval: should_buy = True
                
        if should_buy and equity > 0:
            # Position Sizing: 20% of Current Total Value (or Cash?)
            # Let's use 20% of Total Value to compound.
            invest_amount = total_value * POS_SIZE_PCT
            
            # Can we afford it?
            if equity >= invest_amount:
                equity -= invest_amount # Move Cash to Position
                
                tp_w = curr_atr * (TP_BASE * vol_ratio)
                sl_w = curr_atr * SL_FIXED
                
                positions.append({
                    'price': price,
                    'tp': tp_w,
                    'sl': sl_w,
                    'size': invest_amount
                })
                
    # Close all at end
    final_equity = equity
    for pos in positions:
        curr_val = pos['size'] * (1 + (closes[-1] - pos['price'])/pos['price'])
        final_equity += curr_val
        
    return final_equity, max_dd, trades


# ==========================================
# 3. 15m ロジック (The 39% Strategy)
# ==========================================
def run_15m_simulation(df):
    # --- Indicators ---
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['vol_mult'] = df['volume'] / df['volume_sma']
    df['sma_200'] = df['close'].rolling(window=200).mean()
    df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # --- Simulation ---
    df_sim = df[df.index >= START_DATE].copy()
    start_idx_offset = len(df) - len(df_sim)
    
    equity = INITIAL_CAPITAL
    positions = [] # Max 1 position
    trades = []
    
    closes = df['close'].values
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    times = df.index
    
    # Arrays
    sma200 = df['sma_200'].values
    range_pct = df['range_pct'].values
    vol_mult = df['vol_mult'].values
    rsi = df['rsi'].values
    
    # Params
    TP_PCT = 0.05
    SL_PCT = 0.03
    
    peak_equity = equity
    max_dd = 0

    print("Running 15m Simulation...")
    
    # Logic requires i-3.
    iter_start = max(start_idx_offset, 205)

    for i in range(iter_start, len(df)):
        current_time = times[i]
        
        # --- Exits ---
        # Assume 1 position max
        if len(positions) > 0:
            pos = positions[0]
            p_type = pos['type']
            entry = pos['price']
            p_size = pos['size']
            
            pnl_pct = 0
            exit_hit = False
            
            # Check Low/High for hit
            if p_type == 'LONG':
                if lows[i] <= entry * (1 - SL_PCT):
                    pnl_pct = -SL_PCT
                    exit_hit = True
                elif highs[i] >= entry * (1 + TP_PCT):
                    pnl_pct = TP_PCT
                    exit_hit = True
            elif p_type == 'SHORT':
                if highs[i] >= entry * (1 + SL_PCT):
                    pnl_pct = -SL_PCT
                    exit_hit = True
                elif lows[i] <= entry * (1 - TP_PCT):
                    pnl_pct = TP_PCT
                    exit_hit = True
            
            if exit_hit:
                # Fee calculation
                # Note: Fixed TP/SL includes price moves. 
                # Net = PnL - Fees
                net_amt = (p_size * pnl_pct) - (p_size * FEE_RATE * 2)
                equity += net_amt + p_size
                trades.append({'time': current_time, 'pnl': pnl_pct, 'type': 'Exit'})
                positions = [] # Clear
        
        # --- Update DD ---
        # If position open, calculate floating
        total_val = equity
        if positions:
            pos = positions[0]
            curr_price = closes[i]
            if pos['type'] == 'LONG':
                float_pnl = (curr_price - pos['price']) / pos['price']
            else:
                float_pnl = (pos['price'] - curr_price) / pos['price']
            total_val += pos['size'] * (1 + float_pnl) # Wait, equity was subtracted?
            # Fix: Yes, remove from equity when open
            
        if total_val > peak_equity: peak_equity = total_val
        dd = peak_equity - total_val
        if dd > max_dd: max_dd = dd
        
        # --- Entry ---
        if len(positions) == 0:
            p1 = i - 1
            p2 = i - 2
            p3 = i - 3
            
            # Logic: Running Start
            inc_range = (range_pct[p1] > range_pct[p2]) and (range_pct[p2] > range_pct[p3])
            inc_vol = (vol_mult[p1] > vol_mult[p2]) and (vol_mult[p2] > vol_mult[p3])
            
            if inc_range and inc_vol:
                entry_price = opens[i]
                sma_val = sma200[p1]
                
                signal = None
                p_rsi = [rsi[p1], rsi[p2], rsi[p3]]
                
                if entry_price > sma_val and all(r >= 50 for r in p_rsi):
                    signal = 'LONG'
                elif entry_price < sma_val and all(r <= 47 for r in p_rsi):
                    signal = 'SHORT'
                
                if signal:
                    invest_amt = equity # Full compounding
                    equity -= invest_amt
                    positions.append({
                        'type': signal,
                        'price': entry_price,
                        'size': invest_amt
                    })

    # Close end
    final_equity = equity
    if positions:
        pos = positions[0]
        curr = closes[-1]
        if pos['type'] == 'LONG': pnl = (curr - pos['price'])/pos['price']
        else: pnl = (pos['price'] - curr)/pos['price']
        final_equity += pos['size'] * (1 + pnl)

    return final_equity, max_dd, trades

# ==========================================
# Main Comparison
# ==========================================
def main():
    print("==========================================")
    print("      Strategy Generator & Comparison     ")
    print("==========================================")
    print(f"初期資金 (Start Capital): {INITIAL_CAPITAL:,.0f} JPY")
    print(f"開始日   (Start Date)   : {START_DATE}")
    print("-" * 60)
    
    # 1. 1H
    df_1h = load_and_prep_data('data/bybit_btc_usdt_linear_1h_full.csv', START_DATE)
    if df_1h is not None:
        eq_1h, dd_1h, trades_1h = run_1h_simulation(df_1h)
        
        wins = len([t for t in trades_1h if t['pnl'] > 0])
        total = len(trades_1h)
        wr = (wins/total*100) if total > 0 else 0
        roi = (eq_1h - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
        
        print("\n[Strategy A] 1H Ishikawa Hybrid (Legacy/Stable)")
        print(f"Final Equity : {eq_1h:,.0f} JPY")
        print(f"ROI          : {roi:+.2f}%")
        print(f"Max Drawdown : {dd_1h:,.0f} JPY")
        print(f"Trades       : {total} (Win Rate: {wr:.1f}%)")
    
    # 2. 15m
    df_15m = load_and_prep_data('data/bybit_btc_usdt_linear_15m_full.csv', START_DATE)
    if df_15m is not None:
        eq_15m, dd_15m, trades_15m = run_15m_simulation(df_15m)

        wins = len([t for t in trades_15m if t['pnl'] > 0])
        total = len(trades_15m)
        wr = (wins/total*100) if total > 0 else 0
        roi = (eq_15m - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
        
        print("\n[Strategy B] 15m 39% Strategy (Aggressive/Running)")
        print(f"Final Equity : {eq_15m:,.0f} JPY")
        print(f"ROI          : {roi:+.2f}%")
        print(f"Max Drawdown : {dd_15m:,.0f} JPY")
        print(f"Trades       : {total} (Win Rate: {wr:.1f}%)")

if __name__ == "__main__":
    main()
