import pandas as pd
from pybit.unified_trading import HTTP
import config

# ==============================================================================
# 1. STRATEGY PARAMETERS (Copied from live_bot.py)
# ==============================================================================

STRATEGY_PARAMS = {
    "SELL": {
        "HighestQuality": {"vol_mult": 2.0, "body_ratio": 0.3},
        "Balanced": {"vol_mult": 1.6, "body_ratio": 0.5},
        "Action": {"vol_mult": 1.2, "body_ratio": 0.6}
    },
    "BUY": {
        "HighestQuality": {"vol_mult": 2.0, "body_ratio": 0.3},
        "Balanced": {"vol_mult": 1.7, "body_ratio": 0.6},
        "Action": {"vol_mult": 1.3, "body_ratio": 0.6}
    }
}

# ==============================================================================
# 2. CORE LOGIC (Adapted from live_bot.py)
# ==============================================================================

def calculate_indicators(df, atr_period=14, vol_sma_period=20):
    """Calculates ATR and Volume SMA."""
    df['high_low'] = df['high'] - df['low']
    df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
    df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
    df['atr'] = df['true_range'].ewm(span=atr_period, adjust=False).mean()
    df['volume_sma'] = df['volume'].rolling(window=vol_sma_period).mean()
    return df

def check_for_signal_on_candle(candle):
    """Checks a single candle for any of the 6 defined signals and prints an alert."""
    signal_detected = False
    
    # --- Check for SELL signals ---
    for quality, params in STRATEGY_PARAMS["SELL"].items():
        # Ensure we have the data needed to check the signal
        if pd.isna(candle['volume_sma']) or pd.isna(candle['atr']):
            continue

        is_high_volume = candle['volume'] > (candle['volume_sma'] * params["vol_mult"])
        is_bullish_candle = candle['close'] > candle['open']
        candle_body_size = candle['close'] - candle['open']
        is_small_body = candle_body_size < (candle['atr'] * params["body_ratio"])
        
        if is_high_volume and is_bullish_candle and is_small_body:
            signal_message = f"【PAST SIGNAL FOUND: SELL】\nQuality: {quality}\nPrice: {candle['close']}\nTime: {candle.name}"
            print("\n" + "="*50)
            print(signal_message)
            print("="*50 + "\n")
            signal_detected = True
            return True # Stop after the first (highest quality) signal is found

    # --- Check for BUY signals ---
    if not signal_detected:
        for quality, params in STRATEGY_PARAMS["BUY"].items():
            if pd.isna(candle['volume_sma']) or pd.isna(candle['atr']):
                continue

            is_high_volume = candle['volume'] > (candle['volume_sma'] * params["vol_mult"])
            is_bearish_candle = candle['close'] < candle['open']
            candle_body_size = abs(candle['close'] - candle['open'])
            is_small_body = candle_body_size < (candle['atr'] * params["body_ratio"])

            if is_high_volume and is_bearish_candle and is_small_body:
                signal_message = f"【PAST SIGNAL FOUND: BUY】\nQuality: {quality}\nPrice: {candle['close']}\nTime: {candle.name}"
                print("\n" + "="*50)
                print(signal_message)
                print("="*50 + "\n")
                return True # Stop after the first (highest quality) signal is found
    
    return False

# ==============================================================================
# 3. MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("Fetching historical data to check for signals in the last 24 hours...")
    
    session = HTTP(testnet=False, api_key=config.BYBIT_API_KEY, api_secret=config.BYBIT_API_SECRET)
    
    SYMBOL = "BTCUSDT"
    CATEGORY = "spot"
    INTERVAL = "60" # 1-hour interval
    
    try:
        # Fetch enough data for indicator calculation + 24 hours
        response = session.get_kline(
            category=CATEGORY,
            symbol=SYMBOL,
            interval=INTERVAL,
            limit=200 
        )

        if response['retCode'] == 0 and response['result']['list']:
            data = response['result']['list']
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df = df.astype(float).sort_index()

            # Calculate indicators on the full dataset
            df_with_indicators = calculate_indicators(df)
            
            # --- Print specific candle data for user's request ---
            target_dates = [
                pd.Timestamp('2025-11-12 07:00:00'),
                pd.Timestamp('2025-11-12 08:00:00')
            ]
            
            print("\n--- Requested Candle Data (UTC) ---")
            found_requested_candles = False
            for target_date in target_dates:
                # Find the candle that starts at the target_date
                # The index is the start time of the candle
                if target_date in df_with_indicators.index:
                    candle_data = df_with_indicators.loc[target_date]
                    print(f"\nCandle at {target_date} (UTC):")
                    print(f"  Open: {candle_data['open']}")
                    print(f"  High: {candle_data['high']}")
                    print(f"  Low: {candle_data['low']}")
                    print(f"  Close: {candle_data['close']}")
                    print(f"  Volume: {candle_data['volume']}")
                    print(f"  Turnover: {candle_data['turnover']}")
                    found_requested_candles = True
                else:
                    print(f"\nCandle at {target_date} (UTC) not found in fetched data.")
            
            if not found_requested_candles:
                print("No requested candles found.")
            print("-----------------------------------")
            # --- End of specific candle data ---

            # We check the last 24 candles from the historical data
            # The most recent candle from the API might be incomplete, so we check from -25 to -1
            candles_to_check = df_with_indicators.iloc[-25:-1] 
            
            print(f"Checking {len(candles_to_check)} completed 1-hour candles for signals...")
            
            signals_found_count = 0
            for index, candle in candles_to_check.iterrows():
                if check_for_signal_on_candle(candle):
                    signals_found_count += 1
            
            if signals_found_count == 0:
                print("\nNo trade signals found in the last 24 completed hours.")

        else:
            print(f"Could not fetch data from Bybit: {response['retMsg']}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
