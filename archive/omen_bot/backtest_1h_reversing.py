import pandas as pd
import numpy as np
import logging
import os

# Configure logging for the backtest script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# 1. STRATEGY PARAMETERS (Copied from omen_bot/live_bot.py)
# ==============================================================================

STRATEGY_PARAMS = {
    "SELL": {
        "HighestQuality": {"vol_mult": 2.0, "body_ratio": 0.3},
        "Balanced": {"vol_mult": 1.6, "body_ratio": 0.5},
        "Action": {"vol_mult": 1.2, "body_ratio": 0.6}
    },
    "BUY": {
        "HighestQuality": {"vol_mult": 2.0, "body_ratio": 0.3},
        "Balanced": {"vol_mult": 1.7, "body_ratio": 0.6},
        "Action": {"vol_mult": 1.3, "body_ratio": 0.6}
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

    usdt_capital = initial_jpy_capital / jpy_usdt_rate
    btc_holdings = 0.0
    position = None  # Can be 'LONG', 'SHORT', or None
    entry_price = 0.0
    trade_log = []

    logging.info(f"Initial USDT capital: {usdt_capital:,.2f} USDT")

    df = calculate_indicators(df)
    df.dropna(inplace=True)

    if df.empty:
        logging.warning("DataFrame is empty after dropping NaN values. Cannot run backtest.")
        return

    for index, candle in df.iterrows():
        if usdt_capital <= 0:
            logging.warning("Capital is zero or negative. Stopping backtest.")
            break
        signal, quality = check_for_signals(candle)

        # --- Handle BUY signal (go long) ---
        if signal == "BUY":
            if position == 'SHORT':
                # Close short position first
                profit = (entry_price - candle['close']) * btc_holdings * (1 - trading_fee_rate)
                usdt_capital += profit
                logging.info(f"{index.strftime('%Y-%m-%d %H:%M')}: CLOSE SHORT at {candle['close']:,.2f}. Profit: {profit:,.2f} USDT. New capital: {usdt_capital:,.2f} USDT.")
                trade_log.append({
                    'date': index, 'type': 'CLOSE_SHORT', 'price': candle['close'],
                    'btc_amount': btc_holdings, 'usdt_capital_after_trade': usdt_capital,
                    'profit_usdt': profit, 'signal_quality': quality
                })
                btc_holdings = 0.0
                position = None

            if position is None:
                # Open long position
                btc_to_buy = (usdt_capital * (1 - trading_fee_rate)) / candle['close']
                btc_holdings = btc_to_buy
                entry_price = candle['close']
                position = 'LONG'
                logging.info(f"{index.strftime('%Y-%m-%d %H:%M')}: OPEN LONG ({quality}) at {entry_price:,.2f}. Bought {btc_holdings:.6f} BTC.")
                trade_log.append({
                    'date': index, 'type': 'OPEN_LONG', 'price': entry_price,
                    'btc_amount': btc_holdings, 'usdt_capital_after_trade': usdt_capital, # capital is now in BTC
                    'profit_usdt': 0, 'signal_quality': quality
                })

        # --- Handle SELL signal (go short) ---
        elif signal == "SELL":
            if position == 'LONG':
                # Close long position first
                usdt_received = btc_holdings * candle['close'] * (1 - trading_fee_rate)
                profit = usdt_received - (entry_price * btc_holdings)
                usdt_capital = usdt_received
                logging.info(f"{index.strftime('%Y-%m-%d %H:%M')}: CLOSE LONG at {candle['close']:,.2f}. Profit: {profit:,.2f} USDT. New capital: {usdt_capital:,.2f} USDT.")
                trade_log.append({
                    'date': index, 'type': 'CLOSE_LONG', 'price': candle['close'],
                    'btc_amount': 0, 'usdt_capital_after_trade': usdt_capital,
                    'profit_usdt': profit, 'signal_quality': quality
                })
                btc_holdings = 0.0
                position = None

            if position is None:
                # Open short position
                btc_to_sell = (usdt_capital * (1 - trading_fee_rate)) / candle['close']
                btc_holdings = btc_to_sell
                entry_price = candle['close']
                position = 'SHORT'
                logging.info(f"{index.strftime('%Y-%m-%d %H:%M')}: OPEN SHORT ({quality}) at {entry_price:,.2f}. Sold {btc_holdings:.6f} BTC.")
                trade_log.append({
                    'date': index, 'type': 'OPEN_SHORT', 'price': entry_price,
                    'btc_amount': btc_holdings, 'usdt_capital_after_trade': usdt_capital,
                    'profit_usdt': 0, 'signal_quality': quality
                })

    # --- Final Calculation ---
    final_usdt_value = usdt_capital
    if position == 'LONG':
        final_usdt_value = btc_holdings * df.iloc[-1]['close']
    elif position == 'SHORT':
        profit = (entry_price - df.iloc[-1]['close']) * btc_holdings
        final_usdt_value += profit

    final_jpy_value = final_usdt_value * jpy_usdt_rate
    total_profit_jpy = final_jpy_value - initial_jpy_capital

    logging.info("==================================================")
    logging.info(f"Backtest Finished: {df.index.min().strftime('%Y-%m-%d')} to {df.index.max().strftime('%Y-%m-%d')}")
    logging.info(f"Initial JPY Capital: {initial_jpy_capital:,.0f} JPY")
    logging.info(f"Final JPY Value: {final_jpy_value:,.0f} JPY")
    logging.info(f"Total Profit/Loss: {total_profit_jpy:,.0f} JPY ({total_profit_jpy / initial_jpy_capital * 100:,.2f}%)")
    logging.info(f"Number of Trades: {len(trade_log)}")
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

    # Backtest parameters
    INITIAL_JPY_CAPITAL = 100000  # 10万円
    JPY_USDT_RATE = 150           # 仮定: 1 USDT = 150 JPY
    TRADING_FEE_RATE = 0.001      # 0.1% fee per trade

    final_value, trades = run_backtest(df.copy(), INITIAL_JPY_CAPITAL, JPY_USDT_RATE, TRADING_FEE_RATE)

    # Optionally save trade log
    trade_log_df = pd.DataFrame(trades)
    trade_log_df.to_csv("/Users/mucbook/バシャール/omen_bot/data/backtest_trade_log_1h.csv")
    logging.info("Trade log saved to /Users/mucbook/バシャール/omen_bot/data/backtest_trade_log_1h.csv")