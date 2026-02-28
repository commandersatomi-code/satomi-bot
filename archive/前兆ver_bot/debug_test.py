import config
from pybit.unified_trading import HTTP
import sys

print("--- DEBUG TEST START ---")
print("Attempting to import config and pybit... Success.")

try:
    print("Attempting to initialize HTTP session...")
    session = HTTP(
        testnet=False,
        api_key=config.BYBIT_API_KEY,
        api_secret=config.BYBIT_API_SECRET
    )
    print("HTTP session initialized successfully.")
except Exception as e:
    print(f"An error occurred during HTTP initialization: {e}", file=sys.stderr)
    sys.exit(1)

print("--- DEBUG TEST END ---")
