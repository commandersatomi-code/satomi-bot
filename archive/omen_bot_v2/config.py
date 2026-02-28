# ==============================================================================
# Omen Bot V2 - Central Configuration
# ==============================================================================
import os

# --- APIキー設定 ---
# ライブ取引には使用しませんが、データ取得のために設定
BYBIT_API_KEY = "59pB2v2TDUpAZEuSX3"
BYBIT_API_SECRET = "ut6uiGKlJkCTqGE7pVJVkhXNJcYfktABILb1"


# --- 取引所・データ設定 ---
EXCHANGE_NAME = 'bybit'
SYMBOL = 'BTCUSDT'
TIMEFRAME = '15m'


# --- ファイルパス設定 ---
# v2ディレクトリの場所を基準に、親ディレクトリにあるomen_bot/dataを参照
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '..', '..', 'data')

PRICE_DATA_PATH = os.path.join(DATA_DIR, 'bybit_btc_usdt_linear_15m_full_cleaned.csv')
FUNDING_RATE_DATA_PATH = os.path.join(DATA_DIR, 'bybit_btc_usdt_funding_rates.csv')

# ログファイルはv2ディレクトリ内に保存
TRADE_LOG_PATH = os.path.join(BASE_DIR, 'trade_log_v2.csv')

# バックテスト終了日 (過剰適合防止のため直近1年を除外)
BACKTEST_END_DATE = '2024-11-15'


# --- バックテスト設定 ---
INITIAL_CAPITAL_USDT = 1000.0
LEVERAGE = 1.0  # レバレッジ1倍の低リスク設定から開始
TRADE_CAPITAL_PERCENTAGE = 1.0 # 口座資金の100%を証拠金として使用

# 新しい戦略パラメータ (賢者の道)
TAKE_PROFIT_PCT = 0.05      # 5.00%
STOP_LOSS_PCT = 0.03        # 3.00% (絶対値で指定)
PROFIT_LOCK_PCT = 0.01      # 1.00% (この利益に達したらSLを建値に移動するなど)

# 長期SMAの期間 (トレンドフィルター用)
LONG_SMA_PERIOD = 200

# 手数料
DERIVATIVES_TAKER_FEE = 0.06 / 100


# --- 戦略パラメータ ---
# 「静けさの後の嵐」戦略
# vol_mult: 出来高が平均の何倍「以下」か
# body_ratio: 実体がATRの何倍「以下」か
STRATEGY_PARAMS = {
    "SELL": {"vol_mult": 1.0, "body_ratio": 0.4},
    "BUY": {"vol_mult": 1.0, "body_ratio": 0.4}
}

# --- 通知設定 ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1436537502952329276/EfCLmREsSJDu1_JS1NHYy4TA8FrUSOWDcWdtBSAyaIWZqirCxYwm5208vKOPx0W82tv3"

