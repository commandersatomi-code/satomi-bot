"""
🌀 Bashar_5D — The Genesis Bot
==============================
The harmonization of Flow (SMA200) and Wave (Grid).
Simple, robust, and fearless.

Philosophy:
  - Timeframe: 1H (The Great Wave)
  - Axis: SMA1000 (Macro Trend)
  - Action: Grid 20% (Huge Waves)
  - Being: Trust the Process
  - Action: Relative Grid 7% (Wave)
  - Being: Long Only, No SL (Trust)

Logic:
  - Buy: Price < SMA200 && Price crossed down new grid level
  - Sell: Price > SMA200 && Price crossed up new grid level
  - No other filters. The structure itself is the filter.
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
from datetime import datetime, timezone
import requests
import importlib.util

# --- Load Config ---
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'config.py'))
spec = importlib.util.spec_from_file_location("config", config_path)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

# --- Logging ---
log_format = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format,
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler(config.BASHAR_LOG_FILE)])
logger = logging.getLogger('Bashar_5D')

# --- Bybit API ---
from pybit.unified_trading import HTTP
session = HTTP(testnet=False, api_key=config.BYBIT_API_KEY, api_secret=config.BYBIT_API_SECRET)


# ==============================================================================
#  Discord Notification
# ==============================================================================
def send_discord(message):
    try:
        requests.post(config.DISCORD_WEBHOOK_URL,
                      json={"content": message}, timeout=10)
    except Exception as e:
        logger.warning(f"Discord send failed: {e}")


# ==============================================================================
#  Trade Logger
# ==============================================================================
def log_trade(trade_info):
    fieldnames = ['timestamp', 'type', 'entry_price', 'exit_price',
                  'pnl_pct', 'pnl_amt', 'positions_held']
    filepath = config.BASHAR_TRADE_LOG
    file_exists = os.path.exists(filepath)
    with open(filepath, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': trade_info.get('type', ''),
            'entry_price': trade_info.get('entry_price', ''),
            'exit_price': trade_info.get('exit_price', ''),
            'pnl_pct': trade_info.get('pnl_pct', ''),
            'pnl_amt': trade_info.get('pnl_amt', ''),
            'positions_held': trade_info.get('positions_held', ''),
        })


# ==============================================================================
#  Shared State
# ==============================================================================
class BasharState:
    """Thread-safe state for Bashar_5D."""

    def __init__(self):
        self._lock = threading.Lock()
        self.positions = []
        self.last_grid_level = None
        self.current_price = 0.0
        self.current_sma200 = 0.0
        self.equity = config.INITIAL_CAPITAL_USDT
        self.total_realized_pnl = 0.0
        self.peak_equity = config.INITIAL_CAPITAL_USDT
        self.max_drawdown = 0.0
        self.trade_count = 0
        self.is_running = True

        self._load_state()

    def _load_state(self):
        if os.path.exists(config.BASHAR_STATE_FILE):
            try:
                with open(config.BASHAR_STATE_FILE, 'r') as f:
                    data = json.load(f)
                self.positions = data.get('positions', [])
                self.equity = data.get('equity', config.INITIAL_CAPITAL_USDT)
                self.total_realized_pnl = data.get('total_realized_pnl', 0.0)
                self.peak_equity = data.get('peak_equity', self.equity)
                self.max_drawdown = data.get('max_drawdown', 0.0)
                self.trade_count = data.get('trade_count', 0)
                self.last_grid_level = data.get('last_grid_level', None)
                logger.info(f"🔄 State restored: {len(self.positions)} positions, equity={self.equity:.2f}")
            except Exception as e:
                logger.error(f"State load error: {e}")

    def save_state(self):
        try:
            with self._lock:
                data = {
                    'positions': self.positions,
                    'equity': self.equity,
                    'total_realized_pnl': self.total_realized_pnl,
                    'peak_equity': self.peak_equity,
                    'max_drawdown': self.max_drawdown,
                    'trade_count': self.trade_count,
                    'last_grid_level': self.last_grid_level,
                }
            with open(config.BASHAR_STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"State save error: {e}")

    def get_total_value(self, price):
        with self._lock:
            pos_val = sum(p['size'] * (1 + (price - p['price']) / p['price'])
                          for p in self.positions)
            return self.equity + pos_val

    def add_position(self, price, size):
        with self._lock:
            pos = {
                'price': price,
                'size': size,
                'entry_time': datetime.now(timezone.utc).isoformat(),
            }
            self.positions.append(pos)
            self.equity -= size
            self.trade_count += 1
        self.save_state()
        return pos

    def close_position(self, idx, exit_price):
        with self._lock:
            if idx >= len(self.positions):
                return None
            pos = self.positions.pop(idx)
            entry_price = pos['price']
            size = pos['size']
            pnl_pct = (exit_price - entry_price) / entry_price
            pnl_amt = size * pnl_pct - (size * config.DERIVATIVES_TAKER_FEE * 2)
            self.equity += size + pnl_amt
            self.total_realized_pnl += pnl_amt

            # Drawdown update
            total_val = self.get_total_value(exit_price)
            if total_val > self.peak_equity:
                self.peak_equity = total_val
            dd = self.peak_equity - total_val
            if dd > self.max_drawdown:
                self.max_drawdown = dd
        self.save_state()
        return {
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct,
            'pnl_amt': pnl_amt,
            'entry_time': pos['entry_time']
        }


# ==============================================================================
#  Thread 1: The Engine
# ==============================================================================
def bashar_engine(state: BasharState, dry_run=False):
    logger.info("🌀 Bashar_5D Engine starting...")
    symbol = config.BASHAR_SYMBOL
    grid_pct = config.BASHAR_GRID_PCT
    log_base = np.log(1 + grid_pct)

    def calc_grid_level(price):
        return int(np.log(max(price, 1)) / log_base)

    while state.is_running:
        try:
            # 1. Fetch Data
            resp = session.get_kline(category='linear', symbol=symbol,
                                     interval=config.BASHAR_TIMEFRAME, limit=1000)
            if resp['retCode'] != 0:
                logger.error(f"Kline error: {resp['retMsg']}")
                time.sleep(60)
                continue

            klines = resp['result']['list']
            if len(klines) < 210:
                time.sleep(60)
                continue

            # 2. Parse & SMA200
            closes = [float(k[4]) for k in reversed(klines)]
            df = pd.DataFrame({'close': closes})
            df['sma200'] = df['close'].rolling(config.BASHAR_SMA_PERIOD).mean()

            price = df['close'].iloc[-1]
            sma = df['sma200'].iloc[-1]

            if np.isnan(sma):
                logger.warning("SMA200 not ready.")
                time.sleep(300)
                continue

            # Update State indicators
            state.current_price = price
            state.current_sma200 = sma

            # 3. Grid Logic
            current_grid = calc_grid_level(price)
            
            # Initialize if first run
            if state.last_grid_level is None:
                state.last_grid_level = current_grid
                pos_label = "📉 Cheap" if price < sma else "📈 Expensive"
                grid_spacing = price * grid_pct
                logger.info(f"Initialized: {price:,.0f} (SMA{sma:,.0f} {pos_label}) | Grid ~${grid_spacing:,.0f}")
                time.sleep(300)
                continue

            # --- BUY ZONE (Flow says Up, Price says Down) ---
            if current_grid < state.last_grid_level:
                levels = state.last_grid_level - current_grid
                
                # Condition: Price MUST be below SMA200 to buy
                if price < sma:
                    for _ in range(levels):
                        if len(state.positions) >= config.BASHAR_MAX_POSITIONS:
                            continue
                        
                        # Size: Fixed % of Total Value
                        total_val = state.get_total_value(price)
                        invest = total_val * config.BASHAR_POSITION_SIZE_PCT
                        
                        if state.equity < invest:
                            continue
                            
                        state.add_position(price, invest)
                        
                        dev = (price - sma) / sma * 100
                        msg = (f"🌀 **Bashar Buy**\n"
                               f"Price: `{price:,.0f}` (SMA `{sma:,.0f}` {dev:+.1f}%)\n"
                               f"Size: `{config.BASHAR_POSITION_SIZE_PCT*100:.0f}%`\n"
                               f"Held: {len(state.positions)}/{config.BASHAR_MAX_POSITIONS}")
                        send_discord(msg)
                        logger.info(f"💎 BUY @ {price:,.0f}")
                else:
                    logger.info(f"  Grid Down but Price > SMA200. Skipped.")

            # --- SELL ZONE (Price says Up, Flow says Up) ---
            elif current_grid > state.last_grid_level:
                levels = current_grid - state.last_grid_level
                
                # Condition: Price MUST be above SMA200 to sell
                if price > sma:
                    for _ in range(levels):
                        if len(state.positions) == 0:
                            continue
                        
                        # FIFO Exit
                        res = state.close_position(0, price)
                        if res:
                            emoji = "✅" if res['pnl_pct'] > 0 else "❌"
                            msg = (f"{emoji} **Bashar Sell**\n"
                                   f"Exit: `{price:,.0f}` (Entry `{res['entry_price']:,.0f}`)\n"
                                   f"PnL: `{res['pnl_pct']*100:+.2f}%` (`{res['pnl_amt']:+.0f}` USDT)\n"
                                   f"Held: {len(state.positions)}")
                            send_discord(msg)
                            log_trade({
                                'type': 'SELL',
                                'entry_price': res['entry_price'],
                                'exit_price': price,
                                'pnl_pct': res['pnl_pct'],
                                'pnl_amt': res['pnl_amt'],
                                'positions_held': len(state.positions)
                            })
                            logger.info(f"✅ SELL @ {price:,.0f} ({res['pnl_pct']*100:+.1f}%)")
                else:
                     logger.info(f"  Grid Up but Price < SMA200. Skipped.")

            state.last_grid_level = current_grid

            # Update Peak (for DD)
            tv = state.get_total_value(price)
            if tv > state.peak_equity:
                state.peak_equity = tv
            dd = state.peak_equity - tv
            if dd > state.max_drawdown:
                state.max_drawdown = dd

            time.sleep(300) # 5 min heartbeat

        except Exception as e:
            logger.error(f"Engine Error: {e}", exc_info=True)
            time.sleep(60)


# ==============================================================================
#  Thread 2: Reporter
# ==============================================================================
def status_reporter(state: BasharState):
    time.sleep(30)
    while state.is_running:
        try:
            price = state.current_price
            sma = state.current_sma200
            val = state.get_total_value(price)
            pos_n = len(state.positions)
            
            if sma > 0:
                rel = "📉 BELOW" if price < sma else "📈 ABOVE"
                dev = (price - sma) / sma * 100
            else:
                rel = "⏳"
                dev = 0
            
            unrealized = 0
            if pos_n > 0:
                unrealized = sum(p['size'] * ((price - p['price'])/p['price']) for p in state.positions)
            
            msg = (f"🔮 **Bashar_5D Status**\n"
                   f"```\n"
                   f"BTC: {price:,.0f} ({rel})\n"
                   f"SMA: {sma:,.0f} ({dev:+.1f}%)\n"
                   f"Val: {val:,.0f} USDT\n"
                   f"Unr: {unrealized:+.0f} USDT\n"
                   f"Pos: {pos_n}/{config.BASHAR_MAX_POSITIONS}\n"
                   f"DD : {state.max_drawdown:,.0f}\n"
                   f"```")
            send_discord(msg)
            time.sleep(3600 * 4) # Every 4 hours
        except Exception as e:
            logger.error(f"Reporter Error: {e}")
            time.sleep(60)


# ==============================================================================
#  Main
# ==============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    mode = "DRY RUN 🧪" if args.dry_run else "LIVE 🚀"
    
    state = BasharState()
    
    logger.info(f"Bashar_5D Initialized. Mode: {mode}")
    send_discord(f"🌀 **Bashar_5D Genesis** Started\nMode: `{mode}`\nEquity: `{state.equity:,.0f}`")
    
    threads = [
        threading.Thread(target=bashar_engine, args=(state, args.dry_run), daemon=True),
        threading.Thread(target=status_reporter, args=(state,), daemon=True)
    ]
    
    for t in threads: t.start()
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown...")
        state.is_running = False
        state.save_state()

if __name__ == '__main__':
    main()
