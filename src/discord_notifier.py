import pandas as pd
import numpy as np
import logging
import time
import os
import threading
from datetime import datetime
import requests
import importlib.util
from pybit.unified_trading import HTTP

# ==============================================================================
# Dual Strategy Monitor: 15m RSI Compass & 5m Dead Pulse Hunter
# ==============================================================================

# --- Load Config ---
try:
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'config.py'))
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
except Exception as e:
    print(f"FATAL: Could not load configuration from {config_path}. Error: {e}")
    exit(1)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])

# --- API Session ---
session = HTTP(testnet=False, api_key=config.BYBIT_API_KEY, api_secret=config.BYBIT_API_SECRET)

def send_discord_notification(message):
    if not config.DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(config.DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        logging.error(f"Discord Error: {e}")

def fetch_candles(symbol, interval, limit=250):
    try:
        response = session.get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)
        if response['retCode'] == 0 and response['result']['list']:
            data = response['result']['list']
            data.reverse() # Oldest first
            candles = []
            for item in data:
                candles.append({
                    'timestamp': pd.to_datetime(int(item[0]), unit='ms', utc=True),
                    'open': float(item[1]),
                    'high': float(item[2]),
                    'low': float(item[3]),
                    'close': float(item[4]),
                    'volume': float(item[5])
                })
            return candles
    except Exception as e:
        logging.error(f"Bybit API Error ({interval}m): {e}")
    return None

# ==============================================================================
# STRATEGY 1: 15m RSI Compass (The 39% Runner)
# ==============================================================================
def monitor_15m_strategy():
    logging.info("Starting 15m RSI Compass Monitor...")
    last_processed_time = None
    symbol = config.SYMBOL

    while True:
        try:
            raw_candles = fetch_candles(symbol, "15", limit=250)
            if not raw_candles or len(raw_candles) < 205:
                time.sleep(30)
                continue

            df = pd.DataFrame(raw_candles)
            
            # Indicators
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['vol_mult'] = df['volume'] / df['volume_sma']
            df['sma_200'] = df['close'].rolling(window=200).mean()
            df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
            
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df['rsi'] = 100 - (100 / (1 + (gain / loss)))

            current_candle = df.iloc[-1]
            p1, p2, p3 = df.iloc[-2], df.iloc[-3], df.iloc[-4]

            if p1['timestamp'] != last_processed_time:
                last_processed_time = p1['timestamp']
                
                # Check for "Running Start"
                is_increasing_range = p1['range_pct'] > p2['range_pct'] > p3['range_pct']
                is_increasing_volume = p1['vol_mult'] > p2['vol_mult'] > p3['vol_mult']
                
                if is_increasing_range and is_increasing_volume:
                    entry_price = current_candle['open']
                    is_uptrend = entry_price > p1['sma_200']
                    is_downtrend = entry_price < p1['sma_200']
                    
                    signal = None
                    if is_uptrend and (p1['rsi'] >= 50 and p2['rsi'] >= 50 and p3['rsi'] >= 50):
                        signal = "BUY"
                    elif is_downtrend and (p1['rsi'] <= 47 and p2['rsi'] <= 47 and p3['rsi'] <= 47):
                        signal = "SELL"
                    
                    if signal:
                        msg = (
                               f"🚀 **【15分足・39%戦略】助走検知！**\n"
                               f"ターゲット: `{symbol}`\n"
                               f"方向: **{signal}** @ `{current_candle['open']:.4f}`\n"
                               f"理由: 3連続拡大 + RSI順張り + SMA200適合"
                        )
                        send_discord_notification(msg)
                        logging.info(f"15m Signal: {signal}")

            time.sleep(120)
        except Exception as e:
            logging.error(f"15m Loop Error: {e}")
            time.sleep(120)

# ==============================================================================
# STRATEGY 2: 5m Dead Pulse Hunter (The Sniper)
# ==============================================================================
def monitor_5m_strategy():
    logging.info("Starting 5m Dead Pulse Monitor...")
    silence_counter = 0
    last_processed_time = None
    symbol = config.SYMBOL
    
    SILENCE_THRESHOLD = 0.05 # 0.05% range
    SILENCE_DURATION = 3
    WAKEUP_TRIGGER = 0.2    # 0.2% breakout

    while True:
        try:
            raw_candles = fetch_candles(symbol, "5", limit=10)
            if not raw_candles or len(raw_candles) < 5:
                time.sleep(10)
                continue

            current_candle = raw_candles[-1]
            completed_candle = raw_candles[-2]

            # Track Silence on completed candles
            if completed_candle['timestamp'] != last_processed_time:
                last_processed_time = completed_candle['timestamp']
                comp_range = (completed_candle['high'] - completed_candle['low']) / completed_candle['open'] * 100
                
                if comp_range < SILENCE_THRESHOLD:
                    silence_counter += 1
                    logging.info(f"5m Silence Count: {silence_counter}")
                    if silence_counter == SILENCE_DURATION:
                        send_discord_notification(f"🤫 **【5分足】完全なる静寂...**\n`{symbol}` が息を止めています。ブレイクアウト待機。")
                else:
                    silence_counter = 0

            # Check for Awakening on current candle
            if silence_counter >= SILENCE_DURATION:
                curr_body = (current_candle['close'] - current_candle['open']) / current_candle['open'] * 100
                if abs(curr_body) >= WAKEUP_TRIGGER:
                    direction = "LONG" if curr_body > 0 else "SHORT"
                    msg = (
                           f"💀 **【5分足・スナイパー】静寂からの蘇生！**\n"
                           f"ターゲット: `{symbol}`\n"
                           f"アクション: **{direction}** @ `{current_candle['close']:.4f}`\n"
                           f"トリガー: `{curr_body:.2f}%` の急襲"
                    )
                    send_discord_notification(msg)
                    logging.info(f"5m Signal: {direction}")
                    silence_counter = 0 # Reset after signal

            time.sleep(30)
        except Exception as e:
            logging.error(f"5m Loop Error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    send_discord_notification("🤖 **バシャール・デュアルモニター起動**\n15分足(39%戦略) & 5分足(スナイパー) の同時監視を開始しました。")
    
    # Run both strategies in separate threads
    t1 = threading.Thread(target=monitor_15m_strategy)
    t2 = threading.Thread(target=monitor_5m_strategy)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()