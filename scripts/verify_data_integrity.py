
import pandas as pd
import argparse
import sys

def verify_monthly_data(file_path: str):
    """
    Verifies the integrity of a monthly timeseries data file by checking
    for month-by-month continuity.
    """
    print(f"--- Verifying: {file_path} (Monthly Interval) ---")
    
    try:
        df = pd.read_csv(file_path)
        if 'timestamp' not in df.columns:
            print("Error: 'timestamp' column not found.")
            return

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.sort_values('timestamp', inplace=True)
        
        print(f"Total Rows: {len(df)}")
        if df.empty:
            print("File is empty.")
            return
        print(f"Start Date: {df['timestamp'].iloc[0]}")
        print(f"End Date:   {df['timestamp'].iloc[-1]}")

        gaps = []
        # Iterate from the second row
        for i in range(1, len(df)):
            prev_ts = df['timestamp'].iloc[i-1]
            curr_ts = df['timestamp'].iloc[i]
            
            # Expected next month logic
            expected_year, expected_month = (prev_ts.year, prev_ts.month + 1) if prev_ts.month < 12 else (prev_ts.year + 1, 1)

            if not (curr_ts.year == expected_year and curr_ts.month == expected_month):
                gap_info = {
                    "after": prev_ts,
                    "found": curr_ts,
                    "expected": f"{expected_year}-{expected_month:02d}"
                }
                gaps.append(gap_info)
        
        if not gaps:
            print("\n[SUCCESS] No time gaps found. Data is continuous month-by-month.")
        else:
            print(f"\n[WARNING] Found {len(gaps)} gap(s) where the month was not sequential.")
            for gap in gaps[:5]: # Print up to 5 gaps
                print(f"  - After {gap['after'].strftime('%Y-%m')}, expected ~{gap['expected']} but found {gap['found'].strftime('%Y-%m')}")

        print("-" * 50)

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def verify_data(file_path: str, expected_interval: str):
    """
    Verifies the integrity of a timeseries data file.

    Args:
        file_path (str): The path to the CSV file.
        expected_interval (str): The expected interval as a pandas frequency string (e.g., '15T', '1H', 'D').
    """
    print(f"--- Verifying: {file_path} (Expected Interval: {expected_interval}) ---")
    
    try:
        # Load the data
        df = pd.read_csv(file_path)

        # Check for required column
        if 'timestamp' not in df.columns:
            print("Error: 'timestamp' column not found.")
            return

        # Convert to datetime objects
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.sort_values('timestamp', inplace=True)
        
        # --- Report Basic Info ---
        print(f"Total Rows: {len(df)}")
        if not df.empty:
            print(f"Start Date: {df['timestamp'].iloc[0]}")
            print(f"End Date:   {df['timestamp'].iloc[-1]}")
        else:
            print("File is empty.")
            return

        # --- Check for Gaps ---
        expected_delta = pd.to_timedelta(expected_interval)
        
        # Calculate the difference between consecutive timestamps
        df['delta'] = df['timestamp'].diff()
        
        # The first delta will be NaT, so we start from the second row
        gaps = df[df['delta'] != expected_delta].iloc[1:]
        
        num_gaps = len(gaps)
        
        if num_gaps == 0:
            print("\n[SUCCESS] No time gaps found. Data is continuous.")
        else:
            print(f"\n[WARNING] Found {num_gaps} gap(s) where the time difference was not exactly '{expected_interval}'.")
            
            # Show the top 5 largest gaps
            print("\nTop 5 largest gaps:")
            top_5_gaps = gaps.nlargest(5, 'delta')
            for index, row in top_5_gaps.iterrows():
                prev_timestamp = df.loc[index - 1, 'timestamp']
                print(f"  - Gap of {row['delta']} found after {prev_timestamp}")

        print("-" * 50)

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify the integrity of Bybit data files.")
    parser.add_argument("file", type=str, help="Path to the input CSV file.")
    parser.add_argument("interval", type=str, help="Expected interval (e.g., '5T', '15T', '1H', '1D', '7D', 'M').")
    args = parser.parse_args()
    
    if args.interval.upper() == 'M':
        verify_monthly_data(args.file)
    else:
        verify_data(args.file, args.interval)
