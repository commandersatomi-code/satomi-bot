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

def validate_new_hypothesis(end_date=None):
    # --- Analysis Parameters ---
    MOVE_WINDOW_HOURS = 6
    MOVE_THRESHOLD_PCT = 0.7 / 100
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
    df['future_max_price'] = df['high'].rolling(window=MOVE_WINDOW_HOURS).apply(lambda x: x.max(), raw=True).shift(-MOVE_WINDOW_HOURS)
    df['future_min_price'] = df['low'].rolling(window=MOVE_WINDOW_HOURS).apply(lambda x: x.min(), raw=True).shift(-MOVE_WINDOW_HOURS)
    df['potential_up_move'] = (df['future_max_price'] - df['close']) / df['close']
    df['potential_down_move'] = (df['future_min_price'] - df['close']) / df['close']

    up_moves = df[df['potential_up_move'] >= MOVE_THRESHOLD_PCT]
    down_moves = df[df['potential_down_move'] <= -MOVE_THRESHOLD_PCT]

    total_days = (df.index.max() - df.index.min()).days
    if total_days == 0: total_days = 1
    
    logging.info(f"Found {len(up_moves)} candles preceding a large UP move (Frequency: {len(up_moves) / total_days:.2f}/day).")
    logging.info(f"Found {len(down_moves)} candles preceding a large DOWN move (Frequency: {len(down_moves) / total_days:.2f}/day).")

    # --- 2. Analyze Precursors for the NEW Signal ---
    up_move_signals = 0
    up_move_pattern_outcomes = {} # 変更: Counterから辞書へ
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
                # パターン抽出ロジックを追加
                precursor_candle_idx = df.index.get_loc(p_index)
                if precursor_candle_idx >= 2 and precursor_candle_idx + 2 < len(df):
                    pattern_segment = df.iloc[precursor_candle_idx-2 : precursor_candle_idx+3] # -2, -1, 0, 1, 2
                    if len(pattern_segment) == 5:
                        pattern_str = get_candle_pattern(pattern_segment)
                        if pattern_str not in up_move_pattern_outcomes:
                            up_move_pattern_outcomes[pattern_str] = []
                        up_move_pattern_outcomes[pattern_str].append(row['potential_up_move']) # 関連する変動率を記録
                break

    down_move_signals = 0
    down_move_pattern_outcomes = {} # 変更: Counterから辞書へ
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
                # パターン抽出ロジックを追加
                precursor_candle_idx = df.index.get_loc(p_index)
                if precursor_candle_idx >= 2 and precursor_candle_idx + 2 < len(df):
                    pattern_segment = df.iloc[precursor_candle_idx-2 : precursor_candle_idx+3] # -2, -1, 0, 1, 2
                    if len(pattern_segment) == 5:
                        pattern_str = get_candle_pattern(pattern_segment)
                        if pattern_str not in down_move_pattern_outcomes:
                            down_move_pattern_outcomes[pattern_str] = []
                        down_move_pattern_outcomes[pattern_str].append(row['potential_down_move']) # 関連する変動率を記録
                break

    # --- 3. Report Results ---
    logging.info("--- New Hypothesis Analysis Results ---")
    if len(up_moves) > 0:
        up_signal_effectiveness = (up_move_signals / len(up_moves)) * 100
        logging.info(f"NEW BUY Signal Effectiveness: {up_signal_effectiveness:.2f}%")
        logging.info(f"  - Of all large UP moves, {up_signal_effectiveness:.2f}% were preceded by the new 'calm' BUY signal.")
        
        # 期待値の計算と報告
        avg_up_outcomes = {pattern: np.mean(outcomes) for pattern, outcomes in up_move_pattern_outcomes.items()}
        sorted_avg_up_outcomes = sorted(avg_up_outcomes.items(), key=lambda item: item[1], reverse=True)
        logging.info(f"Top 5 BUY Signal Candle Patterns by Average UP Move: {sorted_avg_up_outcomes[:5]}")
    else:
        logging.info("No large UP moves found to analyze.")

    if len(down_moves) > 0:
        down_signal_effectiveness = (down_move_signals / len(down_moves)) * 100
        logging.info(f"NEW SELL Signal Effectiveness: {down_signal_effectiveness:.2f}%")
        logging.info(f"  - Of all large DOWN moves, {down_signal_effectiveness:.2f}% were preceded by the new 'calm' SELL signal.")

        # 期待値の計算と報告
        avg_down_outcomes = {pattern: np.mean(outcomes) for pattern, outcomes in down_move_pattern_outcomes.items()}
        sorted_avg_down_outcomes = sorted(avg_down_outcomes.items(), key=lambda item: item[1]) # 下降なので昇順
        logging.info(f"Top 5 SELL Signal Candle Patterns by Average DOWN Move: {sorted_avg_down_outcomes[:5]}")
    else:
        logging.info("No large DOWN moves found to analyze.")

if __name__ == '__main__':
    validate_new_hypothesis()