import pandas as pd
import numpy as np
import logging
import time
import importlib.util
import os
import argparse
import json

# --- Load Config ---
try:
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/config.py'))
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
except Exception as e:
    print(f"FATAL: Could not load configuration from {config_path}. Error: {e}")
    exit(1)

# ==============================================================================
# Backtester for "RSI Compass with Running Start" Strategy
# ==============================================================================

# --- Logging Setup ---
# Suppress informational logging if running in optimization mode (json output)
is_json_output = '--json' in os.sys.argv
log_level = logging.WARNING if is_json_output else logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])

def calculate_indicators(df, rsi_period, vol_sma_period, long_sma_period, atr_period):
    """Calculates all necessary indicators."""
    df['range_pct'] = (df['high'] - df['low']) / df['open'] * 100
    df['volume_sma'] = df['volume'].rolling(window=vol_sma_period, min_periods=vol_sma_period).mean()
    df['vol_mult'] = df['volume'] / df['volume_sma']
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['sma_200'] = df['close'].rolling(window=long_sma_period, min_periods=long_sma_period).mean()
    df['tr'] = np.maximum(df['high'] - df['low'], np.abs(df['high'] - df['close'].shift(1)))
    df['tr'] = np.maximum(df['tr'], np.abs(df['low'] - df['close'].shift(1)))
    df['atr'] = df['tr'].rolling(window=atr_period, min_periods=1).mean()
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)
    return df

