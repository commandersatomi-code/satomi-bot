import time
import logging
import traceback
import pandas as pd
import numpy as np
from pybit.unified_trading import HTTP
import config
import requests
import discord_config
import os

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
HOURLY_LOG_FILE = 'hourly_data_log.csv'
CSV_HEADER = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'atr', 'volume_sma']

# ==============================================================================
# 2. STRATEGY PARAMETERS
# ==============================================================================

STRATEGY_PARAMS = {
    "SELL": {
        "HighestQuality": {"vol_mult": 1.6, "body_ratio": 0.6},
        "Balanced":       {"vol_mult": 1.6, "body_ratio": 0.6},
        "Action":         {"vol_mult": 1.6, "body_ratio": 0.6}
    },
    "BUY": {
        "HighestQuality": {"vol_mult": 1.4, "body_ratio": 0.6},
        "Balanced":       {"vol_mult": 1.4, "body_ratio": 0.6},
        "Action":         {"vol_mult": 1.4, "body_ratio": 0.6}
    }
}

# ==============================================================================
# 3. CORE BOT LOGIC
# ==============================================================================

def send_discord_notification(message):
    """Sends a notification to the configured Discord webhook."""
    try:
        payload = {"content": message}
        response = requests.post(discord_config.WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            logging.info("Successfully sent Discord notification.")
        else:
            logging.warning(f"Failed to send Discord notification. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while sending Discord notification: {e}")

def calculate_indicators(df, atr_period=14, vol_sma_period=20):
    df['high_low'] = df['high'] - df['low']
    df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
    df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
    df['atr'] = df['true_range'].ewm(span=atr_period, adjust=False).mean()
    df['volume_sma'] = df['volume'].rolling(window=vol_sma_period).mean()
    return df

def log_data_to_csv(candle_data):
    """Appends the given candle data to the hourly log CSV file."""
    try:
        log_data = {
            'timestamp': candle_data.name,
            'open': candle_data['open'],
            'high': candle_data['high'],
            'low': candle_data['low'],
            'close': candle_data['close'],
            'volume': candle_data['volume'],
            'atr': candle_data['atr'],
            'volume_sma': candle_data['volume_sma']
        }
        
        file_exists = os.path.isfile(HOURLY_LOG_FILE)
        
        # Use pandas to easily write to CSV
        df_to_log = pd.DataFrame([log_data])
        df_to_log.to_csv(HOURLY_LOG_FILE, mode='a', header=not file_exists, index=False, columns=CSV_HEADER)
        
        logging.info(f"Successfully logged data for candle to {HOURLY_LOG_FILE}: {candle_data.name}")

    except Exception as e:
        logging.error(f"Failed to log data to CSV: {e}")


def check_for_signals(df):
    """Checks the latest candle for any of the 6 defined signals and prints an alert."""
    latest_candle = df.iloc[-1]
    signal_detected = False

    # --- Check for SELL signals (in order of quality) ---
    for quality, params in STRATEGY_PARAMS["SELL"].items():
        is_high_volume = latest_candle['volume'] > (latest_candle['volume_sma'] * params["vol_mult"])
        is_bullish_candle = latest_candle['close'] > latest_candle['open']
        candle_body_size = latest_candle['close'] - latest_candle['open']
        is_small_body = candle_body_size < (latest_candle['atr'] * params["body_ratio"])
        
        if is_high_volume and is_bullish_candle and is_small_body:
            signal_message = f"【MANUAL TRADE ALERT: SELL】\nQuality: {quality}\nPrice: {latest_candle['close']}\nTime: {latest_candle.name}"
            print("\n" + "="*50)
            print(signal_message)
            print("="*50 + "\n")
            logging.info(f"SELL Signal ({quality}) detected on candle {latest_candle.name}")
            send_discord_notification(f"```\n{signal_message}\n```")
            signal_detected = True
            break # Stop after the first (highest quality) signal is found

    # --- Check for BUY signals (in order of quality) ---
    if not signal_detected:
        for quality, params in STRATEGY_PARAMS["BUY"].items():
            is_high_volume = latest_candle['volume'] > (latest_candle['volume_sma'] * params["vol_mult"])
            is_bearish_candle = latest_candle['close'] < latest_candle['open']
            candle_body_size = abs(latest_candle['close'] - latest_candle['open'])
            is_small_body = candle_body_size < (latest_candle['atr'] * params["body_ratio"])

            if is_high_volume and is_bearish_candle and is_small_body:
                signal_message = f"【MANUAL TRADE ALERT: BUY】\nQuality: {quality}\nPrice: {latest_candle['close']}\nTime: {latest_candle.name}"
                print("\n" + "="*50)
                print(signal_message)
                print("="*50 + "\n")
                logging.info(f"BUY Signal ({quality}) detected on candle {latest_candle.name}")
                send_discord_notification(f"```\n{signal_message}\n```")
                break # Stop after the first (highest quality) signal is found
    
    # --- Log the data regardless of signal ---
    log_data_to_csv(latest_candle)


# ==============================================================================
# 4. MAIN EXECUTION LOOP
# ==============================================================================

if __name__ == "__main__":
    # Note: The requests library might not be installed. 
    # I should check for it and install if necessary.
    try:
        import requests
    except ImportError:
        print("The 'requests' library is not installed. Installing it now...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        print("'requests' library installed successfully.")


    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("bot.log", mode='a'),
            logging.StreamHandler()
        ]
    )

    # --- Send a test notification ---
    send_discord_notification("Omen Bot RESTARTED with Data Logging. A test notification from your Omen Bot. If you received this, the webhook is working correctly!")
    # --------------------------------

    logging.info("Starting signal alerter for manual trading...")
    session = HTTP(testnet=False, api_key=config.BYBIT_API_KEY, api_secret=config.BYBIT_API_SECRET)
    
    SYMBOL = "BTCUSDT"
    CATEGORY = "spot"
    INTERVAL = "60" # Changed to 1-hour interval
    last_processed_timestamp = None

    while True:
        try:
            response = session.get_kline(
                category=CATEGORY,
                symbol=SYMBOL,
                interval=INTERVAL,
                limit=30 # Using 30 periods for indicator calculation
            )

            if response['retCode'] == 0 and response['result']['list']:
                data = response['result']['list']
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                df = df.astype(float).sort_index()

                latest_candle_timestamp = df.index[-1]

                if last_processed_timestamp is None:
                    last_processed_timestamp = latest_candle_timestamp
                    logging.info(f"Initial 1-hour candle {last_processed_timestamp} registered. Waiting for next candle.")
                
                elif latest_candle_timestamp > last_processed_timestamp:
                    logging.info(f"New 1-hour candle detected: {latest_candle_timestamp}")
                    df_with_indicators = calculate_indicators(df)
                    
                    # Check for signals and also log the data
                    check_for_signals(df_with_indicators)
                    
                    last_processed_timestamp = latest_candle_timestamp
                else:
                    # Waiting for the next candle
                    print(".", end="", flush=True)

            else:
                logging.warning(f"Could not fetch data: {response['retMsg']}")

        except Exception as e:
            logging.error("An unexpected error occurred!")
            logging.error(traceback.format_exc())

        # Check for a new candle every minute
        time.sleep(60)