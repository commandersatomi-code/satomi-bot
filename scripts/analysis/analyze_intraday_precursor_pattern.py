
import pandas as pd
import os
from datetime import timedelta
import traceback

def analyze_intraday_patterns():
    """
    For each identified large daily move, this script "zooms into" the
    precursor day and analyzes its internal 4-hour candle patterns.
    """
    precursor_events_file = 'daily_multi_candle_precursors.csv'
    intraday_data_file = 'data/bybit_btc_usdt_linear_4h_full.csv'

    print(f"--- Analyzing 4-Hour Intraday Patterns of Precursor Days ---")

    try:
        # 1. Load the event and intraday data files
        df_events = pd.read_csv(precursor_events_file, parse_dates=['timestamp'])
        df_4h = pd.read_csv(intraday_data_file, parse_dates=['timestamp'])

        # 2. Standardize timestamps to UTC for robust comparison
        if df_events['timestamp'].dt.tz is None:
            df_events['timestamp'] = df_events['timestamp'].dt.tz_localize('utc')
        else:
            df_events['timestamp'] = df_events['timestamp'].dt.tz_convert('utc')
        
        if df_4h['timestamp'].dt.tz is None:
            df_4h['timestamp'] = df_4h['timestamp'].dt.tz_localize('utc')
        else:
            df_4h['timestamp'] = df_4h['timestamp'].dt.tz_convert('utc')
            
        # 3. Calculate change % for the 4h data
        df_4h['change_pct_4h'] = 100 * (df_4h['close'] - df_4h['open']) / df_4h['open']

        # Get the unique precursor events to iterate through
        unique_event_ids = df_events['event_id'].unique()

        # 4. Loop through each event
        for event_id in unique_event_ids:
            event_df = df_events[df_events['event_id'] == event_id]
            
            # The precursor day is the one at candle_pos -1
            precursor_day_row = event_df[event_df['candle_pos'] == -1]
            # The large move itself is at candle_pos 0
            move_day_row = event_df[event_df['candle_pos'] == 0]

            if precursor_day_row.empty or move_day_row.empty:
                continue

            precursor_day_start = precursor_day_row['timestamp'].iloc[0]
            final_move_pct = move_day_row['move_change_pct'].iloc[0]
            
            # Define the 24-hour window for the precursor day
            precursor_day_end = precursor_day_start + timedelta(days=1)

            # Filter the 4h data for this specific day
            intraday_df = df_4h[
                (df_4h['timestamp'] >= precursor_day_start) & 
                (df_4h['timestamp'] < precursor_day_end)
            ].copy()

            # --- Display the results for this event ---
            direction = "RISE" if final_move_pct > 0 else "FALL"
            print("\n" + "="*80)
            print(f"Event ID: {event_id} | Precursor Day: {precursor_day_start.strftime('%Y-%m-%d')} | Followed by a {final_move_pct:.2f}% {direction}")
            print("="*80)
            
            if not intraday_df.empty:
                print(intraday_df[['timestamp', 'open', 'close', 'change_pct_4h']].to_string(index=False))
            else:
                print(f"No 4-hour data found for the precursor day {precursor_day_start.strftime('%Y-%m-%d')}.")

        print("\n--- Analysis Complete ---")

    except FileNotFoundError as e:
        print(f"Error: A data file was not found. {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    analyze_intraday_patterns()
