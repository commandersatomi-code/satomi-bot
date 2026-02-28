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

def analyze_mfe(df, atr_multiplier):
    closes = df['close'].values
    atrs = df['atr'].values
    
    # Virtual Positions for MFE Analysis
    # MFE (Maximum Favorable Excursion) = エントリー後に最大でどれだけ含み益になったか
    
    last_entry_price = closes[0]
    mfe_data = [] # List of MFE ratios (multiple of ATR) 
    
    print("Simulating trades to collect MFE data...")
    
    # ATR 1.0倍のエントリー条件で調査
    # 今回は「損切りされる前（ATR 7倍の逆行前）に、最大どこまで伸びたか」を見る必要がある
    # なので、損切りラインも考慮する
    sl_threshold = 7.0 
    
    for i in range(1, len(closes) - 1000): 
        price = closes[i]
        current_atr = atrs[i]
        interval = current_atr * atr_multiplier
        
        if price > last_entry_price:
            last_entry_price = price
            continue
            
        if price <= last_entry_price - interval:
            entry_price = price
            sl_price = entry_price - (current_atr * sl_threshold)
            
            # 未来スキャン
            max_profit_dist = 0
            is_stopped_out = False
            
            future_prices = closes[i+1 : i+1001]
            
            for future_price in future_prices:
                # 損切りチェック
                if future_price <= sl_price:
                    is_stopped_out = True
                    # 損切りされるまでの間の最大含み益を記録する
                    break
                
                # 含み益更新
                profit = future_price - entry_price
                if profit > max_profit_dist:
                    max_profit_dist = profit
            
            # 損切りされたかどうかにかかわらず、「最大でどこまで伸びたか」を記録
            # ただし、損切りされる前にプラス圏に行かなかった場合は0
            if max_profit_dist > 0:
                mfe_data.append(max_profit_dist / current_atr)
            else:
                mfe_data.append(0)
            
            last_entry_price = entry_price
            
    # 分析
    if len(mfe_data) == 0:
        print("No trades found.")
        return

    print(f"\nTotal Trades Analyzed: {len(mfe_data)}")
    mfe_series = pd.Series(mfe_data)
    
    print("\n--- MFE Analysis (Potential Profit per Trade) ---")
    print("How far does price go up before hitting SL (7.0 ATR)?")
    
    percentiles = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    # MFEは「大きい方が良い」ので、上位X%がどこまで伸びたかを見る
    # 例：上位80%（＝ほとんどのトレード）は少なくともここまで伸びた、を知りたい場合は逆
    # "At least X% of trades reached this profit level" -> 100 - X percentile
    
    # 読みやすくするため、「少なくともX%のトレードが到達した利益幅」を表示
    for p in percentiles:
        threshold = np.percentile(mfe_series, 100 - p)
        print(f"At least {p}% of trades reached > {threshold:.2f} x ATR profit")
        
    print("-" * 50)
    print("Insight: If 50% trades reach > 3.0 ATR, setting TP=3.0 doubles efficiency.")

def main():
    path = 'data/bybit_btcusdt_linear_1h_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    df['atr'] = calculate_indicators(df)
    
    test_df = df[df.index < '2025-01-25']
    
    print("\n--- Max Favorable Excursion (MFE) Analysis ---")
    analyze_mfe(test_df, 1.0) # ATR 1.0 Entry

if __name__ == "__main__":
    main()
