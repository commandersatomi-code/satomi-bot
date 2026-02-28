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

def run_backtest(df, initial_jpy_capital, jpy_usdt_rate, trading_fee_rate, stop_loss_pct=None):
    logging.info(f"Starting backtest with initial JPY capital: {initial_jpy_capital:,} JPY")
    logging.info(f"JPY/USDT conversion rate: 1 USDT = {jpy_usdt_rate} JPY")
    logging.info(f"Trading fee rate: {trading_fee_rate * 100}% per trade")
    if stop_loss_pct:
        logging.info(f"Stop-loss percentage: {stop_loss_pct}%")

    current_usdt_capital = initial_jpy_capital / jpy_usdt_rate
    btc_holdings = 0.0
    in_position = False
    entry_price = 0.0
    stop_loss_price = 0.0
    trade_log = []

    logging.info(f"Initial USDT capital: {current_usdt_capital:,.2f} USDT")

    df = calculate_indicators(df)
    df.dropna(inplace=True)

    if df.empty:
        logging.warning("DataFrame is empty after dropping NaN values. Cannot run backtest.")
        return

    for index, candle in df.iterrows():
        # Check for stop-loss first
        if in_position and stop_loss_pct and candle['low'] <= stop_loss_price:
            usdt_received = btc_holdings * stop_loss_price * (1 - trading_fee_rate)
            profit_usdt = usdt_received - (entry_price * btc_holdings)
            current_usdt_capital = usdt_received
            btc_holdings = 0.0
            in_position = False
            trade_log.append({
                'date': index, 'type': 'STOP-LOSS', 'price': stop_loss_price,
                'btc_amount': 0, 'usdt_capital_after_trade': current_usdt_capital,
                'profit_usdt': profit_usdt, 'signal_quality': 'N/A'
            })
            logging.info(f"{index.strftime('%Y-%m-%d %H:%M')}: STOP-LOSS triggered at {stop_loss_price:,.2f}. Profit: {profit_usdt:,.2f} USDT. New capital: {current_usdt_capital:,.2f} USDT.")
            continue # Continue to the next candle after stop-loss

        signal, quality = check_for_signals(candle)

        # --- Handle BUY signal ---
        if signal == "BUY" and not in_position:
            if current_usdt_capital > 0:
                btc_to_buy = (current_usdt_capital * (1 - trading_fee_rate)) / candle['close']
                btc_holdings = btc_to_buy
                entry_price = candle['close']
                if stop_loss_pct:
                    stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
                current_usdt_capital = 0.0
                in_position = True
                trade_log.append({
                    'date': index, 'type': 'BUY', 'price': entry_price,
                    'btc_amount': btc_holdings, 'usdt_capital_after_trade': current_usdt_capital,
                    'btc_holdings_after_trade': btc_holdings, 'signal_quality': quality
                })
                logging.info(f"{index.strftime('%Y-%m-%d %H:%M')}: BUY signal ({quality}) at {entry_price:,.2f}. Bought {btc_holdings:.6f} BTC.")

        # --- Handle SELL signal ---
        elif signal == "SELL" and in_position:
            usdt_received = btc_holdings * candle['close'] * (1 - trading_fee_rate)
            profit_usdt = usdt_received - (entry_price * btc_holdings)
            current_usdt_capital = usdt_received
            btc_holdings = 0.0
            in_position = False
            trade_log.append({
                'date': index, 'type': 'SELL', 'price': candle['close'],
                'btc_amount': 0, 'usdt_capital_after_trade': current_usdt_capital,
                'profit_usdt': profit_usdt, 'signal_quality': quality
            })
            logging.info(f"{index.strftime('%Y-%m-%d %H:%M')}: SELL signal ({quality}) at {candle['close']:,.2f}. Sold all BTC. Profit: {profit_usdt:,.2f} USDT. New capital: {current_usdt_capital:,.2f} USDT.")

    # --- Final Calculation ---
    final_usdt_value = current_usdt_capital
    if in_position:
        final_usdt_value = btc_holdings * df.iloc[-1]['close']

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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Run a backtest with a stop-loss.')
    parser.add_argument('--stop_loss', type=float, help='Stop-loss percentage (e.g., 2 for 2%)')
    args = parser.parse_args()

    data_file_path = "/Users/mucbook/バシャール/omen_bot/data/bybit_btc_usdt_linear_1h_full.csv"

    if not os.path.exists(data_file_path):
        logging.error(f"Data file not found: {data_file_path}. Please ensure the data is fetched first.")
        exit()

    df = pd.read_csv(data_file_path, parse_dates=['timestamp'], index_col='timestamp')
    df.sort_index(inplace=True)

    INITIAL_JPY_CAPITAL = 100000
    JPY_USDT_RATE = 150
    TRADING_FEE_RATE = 0.001

    final_value, trades = run_backtest(df.copy(), INITIAL_JPY_CAPITAL, JPY_USDT_RATE, TRADING_FEE_RATE, stop_loss_pct=args.stop_loss)

    if args.stop_loss:
        log_filename = f"/Users/mucbook/バシャール/omen_bot/data/backtest_trade_log_1h_stoploss_{args.stop_loss}.csv"
    else:
        log_filename = "/Users/mucbook/バシャール/omen_bot/data/backtest_trade_log_1h_stoploss_none.csv"

    trade_log_df = pd.DataFrame(trades)
    trade_log_df.to_csv(log_filename)
    logging.info(f"Trade log saved to {log_filename}")