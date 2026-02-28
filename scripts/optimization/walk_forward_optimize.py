import pandas as pd
import numpy as np
import logging
import time
from dateutil.relativedelta import relativedelta

# ==============================================================================
# Walk-Forward Optimizer for "RSI Compass with Running Start" Strategy
# ==============================================================================

# --- Configuration ---
DATA_FILE = 'data/bybit_btc_usdt_linear_15m_full.csv'
BACKTEST_END_DATE = '2024-11-15'
INITIAL_CAPITAL = 30000.0

# Walk-Forward Parameters
TRAIN_PERIOD = relativedelta(years=2)
VALIDATION_PERIOD = relativedelta(months=6)

# Optimization Parameters
TP_RANGE = [0.01, 0.02, 0.03, 0.05, 0.08, 0.10]
SL_RANGE = [-0.01, -0.02, -0.03, -0.05]
MOVE_WINDOW_HOURS_RANGE = [3, 6, 9, 12] # Test various holding times

# Volatility Filter Parameters (ATR as % of Close)
ATR_LOW_BOUND_RANGE = [0.005, 0.01, 0.015] # 0.5% to 1.5%
ATR_HIGH_BOUND_RANGE = [0.02, 0.03, 0.04, 0.05] # 2% to 5%

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])

def calculate_indicators(df, rsi_period=14, vol_sma_period=20, long_sma_period=200, atr_period=14):
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
    
    # ATR Calculation
    df['tr'] = np.maximum(df['high'] - df['low'], np.abs(df['high'] - df['close'].shift(1)))
    df['tr'] = np.maximum(df['tr'], np.abs(df['low'] - df['close'].shift(1)))
    df['atr'] = df['tr'].rolling(window=atr_period, min_periods=1).mean()

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)
    return df

def find_signals(df, atr_low_bound, atr_high_bound):
    """Finds trade signals based on the strategy logic."""
    signals = []
    for i in range(3, len(df)):
        p3, p2, p1 = df.iloc[i-3], df.iloc[i-2], df.iloc[i-1] 
        
        # Volatility filter condition
        current_atr = df['atr'].iloc[i]
        entry_price_check = df['open'].iloc[i]
        
        if pd.isna(current_atr) or current_atr == 0:
            continue

        atr_pct = current_atr / entry_price_check
        if not (atr_low_bound <= atr_pct <= atr_high_bound):
            continue
        
        is_increasing_range = p1['range_pct'] > p2['range_pct'] > p3['range_pct']
        is_increasing_volume = p1['vol_mult'] > p2['vol_mult'] > p3['vol_mult']
        
        if is_increasing_range and is_increasing_volume:
            is_uptrend = entry_price_check > p1['sma_200']
            is_downtrend = entry_price_check < p1['sma_200']
            
            if is_uptrend and (p1['rsi'] >= 50 and p2['rsi'] >= 50 and p3['rsi'] >= 50):
                signals.append({'timestamp': df.index[i], 'direction': 'BUY', 'entry_price': entry_price_check})
            elif is_downtrend and (p1['rsi'] <= 47 and p2['rsi'] <= 47 and p3['rsi'] <= 47):
                signals.append({'timestamp': df.index[i], 'direction': 'SELL', 'entry_price': entry_price_check})
    return signals

def run_single_backtest(df, signals, tp, sl, move_window_hours):
    """Fast, non-compounding backtest for optimization. Returns total PnL percentage."""
    total_pnl = 0
    num_trades = 0
    
    candles_in_window = move_window_hours * 4
    next_allowed_trade_time = pd.Timestamp.min.tz_localize('UTC')

    for signal in signals:
        if signal['timestamp'] < next_allowed_trade_time:
            continue
        
        num_trades += 1
        entry_time = signal['timestamp']
        entry_price = signal['entry_price']
        direction = signal['direction']
        
        
        # Calculate dynamic TP/SL prices based on fixed percentages
        tp_pct = tp
        sl_pct = sl
        
        entry_idx = df.index.get_loc(entry_time)
        trade_window_df = df.iloc[entry_idx : entry_idx + candles_in_window]
        
        if trade_window_df.empty:
            continue
            
        pnl_pct = 0
        trade_closed = False
        
        for _, candle in trade_window_df.iterrows():
            if direction == 'BUY':
                tp_price = entry_price * (1 + tp_pct)
                sl_price = entry_price * (1 + sl_pct) # sl_pct is negative
                
                if candle['low'] <= sl_price:
                    pnl_pct = sl_pct; trade_closed = True; break
                elif candle['high'] >= tp_price:
                    pnl_pct = tp_pct; trade_closed = True; break
            elif direction == 'SELL':
                tp_price = entry_price * (1 - tp_pct)
                sl_price = entry_price * (1 - sl_pct) # sl_pct is negative, so 1 - (-X) = 1 + X
                
                if candle['high'] >= sl_price: # Price moves up for SL
                    pnl_pct = sl_pct; trade_closed = True; break
                elif candle['low'] <= tp_price: # Price moves down for TP
                    pnl_pct = tp_pct; trade_closed = True; break

        if not trade_closed:
            exit_price = trade_window_df.iloc[-1]['close']
            pnl_pct = (exit_price - entry_price) / entry_price if direction == 'BUY' else (entry_price - exit_price) / entry_price
        
        total_pnl += pnl_pct
        next_allowed_trade_time = trade_window_df.index[-1] + pd.Timedelta(minutes=15)

    return total_pnl / num_trades if num_trades > 0 else 0

