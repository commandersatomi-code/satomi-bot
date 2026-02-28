
import pandas as pd
import numpy as np
import itertools
import subprocess
import json
import os
from datetime import datetime, timedelta

# --- Configuration ---
BACKTEST_SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backtesting/backtest_rsi_compass_strategy.py'))
DATA_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/bybit_1000pepeusdt_linear_15m_full.csv'))

# --- Optimization Parameters ---
# Define the grid of parameters to search.
# Be careful with the number of combinations, as it can grow very quickly.
PARAM_GRID = {
    'tp_pct': [0.03, 0.05, 0.08, 0.10],
    'sl_pct': [-0.02, -0.03, -0.05],
    'atr_low': [0.01, 0.015, 0.02],
    'atr_high': [0.02, 0.025, 0.03]
}

# --- Data Splitting ---
# Use 80% for training, 20% for testing to prevent overfitting.
TRAIN_TEST_SPLIT_RATIO = 0.8

def run_single_backtest(params, start_date, end_date):
    """
    Runs the backtesting script with a given set of parameters
    and returns the Sharpe Ratio.
    """
    command = [
        'python3',
        BACKTEST_SCRIPT_PATH,
        '--json',
        f'--start_date={start_date}',
        f'--end_date={end_date}',
        f'--tp_pct={params["tp_pct"]}',
        f'--sl_pct={params["sl_pct"]}',
        f'--atr_low={params["atr_low"]}',
        f'--atr_high={params["atr_high"]}'
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        return output.get('sharpe_ratio', -999)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error running backtest for params {params}: {e}")
        # print(f"Stderr: {e.stderr if isinstance(e, subprocess.CalledProcessError) else 'N/A'}")
        return -999

def main():
    """
    Main function to run the optimization process.
    """
    print("--- Starting RSI Compass Strategy Optimization ---")

    # 1. Load data to determine the date range for splitting
    try:
        df = pd.read_csv(DATA_FILE, parse_dates=['timestamp'])
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
    except FileNotFoundError:
        print(f"FATAL: Data file not found at {DATA_FILE}. Cannot proceed.")
        return

    split_index = int(len(df) * TRAIN_TEST_SPLIT_RATIO)
    training_end_date = df.index[split_index]
    
    train_start_str = df.index[0].strftime('%Y-%m-%d')
    train_end_str = training_end_date.strftime('%Y-%m-%d')
    test_start_str = (training_end_date + timedelta(days=1)).strftime('%Y-%m-%d')
    test_end_str = df.index[-1].strftime('%Y-%m-%d')

    print(f"Training Period: {train_start_str} to {train_end_str}")
    print(f"Testing Period:  {test_start_str} to {test_end_str}")


    # 2. Create all combinations of parameters
    keys, values = zip(*PARAM_GRID.items())
    param_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    print(f"\nStarting grid search with {len(param_combinations)} parameter combinations...")

    best_sharpe = -float('inf')
    best_params = None

    # 3. Run backtest for each combination on the training data
    for i, params in enumerate(param_combinations):
        # Basic validation: SL must be negative, TP must be positive, atr_low < atr_high
        if params['sl_pct'] >= 0 or params['tp_pct'] <= 0 or params['atr_low'] >= params['atr_high']:
            continue

        print(f"  ({i+1}/{len(param_combinations)}) Testing params: {params}", end="", flush=True)
        sharpe_ratio = run_single_backtest(params, train_start_str, train_end_str)
        print(f" -> Sharpe: {sharpe_ratio:.2f}")

        if sharpe_ratio > best_sharpe:
            best_sharpe = sharpe_ratio
            best_params = params

    if best_params is None:
        print("\nOptimization failed. No valid results were returned from backtests.")
        return

    print(f"\n--- Optimization Complete ---")
    print(f"Best Sharpe Ratio (Training): {best_sharpe:.2f}")
    print(f"Best Parameters: {best_params}")


    # 4. Run the final backtest with the best parameters on the test data
    print("\n--- Running Final Backtest on Test Data (Out-of-Sample) ---")
    
    final_command = [
        'python3',
        BACKTEST_SCRIPT_PATH,
        f'--start_date={test_start_str}',
        f'--end_date={test_end_str}',
        f'--tp_pct={best_params["tp_pct"]}',
        f'--sl_pct={best_params["sl_pct"]}',
        f'--atr_low={best_params["atr_low"]}',
        f'--atr_high={best_params["atr_high"]}'
    ]
    
    # Run and print the full report
    subprocess.run(final_command)

if __name__ == "__main__":
    main()
