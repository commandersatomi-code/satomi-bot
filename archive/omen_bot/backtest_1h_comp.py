import pandas as pd
import numpy as np
import logging
import os
from datetime import timedelta

# Configure logging for the backtest script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# 1. STRATEGY PARAMETERS (Copied from omen_bot/live_bot.py)
# ==============================================================================

STRATEGY_PARAMS = {
    "SELL": {
        "HighestQuality": {"vol_mult": 1.6, "body_ratio": 0.6},
        "Balanced":       {"vol_mult": 1.6, "body_ratio": 0.6},
        "Action":         {"vol_mult": 1.6, "body_ratio": 0.6}
    },
    "BUY": {
        "HighestQuality": {"vol_mult": 1.4, "body_ratio": 0.6},
        "Balanced":       {"vol_mult": 1.4, "body_ratio": 0.6},
        "Action":         {"vol_mult": 1.4, "body_ratio": 0.6}
    }
}

# ==============================================================================
# 2. CORE BOT LOGIC (Adapted from omen_bot/live_bot.py)
# ==============================================================================

def calculate_indicators(df, atr_period=14, vol_sma_period=20):
    df['high_low'] = df['high'] - df['low']
    df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
    df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
    df['atr'] = df['true_range'].ewm(span=atr_period, adjust=False).mean()
    df['volume_sma'] = df['volume'].rolling(window=vol_sma_period).mean()
    return df

def check_for_signals(candle_data):
    """Checks a single candle for any of the defined signals and returns the signal type (BUY/SELL) and quality."""

    # --- Check for SELL signals ---
    for quality, params in STRATEGY_PARAMS["SELL"].items():
        is_high_volume = candle_data['volume'] > (candle_data['volume_sma'] * params["vol_mult"])
        is_bullish_candle = candle_data['close'] > candle_data['open']
        candle_body_size = candle_data['close'] - candle_data['open']
        is_small_body = candle_body_size < (candle_data['atr'] * params["body_ratio"])

        if is_high_volume and is_bullish_candle and is_small_body:
            return "SELL", quality

    # --- Check for BUY signals ---
    for quality, params in STRATEGY_PARAMS["BUY"].items():
        is_high_volume = candle_data['volume'] > (candle_data['volume_sma'] * params["vol_mult"])
        is_bearish_candle = candle_data['close'] < candle_data['open']
        candle_body_size = abs(candle_data['close'] - candle_data['open'])
        is_small_body = candle_body_size < (candle_data['atr'] * params["body_ratio"])

        if is_high_volume and is_bearish_candle and is_small_body:
            return "BUY", quality

    return None, None # No signal detected

# ==============================================================================
# 3. BACKTESTING LOGIC
# ==============================================================================

