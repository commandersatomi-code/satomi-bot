"""
🌀 5D Oracle Shield Bot (Bidirectional + Heart)
=================================================
A living organism with 5 organs:
  - 🧠 Oracle Watcher (神経系) — senses Vol Lag omens on 1m Renko
  - 🦴 Grid Engine (骨格)     — dynamic Price×% bidirectional grid
  - 💓 Heart (心臓)           — Funding Rate sentiment filter
  - 🛡️ Position Manager (守護) — ATR SL guard for LONG & SHORT
  - 📊 Status Reporter        — periodic health check

Evolution log:
  - Oracle Duration: 4h→1h (coverage 31%→9%)
  - SL: ATR×7→ATR×3 (MaxDD 73%→56%)
  - TP: Removed (Grid handles profit-taking)
  - Direction: LONG-only → Bidirectional (Oracle-gated SHORT)
  - Grid: Fixed $2000 → Price×7% (return +0.52%→+2.18%)
  - Heart: FR suppress (MaxDD 19.75%→13.72%, 30% reduction)
  - Position size: 20%→10% per position

Phase 1: Signal notification via Discord (no live orders).
"""

import pandas as pd
import numpy as np
import logging
import time
import os
import sys
import json
import threading
import csv
from datetime import datetime, timezone, timedelta
import requests
import importlib.util
from collections import deque

# --- Load Config ---
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'config.py'))
spec = importlib.util.spec_from_file_location("config", config_path)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

# --- Load Renko Engine ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'engines')))
from renko_engine import RenkoChart

# --- Load Cosmic Tuner ---
from cosmic_tuner import get_cosmic_report

# --- Logging ---
log_format = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format,
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler(os.path.join(config.LOGS_DIR, 'oracle_shield.log'))])
logger = logging.getLogger('OracleShield')

# --- Bybit API ---
from pybit.unified_trading import HTTP
session = HTTP(testnet=False, api_key=config.BYBIT_API_KEY, api_secret=config.BYBIT_API_SECRET)


