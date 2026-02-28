import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# 1. データの準備（市場の呼吸をシミュレート）
# ==========================================
# ※実際はここに取引所からBTCのデータを読み込みます
# 今回はテスト用に「波打つ相場」を人工的に作ります
np.random.seed(42)
periods = 200
base_price = 1000000 # 100万円スタート
# 緩やかな波（トレンド） + ランダムなノイズ（日々の値動き）
price_data = base_price + (np.sin(np.linspace(0, 10, periods)) * 20000) + np.random.normal(0, 5000, periods)

df = pd.DataFrame(price_data, columns=['Close'])

# ==========================================
# 2. ロジックの実装（ここがBotの「脳」です）
# ==========================================

# パラメータ設定（石川さまの「心の余裕」係数）
WINDOW = 20      # 過去20時間の平均を見る
SIGMA = 2.0      # 標準偏差の2倍（95%の確率で収まる範囲）

# ボリンジャーバンドの計算
df['MA'] = df['Close'].rolling(window=WINDOW).mean()           # 中心線（調和のライン）
df['Std'] = df['Close'].rolling(window=WINDOW).std()           # 変動幅
df['Upper'] = df['MA'] + (df['Std'] * SIGMA)                   # 上限（強欲の限界）
df['Lower'] = df['MA'] - (df['Std'] * SIGMA)                   # 下限（恐怖の限界）

# シグナルの判定（0:なし, 1:買い, -1:売り, 2:決済）
signals = []
position = 0 # 0:ノーポジ, 1:ロング中, -1:ショート中

for i in range(len(df)):
    close = df['Close'].iloc[i]
    upper = df['Upper'].iloc[i]
    lower = df['Lower'].iloc[i]
    ma = df['MA'].iloc[i]

    # バンドが計算できるまでは何もしない
    if pd.isna(upper):
        signals.append(0)
        continue

    # --- ここからが『Harmony』の哲学 ---

    # 【買い】: 恐怖で行き過ぎた（下限ブレイク）時、優しく拾う
    if position == 0 and close < lower:
        signals.append(1) # Buy Signal
        position = 1

    # 【売り】: 強欲で行き過ぎた（上限ブレイク）時、譲ってあげる
    elif position == 0 and close > upper:
        signals.append(-1) # Sell Signal
        position = -1

    # 【決済（ロング用）】: 調和（中心）に戻ったら感謝して手放す
    elif position == 1 and close >= ma:
        signals.append(2) # Exit Signal
        position = 0

    # 【決済（ショート用）】: 調和（中心）に戻ったら感謝して手放す
    elif position == -1 and close <= ma:
        signals.append(2) # Exit Signal
        position = 0

    # 何もしない（静観）
    else:
        signals.append(0)

df['Signal'] = signals

# ==========================================
# 3. 可視化（アートとして眺める）
# ==========================================
plt.figure(figsize=(12, 6))
plt.plot(df.index, df['Close'], label='BTC Price', color='gray', alpha=0.5)
plt.plot(df.index, df['Upper'], label='Upper Band (+2σ)', color='green', linestyle='--', alpha=0.3)
plt.plot(df.index, df['Lower'], label='Lower Band (-2σ)', color='green', linestyle='--', alpha=0.3)
plt.plot(df.index, df['MA'], label='Center Line (Harmony)', color='orange', alpha=0.8)

# 売買ポイントをプロット
# ▲ = 買い（優しく拾う）
buy_points = df[df['Signal'] == 1]
plt.scatter(buy_points.index, buy_points['Close'], marker='^', color='red', s=100, label='Buy (Support)')

# ▼ = 売り（譲る）
sell_points = df[df['Signal'] == -1]
plt.scatter(sell_points.index, sell_points['Close'], marker='v', color='blue', s=100, label='Sell (Share)')

# × = 決済（調和への帰還）
exit_points = df[df['Signal'] == 2]
plt.scatter(exit_points.index, exit_points['Close'], marker='x', color='black', s=50, label='Exit (Harmony)')

plt.title("Project 'Harmony' - Logic Test")
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()