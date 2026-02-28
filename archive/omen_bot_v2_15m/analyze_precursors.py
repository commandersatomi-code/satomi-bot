# ==============================================================================
# Omen Bot V2 - New Hypothesis Validator
# ==============================================================================
# This script validates the "calm before the storm" hypothesis.
# It checks what percentage of large price moves are preceded by a signal
# defined by LOW volume and a SMALL candle body.
# ==============================================================================

import pandas as pd
import numpy as np
import logging
from collections import Counter # 追加

# Import the new v2 modules
from . import config
from .core import strategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ヘルパー関数を追加
def is_bullish(candle):
    return candle['close'] > candle['open']

def is_bearish(candle):
    return candle['close'] < candle['open']

def get_candle_pattern(df_segment):
    pattern = []
    for _, candle in df_segment.iterrows():
        if is_bullish(candle):
            pattern.append('B') # Bullish (陽線)
        elif is_bearish(candle):
            pattern.append('R') # Bearish (陰線)
        else:
            pattern.append('D') # Doji or neutral (どちらでもない)
    return "".join(pattern)

def validate_new_hypothesis(end_date=None, move_threshold_pct=0.7/100, move_window_hours=6): # move_window_hoursを引数に追加
    # --- Analysis Parameters ---
    # MOVE_WINDOW_HOURS = 6 # 引数から受け取る
    PRECURSOR_WINDOW_HOURS = 6

    # --- New Signal Definition ---
    NEW_BUY_VOL_MULT_MAX = 1.0
    NEW_BUY_BODY_RATIO_MAX = 0.4

    NEW_SELL_VOL_MULT_MAX = 1.0  # Let's test the same logic for sells
    NEW_SELL_BODY_RATIO_MAX = 0.4

    logging.info("Starting new hypothesis validation: 'Calm before the storm'.")
    logging.info(f"New BUY Signal: vol_mult < {NEW_BUY_VOL_MULT_MAX} AND body_ratio < {NEW_BUY_BODY_RATIO_MAX} AND bearish candle")
    logging.info(f"New SELL Signal: vol_mult < {NEW_SELL_VOL_MULT_MAX} AND body_ratio < {NEW_SELL_BODY_RATIO_MAX} AND bullish candle")

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

    # --- 1. Find all Large Moves ---
    df['future_max_price'] = df['high'].rolling(window=move_window_hours).apply(lambda x: x.max(), raw=True).shift(-move_window_hours)
    df['future_min_price'] = df['low'].rolling(window=move_window_hours).apply(lambda x: x.min(), raw=True).shift(-move_window_hours)
    df['potential_up_move'] = (df['future_max_price'] - df['close']) / df['close']
    df['potential_down_move'] = (df['future_min_price'] - df['close']) / df['close']

    up_moves = df[df['potential_up_move'] >= move_threshold_pct] # 引数を使用
    down_moves = df[df['potential_down_move'] <= -move_threshold_pct] # 引数を使用

    total_days = (df.index.max() - df.index.min()).days
    if total_days == 0: total_days = 1
    
    logging.info(f"Found {len(up_moves)} candles preceding a large UP move (Frequency: {len(up_moves) / total_days:.2f}/day).")
    logging.info(f"Found {len(down_moves)} candles preceding a large DOWN move (Frequency: {len(down_moves) / total_days:.2f}/day).")

    # --- 2. Analyze Precursors for the NEW Signal ---
    up_move_signals = 0
    up_move_pattern_outcomes = {}
    all_precursor_timestamps = [] # 追加

    for index, row in up_moves.iterrows():
        precursor_start_time = index - pd.Timedelta(hours=PRECURSOR_WINDOW_HOURS)
        precursor_df = df.loc[precursor_start_time:index]
        
        for p_index, p_row in precursor_df.iterrows():
            # NEW HYPOTHESIS LOGIC FOR BUY
            is_low_volume = p_row['vol_mult'] < NEW_BUY_VOL_MULT_MAX
            is_small_body = p_row['body_ratio'] < NEW_BUY_BODY_RATIO_MAX
            is_bearish_candle = p_row['close'] < p_row['open']
            
            if is_low_volume and is_small_body and is_bearish_candle:
                up_move_signals += 1
                all_precursor_timestamps.append(p_index) # タイムスタンプを収集
                precursor_candle_idx = df.index.get_loc(p_index)
                if precursor_candle_idx >= 2 and precursor_candle_idx + 2 < len(df):
                    pattern_segment = df.iloc[precursor_candle_idx-2 : precursor_candle_idx+3]
                    if len(pattern_segment) == 5:
                        pattern_str = get_candle_pattern(pattern_segment)
                        if pattern_str not in up_move_pattern_outcomes:
                            up_move_pattern_outcomes[pattern_str] = []
                        up_move_pattern_outcomes[pattern_str].append(row['potential_up_move'])
                break

    down_move_signals = 0
    down_move_pattern_outcomes = {}
    for index, row in down_moves.iterrows():
        precursor_start_time = index - pd.Timedelta(hours=PRECURSOR_WINDOW_HOURS)
        precursor_df = df.loc[precursor_start_time:index]

        for p_index, p_row in precursor_df.iterrows():
            # NEW HYPOTHESIS LOGIC FOR SELL
            is_low_volume = p_row['vol_mult'] < NEW_SELL_VOL_MULT_MAX
            is_small_body = p_row['body_ratio'] < NEW_SELL_BODY_RATIO_MAX
            is_bullish_candle = p_row['close'] > p_row['open']

            if is_low_volume and is_small_body and is_bullish_candle:
                down_move_signals += 1
                all_precursor_timestamps.append(p_index) # タイムスタンプを収集
                precursor_candle_idx = df.index.get_loc(p_index)
                if precursor_candle_idx >= 2 and precursor_candle_idx + 2 < len(df):
                    pattern_segment = df.iloc[precursor_candle_idx-2 : precursor_candle_idx+3]
                    if len(pattern_segment) == 5:
                        pattern_str = get_candle_pattern(pattern_segment)
                        if pattern_str not in down_move_pattern_outcomes:
                            down_move_pattern_outcomes[pattern_str] = []
                        down_move_pattern_outcomes[pattern_str].append(row['potential_down_move'])
                break

    # 前兆間の期間分析を追加
    all_precursor_timestamps = sorted(list(set(all_precursor_timestamps))) # 重複を削除しソート
    time_diffs = []
    if len(all_precursor_timestamps) > 1:
        time_diffs = [(all_precursor_timestamps[i] - all_precursor_timestamps[i-1]).total_seconds() / 3600 for i in range(1, len(all_precursor_timestamps))] # 時間単位
    
    avg_time_between_precursors = np.mean(time_diffs) if time_diffs else 0
    min_time_between_precursors = np.min(time_diffs) if time_diffs else 0
    max_time_between_precursors = np.max(time_diffs) if time_diffs else 0

    logging.info(f"--- Precursor Interval Analysis ---")
    logging.info(f"Total unique precursors found: {len(all_precursor_timestamps)}")
    logging.info(f"Average time between precursors: {avg_time_between_precursors:.2f} hours")
    logging.info(f"Min time between precursors: {min_time_between_precursors:.2f} hours")
    logging.info(f"Max time between precursors: {max_time_between_precursors:.2f} hours")

    # --- 3. Report Results ---
    # logging.info("--- New Hypothesis Analysis Results ---") # この行はrun_threshold_analysisで出力
    
    avg_up_outcome = np.mean([val for sublist in up_move_pattern_outcomes.values() for val in sublist]) if up_move_pattern_outcomes else 0
    avg_down_outcome = np.mean([val for sublist in down_move_pattern_outcomes.values() for val in sublist]) if down_move_pattern_outcomes else 0

    results = {
        "move_threshold_pct": move_threshold_pct,
        "up_move_frequency_per_day": len(up_moves) / total_days,
        "avg_up_move_outcome": avg_up_outcome,
        "buy_signal_effectiveness": (up_move_signals / len(up_moves)) * 100 if len(up_moves) > 0 else 0,
        "down_move_frequency_per_day": len(down_moves) / total_days,
        "avg_down_move_outcome": avg_down_outcome,
        "sell_signal_effectiveness": (down_move_signals / len(down_moves)) * 100 if len(down_moves) > 0 else 0,
        "avg_time_between_precursors_hours": avg_time_between_precursors, # 結果に追加
        "min_time_between_precursors_hours": min_time_between_precursors, # 結果に追加
        "max_time_between_precursors_hours": max_time_between_precursors, # 結果に追加
    }
    # logging.info(f"Results for {move_threshold_pct*100:.2f}%: {results}") # run_threshold_analysisで出力するためコメントアウト
    return results # 結果を返すように変更

