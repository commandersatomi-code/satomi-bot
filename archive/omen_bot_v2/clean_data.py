import pandas as pd
import os

# Define the path to the data file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '..', 'omen_bot', 'data')
PRICE_DATA_PATH = os.path.join(DATA_DIR, 'bybit_btc_usdt_linear_15m_full.csv')

# Load the data
df = pd.read_csv(PRICE_DATA_PATH, parse_dates=['timestamp'], index_col='timestamp')

# Define the date to remove
problematic_date = '2023-07-23'

# Filter out the problematic date
df_cleaned = df[df.index.date != pd.to_datetime(problematic_date).date()]

# Save the cleaned data to a new file or overwrite the old one
# For safety, let's save to a new file first, then replace if confirmed good.
CLEANED_PRICE_DATA_PATH = os.path.join(DATA_DIR, 'bybit_btc_usdt_linear_15m_full_cleaned.csv')
df_cleaned.to_csv(CLEANED_PRICE_DATA_PATH)

print(f"Original data shape: {df.shape}")
print(f"Cleaned data shape: {df_cleaned.shape}")
print(f"Problematic date '{problematic_date}' removed. Cleaned data saved to: {CLEANED_PRICE_DATA_PATH}")
