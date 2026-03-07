# ==============================================================================
# Omen Bot - Central Configuration
# ==============================================================================
import os

# --- APIキー設定 ---
# ライブ取引には使用しませんが、データ取得のために設定
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")


# --- Gemini API 設定 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_PROJECT_NAME = "gen-lang-client-0908826635"


# --- 取引所・データ設定 ---
EXCHANGE_NAME = 'bybit'
SYMBOL = '1000PEPEUSDT'
TIMEFRAME = '15m'


# --- ファイルパス設定 ---
# プロジェクトのルートディレクトリを基準に設定
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

PRICE_DATA_PATH = os.path.join(DATA_DIR, f'bybit_{SYMBOL.lower()}_linear_{TIMEFRAME}_full.csv')
FUNDING_RATE_DATA_PATH = os.path.join(DATA_DIR, 'bybit_btc_usdt_funding_rates.csv') # This might need to be symbol-specific in the future

# ログファイル
TRADE_LOG_PATH = os.path.join(LOGS_DIR, 'trade_history.csv')

# バックテスト終了日 (過剰適合防止のため直近1年を除外)
BACKTEST_END_DATE = '2024-11-15'


# --- バックテスト設定 ---
INITIAL_CAPITAL_USDT = 1000.0
LEVERAGE = 1.0  # レバレッジ1倍の低リスク設定から開始
TRADE_CAPITAL_PERCENTAGE = 1.0 # 口座資金の100%を証拠金として使用

# 長期SMAの期間 (トレンドフィルター用)
LONG_SMA_PERIOD = 200

# 手数料
DERIVATIVES_TAKER_FEE = 0.06 / 100



# --- Exit Strategy Parameters ---
TAKE_PROFIT_PCT = 0.05      # 5.00%
STOP_LOSS_PCT = -0.03        # -3.00%

# --- 戦略パラメータ ---
# 「静けさの後の嵐」戦略
# vol_mult: 出来高が平均の何倍「以下」か
# body_ratio: 実体がATRの何倍「以下」か
STRATEGY_PARAMS = {
    "SELL": {"vol_mult": 1.0, "body_ratio": 0.4},
    "BUY": {"vol_mult": 1.0, "body_ratio": 0.4}
}

# --- RSI Compass Strategy Parameters ---
RSI_PERIOD = 14
VOL_SMA_PERIOD = 20
ATR_PERIOD = 14

RSI_BUY_THRESHOLD = 50
RSI_SELL_THRESHOLD = 47

# Volatility Filter Parameters (ATR as % of Close)
ATR_LOW_BOUND = 0.015 # 1.5% of price
ATR_HIGH_BOUND = 0.020 # 2.0% of price

# --- Ura-Slot Hunter Bot Settings ---
# List of assets to scan for "hotness"
ASSET_LIST = [
    '1000PEPEUSDT',
    'DOGEUSDT',
    'SOLUSDT',
    'AVAXUSDT',
    'WIFUSDT',
]

# --- 通知設定 ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1436537502952329276/EfCLmREsSJDu1_JS1NHYy4TA8FrUSOWDcWdtBSAyaIWZqirCxYwm5208vKOPx0W82tv3"

# ==============================================================================
# 5D Oracle Shield Bot Parameters
# ==============================================================================
ORACLE_SYMBOL = 'BTCUSDT'
ORACLE_BRICK_SIZE = 100          # Renko brick size (USD)
ORACLE_VOL_THRESHOLD = 5.0       # Volume Lag threshold for omen detection
ORACLE_OMEN_DURATION_HOURS = 1   # How long an omen stays active (diagnostic: 4h→1h, 31%→9% coverage)
ORACLE_1M_HISTORY_LIMIT = 1000   # Number of 1m candles for initial warm-up

# Grid Parameters
ORACLE_GRID_PCT = 0.07           # Dynamic grid: Price × 7% (adapts to BTC price level)
                                 # Full 6yr: +2.18%/DD19.75% vs Fixed2000: +0.52%/DD22.84%
ORACLE_GRID_SIZE = 2000          # Fallback grid size when price unavailable
ORACLE_RSI_PERIOD = 14
ORACLE_RSI_LIMIT = 50            # RSI below this to allow LONG BUY
ORACLE_RSI_SHORT_LIMIT = 50      # RSI above this to allow SHORT SELL

