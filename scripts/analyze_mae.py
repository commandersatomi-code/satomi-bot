import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

def calculate_indicators(df, atr_period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean().ffill().bfill()
    return atr

def analyze_mae(df, atr_multiplier):
    closes = df['close'].values
    atrs = df['atr'].values
    times = df.index
    
    # 破綻しないように、今回は損切りなしで全期間シミュレーションし、
    # 全ての「仮想エントリー」について、その後の挙動（最大含み損、利確可否）を追跡する。
    
    # Virtual Positions: {entry_price, entry_atr, max_loss_atr, closed, close_time}
    virtual_positions = []
    
    reference_high = closes[0]
    
    print("Simulating trades to collect MAE data...")
    
    # サンプリング数を減らすため、エントリー判定のみ行う
    # 決済ロジックはシミュレーションせず、エントリー後の未来を覗いて判定する（高速化）
    
    for i in range(1, len(closes) - 1000): # 最後の方は追跡できないので除外
        price = closes[i]
        current_atr = atrs[i]
        
        if price > reference_high: reference_high = price
            
        interval = current_atr * atr_multiplier
        entry_target = reference_high - interval
        
        # エントリー条件（簡易）：高値からATR分下がったら「仮想エントリー」
        # ただし、連続して入るとデータが重複しすぎるので、
        # 「最後の仮想エントリー」から一定以上離れたら次を入れる等の間引きが必要だが、
        # 今回は「全ての押し目」の質を見たいので、
        # 「前回エントリーより interval 下がったら」という条件で採取する。
        
        should_enter = False
        if len(virtual_positions) == 0:
            if price <= entry_target: should_enter = True
        else:
             if price <= virtual_positions[-1]['entry_price'] - interval: should_enter = True
        
        if should_enter:
            # 未来のデータをスキャンして、
            # 1. 利確（Entry + Interval）できるか？
            # 2. その前に最大でどれくらい掘る（含み損になる）か？
            
            entry_price = price
            tp_target = entry_price + interval
            max_loss_dist = 0
            is_winner = False
            
            # 未来のデータ（最大1000時間＝約40日後まで見る）
            future_prices = closes[i+1 : i+1001]
            
            for future_price in future_prices:
                # 含み損の深さ更新
                drawdown = entry_price - future_price
                if drawdown > max_loss_dist:
                    max_loss_dist = drawdown
                
                # 利確判定
                if future_price >= tp_target:
                    is_winner = True
                    break # 終了
            
            # 記録
            virtual_positions.append({
                'entry_price': entry_price,
                'entry_atr': current_atr,
                'max_loss_atr': max_loss_dist / current_atr, # ATR何倍分の含み損か
                'is_winner': is_winner
            })
            
    # 分析
    results = pd.DataFrame(virtual_positions)
    
    if len(results) == 0:
        print("No trades found.")
        return

    print(f"\nTotal Trades Analyzed: {len(results)}")
    
    # 勝ちトレードの最大含み損分布
    winners = results[results['is_winner'] == True]
    losers = results[results['is_winner'] == False]
    
    print(f"Winners: {len(winners)} ({len(winners)/len(results)*100:.1f}%)")
    print(f"Losers (Timed out > 1000h): {len(losers)} ({len(losers)/len(results)*100:.1f}%)")
    
    print("\n--- MAE Analysis (How deep did winners dive?) ---")
    # パーセンタイルで境界線を探る
    # 「95%の勝ちトレードは、含み損がATRのX倍以内に収まっていた」を知りたい
    
    percentiles = [50, 75, 90, 95, 98, 99]
    for p in percentiles:
        threshold = np.percentile(winners['max_loss_atr'], p)
        print(f"{p}% of winners survived MaxLoss < {threshold:.2f} x ATR")
        
    print("-" * 50)
    print("Insight: Setting SL beyond the 95% or 98% line might be the optimal stop loss.")

def main():
    path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['atr'] = calculate_indicators(df)
    
    # 過去5年
    test_df = df[df.index < '2025-01-25']
    
    print("\n--- Max Adverse Excursion (MAE) Analysis ---")
    # ATR 0.8倍のエントリー条件で調査
    analyze_mae(test_df, 0.8)

if __name__ == "__main__":
    main()
