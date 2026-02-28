
import pandas as pd
import os

def merge_and_clean_data():
    """
    Merges and cleans the two 15-minute data files into a single,
    sorted, and deduplicated file.
    """
    data_dir = 'data'
    file1 = os.path.join(data_dir, 'bybit_btc_usdt_linear_15m_full.csv')
    file2 = os.path.join(data_dir, 'bybit_btc_usdt_linear_15m_full_cleaned.csv')
    output_file = file2 # Overwrite the 'cleaned' file as it's the main one

    try:
        print(f"Reading {file1}...")
        df1 = pd.read_csv(file1)

        print(f"Reading {file2}...")
        df2 = pd.read_csv(file2)

        print("Combining the two dataframes...")
        combined_df = pd.concat([df1, df2], ignore_index=True)
        initial_rows = len(combined_df)
        print(f"Initial combined rows: {initial_rows}")

        print("Cleaning data...")
        # Convert timestamp to datetime, coercing errors will turn bad data into NaT
        combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'], errors='coerce')

        # Drop rows where timestamp could not be parsed
        rows_before_dropna = len(combined_df)
        combined_df.dropna(subset=['timestamp'], inplace=True)
        dropped_rows = rows_before_dropna - len(combined_df)
        if dropped_rows > 0:
            print(f"Dropped {dropped_rows} rows with invalid timestamps.")

        # Sort by timestamp and drop duplicates
        print("Sorting by timestamp and removing duplicates...")
        combined_df.sort_values('timestamp', inplace=True)
        rows_before_dedupe = len(combined_df)
        combined_df.drop_duplicates(subset='timestamp', keep='first', inplace=True)
        deduped_rows = rows_before_dedupe - len(combined_df)
        if deduped_rows > 0:
            print(f"Removed {deduped_rows} duplicate rows.")

        # Save the final dataframe
        print(f"Saving cleaned data to {output_file}...")
        combined_df.to_csv(output_file, index=False)

        final_rows = len(combined_df)
        print("\n--- Merge Successful ---")
        print(f"Final total rows: {final_rows}")
        print(f"Data range from {combined_df['timestamp'].min()} to {combined_df['timestamp'].max()}")

    except FileNotFoundError as e:
        print(f"Error: Could not find a data file. {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    merge_and_clean_data()