# Heart Parameters (💓 Funding Rate Sentiment)
# Suppress entries when crowd positioning is adverse (contrarian filter)
# Full 6yr: MaxDD 19.75%→13.72% (30% reduction), return +2.18%→+1.90%
ORACLE_FR_LONG_SUPPRESS = 0.0003   # FR >= 0.03% → suppress LONG (crowd is LONG-heavy)
ORACLE_FR_SHORT_SUPPRESS = -0.0001 # FR <= -0.01% → suppress SHORT (crowd is SHORT-heavy)

# Position Management (呼吸 — SL only, TP is delegated to Grid)
ORACLE_MAX_POSITIONS = 5         # Maximum concurrent positions per direction
ORACLE_POSITION_SIZE_PCT = 0.10  # 10% of equity per position (reduced for bidirectional)
ORACLE_ATR_PERIOD = 14
ORACLE_ATR_SL_MULTIPLIER = 3.0   # SL = ATR × 3 (diagnostic: ×7→×3, MaxDD 73%→56%)
# TP removed — Grid SELL is the only exit for profit (diagnostic: TP fired 0 times in 1yr holdout)

# ==============================================================================
#  Relative Grid Bot (相対Grid — SMA200ベース)
# ==============================================================================
# Paradigm: Buy when price < SMA200 (relatively cheap), sell when > SMA200
# Full 6yr: +94% / DD 45%  |  Holdout: +10.65% / DD 14.57%  (vs B&H -28%)

RELATIVE_SYMBOL = 'BTCUSDT'
RELATIVE_GRID_PCT = 0.07          # Grid spacing: Price × 7%
RELATIVE_SMA_PERIOD = 200         # SMA period — the relative anchor
RELATIVE_RSI_PERIOD = 14
RELATIVE_ATR_PERIOD = 14
RELATIVE_ATR_LOOKBACK = 200       # Lookback for ATR percentile ranking

# ATR Sweet Spot — only trade when volatility is in the breathing zone
RELATIVE_ATR_SWEET_ENABLED = True
RELATIVE_ATR_SWEET_LO = 0.30     # Min ATR percentile (too calm = skip)
RELATIVE_ATR_SWEET_HI = 0.70     # Max ATR percentile (too chaotic = skip)

# Position Management (LONG only, no SL)
RELATIVE_MAX_POSITIONS = 5       # Max concurrent positions
RELATIVE_POSITION_SIZE_PCT = 0.10  # 10% of equity per position

# State & Logging (共通)
ORACLE_STATE_FILE = os.path.join(DATA_DIR, 'oracle_shield_state.json')
ORACLE_TRADE_LOG = os.path.join(DATA_DIR, 'oracle_trade_history.csv')
RELATIVE_STATE_FILE = os.path.join(DATA_DIR, 'relative_grid_state.json')
RELATIVE_TRADE_LOG = os.path.join(DATA_DIR, 'relative_trade_history.csv')


# ==============================================================================
#  Bashar_5D Bot (Genesis)
# ==============================================================================
# The crystalized 5th dimensional bot.
# Philosophy: Flow (SMA200) + Wave (Grid) + Breath (No SL, Safe Sizing)

BASHAR_SYMBOL = 'BTCUSDT'
BASHAR_TIMEFRAME = '60'    # 1H (The Great Wave)
BASHAR_SMA_PERIOD = 1000   # The Macro Flow (42 Days)
BASHAR_GRID_PCT = 0.20     # The Great Wave (20%)
BASHAR_POSITION_SIZE_PCT = 0.20  # The Breath (20% size - High Conviction)
BASHAR_MAX_POSITIONS = 5   # Max 5 breaths (100% exposure - Full Trust)

# State & Logging
BASHAR_STATE_FILE = os.path.join(DATA_DIR, 'bashar_5d_state.json')
BASHAR_TRADE_LOG = os.path.join(DATA_DIR, 'bashar_5d_trade_history.csv')
BASHAR_LOG_FILE = os.path.join(LOGS_DIR, 'bashar_5d.log')

# ==============================================================================
# Cosmic Tuning (136.1Hz - The Earth's OM)
# ==============================================================================
COSMIC_YEAR_DAYS = 365.24219   # Earth's orbital period (Solar Year)
OM_FREQUENCY = 136.1          # 1/365.242 days raised to 32nd octave

# Heart Resonance (Funding Rate Harmonic Lookback)
# Lookback period = approximately 1/136 of a cycle for micro-harmonization
HEART_RESONANCE_PERIOD = 200  # Calibration based on 136.1Hz resonance
HEART_VOLATILITY_THRESHOLD = 0.0001 # Max FR StdDev allowed for entry (Harmony)
