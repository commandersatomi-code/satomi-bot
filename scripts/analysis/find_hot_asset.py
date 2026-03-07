import pandas as pd
import numpy as np
import logging
import time
import importlib.util
import os
from pybit.unified_trading import HTTP

# --- Load Config ---
try:
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/config.py'))
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
except Exception as e:
    print(f"FATAL: Could not load configuration from {config_path}. Error: {e}")
    exit(1)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])

def fetch_data_for_asset(symbol, timeframe='15', limit=200):
    """Fetches the latest N candles for a given symbol from Bybit."""
    session = HTTP(testnet=False, api_key=config.BYBIT_API_KEY, api_secret=config.BYBIT_API_SECRET)
    try:
        response = session.get_kline(
            category="linear",
            symbol=symbol,
            interval=timeframe,
            limit=limit
        )
        if response and response['retCode'] == 0 and response['result']['list']:
            data = response['result']['list']
            data.reverse()
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            return df
        else:
            logging.warning(f"Could not fetch data for {symbol}: {response.get('retMsg', 'Unknown error')}")
            return None
    except Exception as e:
        logging.error(f"An error occurred while fetching data for {symbol}: {e}")
        return None

def calculate_hotness(df, atr_period=14, short_vol_sma=20, long_vol_sma=100):
    """Calculates a 'hotness' score for a given asset's dataframe."""
    if df is None or len(df) < long_vol_sma:
        return 0

    # 1. Volatility Score (based on ATR as a percentage of close price)
    df['tr'] = np.maximum(df['high'] - df['low'], np.abs(df['high'] - df['close'].shift(1)))
    df['tr'] = np.maximum(df['tr'], np.abs(df['low'] - df['close'].shift(1)))
    df['atr'] = df['tr'].rolling(window=atr_period).mean()
    # Use the most recent ATR value
    last_atr_pct = (df['atr'].iloc[-1] / df['close'].iloc[-1]) * 100
    
    # 2. Volume Score (ratio of short-term to long-term volume)
    df['vol_sma_short'] = df['volume'].rolling(window=short_vol_sma).mean()
    df['vol_sma_long'] = df['volume'].rolling(window=long_vol_sma).mean()
    
    # Avoid division by zero
    if df['vol_sma_long'].iloc[-1] == 0:
        volume_ratio = 0
    else:
        volume_ratio = df['vol_sma_short'].iloc[-1] / df['vol_sma_long'].iloc[-1]
        
    # 3. Combine scores into a final "hotness" score
    # We give more weight to the volume ratio as it can be a stronger indicator of interest.
    hotness_score = last_atr_pct * volume_ratio
    
    return hotness_score

def find_hottest_asset():
    """
    Analyzes a list of assets and identifies the "hottest" one based on
    a combination of recent volatility and volume.
    """
    logging.info("--- Ura-Slot Hunter: Searching for a 'hot' table... ---")
    
    asset_scores = {}
    
    for asset in config.ASSET_LIST:
        logging.info(f"Scanning asset: {asset}...")
        # Fetch last 200 candles (50 hours of 15m data) to have enough data for indicators
        df = fetch_data_for_asset(asset, limit=200)
        
        if df is not None:
            score = calculate_hotness(df)
            asset_scores[asset] = score
            logging.info(f" -> Hotness score for {asset}: {score:.2f}")
        
        time.sleep(0.5) # Politeness delay to avoid hitting API rate limits

    if not asset_scores:
        logging.error("Could not score any assets. Exiting.")
        return None

    # Find the asset with the highest score
    hottest_asset = max(asset_scores, key=asset_scores.get)
    
    logging.info("\n--- Scan Complete ---")
    logging.info(f"The 'hottest' table right now is: 🔥 {hottest_asset} 🔥")
    
    # This script's primary purpose is to output the symbol,
    # so we print it to stdout for other scripts to capture.
    print(hottest_asset)
    
    return hottest_asset

if __name__ == "__main__":
    find_hottest_asset()
