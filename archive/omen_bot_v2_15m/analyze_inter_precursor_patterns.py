import pandas as pd
import numpy as np
import logging
import os

from . import config
from .core import strategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def analyze_inter_precursor_patterns(end_date=None, move_threshold_pct=3.00/100, move_window_hours=6):
    logging.info(f"--- Starting Inter-Precursor Pattern Analysis ---")
    logging.info(f"MOVE_THRESHOLD_PCT: {move_threshold_pct*100:.2f}%")
    logging.info(f"MOVE_WINDOW_HOURS: {move_window_hours} hours")

    # --- Load Data ---
    try:
        df = pd.read_csv(config.PRICE_DATA_PATH, parse_dates=['timestamp'], index_col='timestamp')
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]
            logging.info(f"Data filtered up to {end_date}.")
        df = strategy.calculate_indicators(df)
        df.dropna(inplace=True)
        logging.info(f"Data loaded. Analyzing {len(df)} candles.")
    except FileNotFoundError:
        logging.error(f"Error: Price data not found at {config.PRICE_DATA_PATH}.")
        return

    # --- Identify Precursor Signals ---
    # Calculate potential future moves based on the specified move_window_hours
    df['future_max_price'] = df['high'].rolling(window=move_window_hours*4).apply(lambda x: x.max(), raw=True).shift(-move_window_hours*4)
    df['future_min_price'] = df['low'].rolling(window=move_window_hours*4).apply(lambda x: x.min(), raw=True).shift(-move_window_hours*4)
    df['potential_up_move'] = (df['future_max_price'] - df['close']) / df['close']
    df['potential_down_move'] = (df['future_min_price'] - df['close']) / df['close']

    precursor_signals = [] # List of {'timestamp', 'direction', 'entry_price'}

    for i in range(len(df)):
        p_row = df.iloc[i]
        p_index = p_row.name # Get timestamp of current candle

        # Check for BUY signal precursor
        is_low_volume_buy = p_row['vol_mult'] < 1.0
        is_small_body_buy = p_row['body_ratio'] < 0.4
        is_bearish_candle_buy = p_row['close'] < p_row['open']
        
        if is_low_volume_buy and is_small_body_buy and is_bearish_candle_buy:
            if p_row['potential_up_move'] >= move_threshold_pct:
                precursor_signals.append({'timestamp': p_index, 'direction': 'buy', 'entry_price': p_row['close']})

        # Check for SELL signal precursor
        is_low_volume_sell = p_row['vol_mult'] < 1.0
        is_small_body_sell = p_row['body_ratio'] < 0.4
        is_bullish_candle_sell = p_row['close'] > p_row['open']

        if is_low_volume_sell and is_small_body_sell and is_bullish_candle_sell:
            if p_row['potential_down_move'] <= -move_threshold_pct:
                precursor_signals.append({'timestamp': p_index, 'direction': 'sell', 'entry_price': p_row['close']})
    
    logging.info(f"Found {len(precursor_signals)} precursor signals.")

    if len(precursor_signals) < 2:
        logging.info("Not enough precursor signals to analyze inter-precursor patterns.")
        return

    # --- Analyze Inter-Precursor Patterns ---
    inter_precursor_data = {
        'buy_to_buy': [],
        'buy_to_sell': [],
        'sell_to_buy': [],
        'sell_to_sell': []
    }

    for i in range(len(precursor_signals) - 1):
        sig1 = precursor_signals[i]
        sig2 = precursor_signals[i+1]

        # Ensure sig2 is after sig1
        if sig2['timestamp'] <= sig1['timestamp']:
            continue

        # Get data between sig1 and sig2
        inter_period_df = df.loc[sig1['timestamp'] : sig2['timestamp']].iloc[1:-1] # Exclude signal candles themselves

        if inter_period_df.empty:
            max_rise_pct = 0
            max_fall_pct = 0
        else:
            entry_price = sig1['entry_price']
            highest_high = inter_period_df['high'].max()
            lowest_low = inter_period_df['low'].min()
            max_rise_pct = (highest_high - entry_price) / entry_price if entry_price != 0 else 0
            max_fall_pct = (lowest_low - entry_price) / entry_price if entry_price != 0 else 0

        duration_hours = (sig2['timestamp'] - sig1['timestamp']).total_seconds() / 3600

        pattern_type = f"{sig1['direction']}_to_{sig2['direction']}"
        if pattern_type in inter_precursor_data:
            inter_precursor_data[pattern_type].append({
                'duration_hours': duration_hours,
                'max_rise_pct': max_rise_pct,
                'max_fall_pct': max_fall_pct,
            })

    # --- Report Results and Save to CSV ---
    logging.info("\n--- Inter-Precursor Pattern Analysis Summary ---")
    output_dir = os.path.dirname(config.PRICE_DATA_PATH) # Save in the same directory as the data

    for pattern_type, data_list in inter_precursor_data.items():
        if not data_list:
            logging.info(f"Pattern: {pattern_type.replace('_', ' to ').title()} - No occurrences.")
            continue

        # Create DataFrame for analysis and saving
        pattern_df = pd.DataFrame(data_list)
        
        # Log summary statistics
        logging.info(f"Pattern: {pattern_type.replace('_', ' to ').title()} ({len(pattern_df)} occurrences)")
        logging.info(f"  - Avg Duration: {pattern_df['duration_hours'].mean():.2f} hours")
        logging.info(f"  - Avg Max Rise: {pattern_df['max_rise_pct'].mean()*100:.2f}%")
        logging.info(f"  - Avg Max Fall: {pattern_df['max_fall_pct'].mean()*100:.2f}%")
        
        # Save the full data to a CSV file
        csv_filename = f"inter_precursor_{pattern_type}_move_window_{move_window_hours}h.csv"
        csv_path = os.path.join(output_dir, csv_filename)
        pattern_df.to_csv(csv_path, index=False)
        logging.info(f"  -> Saved detailed data to {csv_path}")

if __name__ == '__main__':
    # Use the 6-hour window for precursor identification as a baseline
    analyze_inter_precursor_patterns(end_date='2024-11-15', move_window_hours=6)
    # Also run for the "no time limit" scenario
    analyze_inter_precursor_patterns(end_date='2024-11-15', move_window_hours=9999)
