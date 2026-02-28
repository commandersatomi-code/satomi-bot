# ==============================================================================
# Omen Bot - Core Strategy Logic
# ==============================================================================
# This module contains the pure logic for generating trading signals and
# determining trade actions based on market data and current position state.
# It is configured via the central config.py file.
# ==============================================================================

import pandas as pd
import numpy as np # Added for pd.NA handling

# Import the central configuration
try:
    from .. import config
except ImportError:
    print("Error: Could not import config.py. Make sure it's in the 'omen_bot' directory.")
    exit()

def calculate_indicators(df, atr_period=14, vol_sma_period=20, long_sma_period=None):
    """
    Calculates technical indicators required for the strategy and adds them
    to the DataFrame.
    
    Args:
        df (pd.DataFrame): DataFrame with at least 'high', 'low', 'close', 'volume' columns.
        atr_period (int): The period for calculating ATR.
        vol_sma_period (int): The period for the volume SMA.
        long_sma_period (int): The period for the long-term SMA trend filter.

    Returns:
        pd.DataFrame: The DataFrame with added indicator columns.
    """
    if long_sma_period is None:
        long_sma_period = config.LONG_SMA_PERIOD

    # ATR Calculation
    if 'close' in df and len(df) > 1:
        df['high_low'] = df['high'] - df['low']
        df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
        df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
        df['atr'] = df['true_range'].ewm(span=atr_period, adjust=False).mean()
    
    # Volume Multiplier Calculation
    if 'volume' in df:
        df['volume_sma'] = df['volume'].rolling(window=vol_sma_period).mean()
        df['vol_mult'] = df['volume'] / df['volume_sma']

    # Body Ratio Calculation
    df['candle_range'] = df['high'] - df['low']
    df['body_size'] = abs(df['open'] - df['close'])
    df['body_ratio'] = df['body_size'] / df['candle_range']
    
    # Long-term SMA for Trend Filter
    df['long_sma'] = df['close'].rolling(window=long_sma_period).mean()

    # Handle potential division by zero if candle_range is 0
    df.replace([float('inf'), -float('inf')], pd.NA, inplace=True)
        
    return df

class MyStrategy:
    """
    Encapsulates the strategy's signal generation and trade decision logic.
    """
    def __init__(self):
        self.buy_signal_params = config.STRATEGY_PARAMS.get("BUY", {})
        self.sell_signal_params = config.STRATEGY_PARAMS.get("SELL", {})
        self.long_sma_period = config.LONG_SMA_PERIOD

    def check_for_signal(self, candle_data):
        """
        Checks a single candle for a BUY or SELL signal based on defined parameters and trend filter.
        Returns "BUY", "SELL", or None.
        """
        # Ensure long_sma is available for trend filtering
        if 'long_sma' not in candle_data or pd.isna(candle_data['long_sma']):
            return None

        # --- Trend Filter: Only Trade with the Trend ---
        is_uptrend = candle_data['close'] > candle_data['long_sma']
        is_downtrend = candle_data['close'] < candle_data['long_sma']

        # --- Check for BUY signal (Calm before the storm precursor to an UP move is a bearish candle) ---
        if is_uptrend: # Only consider BUY in an uptrend
            is_low_volume_buy = candle_data['vol_mult'] < self.buy_signal_params.get("vol_mult", 1.0)
            is_bearish_candle = candle_data['close'] < candle_data['open']
            is_small_body_buy = candle_data['body_ratio'] < self.buy_signal_params.get("body_ratio", 0.5) # Using pre-calculated body_ratio
            
            if is_low_volume_buy and is_small_body_buy and is_bearish_candle:
                return "BUY"

        # --- Check for SELL signal (Calm before the storm precursor to a DOWN move is a bullish candle) ---
        if is_downtrend: # Only consider SELL in a downtrend
            is_low_volume_sell = candle_data['vol_mult'] < self.sell_signal_params.get("vol_mult", 1.0)
            is_bullish_candle = candle_data['close'] > candle_data['open']
            is_small_body_sell = candle_data['body_ratio'] < self.sell_signal_params.get("body_ratio", 0.5) # Using pre-calculated body_ratio
            
            if is_low_volume_sell and is_small_body_sell and is_bullish_candle:
                return "SELL"

        return None

    def get_trade_action(self, signal, current_long_pos_size, current_short_pos_size):
        """
        Determines the trade action based on the signal and current position status,
        implementing pyramiding and no-reversing logic.

        Args:
            signal (str or None): "BUY", "SELL", or None from check_for_signal.
            current_long_pos_size (float): Current total size of long positions in BTC.
            current_short_pos_size (float): Current total size of short positions in BTC.

        Returns:
            str: Action to take ("OPEN_LONG", "ADD_LONG", "OPEN_SHORT", "ADD_SHORT", "HOLD").
        """
        if signal == "BUY":
            if current_short_pos_size > 0:
                return "HOLD" # Don't reverse, and don't close short for a buy signal
            elif current_long_pos_size > 0:
                return "ADD_LONG" # Pyramiding
            else:
                return "OPEN_LONG" # No long position, open new
        
        elif signal == "SELL":
            if current_long_pos_size > 0:
                return "HOLD" # Don't reverse, and don't close long for a sell signal
            elif current_short_pos_size > 0:
                return "ADD_SHORT" # Pyramiding
            else:
                return "OPEN_SHORT" # No short position, open new
        
        return "HOLD" # No signal or conflicting position