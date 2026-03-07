
import pandas as pd
import os
from datetime import timedelta

def quantify_intraday_patterns():
    """
    Quantifies the intraday (4h) patterns of precursor days by calculating
    metrics like drift, volatility, drawdown, and rebound.
    """
    precursor_events_file = 'daily_multi_candle_precursors.csv'
    intraday_data_file = 'data/bybit_btc_usdt_linear_4h_full.csv'

    print(f"--- Quantifying 4-Hour Intraday Patterns of Precursor Days ---")

    try:
        # 1. Load data and standardize timestamps
        df_events = pd.read_csv(precursor_events_file, parse_dates=['timestamp'])
        df_4h = pd.read_csv(intraday_data_file, parse_dates=['timestamp'])

        if df_events['timestamp'].dt.tz is None:
            df_events['timestamp'] = df_events['timestamp'].dt.tz_localize('utc')
        if df_4h['timestamp'].dt.tz is None:
            df_4h['timestamp'] = df_4h['timestamp'].dt.tz_localize('utc')
            
        # Get unique event IDs
        unique_event_ids = df_events['event_id'].unique()
        
        event_analyses = []

        # 2. Loop through each event and calculate intraday metrics
        for event_id in unique_event_ids:
            event_df = df_events[df_events['event_id'] == event_id]
            move_day_row = event_df[event_df['candle_pos'] == 0].iloc[0]
            precursor_day_row = event_df[event_df['candle_pos'] == -1].iloc[0]

            precursor_day_start = precursor_day_row['timestamp']
            final_move_pct = move_day_row['move_change_pct']
            move_direction = 'Rise' if final_move_pct > 0 else 'Fall'
            precursor_day_end = precursor_day_start + timedelta(days=1)

            # Filter the 4h data for this specific precursor day
            intraday_df = df_4h[
                (df_4h['timestamp'] >= precursor_day_start) & 
                (df_4h['timestamp'] < precursor_day_end)
            ]

            if intraday_df.empty or len(intraday_df) < 2: # Need at least 2 candles for meaningful stats
                continue

            # --- Calculate Intraday Metrics ---
            day_open = intraday_df['open'].iloc[0]
            day_close = intraday_df['close'].iloc[-1]
            day_high = intraday_df['high'].max()
            day_low = intraday_df['low'].min()
            
            # Net drift over the 24h period
            intraday_drift_pct = ((day_close - day_open) / day_open) * 100 if day_open != 0 else 0
            
            # Volatility over the 24h period
            intraday_volatility_pct = ((day_high - day_low) / day_open) * 100 if day_open != 0 else 0
            
            # Max drawdown within the day
            running_max = intraday_df['high'].cummax()
            drawdown = (running_max - intraday_df['low']) / running_max
            intraday_max_drawdown_pct = drawdown.max() * 100 if not drawdown.empty else 0
            
            # Rebound from the day's low to the close
            rebound_from_low_pct = ((day_close - day_low) / day_low) * 100 if day_low != 0 else 0
            
            event_analyses.append({
                'event_id': event_id,
                'move_direction': move_direction,
                'intraday_drift_pct': intraday_drift_pct,
                'intraday_volatility_pct': intraday_volatility_pct,
                'intraday_max_drawdown_pct': intraday_max_drawdown_pct,
                'rebound_from_low_pct': rebound_from_low_pct
            })

        # 3. Create a results DataFrame and display aggregate stats
        results_df = pd.DataFrame(event_analyses)
        
        pd.set_option('display.width', 120)
        pd.set_option('display.float_format', '{:.2f}'.format)

        print("\n" + "="*80)
        print("    AVERAGE INTRADAY PRECURSOR CHARACTERISTICS (LEADING TO RISES)")
        print("="*80)
        rise_precursors_avg = results_df[results_df['move_direction'] == 'Rise'].mean(numeric_only=True)
        print(rise_precursors_avg)

        print("\n" + "="*80)
        print("    AVERAGE INTRADAY PRECURSOR CHARACTERISTICS (LEADING TO FALLS)")
        print("="*80)
        fall_precursors_avg = results_df[results_df['move_direction'] == 'Fall'].mean(numeric_only=True)
        print(fall_precursors_avg)
        
        print("\n--- Analysis Complete ---")

    except FileNotFoundError as e:
        print(f"Error: A data file was not found. {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    quantify_intraday_patterns()
