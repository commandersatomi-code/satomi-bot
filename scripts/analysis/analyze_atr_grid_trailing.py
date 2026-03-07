import pandas as pd
import numpy as np
import os

def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr.ffill().bfill() # fillna method fix

def run_trailing_atr_grid(df, atr_multiplier):
    closes = df['close'].values
    atrs = df['atr'].values
    
    initial_equity = 1000000 
    positions_detailed = []
    
    total_realized_profit = 0
    total_fees = 0
    fee_rate = 0.0006
    
    max_drawdown = 0
    peak_equity = initial_equity
    trade_count = 0
    
    # トレーリング用の基準価格（最初は始値）
    reference_high = closes[0]
    
    for i in range(1, len(closes)):
        price = closes[i]
        current_atr = atrs[i]
        
        # 0. 基準価格（最高値）の更新
        # ポジションを持っていてもいなくても、高値は更新していく
        # ただし、ポジションを持った直後に基準を上げすぎると、ナンピン幅が狭くなる問題がある。
        # ここでは「最後の買い価格」とは別に「相場の高値」を追跡する。
        
        if price > reference_high:
            reference_high = price
            
        # 1. 買い判定
        # 「基準高値」から ATR*Multi 分下がったら買う
        # ただし、すでに持っている場合は、さらにそこから下がったら買う（ナンピン）
        
        # 最初の1発目：高値からの押し目
        first_entry_target = reference_high - (current_atr * atr_multiplier)
        
        should_buy = False
        buy_price = price
        target_profit = current_atr * atr_multiplier # 利確幅も動的
        
        if len(positions_detailed) == 0:
            if price <= first_entry_target:
                should_buy = True
        else:
            # 2発目以降（ナンピン）：最後の取得単価から ATR*Multi 下がったら
            last_buy_price = positions_detailed[-1]['price']
            next_entry_target = last_buy_price - (current_atr * atr_multiplier)
            
            if price <= next_entry_target:
                should_buy = True
        
        if should_buy:
            positions_detailed.append({'price': buy_price, 'target_profit': target_profit})
            trade_count += 1
            total_fees += buy_price * fee_rate
            
            # 買ったので、基準高値が遠すぎる場合はリセットするか？
            # いや、ナンピンロジックに移行するのでそのままでOK
            
        # 2. 売り判定
        remaining_positions = []
        for pos in positions_detailed:
            buy_p = pos['price']
            target = pos['target_profit']
            sell_target = buy_p + target
            
            if price >= sell_target:
                profit = price - buy_p
                total_realized_profit += profit
                total_fees += price * fee_rate
            else:
                remaining_positions.append(pos)
        
        positions_detailed = remaining_positions
        
        # ノーポジになったら基準高値を現在価格付近（またはその時の高値）に再セットする必要があるか？
        # 上昇トレンド復帰なら reference_high は自然に上がっているはず。
        # 急落後の反発で全決済した場合、reference_high はまだ遥か上の可能性がある。
        # その場合、次のエントリーが遠くなる。
        # -> ノーポジになったら、reference_high を現在価格（または直近の動き）にリセットすべき。
        
        if len(positions_detailed) == 0 and len(remaining_positions) < len(positions_detailed):
             # 全決済直後
             reference_high = price 
             # もしpriceが下がっているなら、ここからまた高値更新を待つか、
             # すぐにまた下がり始めたら入るか。
             # シンプルに「現在価格」にリセット。
        
        # Equity Update
        unrealized = sum(price - p['price'] for p in positions_detailed)
        current_equity = initial_equity + total_realized_profit - total_fees + unrealized
        
        if current_equity > peak_equity: peak_equity = current_equity
        dd = peak_equity - current_equity
        if dd > max_drawdown: max_drawdown = dd
            
    final_unrealized = sum(closes[-1] - p['price'] for p in positions_detailed)
    final_equity = initial_equity + total_realized_profit - total_fees + final_unrealized
    
    return final_equity, max_drawdown, trade_count

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    df['atr'] = calculate_atr(df)
    
    split_date = df.index[-1] - pd.Timedelta(days=365)
    analysis_df = df[df.index < split_date]
    
    multipliers = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0]
    
    print(f"\n--- Trailing ATR Grid Analysis ---")
    print(f"Period: {analysis_df.index[0].date()} to {analysis_df.index[-1].date()}")
    print(f"{ 'ATR Mult':<8} | {'Return':<10} | {'MaxDD':<12} | {'Trades':<8} | {'DD/Ret Ratio':<12}")
    print("-" * 65)
    
    for m in multipliers:
        final, dd, trades = run_trailing_atr_grid(analysis_df, m)
        ret_pct = (final - 1000000) / 1000000 * 100
        ratio = dd / (final - 1000000) if final > 1000000 else 9.99
        
        print(f"{m:<8} | {ret_pct:>8.2f}% | {dd:>11,.0f} | {trades:>8} | {ratio:>11.2f}")
    
    print("-" * 65)

if __name__ == "__main__":
    main()
