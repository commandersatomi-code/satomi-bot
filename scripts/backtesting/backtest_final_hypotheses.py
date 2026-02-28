
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

def backtest_final_hypotheses(
    daily_file_path: str,
    intraday_file_path: str,
    intraday_drawdown_threshold: float = 6.0,
    strong_rebound_threshold: float = 4.0,
    weak_rebound_threshold: float = 3.5,
    move_threshold: float = 10.0
):
    """
    Backtests the final, refined hypotheses based on intraday precursor patterns.
    """
    print("--- Backtesting Final Hypotheses (Intraday Analysis) ---")
    print(f"Rise Signal: Drawdown > {intraday_drawdown_threshold}% AND Rebound > {strong_rebound_threshold}%")
    print(f"Fall Signal: Drawdown > {intraday_drawdown_threshold}% AND Rebound < {weak_rebound_threshold}%")

    try:
        # 1. Load and prepare data
        df_daily = pd.read_csv(daily_file_path, parse_dates=['timestamp'])
        df_intraday = pd.read_csv(intraday_file_path, parse_dates=['timestamp'])

        # Standardize timestamps to UTC
        for df in [df_daily, df_intraday]:
            if df['timestamp'].dt.tz is None:
                df['timestamp'] = df['timestamp'].dt.tz_localize('utc')
            else:
                df['timestamp'] = df['timestamp'].dt.tz_convert('utc')

        # 2. Select training period for the daily data
        split_date = datetime.now(timezone.utc) - timedelta(days=365) # Use timezone-aware split_date
        training_df = df_daily[df_daily['timestamp'] < split_date].copy()
        training_df['move_change_pct'] = 100 * (training_df['close'] - training_df['open']) / training_df['open']
        
        # 3. Calculate intraday metrics for each day in the training set
        precursor_metrics = []
        # We check the precursor day for each day in the training set
        for index, row in training_df.iterrows():
            # The precursor day is the day before the current 'row'
            precursor_day_start = row['timestamp'] - timedelta(days=1)
            precursor_day_end = row['timestamp']
            
            # Filter the 4h data for this specific precursor day
            intraday_df = df_intraday[
                (df_intraday['timestamp'] >= precursor_day_start) & 
                (df_intraday['timestamp'] < precursor_day_end)
            ]

            if intraday_df.empty or len(intraday_df) < 2:
                precursor_metrics.append({'intraday_max_drawdown_pct': np.nan, 'rebound_from_low_pct': np.nan})
                continue

            # Calculate metrics for the precursor day
            day_open = intraday_df['open'].iloc[0]
            day_close = intraday_df['close'].iloc[-1]
            day_high = intraday_df['high'].max()
            day_low = intraday_df['low'].min()
            
            running_max = intraday_df['high'].cummax()
            drawdown = (running_max - intraday_df['low']) / running_max
            max_drawdown = drawdown.max() * 100 if not drawdown.empty else 0
            rebound = ((day_close - day_low) / day_low) * 100 if day_low != 0 else 0
            
            precursor_metrics.append({'intraday_max_drawdown_pct': max_drawdown, 'rebound_from_low_pct': rebound})

        # Add calculated metrics to the daily training dataframe
        metrics_df = pd.DataFrame(precursor_metrics, index=training_df.index)
        training_df = pd.concat([training_df, metrics_df], axis=1)
        training_df.dropna(inplace=True)

        # 4. Identify Signals
        # Rise Signal: "Strong Rebound"
        rise_signals = training_df[
            (training_df['intraday_max_drawdown_pct'] > intraday_drawdown_threshold) &
            (training_df['rebound_from_low_pct'] > strong_rebound_threshold)
        ]

        # Fall Signal: "Weak Rebound"
        fall_signals = training_df[
            (training_df['intraday_max_drawdown_pct'] > intraday_drawdown_threshold) &
            (training_df['rebound_from_low_pct'] < weak_rebound_threshold)
        ]

        # 5. Test Signals and Report Results
        print("\n" + "="*60)
        print("    FINAL BACKTEST RESULTS")
        print("="*60)

        # Rise Signal Results
        total_rise_signals = len(rise_signals)
        successful_rises = rise_signals[rise_signals['move_change_pct'] >= move_threshold]
        num_successful_rises = len(successful_rises)
        rise_success_rate = (num_successful_rises / total_rise_signals) * 100 if total_rise_signals > 0 else 0
        
        print("\n--- 'Strong Rebound' (RISE) Signal ---")
        print(f"Total signals found: {total_rise_signals}")
        print(f"Successful predictions (move >= {move_threshold}%): {num_successful_rises}")
        print(f"Success Rate (Precision): {rise_success_rate:.2f}%")

        # Fall Signal Results
        total_fall_signals = len(fall_signals)
        successful_falls = fall_signals[fall_signals['move_change_pct'] <= -move_threshold]
        num_successful_falls = len(successful_falls)
        fall_success_rate = (num_successful_falls / total_fall_signals) * 100 if total_fall_signals > 0 else 0
        
        print("\n--- 'Weak Rebound' (FALL) Signal ---")
        print(f"Total signals found: {total_fall_signals}")
        print(f"Successful predictions (move <= -{move_threshold}%): {num_successful_falls}")
        print(f"Success Rate (Precision): {fall_success_rate:.2f}%")

    except FileNotFoundError as e:
        print(f"Error: A data file was not found. {e}")
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    backtest_final_hypotheses(
        daily_file_path='data/bybit_btc_usdt_linear_daily_full.csv',
        intraday_file_path='data/bybit_btc_usdt_linear_4h_full.csv'
    )