def run_threshold_analysis(end_date=None, thresholds=None, move_window_hours=6): # move_window_hoursを引数に追加
    if thresholds is None:
        thresholds = [0.7, 1.0, 1.5, 2.0, 3.0] # デフォルトの閾値リスト
    
    all_results = []
    for threshold_pct in thresholds:
        result = validate_new_hypothesis(end_date=end_date, move_threshold_pct=threshold_pct/100, move_window_hours=move_window_hours) # move_window_hoursを渡す
        if result:
            all_results.append(result)
    
    logging.info("\n--- Summary of Threshold Analysis ---")
    logging.info("Threshold | UP Freq/Day | Avg UP Move | BUY Eff (%) | DOWN Freq/Day | Avg DOWN Move | SELL Eff (%)")
    logging.info("----------------------------------------------------------------------------------------------------")
    for res in all_results:
        logging.info(f"{res['move_threshold_pct']*100:.2f}%    | {res['up_move_frequency_per_day']:.2f}      | {res['avg_up_move_outcome']:.2%}     | {res['buy_signal_effectiveness']:.2f}      | {res['down_move_frequency_per_day']:.2f}        | {res['avg_down_move_outcome']:.2%}      | {res['sell_signal_effectiveness']:.2f}")

if __name__ == '__main__':
    # validate_new_hypothesis(end_date='2024-11-15') # 以前の呼び出しをコメントアウト
    run_threshold_analysis(end_date='2024-11-15') # 新しい分析関数を呼び出す