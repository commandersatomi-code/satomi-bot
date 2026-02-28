import pandas as pd
import numpy as np
import logging
import os

from . import config
from .core import strategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_exit_optimization(end_date=None, move_threshold_pct=3.00/100,
                          tp_range=None, sl_range=None, move_window_hours=6):

    if tp_range is None:
        tp_range = [0.05, 0.10, 0.15, 0.20, 0.25] # 5% to 25%
    if sl_range is None:
        sl_range = [-0.03, -0.05, -0.07, -0.10, -0.12, -0.15] # -3% to -15%

    logging.info(f"--- Starting Exit Strategy Optimization for MOVE_THRESHOLD_PCT: {move_threshold_pct*100:.2f}% ---")
    logging.info(f"TP Range: {[f'{tp*100:.2f}%' for tp in tp_range]}")
    logging.info(f"SL Range: {[f'{sl*100:.2f}%' for sl in sl_range]}")

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

    # --- Identify Precursor Signals (based on validate_new_hypothesis logic) ---
    # This part is simplified to just identify the precursor candle index
    # and the expected direction (up_move or down_move)
    
    df['future_max_price'] = df['high'].rolling(window=move_window_hours).apply(lambda x: x.max(), raw=True).shift(-move_window_hours)
    df['future_min_price'] = df['low'].rolling(window=move_window_hours).apply(lambda x: x.min(), raw=True).shift(-move_window_hours)
    df['potential_up_move'] = (df['future_max_price'] - df['close']) / df['close']
    df['potential_down_move'] = (df['future_min_price'] - df['close']) / df['close']

    precursor_signals = [] # List of (timestamp, direction, entry_price)

    # Iterate through the DataFrame to find precursor signals
    for i in range(len(df)):
        p_row = df.iloc[i]
        p_index = p_row.name # Get timestamp of current candle

        # Check for BUY signal precursor
        is_low_volume_buy = p_row['vol_mult'] < 1.0
        is_small_body_buy = p_row['body_ratio'] < 0.4
        is_bearish_candle_buy = p_row['close'] < p_row['open']
        
        if is_low_volume_buy and is_small_body_buy and is_bearish_candle_buy:
            # Check if this precursor leads to a large UP move
            if p_row['potential_up_move'] >= move_threshold_pct:
                precursor_signals.append({'timestamp': p_index, 'direction': 'buy', 'entry_price': p_row['close']})

        # Check for SELL signal precursor
        is_low_volume_sell = p_row['vol_mult'] < 1.0
        is_small_body_sell = p_row['body_ratio'] < 0.4
        is_bullish_candle_sell = p_row['close'] > p_row['open']

        if is_low_volume_sell and is_small_body_sell and is_bullish_candle_sell:
            # Check if this precursor leads to a large DOWN move
            if p_row['potential_down_move'] <= -move_threshold_pct:
                precursor_signals.append({'timestamp': p_index, 'direction': 'sell', 'entry_price': p_row['close']})
    
    logging.info(f"Found {len(precursor_signals)} precursor signals for optimization.")

    best_expected_value = -np.inf
    best_tp = None
    best_sl = None
    
    results_summary = []

    # --- Iterate through TP/SL combinations ---
    for tp in tp_range:
        for sl in sl_range:
            total_profit_loss = 0
            num_trades = 0
            
            for signal in precursor_signals:
                num_trades += 1
                entry_price = signal['entry_price']
                direction = signal['direction']
                precursor_timestamp = signal['timestamp']

                # Find the index of the entry candle (the candle *after* the precursor)
                entry_candle_idx = df.index.get_loc(precursor_timestamp) + 1
                if entry_candle_idx >= len(df):
                    continue # Not enough data after precursor

                # Slice the DataFrame for the trade duration (move_window_hours)
                trade_df = df.iloc[entry_candle_idx : entry_candle_idx + (move_window_hours * 4)] # 15min candles, 4 per hour

                if trade_df.empty:
                    continue # Not enough data for trade simulation

                trade_outcome = 0 # PnL for this trade

                # Simulate trade
                for _, current_candle in trade_df.iterrows():
                    trade_outcome = 0
                    sl_hit = False
                    tp_hit = False

                    if direction == 'buy':
                        # Check for SL first
                        if current_candle['low'] <= entry_price * (1 + sl):
                            sl_hit = True
                        # Check for TP
                        if current_candle['high'] >= entry_price * (1 + tp):
                            tp_hit = True
                    elif direction == 'sell':
                        # Check for SL first
                        if current_candle['high'] >= entry_price * (1 - sl):
                            sl_hit = True
                        # Check for TP
                        if current_candle['low'] <= entry_price * (1 - tp):
                            tp_hit = True
                    
                    if sl_hit:
                        trade_outcome = sl
                        break
                    if tp_hit:
                        trade_outcome = tp
                        break
                else:
                    # If loop completes without hitting TP/SL, close at the end of move_window_hours
                    final_price = trade_df.iloc[-1]['close']
                    if direction == 'buy':
                        trade_outcome = (final_price - entry_price) / entry_price
                    elif direction == 'sell':
                        trade_outcome = (entry_price - final_price) / entry_price
                
                total_profit_loss += trade_outcome
            
            if num_trades > 0:
                expected_value_per_trade = total_profit_loss / num_trades
                results_summary.append({
                    'TP': tp,
                    'SL': sl,
                    'Num Trades': num_trades,
                    'Total PnL': total_profit_loss,
                    'Expected Value per Trade': expected_value_per_trade
                })

                if expected_value_per_trade > best_expected_value:
                    best_expected_value = expected_value_per_trade
                    best_tp = tp
                    best_sl = sl

    logging.info("\n--- Optimization Results Summary ---")
    if results_summary:
        # Sort results by Expected Value per Trade in descending order
        results_summary.sort(key=lambda x: x['Expected Value per Trade'], reverse=True)
        
        logging.info("TP (%) | SL (%) | Num Trades | Total PnL (%) | Expected Value per Trade (%)")
        logging.info("--------------------------------------------------------------------------------")
        for res in results_summary:
            logging.info(f"{res['TP']*100:.2f}   | {res['SL']*100:.2f}   | {res['Num Trades']:<10} | {res['Total PnL']*100:.2f}      | {res['Expected Value per Trade']*100:.2f}")
        
        logging.info(f"\nBest TP: {best_tp*100:.2f}% | Best SL: {best_sl*100:.2f}% | Best Expected Value per Trade: {best_expected_value*100:.2f}%")
    else:
        logging.info("No trades simulated. Check precursor signals or data.")

if __name__ == '__main__':
    run_exit_optimization(end_date='2024-11-15')