def run_backtest(data_file, initial_capital, tp_pct, sl_pct, atr_low, atr_high, start_date=None, end_date=None):
    """Runs the full backtest for the new strategy and returns performance metrics."""
    start_time = time.time()
    logging.info(f"--- Starting Backtest for 'RSI Compass with Running Start' Strategy on {config.SYMBOL} ---")
    logging.info(f"TP: {tp_pct*100:.2f}% | SL: {sl_pct*100:.2f}% | ATR Filter: {atr_low*100:.2f}% - {atr_high*100:.2f}%")

    # --- 1. Load and Prepare Data ---
    try:
        df = pd.read_csv(data_file, parse_dates=['timestamp'], index_col='timestamp')
        df.index = df.index.tz_localize('UTC')
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date).tz_localize('UTC')]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date).tz_localize('UTC')]
        
        logging.info(f"Data loaded. Analyzing {len(df)} candles from {df.index.min()} to {df.index.max()}.")
    except FileNotFoundError:
        logging.error(f"FATAL: Data file not found at {data_file}. Exiting.")
        return {'sharpe_ratio': -999} # Return a poor score

    df = calculate_indicators(df, config.RSI_PERIOD, config.VOL_SMA_PERIOD, config.LONG_SMA_PERIOD, config.ATR_PERIOD)

    # --- 2. Signal Identification ---
    signals = []
    for i in range(3, len(df)):
        p3, p2, p1, current_candle = df.iloc[i-3], df.iloc[i-2], df.iloc[i-1], df.iloc[i]
        entry_price_check = current_candle['open']

        if pd.isna(current_candle['atr']) or entry_price_check == 0:
            continue
        
        atr_pct = current_candle['atr'] / entry_price_check
        if not (atr_low <= atr_pct <= atr_high):
            continue
    
        is_increasing_range = p1['range_pct'] > p2['range_pct'] > p3['range_pct']
        is_increasing_volume = p1['vol_mult'] > p2['vol_mult'] > p3['vol_mult']
        
        if is_increasing_range and is_increasing_volume:
            is_uptrend = entry_price_check > current_candle['sma_200']
            is_downtrend = entry_price_check < current_candle['sma_200']
            
            if is_uptrend and (p1['rsi'] >= config.RSI_BUY_THRESHOLD and p2['rsi'] >= config.RSI_BUY_THRESHOLD and p3['rsi'] >= config.RSI_BUY_THRESHOLD):
                signals.append({'timestamp': df.index[i], 'direction': 'BUY', 'entry_price': entry_price_check})
            elif is_downtrend and (p1['rsi'] <= config.RSI_SELL_THRESHOLD and p2['rsi'] <= config.RSI_SELL_THRESHOLD and p3['rsi'] <= config.RSI_SELL_THRESHOLD):
                signals.append({'timestamp': df.index[i], 'direction': 'SELL', 'entry_price': entry_price_check})
    
    logging.info(f"Found {len(signals)} potential trade signals.")
    if len(signals) < 10: # Not enough trades for a meaningful result
        logging.warning("Not enough signals found. Backtest cannot proceed meaningfully.")
        return {'sharpe_ratio': -10}

    # --- 3. Trade Simulation ---
    trades = []
    current_capital = initial_capital
    capital_history = [initial_capital]
    next_allowed_trade_time = pd.Timestamp.min.tz_localize('UTC')
    MOVE_WINDOW_HOURS = 6
    candles_in_window = MOVE_WINDOW_HOURS * 4

    for signal in signals:
        entry_time = signal['timestamp']
        if entry_time < next_allowed_trade_time:
            continue

        entry_price = signal['entry_price']
        direction = signal['direction']
        entry_idx = df.index.get_loc(entry_time)
        trade_window_df = df.iloc[entry_idx : entry_idx + candles_in_window]

        if trade_window_df.empty:
            continue
        
        pnl_pct = 0
        trade_closed = False
        exit_time = trade_window_df.index[-1]
        exit_price = trade_window_df.iloc[-1]['close']
        
        stop_loss_price = entry_price * (1 + sl_pct) if direction == 'BUY' else entry_price * (1 - sl_pct)
        take_profit_price = entry_price * (1 + tp_pct) if direction == 'BUY' else entry_price * (1 - tp_pct)

        for candle_time, candle in trade_window_df.iterrows():
            if direction == 'BUY':
                if candle['low'] <= stop_loss_price:
                    pnl_pct, exit_price, exit_time, trade_closed = sl_pct, stop_loss_price, candle_time, True
                    break
                elif candle['high'] >= take_profit_price:
                    pnl_pct, exit_price, exit_time, trade_closed = tp_pct, take_profit_price, candle_time, True
                    break
            elif direction == 'SELL':
                if candle['high'] >= stop_loss_price:
                    pnl_pct, exit_price, exit_time, trade_closed = sl_pct, stop_loss_price, candle_time, True
                    break
                elif candle['low'] <= take_profit_price:
                    pnl_pct, exit_price, exit_time, trade_closed = tp_pct, take_profit_price, candle_time, True
                    break

        if not trade_closed:
            pnl_pct = (exit_price - entry_price) / entry_price if direction == 'BUY' else (entry_price - exit_price) / entry_price

        current_capital += current_capital * pnl_pct
        capital_history.append(current_capital)
        next_allowed_trade_time = exit_time + pd.Timedelta(minutes=15)

    # --- 4. Performance Calculation ---
    if not capital_history:
        return {'sharpe_ratio': -10}

    capital_series = pd.Series(capital_history)
    trade_returns = capital_series.pct_change().dropna()
    
    sharpe_ratio = -10 # Default poor score
    if trade_returns.std() != 0 and not np.isnan(trade_returns.std()):
        sharpe_ratio = trade_returns.mean() / trade_returns.std() * np.sqrt(252 * (24*4))

    final_capital = capital_series.iloc[-1]
    total_pnl_compounded = (final_capital / initial_capital - 1) * 100
    peak = capital_series.expanding(min_periods=1).max()
    drawdown = ((capital_series / peak) - 1).min()

    results = {
        'sharpe_ratio': sharpe_ratio,
        'final_capital': final_capital,
        'pnl_pct': total_pnl_compounded,
        'max_drawdown': drawdown,
        'num_trades': len(signals)
    }

    if not is_json_output:
        logging.info(f"\n--- Backtest Performance Summary ---")
        logging.info(f"Backtest Duration: {(time.time() - start_time):.2f} seconds")
        logging.info(f"Initial Capital: {initial_capital:,.2f}")
        logging.info(f"Final Capital:   {results['final_capital']:,.2f}")
        logging.info(f"Total PnL (Compounded): {results['pnl_pct']:.2f}%")
        logging.info(f"Total Trades: {results['num_trades']}")
        logging.info(f"Max Drawdown: {results['max_drawdown']*100:.2f}%")
        logging.info(f"Sharpe Ratio (Annualized): {results['sharpe_ratio']:.2f}")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run a backtest for the RSI Compass strategy.")
    parser.add_argument("--json", action="store_true", help="Output results as a JSON string.")
    
    # Date range arguments
    parser.add_argument("--start_date", type=str, default=None, help="Start date for training (YYYY-MM-DD).")
    parser.add_argument("--end_date", type=str, default=None, help="End date for training (YYYY-MM-DD).")

    # Strategy parameter arguments
    parser.add_argument("--tp_pct", type=float, default=config.TAKE_PROFIT_PCT, help="Take Profit percentage.")
    parser.add_argument("--sl_pct", type=float, default=config.STOP_LOSS_PCT, help="Stop Loss percentage (as a negative value).")
    parser.add_argument("--atr_low", type=float, default=config.ATR_LOW_BOUND, help="ATR filter lower bound.")
    parser.add_argument("--atr_high", type=float, default=config.ATR_HIGH_BOUND, help="ATR filter upper bound.")

    args = parser.parse_args()
    
    # Update global flag for logging
    is_json_output = args.json

    results = run_backtest(
        data_file=config.PRICE_DATA_PATH,
        initial_capital=config.INITIAL_CAPITAL_USDT,
        tp_pct=args.tp_pct,
        sl_pct=args.sl_pct,
        atr_low=args.atr_low,
        atr_high=args.atr_high,
        start_date=args.start_date,
        end_date=args.end_date
    )

    if is_json_output:
        print(json.dumps({'sharpe_ratio': results.get('sharpe_ratio', -999)}))
    else:
        # The run_backtest function already prints the detailed report
        pass