def run_backtest(df, initial_jpy_capital, jpy_usdt_rate, trading_fee_rate):
    logging.info(f"Starting backtest with initial JPY capital: {initial_jpy_capital:,} JPY")
    logging.info(f"JPY/USDT conversion rate: 1 USDT = {jpy_usdt_rate} JPY")
    logging.info(f"Trading fee rate: {trading_fee_rate * 100}% per trade")

    current_usdt_capital = initial_jpy_capital / jpy_usdt_rate
    btc_holdings = 0.0
    in_position = False
    entry_price = 0.0
    trade_log = []

    logging.info(f"Initial USDT capital: {current_usdt_capital:,.2f} USDT")

    # Calculate indicators for the entire DataFrame
    df = calculate_indicators(df)

    # Drop rows with NaN values that result from indicator calculations (e.g., first 20 rows for SMA)
    df.dropna(inplace=True)

    if df.empty:
        logging.warning("DataFrame is empty after dropping NaN values. Cannot run backtest.")
        return

    for index, candle in df.iterrows():
        signal, quality = check_for_signals(candle)

        # --- Handle BUY signal ---
        if signal == "BUY" and not in_position:
            if current_usdt_capital > 0:
                # Buy BTC with all available USDT
                btc_to_buy = (current_usdt_capital * (1 - trading_fee_rate)) / candle['close']
                btc_holdings = btc_to_buy
                entry_price = candle['close']
                current_usdt_capital = 0.0
                in_position = True
                trade_log.append({
                    'date': index,
                    'type': 'BUY',
                    'price': entry_price,
                    'btc_amount': btc_holdings,
                    'usdt_capital_after_trade': current_usdt_capital,
                    'btc_holdings_after_trade': btc_holdings,
                    'signal_quality': quality
                })
                logging.info(f"{index.strftime('%Y-%m-%d')}: BUY signal ({quality}) at {entry_price:,.2f}. Bought {btc_holdings:.6f} BTC.")
            else:
                logging.info(f"{index.strftime('%Y-%m-%d')}: BUY signal ({quality}) but no USDT capital.")

        # --- Handle SELL signal ---
        elif signal == "SELL" and in_position:
            # Sell all held BTC
            usdt_received = btc_holdings * candle['close'] * (1 - trading_fee_rate)
            profit_usdt = usdt_received - (entry_price * btc_holdings) # Profit based on initial BTC amount

            current_usdt_capital = usdt_received # Reinvest all profits
            btc_holdings = 0.0
            in_position = False

            trade_log.append({
                'date': index,
                'type': 'SELL',
                'price': candle['close'],
                'btc_amount': btc_holdings, # 0 after selling
                'usdt_capital_after_trade': current_usdt_capital,
                'btc_holdings_after_trade': btc_holdings,
                'profit_usdt': profit_usdt,
                'signal_quality': quality
            })
            logging.info(f"{index.strftime('%Y-%m-%d')}: SELL signal ({quality}) at {candle['close']:,.2f}. Sold all BTC. Profit: {profit_usdt:,.2f} USDT. New capital: {current_usdt_capital:,.2f} USDT.")

    # --- Final Calculation ---
    final_usdt_value = current_usdt_capital
    if in_position:
        # If still in position, value BTC holdings at the last close price
        final_usdt_value += btc_holdings * df.iloc[-1]['close']
        logging.info(f"Backtest ended with an open position. Valuing {btc_holdings:.6f} BTC at {df.iloc[-1]['close']:,.2f} USDT.")

    final_jpy_value = final_usdt_value * jpy_usdt_rate
    total_profit_jpy = final_jpy_value - initial_jpy_capital

    logging.info("==================================================")
    logging.info(f"Backtest Finished: {df.index.min().strftime('%Y-%m-%d')} to {df.index.max().strftime('%Y-%m-%d')}")
    logging.info(f"Initial JPY Capital: {initial_jpy_capital:,.0f} JPY")
    logging.info(f"Final JPY Value: {final_jpy_value:,.0f} JPY")
    logging.info(f"Total Profit/Loss: {total_profit_jpy:,.0f} JPY ({total_profit_jpy / initial_jpy_capital * 100:,.2f}%)")
    logging.info(f"Number of Trades: {len([t for t in trade_log if t['type'] == 'BUY'])}")
    logging.info("==================================================")

    return final_jpy_value, trade_log

# ==============================================================================
# 4. MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    data_file_path = "/Users/mucbook/バシャール/omen_bot/data/bybit_btc_usdt_linear_1h_full.csv"

    if not os.path.exists(data_file_path):
        logging.error(f"Data file not found: {data_file_path}. Please ensure the data is fetched first.")
        exit()

    df = pd.read_csv(data_file_path, parse_dates=['timestamp'], index_col='timestamp')

    # Ensure data is sorted by timestamp
    df.sort_index(inplace=True)

    # --- Exclude the last year of data for holdout testing ---
    last_date = df.index.max()
    one_year_ago = last_date - timedelta(days=365)
    backtest_df = df[df.index < one_year_ago]
    logging.info(f"Full data range: {df.index.min().strftime('%Y-%m-%d')} to {df.index.max().strftime('%Y-%m-%d')}")
    logging.info(f"Excluding data from {one_year_ago.strftime('%Y-%m-%d')} onwards for holdout.")
    logging.info(f"Backtest data range: {backtest_df.index.min().strftime('%Y-%m-%d')} to {backtest_df.index.max().strftime('%Y-%m-%d')}")
    # ---------------------------------------------------------

    # Backtest parameters
    INITIAL_JPY_CAPITAL = 100000  # 10万円
    JPY_USDT_RATE = 150           # 仮定: 1 USDT = 150 JPY
    TRADING_FEE_RATE = 0.001      # 0.1% fee per trade

    final_value, trades = run_backtest(backtest_df.copy(), INITIAL_JPY_CAPITAL, JPY_USDT_RATE, TRADING_FEE_RATE)

    # Optionally save trade log
    trade_log_df = pd.DataFrame(trades)
    output_path = "/Users/mucbook/バシャール/omen_bot/data/backtest_trade_log_1h_comp.csv"
    trade_log_df.to_csv(output_path)
    logging.info(f"Trade log saved to {output_path}")