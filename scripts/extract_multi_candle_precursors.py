
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
import os

def extract_multi_candle_precursors(file_path: str, output_path: str, threshold: float, num_precursors: int):
    """
    Finds large price moves and extracts the N candles immediately preceding them,
    saving the event blocks to a new CSV file.
    """
    print(f"--- Extracting {num_precursors}-Candle Precursor Patterns from: {file_path} ---")
    
    try:
        # 1. Load data and apply training data rule
        df = pd.read_csv(file_path, parse_dates=['timestamp'])
        
        split_date = datetime.now() - timedelta(days=365)
        training_df = df[df['timestamp'] < split_date].copy()
        
        if training_df.empty:
            print("No training data available.")
            return
            
        # Reset index to ensure integer-based indexing works as expected
        training_df.reset_index(drop=True, inplace=True)

        # 2. Calculate the change for each candle
        training_df['move_change_pct'] = 100 * (training_df['close'] - training_df['open']) / training_df['open']

        # 3. Find the indices of the large moves
        large_move_indices = training_df[abs(training_df['move_change_pct']) >= threshold].index

        # 4. Loop through indices and extract precursor blocks
        all_event_blocks = []
        event_id_counter = 1
        
        for idx in large_move_indices:
            # Ensure there are enough preceding candles
            if idx < num_precursors:
                continue
            
            # Slice the dataframe to get the block of num_precursors + the move candle
            start_idx = idx - num_precursors
            end_idx = idx
            event_block_df = training_df.iloc[start_idx:end_idx + 1].copy()
            
            # Add identifiers for easy analysis
            event_block_df['event_id'] = event_id_counter
            # Position 0 is the large move, -1 is the candle just before, etc.
            event_block_df['candle_pos'] = np.arange(-num_precursors, 1)
            
            all_event_blocks.append(event_block_df)
            event_id_counter += 1

        if not all_event_blocks:
            print(f"Found no large move events (≥ +/-{threshold}%) with enough preceding data.")
            return

        # 5. Concatenate all blocks and save
        final_df = pd.concat(all_event_blocks)
        
        # Reorder columns for clarity
        cols = ['event_id', 'candle_pos', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'move_change_pct']
        final_df = final_df[cols]
        
        print(f"Found {len(all_event_blocks)} large move events.")
        print(f"Saving event blocks to {output_path}...")
        final_df.to_csv(output_path, index=False, float_format='%.4f')

        print(f"\n--- Extraction Complete ---")
        print(f"Data saved to {output_path}. Each event is identified by 'event_id'.")

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract multi-candle precursors to large price moves.")
    parser.add_argument("--file_path", type=str, required=True, help="Path to the input CSV file.")
    parser.add_argument("--threshold", type=float, required=True, help="The percentage move threshold to define a 'large move'.")
    parser.add_argument("--num_precursors", type=int, required=True, help="The number of preceding candles to extract for each event.")
    parser.add_argument("--output_path", type=str, required=True, help="Path to save the resulting CSV file.")
    
    args = parser.parse_args()

    extract_multi_candle_precursors(
        file_path=args.file_path,
        threshold=args.threshold,
        num_precursors=args.num_precursors,
        output_path=args.output_path
    )
