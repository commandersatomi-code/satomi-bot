import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def main():
    path = 'data/bybit_btc_usdt_linear_daily_full.csv'
    df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    # ATRとその比率（ATR%）を計算
    df['atr'] = calculate_atr(df)
    df['atr_pct'] = (df['atr'] / df['close']) * 100
    
    # 年ごとの平均ATR%を集計
    df['year'] = df.index.year
    yearly_stats = df.groupby('year')['atr_pct'].mean()
    
    print("\n--- Volatility Diagnosis (ATR %) ---")
    print(f"{ 'Year':<6} | { 'Avg Daily Move (%)':<20} | { 'Status'}")
    print("-" * 50)
    
    for year, val in yearly_stats.items():
        status = ""
        if val > 4.0: status = "Super Volatile (Paradise)"
        elif val > 3.0: status = "High Volatility"
        elif val > 2.0: status = "Normal"
        else: status = "Low Volatility (Desert)"
        
        print(f"{year:<6} | {val:>18.2f}% | {status}")
    
    print("-" * 50)
    
    # 直近の状況（月ごと）
    recent = df[df.index >= '2025-01-01']
    recent['month'] = recent.index.to_period('M')
    monthly_stats = recent.groupby('month')['atr_pct'].mean()
    
    print("\n--- Recent Monthly Trend (2025-2026) ---")
    for month, val in monthly_stats.items():
        print(f"{month} : {val:.2f}%")

if __name__ == "__main__":
    main()

