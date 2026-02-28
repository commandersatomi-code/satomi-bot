import pandas as pd
import numpy as np
import os

# ==========================================
# 1. バックテスト用コアロジック (トレンド適応型)
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def run_adaptive_backtest(closes, rsi_values, sma_values, grid_size, rsi_limit_bull, rsi_limit_bear, fee_rate=0.0006):
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
        sma = sma_values[i]
        new_grid_level = grid_levels[i]
        
        # BUY Logic
        if new_grid_level < prev_level:
            diff = prev_level - new_grid_level
            for _ in range(diff):
                is_bull = False
                if not np.isnan(sma) and price >= sma:
                    is_bull = True
                
                # トレンド判定による条件分岐
                if is_bull:
                    # 強気相場：条件を緩める（rsi_limit_bull）
                    if rsi < rsi_limit_bull:
                        positions.append(price)
                        buy_count += 1
                        total_fees += price * fee_rate
                else:
                    # 弱気相場：条件を厳しくする（rsi_limit_bear）
                    if rsi < rsi_limit_bear:
                        positions.append(price)
                        buy_count += 1
                        total_fees += price * fee_rate
                    
        # SELL Logic
        elif new_grid_level > prev_level:
            diff = new_grid_level - prev_level
            for _ in range(diff):
                if positions:
                    bought = positions.pop(0)
                    total_realized_profit += (price - bought)
                    total_fees += price * fee_rate
        
        prev_level = new_grid_level
        
        # Equity Tracking
        unrealized = sum(price - p for p in positions) if positions else 0
        current_equity = initial_equity + total_realized_profit - total_fees + unrealized
        
        if current_equity > peak_equity:
            peak_equity = current_equity
        
        dd = peak_equity - current_equity
        if dd > max_drawdown:
            max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p for p in positions) if positions else 0
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    
    return final_equity, max_drawdown, buy_count

# ==========================================
# 2. シミュレーション実行関数
# ==========================================
def run_simulation(df, strategy_type='normal'):
    # パラメータ設定
    # Normal: 常に厳しいRSI条件
    # Adaptive: SMA200の上なら緩いRSI、下なら厳しいRSI
    
    grid_size = 2000 # 日足なので少し広め（最適化値の平均的な値）
    
    if strategy_type == 'normal':
        rsi_bull = 40
        rsi_bear = 40
    else:
        rsi_bull = 70 # 強気相場ならRSI70以下（ほぼいつでも）買う
        rsi_bear = 30 # 弱気相場ならRSI30以下（超厳選）でしか買わない
    
    closes = df['close'].values
    rsis = df['rsi'].values
    smas = df['sma200'].values
    
    equity, dd, trades = run_adaptive_backtest(closes, rsis, smas, grid_size, rsi_bull, rsi_bear)
    
    return equity, dd, trades

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    if not os.path.exists(path):
        print("Data file not found.")
        return

    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    # 指標計算
    df['rsi'] = calculate_rsi(df['close'])
    df['sma200'] = df['close'].rolling(window=200).mean()
    
    # 2023年以降でテスト
    test_df = df[df.index >= '2023-01-01']
    
    print("\n--- Strategy Comparison (2023-2026) ---")
    print(f"{'Strategy':<20} | {'Return':<10} | {'MaxDD':<12} | {'Trades':<8}")
    print("-" * 65)
    
    # 1. Normal (Conservative)
    eq_norm, dd_norm, tr_norm = run_simulation(test_df, 'normal')
    ret_norm = (eq_norm - 1000000) / 1000000 * 100
    print(f"{'Conservative (RSI<40)':<20} | {ret_norm:>8.2f}% | {dd_norm:>11,.0f} | {tr_norm:>8}")
    
    # 2. Adaptive (Aggressive)
    eq_adap, dd_adap, tr_adap = run_simulation(test_df, 'adaptive')
    ret_adap = (eq_adap - 1000000) / 1000000 * 100
    print(f"{'Adaptive (SMA200)':<20} | {ret_adap:>8.2f}% | {dd_adap:>11,.0f} | {tr_adap:>8}")
    
    print("-" * 65)
    
    if ret_adap > ret_norm:
        print(f"Improvement: +{ret_adap - ret_norm:.2f}% Return")
        if tr_adap > tr_norm:
             print(f"Trade Frequency Increased: {tr_norm} -> {tr_adap} (+{(tr_adap/tr_norm - 1)*100:.0f}%)")
    else:
        print("Adaptive strategy underperformed.")

if __name__ == "__main__":
    main()