def run_walk_forward_optimization():
    """Main function to run the walk-forward optimization and final backtest."""
    wf_start_time = time.time()
    logging.info("--- Starting Walk-Forward Optimization ---")
    logging.info(f"Train Period: {TRAIN_PERIOD}, Validation Period: {VALIDATION_PERIOD}")

    # --- Load Full Data ---
    try:
        full_df = pd.read_csv(DATA_FILE, parse_dates=['timestamp'], index_col='timestamp')
        full_df = full_df[full_df.index <= pd.to_datetime(BACKTEST_END_DATE)]
        full_df.index = full_df.index.tz_localize('UTC')
    except FileNotFoundError:
        logging.error(f"FATAL: Data file not found at {DATA_FILE}."); return

    full_df = calculate_indicators(full_df)
    
    # --- Setup Walk-Forward Periods ---
    start_date = full_df.index.min()
    end_date = full_df.index.max()
    
    all_out_of_sample_trades = []
    current_date = start_date
    
    fold = 0
    while current_date + TRAIN_PERIOD + VALIDATION_PERIOD <= end_date:
        fold += 1
        train_start = current_date
        train_end = train_start + TRAIN_PERIOD
        validation_start = train_end
        validation_end = validation_start + VALIDATION_PERIOD
        
        logging.info(f"\n--- Fold {fold}: Training {train_start.date()} to {train_end.date()} ---")

        # --- In-Sample Optimization ---
        train_df = full_df.loc[train_start:train_end]

        
        best_expected_value = -np.inf
        best_tp, best_sl, best_move_window_hours = None, None, None
        best_atr_low_bound, best_atr_high_bound = None, None

        for tp in TP_RANGE:
            for sl in SL_RANGE:
                for mwh in MOVE_WINDOW_HOURS_RANGE:
                    for alb in ATR_LOW_BOUND_RANGE:
                        for ahb in ATR_HIGH_BOUND_RANGE:
                            # Ensure low bound is not greater than high bound
                            if alb >= ahb:
                                continue
                            train_signals_filtered = find_signals(train_df, alb, ahb)
                            expected_value = run_single_backtest(train_df, train_signals_filtered, tp, sl, mwh)
                            if expected_value > best_expected_value:
                                best_expected_value = expected_value
                                best_tp, best_sl, best_move_window_hours = tp, sl, mwh
                                best_atr_low_bound, best_atr_high_bound = alb, ahb
        
        logging.info(f"Best Params Found: TP={best_tp*100:.2f}%, SL={best_sl*100:.2f}%, Hold={best_move_window_hours}h, ATR_Range={best_atr_low_bound*100:.2f}%-{best_atr_high_bound*100:.2f}% | Expected Value: {best_expected_value*100:.4f}%")

        # --- Out-of-Sample Validation ---
        logging.info(f"--- Fold {fold}: Validating {validation_start.date()} to {validation_end.date()} ---")
        validation_df = full_df.loc[validation_start:validation_end]
        validation_signals = find_signals(validation_df, best_atr_low_bound, best_atr_high_bound)

        # Run compounding backtest on validation data with best params
        next_allowed_trade_time = pd.Timestamp.min.tz_localize('UTC')
        candles_in_window = best_move_window_hours * 4 # Use optimized holding time

        for signal in validation_signals:
            if signal['timestamp'] < next_allowed_trade_time:
                continue

            trade = {'entry_time': signal['timestamp'], 'direction': signal['direction'], 'entry_price': signal['entry_price']}
            entry_idx = validation_df.index.get_loc(trade['entry_time'])
            
            # Use fixed percentage TP/SL
            tp_pct = best_tp
            sl_pct = best_sl
            
            trade_window_df = validation_df.iloc[entry_idx : entry_idx + candles_in_window]
            
            if trade_window_df.empty: continue

            pnl_pct = 0; trade_closed = False
            exit_time = trade_window_df.index[-1]
            exit_price = trade_window_df.iloc[-1]['close']

            for candle_time, candle in trade_window_df.iterrows():
                if trade['direction'] == 'BUY':
                    tp_price = trade['entry_price'] * (1 + tp_pct)
                    sl_price = trade['entry_price'] * (1 + sl_pct) # sl_pct is negative
                    
                    if candle['low'] <= sl_price:
                        pnl_pct, exit_time, trade_closed = sl_pct, candle_time, True; break
                    elif candle['high'] >= tp_price:
                        pnl_pct, exit_time, trade_closed = tp_pct, candle_time, True; break
                elif trade['direction'] == 'SELL':
                    tp_price = trade['entry_price'] * (1 - tp_pct)
                    sl_price = trade['entry_price'] * (1 - sl_pct) # sl_pct is negative, so 1 - (-X) = 1 + X
                    
                    if candle['high'] >= sl_price:
                        pnl_pct, exit_time, trade_closed = sl_pct, candle_time, True; break
                    elif candle['low'] <= tp_price: # Price moves down for TP
                        pnl_pct, exit_time, trade_closed = tp_pct, candle_time, True; break
            
            if not trade_closed:
                pnl_pct = (exit_price - trade['entry_price']) / trade['entry_price'] if trade['direction'] == 'BUY' else (trade['entry_price'] - exit_price) / trade['entry_price']
            
            trade['pnl_pct'] = pnl_pct
            all_out_of_sample_trades.append(trade)
            next_allowed_trade_time = trade_window_df.index[-1] + pd.Timedelta(minutes=15)

        # Move to the next validation period
        current_date += VALIDATION_PERIOD

    # --- Final Performance Calculation on Aggregated OOS Trades ---
    logging.info("\n--- Aggregating Out-of-Sample Results for Final Performance ---")
    if not all_out_of_sample_trades:
        logging.warning("No out-of-sample trades were executed. Cannot calculate final performance.")
        return
        
    current_capital = INITIAL_CAPITAL
    capital_history = [INITIAL_CAPITAL]
    for trade in all_out_of_sample_trades:
        pnl_amount = current_capital * trade['pnl_pct']
        current_capital += pnl_amount
        capital_history.append(current_capital)

    final_capital = current_capital
    total_pnl_compounded = (final_capital / INITIAL_CAPITAL - 1) * 100
    pnl_series = pd.Series([t['pnl_pct'] for t in all_out_of_sample_trades])
    num_trades = len(all_out_of_sample_trades)
    win_rate = (pnl_series > 0).sum() / num_trades if num_trades > 0 else 0
    capital_series = pd.Series(capital_history)
    peak = capital_series.expanding(min_periods=1).max()
    drawdown = (capital_series / peak) - 1
    max_drawdown = drawdown.min()
    trade_returns = capital_series.pct_change().dropna()
    sharpe_ratio = 0
    if trade_returns.std() != 0 and not np.isnan(trade_returns.std()):
        sharpe_ratio = trade_returns.mean() / trade_returns.std() * np.sqrt(252 * (24*4)) # Assuming daily returns, adjust sqrt factor if needed

    logging.info(f"\n--- Walk-Forward Backtest Performance (Out-of-Sample) ---")
    logging.info(f"Total Process Duration: {(time.time() - wf_start_time):.2f} seconds")
    logging.info(f"Initial Capital: {INITIAL_CAPITAL:,.2f} JPY")
    logging.info(f"Final Capital:   {final_capital:,.2f} JPY")
    logging.info(f"Total PnL (Compounded): {total_pnl_compounded:.2f}%")
    logging.info(f"Total Trades: {num_trades}")
    logging.info(f"Win Rate: {win_rate*100:.2f}%")
    logging.info(f"Max Drawdown: {max_drawdown*100:.2f}%")
    logging.info(f"Sharpe Ratio (Annualized): {sharpe_ratio:.2f}")

if __name__ == '__main__':
    run_walk_forward_optimization()
