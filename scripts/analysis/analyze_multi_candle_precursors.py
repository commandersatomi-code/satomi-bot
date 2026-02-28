
import pandas as pd
import numpy as np
import os
import argparse

def analyze_precursor_blocks(file_path: str, window_sizes: list):
    """
    Analyzes blocks of precursor candles to find their aggregate statistical properties.
    """
    print(f"--- Analyzing Precursor Blocks from: {file_path} ---")

    try:
        df = pd.read_csv(file_path, parse_dates=['timestamp'])
        
        # Get unique event IDs
        event_ids = df['event_id'].unique()
        
        event_analyses = []

        # Analyze each event block
        for event_id in event_ids:
            event_df = df[df['event_id'] == event_id]
            
            # Separate the large move from the precursors
            move_candle = event_df[event_df['candle_pos'] == 0].iloc[0]
            precursor_candles = event_df[event_df['candle_pos'] < 0]

            move_direction = 'Rise' if move_candle['move_change_pct'] > 0 else 'Fall'
            
            event_data = {
                'event_id': event_id,
                'move_direction': move_direction,
                'move_change_pct': move_candle['move_change_pct']
            }

            # Analyze for each window size
            for window_size in window_sizes:
                if len(precursor_candles) < window_size:
                    continue
                
                # Get the specific window of precursor candles (e.g., -3, -2, -1)
                window_df = precursor_candles.tail(window_size)
                
                # --- Calculate Metrics for the Window ---
                # 1. Average Volume
                avg_volume = window_df['volume'].mean()
                
                # 2. Volatility (Price Range)
                window_high = window_df['high'].max()
                window_low = window_df['low'].min()
                volatility_points = window_high - window_low
                
                # 3. Volatility as Percentage of start price
                start_price = window_df['open'].iloc[0]
                volatility_pct = (volatility_points / start_price) * 100 if start_price != 0 else 0
                
                # 4. Net Price Change (Drift) over the window
                end_price = window_df['close'].iloc[-1]
                drift_pct = ((end_price - start_price) / start_price) * 100 if start_price != 0 else 0
                
                # Store metrics
                event_data[f'avg_volume_{window_size}candle'] = avg_volume
                event_data[f'volatility_pct_{window_size}candle'] = volatility_pct
                event_data[f'drift_pct_{window_size}candle'] = drift_pct

            event_analyses.append(event_data)

        # Create a DataFrame from the analysis results
        results_df = pd.DataFrame(event_analyses)

        # --- Display Summary Statistics ---
        pd.set_option('display.width', 120)
        pd.set_option('display.float_format', '{:.2f}'.format)

        print("\n" + "="*80)
        print("    AVERAGE PRECURSOR CHARACTERISTICS (LEADING TO RISES)")
        print("="*80)
        rise_precursors_avg = results_df[results_df['move_direction'] == 'Rise'].mean(numeric_only=True)
        print(rise_precursors_avg)

        print("\n" + "="*80)
        print("    AVERAGE PRECURSOR CHARACTERISTICS (LEADING TO FALLS)")
        print("="*80)
        fall_precursors_avg = results_df[results_df['move_direction'] == 'Fall'].mean(numeric_only=True)
        print(fall_precursors_avg)
        
        print("\n--- Analysis Complete ---")

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze precursor candle blocks.")
    parser.add_argument("file_path", type=str, help="Path to the precursor CSV file.")
    parser.add_argument("--windows", type=int, nargs='+', default=[3], help="A list of window sizes (number of candles) to analyze.")
    
    args = parser.parse_args()

    analyze_precursor_blocks(args.file_path, args.windows)
