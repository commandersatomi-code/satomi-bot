# ==============================================================================
# Omen Bot - Core Data Utilities
# ==============================================================================
# This module contains generic functions for fetching and updating market data
# from Bybit, including price (OHLCV) and funding rates.
# It is designed to be configured via the central config.py file.
# ==============================================================================

import pandas as pd
from pybit.unified_trading import HTTP
import time
import os
from datetime import datetime, timezone

# Import the central configuration
try:
    from .. import config
except ImportError:
    print("Error: Could not import config.py. Make sure it's in the 'omen_bot' directory.")
    exit()

def update_price_data():
    """
    Fetches the latest OHLCV data since the last recorded timestamp in the
    price data CSV file.
    """
    print("--- Starting Price Data Update ---")
    session = HTTP(testnet=False)
    
    last_timestamp_ms = 0
    df_existing = None

    if os.path.exists(config.PRICE_DATA_PATH):
        print(f"Reading existing price data from: {config.PRICE_DATA_PATH}")
        try:
            df_existing = pd.read_csv(config.PRICE_DATA_PATH, parse_dates=['timestamp'])
            if not df_existing.empty:
                last_timestamp = df_existing['timestamp'].max()
                # Start fetching from the next interval
                last_timestamp_ms = int(last_timestamp.timestamp() * 1000) + (60 * 60 * 1000)
                print(f"Last data point found at: {last_timestamp}")
            else:
                print("Price data file is empty. Fetching from a default start date.")
                start_dt = datetime(2020, 3, 1, tzinfo=timezone.utc) # A reasonable default
                last_timestamp_ms = int(start_dt.timestamp() * 1000)
        except Exception as e:
            print(f"Could not read or parse existing price data file. Error: {e}")
            return
    else:
        print("No existing price data file found. Fetching from a default start date.")
        start_dt = datetime(2020, 3, 1, tzinfo=timezone.utc)
        last_timestamp_ms = int(start_dt.timestamp() * 1000)

    all_new_data = []
    while True:
        print(f"Fetching price data starting from {pd.to_datetime(last_timestamp_ms, unit='ms')}...")
        try:
            response = session.get_kline(
                category="linear", # Assuming derivatives data as per discussion
                symbol=config.SYMBOL,
                interval=config.TIMEFRAME.replace('h','').replace('d',''), # pybit needs '60' not '1h'
                start=last_timestamp_ms,
                limit=1000
            )
        except Exception as e:
            print(f"An error occurred during API call: {e}")
            break

        if response.get('retCode') == 0:
            data = response.get('result', {}).get('list', [])
            if not data:
                print("No more new price data to fetch.")
                break
            
            all_new_data.extend(data)
            last_ts_in_batch = int(data[-1][0])
            last_timestamp_ms = last_ts_in_batch + (60 * 60 * 1000) # Move to next hour
            print(f"Fetched {len(data)} rows. Last timestamp in batch: {pd.to_datetime(last_ts_in_batch, unit='ms')}")

            if len(data) < 1000:
                break
            time.sleep(0.5)
        else:
            print(f"API Error fetching price data: {response.get('retMsg')}")
            break

    if all_new_data:
        df_new = pd.DataFrame(all_new_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df_new['timestamp'] = pd.to_datetime(df_new['timestamp'], unit='ms')
        
        # Combine, sort, and remove duplicates
        df_combined = pd.concat([df_existing, df_new], ignore_index=True) if df_existing is not None else df_new
        df_combined.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
        df_combined.sort_values('timestamp', inplace=True)
        
        print(f"Saving updated price data. Total rows are now: {len(df_combined)}")
        df_combined.to_csv(config.PRICE_DATA_PATH, index=False)
    else:
        print("Price data is already up-to-date.")
    print("--- Price Data Update Finished ---\\n")


def update_funding_rate_data():
    """
    Fetches the entire history of funding rates for the configured symbol.
    It works backwards from the current time to retrieve all data.
    NOTE: This function is designed for a bulk download. A more optimized
    version would check the last entry and only fetch newer rates.
    """
    print("--- Starting Funding Rate Data Update ---")
    session = HTTP(testnet=False)
    
    all_rates = []
    # We fetch data by iterating backwards from the present time.
    end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    # Define a practical limit for how far back we go, e.g., start of 2020
    limit_ts = int(datetime(2020, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)

    while end_ts > limit_ts:
        print(f"Fetching funding rates ending at {pd.to_datetime(end_ts, unit='ms')}...")
        try:
            response = session.get_funding_rate_history(
                category="linear",
                symbol=config.SYMBOL,
                endTime=end_ts,
                limit=200
            )
        except Exception as e:
            print(f"An error occurred during API call: {e}")
            break

        if response.get('retCode') == 0:
            rates = response.get('result', {}).get('list', [])
            if not rates:
                print("No more funding rate data in this time range.")
                break

            all_rates.extend(rates)
            # The timestamp of the oldest record in the batch
            oldest_ts_in_batch = int(rates[-1]['fundingRateTimestamp'])
            
            # Set the end of the next window to be just before the oldest record
            end_ts = oldest_ts_in_batch - 1
            
            print(f"Fetched {len(rates)} records. Oldest in batch: {pd.to_datetime(oldest_ts_in_batch, unit='ms')}")
            
            if len(rates) < 200:
                print("Reached the earliest available data.")
                break
            time.sleep(0.5) # Be respectful of API rate limits
        else:
            print(f"API Error fetching funding rates: {response.get('retMsg')}")
            break

    if all_rates:
        df = pd.DataFrame(all_rates)
        # Convert columns to correct types
        df['fundingRateTimestamp'] = pd.to_datetime(df['fundingRateTimestamp'], unit='ms')
        df['fundingRate'] = pd.to_numeric(df['fundingRate'])
        
        # Sort and remove duplicates, just in case
        df.sort_values('fundingRateTimestamp', ascending=False, inplace=True)
        df.drop_duplicates(subset=['fundingRateTimestamp'], keep='first', inplace=True)
        df.sort_values('fundingRateTimestamp', ascending=True, inplace=True)
        
        print(f"Saving {len(df)} funding rate records to: {config.FUNDING_RATE_DATA_PATH}")
        df.to_csv(config.FUNDING_RATE_DATA_PATH, index=False)
    else:
        print("No funding rate data was fetched.")
    print("--- Funding Rate Data Update Finished ---")

if __name__ == '__main__':
    # This allows running the script directly to update all data
    update_price_data()
    update_funding_rate_data()
