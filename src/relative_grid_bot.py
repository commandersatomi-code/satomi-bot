"""
🌀 Relative Grid Bot — 相対的な取引
======================================
A living organism that breathes with the market's rhythm.

Philosophy:
  Absolute: "Buy at $70,000" → doesn't care if that's cheap or expensive
  Relative: "Buy when relatively cheap (below SMA200)" → always in context

Architecture:
  - Thread 1: Market Watcher — fetches 1H candles, computes SMA200/RSI/ATR
  - Thread 2: Relative Grid Engine — buy < SMA200, sell > SMA200
  - Thread 3: Status Reporter — periodic health check

Key design decisions:
  - LONG only (BTC is a trending asset)
  - No SL (relative grid positions recover; SL kills 60% of trades)
  - ATR sweet spot [30-70%] (WR 96.6% in holdout)
  - No Oracle gate (too restrictive — blocks 95% of opportunities)
  - RSI breathing (modulates position size, doesn't gate)

Performance:
  Full 6yr: +94.16% / DD 45.79%  vs  Buy & Hold: +931%
  Holdout:  +10.65% / DD 14.57%  vs  Buy & Hold: -28.1%

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

# --- Load Config ---
config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'config.py'))
spec = importlib.util.spec_from_file_location("config", config_path)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

# --- Logging ---
log_format = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format,
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler(os.path.join(config.LOGS_DIR, 'relative_grid.log'))])
logger = logging.getLogger('RelativeGrid')

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
    filepath = config.RELATIVE_TRADE_LOG
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
#  Shared State (Thread-Safe)
# ==============================================================================
class RelativeState:
    """Thread-safe shared state for the relative grid organism."""

    def __init__(self):
        self._lock = threading.Lock()
        self.positions = []          # List of dicts: {price, size, entry_time}
        self.last_grid_level = None
        self.current_price = 0.0
        self.current_sma200 = 0.0
        self.current_rsi = 50.0
        self.current_atr = 0.0
        self.current_atr_pct = 0.5   # ATR percentile rank (0-1)
        self.equity = config.INITIAL_CAPITAL_USDT
        self.total_realized_pnl = 0.0
        self.peak_equity = config.INITIAL_CAPITAL_USDT
        self.max_drawdown = 0.0
        self.trade_count = 0
        self.is_running = True

        self._load_state()

    def _load_state(self):
        if os.path.exists(config.RELATIVE_STATE_FILE):
            try:
                with open(config.RELATIVE_STATE_FILE, 'r') as f:
                    data = json.load(f)
                self.positions = data.get('positions', [])
                self.equity = data.get('equity', config.INITIAL_CAPITAL_USDT)
                self.total_realized_pnl = data.get('total_realized_pnl', 0.0)
                self.peak_equity = data.get('peak_equity', self.equity)
                self.max_drawdown = data.get('max_drawdown', 0.0)
                self.trade_count = data.get('trade_count', 0)
                self.last_grid_level = data.get('last_grid_level', None)
                n = len(self.positions)
                logger.info(f"🔄 State restored: {n} positions, equity={self.equity:.2f}")
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
            with open(config.RELATIVE_STATE_FILE, 'w') as f:
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

            # Track drawdown
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
            'entry_time': pos['entry_time'],
            'positions_held': len(self.positions),
        }


# ==============================================================================
#  Thread 1: Relative Grid Engine (相対Grid + 🫀 ATR Sweet Spot)
# ==============================================================================
def relative_grid_engine(state: RelativeState, dry_run=False):
    """
    Core engine: Buy below SMA200, Sell above SMA200.
    Grid structure provides timing discipline.
    ATR sweet spot provides breathing rhythm.
    """
    logger.info("🌀 Relative Grid Engine starting...")
    symbol = config.RELATIVE_SYMBOL
    grid_pct = config.RELATIVE_GRID_PCT
    log_base = np.log(1 + grid_pct)

    def calc_grid_level(price):
        return int(np.log(max(price, 1)) / log_base)

    # ATR history for percentile ranking
    atr_history = []

    while state.is_running:
        try:
            # Fetch 1H candles (need 200+ for SMA200)
            resp = session.get_kline(category='linear', symbol=symbol,
                                     interval='60', limit=300)
            if resp['retCode'] != 0:
                logger.error(f"Kline error: {resp['retMsg']}")
                time.sleep(60)
                continue

            klines = resp['result']['list']
            if len(klines) < 220:
                logger.warning(f"Not enough candles: {len(klines)}")
                time.sleep(60)
                continue

            # Parse and compute indicators
            rows = []
            for k in reversed(klines):  # Oldest first
                rows.append({
                    'open': float(k[1]), 'high': float(k[2]),
                    'low': float(k[3]), 'close': float(k[4]),
                })
            df = pd.DataFrame(rows)

            # SMA200
            df['sma200'] = df['close'].rolling(config.RELATIVE_SMA_PERIOD).mean()

            # RSI
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(config.RELATIVE_RSI_PERIOD).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(config.RELATIVE_RSI_PERIOD).mean()
            df['rsi'] = 100 - (100 / (1 + gain / loss))
            df['rsi'] = df['rsi'].fillna(50)

            # ATR
            prev_close = df['close'].shift(1)
            tr = pd.concat([
                df['high'] - df['low'],
                (df['high'] - prev_close).abs(),
                (df['low'] - prev_close).abs()
            ], axis=1).max(axis=1)
            df['atr'] = tr.rolling(config.RELATIVE_ATR_PERIOD).mean()

            # Latest values
            price = df['close'].iloc[-1]
            sma = df['sma200'].iloc[-1]
            rsi = df['rsi'].iloc[-1]
            atr = df['atr'].iloc[-1]

            if np.isnan(sma) or np.isnan(atr):
                logger.warning("Indicators not ready yet.")
                time.sleep(300)
                continue

            # ATR percentile (rolling history)
            atr_history.append(atr)
            if len(atr_history) > config.RELATIVE_ATR_LOOKBACK:
                atr_history = atr_history[-config.RELATIVE_ATR_LOOKBACK:]
            atr_pct = sum(1 for x in atr_history if x <= atr) / len(atr_history)

            # Update state
            state.current_price = price
            state.current_sma200 = sma
            state.current_rsi = rsi
            state.current_atr = atr
            state.current_atr_pct = atr_pct

            # Relative position
            below_ma = price < sma
            above_ma = price > sma
            deviation_pct = (price - sma) / sma * 100

            # ATR sweet spot check
            atr_ok = True
            if config.RELATIVE_ATR_SWEET_ENABLED:
                atr_ok = (atr_pct >= config.RELATIVE_ATR_SWEET_LO and
                          atr_pct <= config.RELATIVE_ATR_SWEET_HI)

            # Grid level
            current_grid = calc_grid_level(price)
            grid_spacing = price * grid_pct

            if state.last_grid_level is None:
                state.last_grid_level = current_grid
                pos_label = "📉 BELOW" if below_ma else "📈 ABOVE"
                logger.info(
                    f"  Grid initialized: level={current_grid}, "
                    f"price={price:,.0f}, SMA200={sma:,.0f} ({pos_label} {abs(deviation_pct):.1f}%), "
                    f"spacing≈{grid_spacing:,.0f}")
                time.sleep(300)
                continue

            # --- GRID DOWN: Buy opportunity (if below SMA200) ---
            if current_grid < state.last_grid_level:
                levels_crossed = state.last_grid_level - current_grid

                if below_ma and atr_ok:
                    for _ in range(levels_crossed):
                        if len(state.positions) >= config.RELATIVE_MAX_POSITIONS:
                            continue

                        # RSI breathing: lower RSI = larger position
                        rsi_breath = max(0.3, 1.0 + (50 - rsi) / 50)
                        eff_pp = np.clip(
                            config.RELATIVE_POSITION_SIZE_PCT * rsi_breath,
                            0.03, 0.25)

                        total_value = state.get_total_value(price)
                        invest = total_value * eff_pp
                        if state.equity < invest:
                            continue

                        pos = state.add_position(price, invest)

                        msg = (
                            f"💎 **【Relative Grid】Buy (below SMA200)**\n"
                            f"価格: `{price:,.0f}` | SMA200: `{sma:,.0f}` "
                            f"({deviation_pct:+.1f}%)\n"
                            f"RSI: {rsi:.1f} | ATR: {atr:.0f} "
                            f"(pct: {atr_pct:.0%})\n"
                            f"Size: {eff_pp*100:.1f}% ({invest:,.0f} USDT) | "
                            f"Positions: {len(state.positions)}/{config.RELATIVE_MAX_POSITIONS}")
                        send_discord(msg)
                        logger.info(
                            f"  💎 BUY @ {price:,.0f} | "
                            f"SMA200={sma:,.0f} ({deviation_pct:+.1f}%) | "
                            f"size={eff_pp*100:.1f}%")
                elif below_ma and not atr_ok:
                    logger.info(
                        f"  🫀 Buy skipped: ATR outside sweet spot "
                        f"({atr_pct:.0%} not in "
                        f"[{config.RELATIVE_ATR_SWEET_LO:.0%}-"
                        f"{config.RELATIVE_ATR_SWEET_HI:.0%}])")
                else:
                    logger.info(
                        f"  Grid DOWN but above SMA200 — no buy "
                        f"(price={price:,.0f} > sma={sma:,.0f})")

            # --- GRID UP: Sell opportunity (if above SMA200) ---
            elif current_grid > state.last_grid_level:
                levels_crossed = current_grid - state.last_grid_level

                if above_ma:
                    for _ in range(levels_crossed):
                        if len(state.positions) == 0:
                            continue

                        result = state.close_position(0, price)
                        if result:
                            emoji = "✅" if result['pnl_pct'] > 0 else "❌"
                            msg = (
                                f"{emoji} **【Relative Grid】Sell (above SMA200)**\n"
                                f"Entry: `{result['entry_price']:,.0f}` → "
                                f"Exit: `{price:,.0f}` | "
                                f"SMA200: `{sma:,.0f}`\n"
                                f"損益: `{result['pnl_pct']*100:+.2f}%` "
                                f"({result['pnl_amt']:+,.0f} USDT)\n"
                                f"残: {len(state.positions)} positions")
                            send_discord(msg)
                            log_trade({
                                'type': 'GRID_SELL',
                                'entry_price': result['entry_price'],
                                'exit_price': price,
                                'pnl_pct': f"{result['pnl_pct']*100:+.2f}",
                                'pnl_amt': f"{result['pnl_amt']:+.0f}",
                                'positions_held': len(state.positions),
                            })
                            logger.info(
                                f"  {emoji} SELL @ {price:,.0f} | "
                                f"PnL={result['pnl_pct']*100:+.2f}%")
                else:
                    logger.info(
                        f"  Grid UP but below SMA200 — no sell "
                        f"(price={price:,.0f} < sma={sma:,.0f})")

            # Update grid level
            state.last_grid_level = current_grid

            # Update peak equity and drawdown
            total_val = state.get_total_value(price)
            if total_val > state.peak_equity:
                state.peak_equity = total_val
            dd = state.peak_equity - total_val
            if dd > state.max_drawdown:
                state.max_drawdown = dd

            time.sleep(300)  # Check every 5 minutes

        except Exception as e:
            logger.error(f"Grid Engine error: {e}", exc_info=True)
            time.sleep(30)


# ==============================================================================
#  Thread 2: Status Reporter
# ==============================================================================
def status_reporter(state: RelativeState):
    """Periodic status report to Discord."""
    time.sleep(60)  # Wait for initialization

    while state.is_running:
        try:
            price = state.current_price
            sma = state.current_sma200
            total_val = state.get_total_value(price)
            n_pos = len(state.positions)

            if sma > 0:
                dev_pct = (price - sma) / sma * 100
                pos_label = "📉 BELOW" if price < sma else "📈 ABOVE"
            else:
                dev_pct = 0
                pos_label = "⏳"

            # ATR sweet spot status
            atr_pct = state.current_atr_pct
            if config.RELATIVE_ATR_SWEET_ENABLED:
                in_sweet = (atr_pct >= config.RELATIVE_ATR_SWEET_LO and
                            atr_pct <= config.RELATIVE_ATR_SWEET_HI)
                atr_status = "🫀 Sweet" if in_sweet else "💤 Outside"
            else:
                atr_status = "—"

            # Unrealized PnL
            unrealized = 0
            if n_pos > 0:
                unrealized = sum(
                    p['size'] * ((price - p['price']) / p['price'])
                    for p in state.positions)

            msg = (
                f"📊 **【Relative Grid】定期レポート**\n"
                f"```\n"
                f"BTC価格:     {price:>12,.0f} USDT\n"
                f"SMA200:      {sma:>12,.0f} USDT\n"
                f"乖離:     {pos_label} {abs(dev_pct):>6.1f}%\n"
                f"総資産:      {total_val:>12,.0f} USDT\n"
                f"実現損益:    {state.total_realized_pnl:>+12,.0f} USDT\n"
                f"含み損益:    {unrealized:>+12,.0f} USDT\n"
                f"最大DD:      {state.max_drawdown:>12,.0f} USDT\n"
                f"Positions:   {n_pos:>12}/{config.RELATIVE_MAX_POSITIONS}\n"
                f"取引回数:    {state.trade_count:>12}\n"
                f"ATR:      {atr_status} ({atr_pct:.0%})\n"
                f"RSI:         {state.current_rsi:>12.1f}\n"
                f"```")
            send_discord(msg)

            time.sleep(config.STATUS_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Status Reporter error: {e}")
            time.sleep(60)


# ==============================================================================
#  Main
# ==============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Relative Grid Bot')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without placing real orders')
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "LIVE"

    logger.info(f"""
    ╔══════════════════════════════════════════╗
    ║    🌀 Relative Grid Bot                  ║
    ║    Mode: {mode:<33}║
    ║    Symbol: {config.RELATIVE_SYMBOL:<31}║
    ╚══════════════════════════════════════════╝
    """)

    state = RelativeState()

    # Startup notification
    send_discord(
        f"🌀 **Relative Grid Bot 起動**\n"
        f"モード: `{mode}`\n"
        f"シンボル: `{config.RELATIVE_SYMBOL}`\n"
        f"初期資金: `{state.equity:,.0f}` USDT\n"
        f"📐 Grid: Price × {config.RELATIVE_GRID_PCT*100:.0f}%\n"
        f"📊 Anchor: SMA{config.RELATIVE_SMA_PERIOD}\n"
        f"🫀 ATR sweet: [{config.RELATIVE_ATR_SWEET_LO:.0%}-"
        f"{config.RELATIVE_ATR_SWEET_HI:.0%}]\n"
        f"📦 Size: {config.RELATIVE_POSITION_SIZE_PCT*100:.0f}% × "
        f"Max {config.RELATIVE_MAX_POSITIONS}"
    )

    # Create threads
    threads = [
        threading.Thread(target=relative_grid_engine,
                         args=(state, args.dry_run),
                         name="RelativeGrid", daemon=True),
        threading.Thread(target=status_reporter,
                         args=(state,),
                         name="StatusReporter", daemon=True),
    ]

    for t in threads:
        t.start()
        logger.info(f"  Started: {t.name}")

    # Main loop
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutdown signal received...")
        state.is_running = False
        time.sleep(2)
        state.save_state()
        logger.info("State saved. Goodbye. 🌀")


if __name__ == '__main__':
    main()
