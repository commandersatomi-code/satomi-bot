import pandas as pd
import numpy as np
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
    
    virtual_positions = []
    
    # 基準価格の管理を少し緩くする
    # 単純に「前回の仮想エントリー価格」から interval 下がったら次を入れる
    # 最初の基準は始値
    
    last_entry_price = closes[0]
    
    print("Simulating trades to collect MAE data...")
    
    for i in range(1, len(closes) - 1000): 
        price = closes[i]
        current_atr = atrs[i]
        interval = current_atr * atr_multiplier
        
        # もし価格が「最後の仮想エントリー」から Interval 分下がったら、そこは「押し目」の候補地
        # あるいは、価格が上がって last_entry_price を超えたら、基準を切り上げる（トレーリング）
        
        if price > last_entry_price:
            last_entry_price = price
            # ここではエントリーしない（高値更新中は待つ）
            continue
            
        if price <= last_entry_price - interval:
            # エントリー発生
            entry_price = price
            
            # 未来予知（検証）
            tp_target = entry_price + interval
            max_loss_dist = 0
            is_winner = False
            
            future_prices = closes[i+1 : i+1001] # 1000時間後まで
            
            for future_price in future_prices:
                drawdown = entry_price - future_price
                if drawdown > max_loss_dist:
                    max_loss_dist = drawdown
                
                if future_price >= tp_target:
                    is_winner = True
                    break
            
            virtual_positions.append({
                'max_loss_atr': max_loss_dist / current_atr,
                'is_winner': is_winner
            })
            
            # 次のエントリー基準をここに更新（ナンピンの起点）
            last_entry_price = entry_price
            
    # 分析
    results = pd.DataFrame(virtual_positions)
    
    if len(results) == 0:
        print("No trades found.")
        return

    print(f"\nTotal Trades Analyzed: {len(results)}")
    
    winners = results[results['is_winner'] == True]
    losers = results[results['is_winner'] == False]
    
    print(f"Winners: {len(winners)} ({len(winners)/len(results)*100:.1f}%)")
    print(f"Losers (Timed out): {len(losers)} ({len(losers)/len(results)*100:.1f}%)")
    
    print("\n--- MAE Analysis (Winners' Deepest Dive) ---")
    percentiles = [50, 75, 90, 95, 98, 99]
    for p in percentiles:
        threshold = np.percentile(winners['max_loss_atr'], p)
        print(f"{p}% of winners survived MaxLoss < {threshold:.2f} x ATR")
        
    print("-" * 50)

def main():
    path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['atr'] = calculate_indicators(df)
    
    test_df = df[df.index < '2025-01-25']
    
    print("\n--- Max Adverse Excursion (MAE) Analysis v2 ---")
    analyze_mae(test_df, 0.8)

if __name__ == "__main__":
    main()