# ==============================================================================
#  Shared State (Thread-Safe)
# ==============================================================================
class OracleState:
    """Thread-safe shared state for the organism."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.omen_active = False
        self.omen_expires_at = None
        self.omen_vol_lag = 0.0
        self.long_positions = []     # List of dicts: {price, sl, size, entry_time, omen_time}
        self.short_positions = []    # List of dicts: {price, sl, size, entry_time, omen_time}
        self.last_grid_level = None
        self.current_price = 0.0
        self.current_atr = 0.0
        self.current_rsi = 50.0
        self.current_funding_rate = 0.0  # 💓 Heart: latest funding rate
        self.equity = config.INITIAL_CAPITAL_USDT
        self.total_realized_pnl = 0.0
        self.peak_equity = config.INITIAL_CAPITAL_USDT
        self.max_drawdown = 0.0
        self.trade_count = 0
        self.is_running = True
        
        # 💓 Heart: Funding Rate history for resonance analysis
        self.fr_history = deque(maxlen=getattr(config, 'HEART_RESONANCE_PERIOD', 200))
        
        # Load saved state if exists
        self._load_state()
    
    def _load_state(self):
        if os.path.exists(config.ORACLE_STATE_FILE):
            try:
                with open(config.ORACLE_STATE_FILE, 'r') as f:
                    data = json.load(f)
                self.long_positions = data.get('long_positions', data.get('positions', []))
                self.short_positions = data.get('short_positions', [])
                self.equity = data.get('equity', config.INITIAL_CAPITAL_USDT)
                self.total_realized_pnl = data.get('total_realized_pnl', 0.0)
                self.peak_equity = data.get('peak_equity', self.equity)
                self.max_drawdown = data.get('max_drawdown', 0.0)
                self.trade_count = data.get('trade_count', 0)
                self.last_grid_level = data.get('last_grid_level', None)
                n = len(self.long_positions) + len(self.short_positions)
                logger.info(f"🔄 State restored: {n} positions (L:{len(self.long_positions)} S:{len(self.short_positions)}), equity={self.equity:.2f}")
            except Exception as e:
                logger.warning(f"Could not load state: {e}. Starting fresh.")
    
    def save_state(self):
        with self._lock:
            data = {
                'long_positions': self.long_positions,
                'short_positions': self.short_positions,
                'equity': self.equity,
                'total_realized_pnl': self.total_realized_pnl,
                'peak_equity': self.peak_equity,
                'max_drawdown': self.max_drawdown,
                'trade_count': self.trade_count,
                'last_grid_level': self.last_grid_level,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        os.makedirs(os.path.dirname(config.ORACLE_STATE_FILE), exist_ok=True)
        with open(config.ORACLE_STATE_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def set_omen(self, vol_lag, duration_hours):
        with self._lock:
            self.omen_active = True
            self.omen_vol_lag = vol_lag
            self.omen_expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        logger.info(f"🔮 OMEN DETECTED! Vol Lag = {vol_lag:.2f}x (active for {duration_hours}h)")
    
    def check_omen(self):
        with self._lock:
            if not self.omen_active:
                return False
            if self.omen_expires_at and datetime.now(timezone.utc) > self.omen_expires_at:
                self.omen_active = False
                self.omen_vol_lag = 0.0
                logger.info("🔮 Omen expired.")
                return False
            return True
    
    def add_position(self, price, sl, size, direction='LONG', omen_time=None):
        with self._lock:
            pos = {
                'price': price,
                'sl': sl,
                'size': size,
                'direction': direction,
                'entry_time': datetime.now(timezone.utc).isoformat(),
                'omen_time': str(omen_time) if omen_time else None
            }
            if direction == 'LONG':
                self.long_positions.append(pos)
            else:
                self.short_positions.append(pos)
            self.equity -= size  # Move cash to position
            self.trade_count += 1
        self.save_state()
        return pos
    
    def close_position(self, idx, exit_price, exit_type, direction='LONG'):
        with self._lock:
            positions = self.long_positions if direction == 'LONG' else self.short_positions
            if idx >= len(positions):
                return None
            pos = positions.pop(idx)
            entry_price = pos['price']
            size = pos['size']
            if direction == 'LONG':
                pnl_pct = (exit_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - exit_price) / entry_price
            pnl_amt = size * pnl_pct - (size * config.DERIVATIVES_TAKER_FEE * 2)
            self.equity += size + pnl_amt
            self.total_realized_pnl += pnl_amt
            
            # Update drawdown
            total_value = self._calc_total_value_unsafe(exit_price)
            if total_value > self.peak_equity:
                self.peak_equity = total_value
            dd = self.peak_equity - total_value
            if dd > self.max_drawdown:
                self.max_drawdown = dd
        
        self.save_state()
        return {'entry_price': entry_price, 'exit_price': exit_price, 
                'pnl_pct': pnl_pct, 'pnl_amt': pnl_amt, 'type': exit_type,
                'direction': direction, 'entry_time': pos['entry_time']}
    
    def _calc_total_value_unsafe(self, current_price):
        """Must be called within lock."""
        float_long = sum(p['size'] * ((current_price - p['price']) / p['price'])
                         for p in self.long_positions)
        float_short = sum(p['size'] * ((p['price'] - current_price) / p['price'])
                          for p in self.short_positions)
        return self.equity + float_long + float_short
    
    def get_total_value(self, current_price):
        with self._lock:
            return self._calc_total_value_unsafe(current_price)

    def is_heart_harmonious(self):
        """💓 Heart: Check if funding rate volatility is within harmonic limits."""
        with self._lock:
            if len(self.fr_history) < self.fr_history.maxlen * 0.5:
                return True  # Not enough data yet, allow (warm-up)
            
            std = np.std(self.fr_history)
            threshold = getattr(config, 'HEART_VOLATILITY_THRESHOLD', 0.0001)
            is_harmonious = std < threshold
            if not is_harmonious:
                logger.debug(f"  💔 Disharmony detected: FR StdDev={std:.6f} > {threshold}")
            return is_harmonious


# ==============================================================================
#  Discord Notification
# ==============================================================================
def send_discord(message):
    if not config.DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(config.DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
    except Exception as e:
        logger.error(f"Discord error: {e}")


# ==============================================================================
#  Trade Logger
# ==============================================================================
def log_trade(trade_info):
    """Append trade to CSV log."""
    filepath = config.ORACLE_TRADE_LOG
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file_exists = os.path.exists(filepath)
    with open(filepath, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'exit_time', 'entry_time', 'entry_price', 'exit_price',
            'pnl_pct', 'pnl_amt', 'type'
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            'exit_time': datetime.now(timezone.utc).isoformat(),
            'entry_time': trade_info.get('entry_time', ''),
            'entry_price': f"{trade_info['entry_price']:.2f}",
            'exit_price': f"{trade_info['exit_price']:.2f}",
            'pnl_pct': f"{trade_info['pnl_pct']:.4f}",
            'pnl_amt': f"{trade_info['pnl_amt']:.2f}",
            'type': trade_info['type']
        })


# ==============================================================================
#  API Helpers
# ==============================================================================
def fetch_candles(symbol, interval, limit=200):
    """Fetch candles from Bybit."""
    try:
        response = session.get_kline(
            category="linear", symbol=symbol,
            interval=str(interval), limit=limit
        )
        if response['retCode'] == 0 and response['result']['list']:
            data = response['result']['list']
            data.reverse()  # Ascending order
            rows = []
            for item in data:
                rows.append({
                    'timestamp': pd.to_datetime(int(item[0]), unit='ms', utc=True),
                    'open': float(item[1]),
                    'high': float(item[2]),
                    'low': float(item[3]),
                    'close': float(item[4]),
                    'volume': float(item[5])
                })
            return pd.DataFrame(rows)
    except Exception as e:
        logger.error(f"API Error ({interval}): {e}")
    return None


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).fillna(50)


def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


# ==============================================================================
#  Thread 1: Oracle Watcher (神経系 - 感知)
# ==============================================================================
def oracle_watcher(state: OracleState, dry_run=False):
    """
    Continuously monitors 1m candles, builds Renko bricks,
    and detects Volume Lag omens.
    """
    logger.info("🧠 Oracle Watcher (神経系) starting...")
    symbol = config.ORACLE_SYMBOL
    
    # Warm up: Load initial history
    logger.info("  Warming up Renko Engine with historical 1m data...")
    renko = RenkoChart(brick_size=config.ORACLE_BRICK_SIZE)
    
    init_candles = fetch_candles(symbol, "1", limit=config.ORACLE_1M_HISTORY_LIMIT)
    if init_candles is not None and len(init_candles) > 0:
        renko.process_data(init_candles)
        logger.info(f"  Renko initialized with {len(renko.bricks)} bricks from {len(init_candles)} candles.")
    else:
        logger.error("  Failed to initialize Renko. Will retry...")
    
    last_processed_ts = None
    
    while state.is_running:
        try:
            candles = fetch_candles(symbol, "1", limit=5)
            if candles is None or len(candles) < 2:
                time.sleep(30)
                continue
            
            # Only process new candles
            latest_ts = candles['timestamp'].iloc[-2]  # Use completed candle
            if last_processed_ts is not None and latest_ts <= last_processed_ts:
                time.sleep(30)
                continue
            
            last_processed_ts = latest_ts
            
            # Process completed candles through Renko
            completed = candles.iloc[:-1]  # Exclude incomplete current candle
            new_bricks = renko.process_incremental(completed)
            
            if new_bricks:
                logger.info(f"  🧱 {len(new_bricks)} new brick(s) formed. Total: {len(renko.bricks)}")
            
            # Check for Omen
            vol_lag, omen_ts = renko.get_latest_vol_lag(window=14)
            
            if vol_lag >= config.ORACLE_VOL_THRESHOLD and not state.check_omen():
                state.set_omen(vol_lag, config.ORACLE_OMEN_DURATION_HOURS)
                msg = (f"🔮 **【Oracle Shield】前兆検知 (Omen Detected)**\n"
                       f"Vol Lag: **{vol_lag:.2f}x** (閾値: {config.ORACLE_VOL_THRESHOLD})\n"
                       f"有効期間: {config.ORACLE_OMEN_DURATION_HOURS}時間\n"
                       f"意味: エネルギーが蓄積されています。Grid Engineがエントリー可能になりました。")
                send_discord(msg)
            
            # Update current price for Position Manager
            state.current_price = float(candles.iloc[-1]['close'])
            
            time.sleep(60)  # Check every 60 seconds
            
        except Exception as e:
            logger.error(f"Oracle Watcher error: {e}")
            time.sleep(30)


# ==============================================================================
#  Funding Rate Fetcher (💓 Heart helper)
# ==============================================================================
def fetch_funding_rate(symbol='BTCUSDT'):
    """Fetch current funding rate from Bybit. Returns rate as float or 0."""
    try:
        result = session.get_tickers(category='linear', symbol=symbol)
        if result['retCode'] == 0:
            ticker = result['result']['list'][0]
            return float(ticker.get('fundingRate', 0))
    except Exception as e:
        logger.warning(f"  💓 FR fetch error: {e}")
    return 0.0


# ==============================================================================
#  Thread 2: Grid Engine (骨格 + 💓 Heart - 動的双方向)
# ==============================================================================
def grid_engine(state: OracleState, dry_run=False):
    """
    Bidirectional Harmony Grid with dynamic Price×% levels:
    - Grid level = floor(log(price) / log(1 + grid_pct))
    - Each level is exactly grid_pct apart (e.g., 7%)
    - Grid DOWN cross: Close SHORT (FIFO) + Open LONG (Oracle-gated, RSI<50)
    - Grid UP cross:   Close LONG (FIFO) + Open SHORT (Oracle-gated, RSI>50)
    """
    logger.info("🦴 Grid Engine (骨格 + 💓 Heart) starting...")
    symbol = config.ORACLE_SYMBOL
    grid_pct = config.ORACLE_GRID_PCT
    log_base = np.log(1 + grid_pct)  # Pre-compute log base
    rsi_buy_limit = config.ORACLE_RSI_LIMIT
    rsi_sell_limit = config.ORACLE_RSI_SHORT_LIMIT
    
    def calc_grid_level(price):
        """Logarithmic grid: each level is (1+pct) apart."""
        if price <= 0:
            return 0
        return int(np.log(price) / log_base)
    
    # Wait for Oracle to warm up
    time.sleep(10)
    
    while state.is_running:
        try:
            df = fetch_candles(symbol, "60", limit=200)
            if df is None or len(df) < 50:
                time.sleep(60)
                continue
            
            # Calculate indicators
            df['rsi'] = calculate_rsi(df['close'], config.ORACLE_RSI_PERIOD)
            df['atr'] = calculate_atr(df, config.ORACLE_ATR_PERIOD)
            
            latest = df.iloc[-2]  # Use completed candle
            price = float(latest['close'])
            rsi = float(latest['rsi'])
            atr = float(latest['atr'])
            
            state.current_price = price
            state.current_atr = atr
            state.current_rsi = rsi
            
            # 💓 Heart: Fetch Funding Rate & Update History
            fr = fetch_funding_rate(symbol)
            state.current_funding_rate = fr
            with state._lock:
                state.fr_history.append(fr)
            
            fr_pct = fr * 100
            
            # Heart resonance logic
            heart_harmonious = state.is_heart_harmonious()
            heart_allow_long = (fr < config.ORACLE_FR_LONG_SUPPRESS) and heart_harmonious
            heart_allow_short = (fr > config.ORACLE_FR_SHORT_SUPPRESS) and heart_harmonious
            
            if not heart_harmonious:
                logger.info(f"  💓 Heart: Disharmony (Arhythmic FR) - Entries suppressed.")
            elif not heart_allow_long:
                logger.info(f"  💓 Heart: LONG suppressed (FR={fr_pct:+.4f}% ≥ {config.ORACLE_FR_LONG_SUPPRESS*100:.2f}%)")
            elif not heart_allow_short:
                logger.info(f"  💓 Heart: SHORT suppressed (FR={fr_pct:+.4f}% ≤ {config.ORACLE_FR_SHORT_SUPPRESS*100:.2f}%)")
            
            # Dynamic Grid Level
            current_grid = calc_grid_level(price)
            grid_spacing = price * grid_pct
            
            if state.last_grid_level is None:
                state.last_grid_level = current_grid
                logger.info(f"  Grid initialized at level {current_grid} (price={price:.0f}, spacing≈{grid_spacing:.0f}, FR={fr_pct:+.4f}%)")
                time.sleep(300)
                continue
            
            # --- Grid DOWN: Close SHORT + Open LONG ---
            if current_grid < state.last_grid_level:
                levels_crossed = state.last_grid_level - current_grid
                
                # Close SHORT positions (FIFO — Grid Cover)
                for _ in range(levels_crossed):
                    if len(state.short_positions) > 0:
                        result = state.close_position(0, price, 'GRID_COVER', direction='SHORT')
                        if result:
                            emoji = "✅" if result['pnl_pct'] > 0 else "❌"
                            msg = (f"{emoji} **【Oracle Shield】SHORT決済 (GRID COVER)**\n"
                                   f"Entry: `{result['entry_price']:,.0f}` → Exit: `{price:,.0f}`\n"
                                   f"損益: `{result['pnl_pct']*100:+.2f}%` ({result['pnl_amt']:+,.0f} USDT)\n"
                                   f"残: L:{len(state.long_positions)} S:{len(state.short_positions)}")
                            send_discord(msg)
                            log_trade(result)
                            logger.info(f"  {emoji} COVER SHORT @ {price:,.0f} | PnL={result['pnl_pct']*100:+.2f}%")
                
                # Open LONG positions (Oracle + Heart gated)
                for _ in range(levels_crossed):
                    if not heart_allow_long:
                        continue
                    if rsi >= rsi_buy_limit:
                        continue
                    if not state.check_omen():
                        logger.info(f"  🛡️ BUY blocked: No omen.")
                        continue
                    if len(state.long_positions) >= config.ORACLE_MAX_POSITIONS:
                        continue
                    
                    total_value = state.get_total_value(price)
                    invest = total_value * config.ORACLE_POSITION_SIZE_PCT
                    if state.equity < invest:
                        continue
                    
                    sl = atr * config.ORACLE_ATR_SL_MULTIPLIER
                    pos = state.add_position(price, sl, invest, direction='LONG',
                                              omen_time=state.omen_expires_at)
                    
                    msg = (f"💎 **【Oracle Shield】LONG エントリー**\n"
                           f"価格: `{price:,.0f}` | SL: `{price - sl:,.0f}` (-{sl:,.0f})\n"
                           f"RSI: {rsi:.1f} | ATR: {atr:.0f}\n"
                           f"L:{len(state.long_positions)}/S:{len(state.short_positions)}")
                    send_discord(msg)
                    logger.info(f"  💎 LONG @ {price:,.0f} | SL={price-sl:,.0f}")
            
            # --- Grid UP: Close LONG + Open SHORT ---
            elif current_grid > state.last_grid_level:
                levels_crossed = current_grid - state.last_grid_level
                
                # Close LONG positions (FIFO — Grid Sell)
                for _ in range(levels_crossed):
                    if len(state.long_positions) > 0:
                        result = state.close_position(0, price, 'GRID_SELL', direction='LONG')
                        if result:
                            emoji = "✅" if result['pnl_pct'] > 0 else "❌"
                            msg = (f"{emoji} **【Oracle Shield】LONG決済 (GRID SELL)**\n"
                                   f"Entry: `{result['entry_price']:,.0f}` → Exit: `{price:,.0f}`\n"
                                   f"損益: `{result['pnl_pct']*100:+.2f}%` ({result['pnl_amt']:+,.0f} USDT)\n"
                                   f"残: L:{len(state.long_positions)} S:{len(state.short_positions)}")
                            send_discord(msg)
                            log_trade(result)
                            logger.info(f"  {emoji} SELL LONG @ {price:,.0f} | PnL={result['pnl_pct']*100:+.2f}%")
                
                # Open SHORT positions (Oracle + Heart gated)
                for _ in range(levels_crossed):
                    if not heart_allow_short:
                        continue
                    if rsi <= rsi_sell_limit:
                        continue
                    if not state.check_omen():
                        logger.info(f"  🛡️ SHORT blocked: No omen.")
                        continue
                    if len(state.short_positions) >= config.ORACLE_MAX_POSITIONS:
                        continue
                    
                    total_value = state.get_total_value(price)
                    invest = total_value * config.ORACLE_POSITION_SIZE_PCT
                    if state.equity < invest:
                        continue
                    
                    sl = atr * config.ORACLE_ATR_SL_MULTIPLIER
                    pos = state.add_position(price, sl, invest, direction='SHORT',
                                              omen_time=state.omen_expires_at)
                    
                    msg = (f"🔻 **【Oracle Shield】SHORT エントリー**\n"
                           f"価格: `{price:,.0f}` | SL: `{price + sl:,.0f}` (+{sl:,.0f})\n"
                           f"RSI: {rsi:.1f} | ATR: {atr:.0f}\n"
                           f"L:{len(state.long_positions)}/S:{len(state.short_positions)}")
                    send_discord(msg)
                    logger.info(f"  🔻 SHORT @ {price:,.0f} | SL={price+sl:,.0f}")
            
            state.last_grid_level = current_grid
            state.save_state()
            
            time.sleep(900)  # Check every 15 minutes
            
        except Exception as e:
            logger.error(f"Grid Engine error: {e}")
            time.sleep(60)


# ==============================================================================
#  Thread 3: Position Manager (守護 - SL Guard for LONG & SHORT)
# ==============================================================================
def position_manager(state: OracleState, dry_run=False):
    """
    Guardian: checks SL for both LONG and SHORT positions.
    - LONG SL: price drops below entry - SL
    - SHORT SL: price rises above entry + SL
    """
    logger.info("🛡️ Position Manager (守護 — 双方向) starting...")
    
    # Wait for other threads
    time.sleep(20)
    
    while state.is_running:
        try:
            price = state.current_price
            if price <= 0:
                time.sleep(10)
                continue
            
            # Check LONG positions for SL
            i = 0
            while i < len(state.long_positions):
                pos = state.long_positions[i]
                sl_price = pos['price'] - pos['sl']
                
                if price <= sl_price:
                    result = state.close_position(i, price, 'SL', direction='LONG')
                    if result:
                        msg = (f"🛑 **【Oracle Shield】LONG損切り (SL)**\n"
                               f"Entry: `{result['entry_price']:,.0f}` → Exit: `{price:,.0f}`\n"
                               f"損益: `{result['pnl_pct']*100:+.2f}%` ({result['pnl_amt']:+,.0f} USDT)\n"
                               f"🛡️ 守護：手放す。")
                        send_discord(msg)
                        log_trade(result)
                        logger.info(f"  🛑 LONG SL @ {price:,.0f} | PnL={result['pnl_pct']*100:+.2f}%")
                else:
                    i += 1
            
            # Check SHORT positions for SL
            i = 0
            while i < len(state.short_positions):
                pos = state.short_positions[i]
                sl_price = pos['price'] + pos['sl']  # SL is ABOVE for shorts
                
                if price >= sl_price:
                    result = state.close_position(i, price, 'SL', direction='SHORT')
                    if result:
                        msg = (f"🛑 **【Oracle Shield】SHORT損切り (SL)**\n"
                               f"Entry: `{result['entry_price']:,.0f}` → Exit: `{price:,.0f}`\n"
                               f"損益: `{result['pnl_pct']*100:+.2f}%` ({result['pnl_amt']:+,.0f} USDT)\n"
                               f"🛡️ 守護：手放す。")
                        send_discord(msg)
                        log_trade(result)
                        logger.info(f"  🛑 SHORT SL @ {price:,.0f} | PnL={result['pnl_pct']*100:+.2f}%")
                else:
                    i += 1
            
            # Periodic status log
            n_pos = len(state.long_positions) + len(state.short_positions)
            if n_pos > 0:
                total_val = state.get_total_value(price)
                logger.debug(f"  L:{len(state.long_positions)} S:{len(state.short_positions)} | Equity: {total_val:,.0f} | Price: {price:,.0f}")
            
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Position Manager error: {e}")
            time.sleep(10)


# ==============================================================================
#  Status Reporter
# ==============================================================================
def status_reporter(state: OracleState):
    """Periodic status report to Discord."""
    time.sleep(60)  # Wait for initialization
    
    while state.is_running:
        try:
            price = state.current_price
            total_val = state.get_total_value(price)
            omen_status = "🟢 Active" if state.check_omen() else "⚪ Dormant"
            n_long = len(state.long_positions)
            n_short = len(state.short_positions)
            
            # Heart status
            fr = state.current_funding_rate
            fr_pct = fr * 100
            heart_status = "💓" if (fr < config.ORACLE_FR_LONG_SUPPRESS and fr > config.ORACLE_FR_SHORT_SUPPRESS) else "💔"
            
            msg = (f"📊 **【Oracle Shield】定期レポート**\n"
                   f"```\n"
                   f"BTC価格:     {price:>12,.0f} USDT\n"
                   f"総資産:      {total_val:>12,.0f} USDT\n"
                   f"実現損益:    {state.total_realized_pnl:>+12,.0f} USDT\n"
                   f"最大DD:      {state.max_drawdown:>12,.0f} USDT\n"
                   f"LONG:        {n_long:>12}/{config.ORACLE_MAX_POSITIONS}\n"
                   f"SHORT:       {n_short:>12}/{config.ORACLE_MAX_POSITIONS}\n"
                   f"取引回数:    {state.trade_count:>12}\n"
                   f"Oracle:      {omen_status:>12}\n"
                   f"Heart:    {heart_status} FR={fr_pct:+.4f}%\n"
                   f"RSI:         {state.current_rsi:>12.1f}\n"
                   f"ATR:         {state.current_atr:>12.0f}\n"
                   f"----------------------------\n"
                   f"🌌 {get_cosmic_report()}\n"
                   f"```")
            send_discord(msg)
            
            time.sleep(3600)  # Report every hour
            
        except Exception as e:
            logger.error(f"Status reporter error: {e}")
            time.sleep(300)


# ==============================================================================
#  Main Entry Point
# ==============================================================================
def main(dry_run=False):
    mode = "DRY RUN" if dry_run else "LIVE SIGNAL"
    
    logger.info(f"""
    ╔══════════════════════════════════════════╗
    ║    🌀 5D Oracle Shield Bot               ║
    ║    Mode: {mode:<32}║
    ║    Symbol: {config.ORACLE_SYMBOL:<30}║
    ╚══════════════════════════════════════════╝
    """)
    
    # Initialize shared state
    state = OracleState()
    
    # Startup notification
    send_discord(
        f"🌀 **Oracle Shield Bot 起動 (5器官)**\n"
        f"モード: `{mode}`\n"
        f"シンボル: `{config.ORACLE_SYMBOL}`\n"
        f"初期資金: `{state.equity:,.0f}` USDT\n"
        f"🧠 Oracle: Vol Lag > {config.ORACLE_VOL_THRESHOLD} ({config.ORACLE_OMEN_DURATION_HOURS}h)\n"
        f"🦴 Grid: Price × {config.ORACLE_GRID_PCT*100:.0f}%\n"
        f"💓 Heart: L suppress ≥ {config.ORACLE_FR_LONG_SUPPRESS*100:.2f}% / S suppress ≤ {config.ORACLE_FR_SHORT_SUPPRESS*100:.2f}%\n"
        f"🛡️ SL: ATR × {config.ORACLE_ATR_SL_MULTIPLIER} | Size: {config.ORACLE_POSITION_SIZE_PCT*100:.0f}%"
    )
    
    # Create threads (organs of the organism)
    threads = [
        threading.Thread(target=oracle_watcher, args=(state, dry_run), name="OracleWatcher", daemon=True),
        threading.Thread(target=grid_engine, args=(state, dry_run), name="GridEngine", daemon=True),
        threading.Thread(target=position_manager, args=(state, dry_run), name="PositionManager", daemon=True),
        threading.Thread(target=status_reporter, args=(state,), name="StatusReporter", daemon=True),
    ]
    
    # Start all organs
    for t in threads:
        t.start()
        logger.info(f"  Started: {t.name}")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutdown signal received...")
        state.is_running = False
        state.save_state()
        send_discord("🛑 **Oracle Shield Bot 停止** — 状態を保存しました。")
        logger.info("State saved. Goodbye. 🌀")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='5D Oracle Shield Bot')
    parser.add_argument('--dry-run', action='store_true', help='Run in paper trading mode')
    args = parser.parse_args()
    
    main(dry_run=args.dry_run)
