import logging
import time
import sys

# This is a minimal script to test if logging and background execution work at all.

try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("bot.log", mode='w'), # Use write mode to ensure it's fresh
            logging.StreamHandler()
        ]
    )
    logging.info("--- MINIMAL TEST: SCRIPT STARTED SUCCESSFULLY ---")
    # Keep the process alive for a moment to check ps
    time.sleep(15)
    logging.info("--- MINIMAL TEST: SCRIPT FINISHING AFTER 15 SECONDS ---")

except Exception as e:
    # If there's any error, write it to a file as a last resort
    with open("crash.log", "w") as f:
        f.write(f"An unexpected error occurred: {str(e)}")