
import pandas as pd
from pybit.unified_trading import HTTP
import time
import datetime
import os

# --- Configuration ---
# We will attempt to import the API keys from the existing config file.
# This makes the script more portable.
try:
    import sys
    # Add the parent directory to the path to find the omen_bot module
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from omen_bot import config as api_config
    API_KEY = api_config.BYBIT_API_KEY
    API_SECRET = api_config.BYBIT_API_SECRET
    print("Successfully imported API keys from omen_bot/config.py")
except (ImportError, ModuleNotFoundError):
    print("Could not import API keys. Please ensure API_KEY and API_SECRET are set.")
    # Define placeholders if the import fails
    API_KEY = "YOUR_API_KEY"
    API_SECRET = "YOUR_API_SECRET"

# --- Script Parameters ---
SYMBOL = "BTCUSDT"
CATEGORY = "linear" # For derivatives, as requested. 'spot' for spot market.
DATA_START_DATE = "2020-01-01" # Go back as far as 2020
OUTPUT_DIR = os.path.dirname(__file__) # Save in the current script's directory ('裏スロ')

def fetch_full_history(session, symbol, category, interval, start_date_str):
    """
    Fetches the complete historical K-line data for a given symbol and interval.

    Bybit's API has a limit of 1000 candles per request. This function
    iteratively fetches data in chunks of 1000 until the start of the
    history or the specified start_date is reached.
    """
    print(f"\nFetching data for interval: {interval}...")
    all_data = []
    
    # Convert string start date to milliseconds timestamp
    start_timestamp_ms = int(datetime.datetime.strptime(start_date_str, "%Y-%m-%d").timestamp() * 1000)
    
    # Start from the present and go backwards
    end_timestamp_ms = int(datetime.datetime.now().timestamp() * 1000)

    while True:
        try:
            response = session.get_kline(
                category=category,
                symbol=symbol,
                interval=interval,
                end=end_timestamp_ms,
                limit=1000
            )

            if response.get('retCode') == 0 and response['result']['list']:
                chunk = response['result']['list']
                first_candle_timestamp_ms = int(chunk[-1][0]) # Bybit returns newest first, so last in list is oldest
                
                all_data.extend(chunk)
                
                print(f"  Fetched {len(chunk)} candles, ending at {datetime.datetime.fromtimestamp(end_timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')}")

                # If the oldest candle in this chunk is older than our desired start date, we can stop
                if first_candle_timestamp_ms < start_timestamp_ms:
                    print("  Reached the desired start date. Halting fetch.")
                    break
                
                # Set the end of the next chunk to be the start of the current chunk
                end_timestamp_ms = first_candle_timestamp_ms
                
                # Be respectful to the API
                time.sleep(0.2) 

            else:
                print(f"  No more data found or an error occurred: {response.get('retMsg', 'Unknown Error')}")
                break
        
        except Exception as e:
            print(f"An exception occurred: {e}")
            time.sleep(1) # Wait a bit before retrying
            continue

    if not all_data:
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.astype(float)
    
    # Clean up: sort by date and remove duplicates
    df = df.sort_values('timestamp').drop_duplicates('timestamp').set_index('timestamp')
    
    print(f"  Successfully fetched a total of {len(df)} unique candles.")
    return df

if __name__ == "__main__":
    print("Initializing Bybit session...")
    session = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)
    
    # Timeframes requested by the user, in the format required by Bybit API
    # M = Month, W = Week, D = Day, 240 = 4h, 60 = 1h, 15 = 15m, 5 = 5m, 1 = 1m
    timeframes_to_fetch = ['M', 'W', 'D', '240', '60', '15', '5', '1']

    for tf in timeframes_to_fetch:
        # Fetch the data
        hist_df = fetch_full_history(session, SYMBOL, CATEGORY, tf, DATA_START_DATE)
        
        if not hist_df.empty:
            # Create a clean filename
            # Replace 'D' with 'daily', 'W' with 'weekly' etc. for clarity
            tf_name_map = {'M': 'monthly', 'W': 'weekly', 'D': 'daily', '240': '4h', '60': '1h'}
            file_tf_name = tf_name_map.get(tf, f'{tf}m') # default to 'Xm' if not in map
            
            filename = f"bybit_{SYMBOL}_{CATEGORY}_{file_tf_name}.csv"
            filepath = os.path.join(OUTPUT_DIR, filename)
            
            # Save to CSV
            hist_df.to_csv(filepath)
            print(f"  Data saved to: {filepath}")

    print("\n--- Data Manifestation Complete ---")
    print("All requested timeframes have been downloaded and saved in the '裏スロ' directory.")
