import pandas as pd
from pybit.unified_trading import HTTP
import config
import time
import numpy as np

# ==============================================================================
# 1. DATA FETCHING
# ==============================================================================

def fetch_all_data(session, symbol, interval, start_timestamp):
    """Fetches all available historical kline data from Bybit from a start date."""
    all_data = []
    # Bybit returns data in reverse chronological order. We paginate backwards from now.
    end_time = int(time.time() * 1000)

    while end_time > start_timestamp:
        try:
            print(f"Fetching 1000 records before {pd.to_datetime(end_time, unit='ms')}...")
            response = session.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                end=end_time,
                limit=1000
            )
            
            if response['retCode'] != 0:
                print(f"Error fetching data: {response['retMsg']}")
                break

            data = response['result']['list']
            if not data:
                print("No more data returned.")
                break
            
            # Data is newest first, prepend to our list
            all_data = data + all_data
            # Update end_time to the timestamp of the oldest record fetched
            oldest_ts = int(data[-1][0])
            
            # Stop if we have gone past our desired start_timestamp
            if oldest_ts < start_timestamp:
                break
            
            end_time = oldest_ts - 1
            
            print(f"Fetched {len(data)} new records. Total: {len(all_data)}")
            time.sleep(0.2) # Respect API rate limits

        except Exception as e:
            print(f"An error occurred: {e}")
            break
            
    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df.astype(float)
    df.sort_index(inplace=True)
    # Filter out data before the start_timestamp that may have been fetched in the last batch
    df = df[df.index >= pd.to_datetime(start_timestamp, unit='ms')]
    return df

# ==============================================================================
# 2. VPA: "EFFORT VS RESULT" ANALYSIS
# ==============================================================================

def calculate_indicators(df, atr_period=14, vol_sma_period=20):
    """Calculates ATR and Volume SMA needed for the VPA analysis."""
    # Calculate True Range
    df['high_low'] = df['high'] - df['low']
    df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
    df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
    
    # Calculate ATR (Average True Range)
    df['atr'] = df['true_range'].ewm(span=atr_period, adjust=False).mean()
    
    # Calculate Volume SMA
    df['volume_sma'] = df['volume'].rolling(window=vol_sma_period).mean()
    return df

def analyze_effort_vs_result(df, vol_multiplier=2.0, body_atr_ratio=0.2, look_forward_period=5):
    """ 
    Finds "Effort vs Result" anomalies and analyzes the subsequent price action.
    Anomaly Definition: High volume on a bullish candle with a very small body.
    """
    # Condition A: High Volume (The "Effort")
    is_high_volume = df['volume'] > (df['volume_sma'] * vol_multiplier)
    
    # Condition B: Lack of Result
    is_bullish_candle = df['close'] > df['open']
    candle_body_size = df['close'] - df['open']
    is_small_body = candle_body_size < (df['atr'] * body_atr_ratio)
    
    # Combine conditions to find the "Omen"
    df['omen_found'] = is_high_volume & is_bullish_candle & is_small_body
    
    omen_indices = df[df['omen_found']].index
    
    results = []
    for idx in omen_indices:
        omen_candle = df.loc[idx]
        
        # Analyze the subsequent N candles
        future_candles_end_index = df.index.get_loc(idx) + 1 + look_forward_period
        if future_candles_end_index > len(df):
            continue # Not enough data to look forward
            
        future_candles = df.iloc[df.index.get_loc(idx) + 1:future_candles_end_index]
        
        if future_candles.empty:
            continue

        # Calculate max drop and max rise in the look-forward period
        max_drawdown_pct = (future_candles['low'].min() - omen_candle['close']) / omen_candle['close'] * 100
        max_rise_pct = (future_candles['high'].max() - omen_candle['close']) / omen_candle['close'] * 100
        final_price_change_pct = (future_candles.iloc[-1]['close'] - omen_candle['close']) / omen_candle['close'] * 100

        results.append({
            'omen_date': idx,
            'omen_close': omen_candle['close'],
            'omen_volume': omen_candle['volume'],
            'omen_volume_sma': omen_candle['volume_sma'],
            'omen_atr': omen_candle['atr'],
            f'max_drawdown_pct_next_{look_forward_period}_days': max_drawdown_pct,
            f'max_rise_pct_next_{look_forward_period}_days': max_rise_pct,
            f'final_change_pct_next_{look_forward_period}_days': final_price_change_pct,
        })
        
    return pd.DataFrame(results)

# ==============================================================================
# 3. EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # --- Parameters ---
    SYMBOL = "BTCUSDT"
    INTERVAL = "D" # Daily timeframe
    # Bybit's earliest spot data for BTCUSDT is around 2018-08-16
    START_TIMESTAMP = 1534377600000 
    OUTPUT_FILENAME = "vpa_analysis_results.csv"

    # --- Initialize Client ---
    # Using production environment as requested
    session = HTTP(
        testnet=False,
        api_key=config.BYBIT_API_KEY,
        api_secret=config.BYBIT_API_SECRET,
    )

    # --- Run Analysis ---
    print("Starting VPA Plan B: 'Effort vs Result' Analysis")
    print(f"Fetching all available data for {SYMBOL} since 2018-08-16...")
    
    full_data = fetch_all_data(session, SYMBOL, INTERVAL, START_TIMESTAMP)
    
    if not full_data.empty:
        print(f"Successfully fetched {len(full_data)} days of data.")
        print("Calculating indicators (ATR, Volume SMA)...")
        
        data_with_indicators = calculate_indicators(full_data)
        
        print("Analyzing for 'Effort vs Result' anomalies...")
        analysis_results = analyze_effort_vs_result(data_with_indicators, vol_multiplier=1.2, body_atr_ratio=0.6)
        
        if not analysis_results.empty:
            analysis_results.to_csv(OUTPUT_FILENAME)
            print(f"\nAnalysis complete. Results saved to {OUTPUT_FILENAME}")
            print(f"Found {len(analysis_results)} instances of the 'Upward Stall Omen'.")
        else:
            print("\nAnalysis complete. No instances of the omen were found with the current parameters.")
    else:
        print("Could not fetch data. Aborting analysis.")
