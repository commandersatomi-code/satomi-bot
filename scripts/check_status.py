import pandas as pd
import os

# Load BTC 1h data
df_1h = pd.read_csv('data/bybit_btc_usdt_linear_1h_full.csv')
df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'])
df_1h.sort_values('timestamp', inplace=True)

# Bashar 5D Check (SMA1000)
df_1h['sma1000'] = df_1h['close'].rolling(window=1000).mean()
latest = df_1h.iloc[-1]
current_price = latest['close']
sma1000 = latest['sma1000']
diff_pct = (current_price - sma1000) / sma1000 * 100 if pd.notna(sma1000) else 0

print(f"--- Bashar 5D (1H) Status ---")
print(f"Current Price: {current_price}")
print(f"SMA1000 (42d): {sma1000:.2f}")
print(f"Distance from Anchor: {diff_pct:.2f}%")
if pd.notna(sma1000):
    print(f"Grid Step (20%): {sma1000 * 0.2:.2f}")

# Oracle Shield (15m) Check
df_15m = pd.read_csv('data/bybit_btc_usdt_linear_15m_full.csv')
df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'])
latest_15m = df_15m.iloc[-1]
print(f"\n--- Oracle Shield (15M) Status ---")
print(f"Current Price: {latest_15m['close']}")
