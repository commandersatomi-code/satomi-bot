import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def backtest_new_hypotheses(
    file_path: str,
    window_size: int = 3,
    rise_drift_threshold: float = -2.0,
    fall_drift_threshold: float = -4.0,
    volatility_threshold: float = 10.0,
    move_threshold: float = 10.0
):
    """
    Backtests the new data-driven hypotheses for large move precursors.
    """
    print("--- Backtesting New Hypotheses ---")
    print(f"Parameters: window={window_size}d, rise_drift<{rise_drift_threshold}%, fall_drift<{fall_drift_threshold}%, vol>{volatility_threshold}%")

    try:
        # 1. Load data and select training period
        df = pd.read_csv(file_path, parse_dates=['timestamp'])
        split_date = datetime.now() - timedelta(days=365)
        training_df = df[df['timestamp'] < split_date].copy()
        
        if len(training_df) <= window_size:
            print("Not enough training data to perform backtest.")
            return

        # 2. Calculate the outcome (the move on the current day)
        training_df['move_change_pct'] = 100 * (training_df['close'] - training_df['open']) / training_df['open']

        # 3. Calculate rolling metrics for the precursor window (e.g., the 3 days *before* the current day)
        # We use .shift(1) to ensure we don't use the current day's data in the precursor calculation.
        rolling_window = training_df.shift(1).rolling(window=window_size)
        
        # We need the open from the start of the window, so we shift by `window_size`.
        open_at_window_start = training_df['open'].shift(window_size)
        
        # Metrics for the window
        high_in_window = rolling_window['high'].max()
        low_in_window = rolling_window['low'].min()
        close_at_window_end = training_df['close'].shift(1) # The close of the last day in the window

        # Calculate volatility and drift for the window
        training_df['precursor_volatility_pct'] = 100 * (high_in_window - low_in_window) / open_at_window_start
        training_df['precursor_drift_pct'] = 100 * (close_at_window_end - open_at_window_start) / open_at_window_start
        
        # Drop initial rows with NaN values from rolling calculations
        training_df.dropna(subset=['precursor_volatility_pct', 'precursor_drift_pct'], inplace=True)

        # 4. Identify days where the precursor signal was met
        # Rise Signal: "Crouch before the leap"
        rise_signal_df = training_df[
            (training_df['precursor_drift_pct'] < rise_drift_threshold) &
            (training_df['precursor_volatility_pct'] > volatility_threshold)
        ]

        # Fall Signal: "Run-up to ruin"
        fall_signal_df = training_df[
            (training_df['precursor_drift_pct'] < fall_drift_threshold) &
            (training_df['precursor_volatility_pct'] > volatility_threshold)
        ]

        # 5. Test the signals
        # Test Rise Signal
        total_rise_signals = len(rise_signal_df)
        successful_rises = rise_signal_df[rise_signal_df['move_change_pct'] >= move_threshold]
        num_successful_rises = len(successful_rises)
        rise_success_rate = (num_successful_rises / total_rise_signals) * 100 if total_rise_signals > 0 else 0

        # Test Fall Signal
        total_fall_signals = len(fall_signal_df)
        successful_falls = fall_signal_df[fall_signal_df['move_change_pct'] <= -move_threshold]
        num_successful_falls = len(successful_falls)
        fall_success_rate = (num_successful_falls / total_fall_signals) * 100 if total_fall_signals > 0 else 0


        # 6. Report Results
        print("\n" + "="*60)
        print("    BACKTEST RESULTS")
        print("="*60)

        print("\n--- 'Crouch before the Leap' (RISE) Signal ---")
        print(f"Total signals found: {total_rise_signals}")
        print(f"Successful predictions (move >= {move_threshold}%): {num_successful_rises}")
        print(f"Success Rate (Precision): {rise_success_rate:.2f}%")

        print("\n--- 'Run-up to Ruin' (FALL) Signal ---")
        print(f"Total signals found: {total_fall_signals}")
        print(f"Successful predictions (move <= -{move_threshold}%): {num_successful_falls}")
        print(f"Success Rate (Precision): {fall_success_rate:.2f}%")

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    backtest_new_hypotheses(
        file_path='data/bybit_btc_usdt_linear_daily_full.csv'
    )
