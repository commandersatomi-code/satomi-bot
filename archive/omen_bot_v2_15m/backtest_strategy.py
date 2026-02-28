import pandas as pd
import numpy as np
import logging
import os

from . import config
from .core import strategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_backtest(end_date=None, move_threshold_pct=3.00/100,
                 tp=0.05, sl=-0.12, move_window_hours=6, initial_capital=30000): # move_window_hoursを引数に追加 # initial_capitalを追加

    logging.info(f"--- Starting Comprehensive Backtest for 15-min Strategy (Compounding) ---") # ログを変更
    logging.info(f"Initial Capital: {initial_capital:.2f} JPY") # ログを追加
    logging.info(f"MOVE_THRESHOLD_PCT: {move_threshold_pct*100:.2f}%")
    logging.info(f"TP: {tp*100:.2f}% | SL: {sl*100:.2f}%")

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

    # --- Identify Precursor Signals ---
    df['future_max_price'] = df['high'].rolling(window=move_window_hours).apply(lambda x: x.max(), raw=True).shift(-move_window_hours)
    df['future_min_price'] = df['low'].rolling(window=move_window_hours).apply(lambda x: x.min(), raw=True).shift(-move_window_hours)
    df['potential_up_move'] = (df['future_max_price'] - df['close']) / df['close']
    df['potential_down_move'] = (df['future_min_price'] - df['close']) / df['close']

    precursor_signals = [] # List of (timestamp, direction, entry_price)

    for i in range(len(df)):
        p_row = df.iloc[i]
        p_index = p_row.name # Get timestamp of current candle

        # Check for BUY signal precursor
        is_low_volume_buy = p_row['vol_mult'] < 1.0
        is_small_body_buy = p_row['body_ratio'] < 0.4
        is_bearish_candle_buy = p_row['close'] < p_row['open']
        
        if is_low_volume_buy and is_small_body_buy and is_bearish_candle_buy:
            precursor_signals.append({'timestamp': p_index, 'direction': 'buy', 'entry_price': p_row['close']})

        # Check for SELL signal precursor
        is_low_volume_sell = p_row['vol_mult'] < 1.0
        is_small_body_sell = p_row['body_ratio'] < 0.4
        is_bullish_candle_sell = p_row['close'] > p_row['open']

        if is_low_volume_sell and is_small_body_sell and is_bullish_candle_sell:
            precursor_signals.append({'timestamp': p_index, 'direction': 'sell', 'entry_price': p_row['close']})
    
    logging.info(f"Found {len(precursor_signals)} precursor signals for backtest.")

    trades = [] # List of {'entry_time', 'exit_time', 'direction', 'entry_price', 'exit_price', 'pnl_pct', 'pnl_amount'}
    current_position = None # Track if we are in a position
    
    current_capital = float(initial_capital) # 現在の資本を追跡
    capital_history = [current_capital] # 資本の履歴を記録

    for signal in precursor_signals:
        signal_timestamp = signal['timestamp']
        signal_direction = signal['direction']
        signal_entry_price = signal['entry_price']

        # If already in a position, check for reversal (ドテン)
        if current_position:
            # If new signal is opposite to current position, close current and open new
            if (current_position['direction'] == 'buy' and signal_direction == 'sell') or \
               (current_position['direction'] == 'sell' and signal_direction == 'buy'):
                
                # Close current position at signal_entry_price
                exit_price = signal_entry_price
                pnl_pct = 0
                if current_position['direction'] == 'buy':
                    pnl_pct = (exit_price - current_position['entry_price']) / current_position['entry_price']
                else: # sell
                    pnl_pct = (current_position['entry_price'] - exit_price) / current_position['entry_price']
                
                pnl_amount = current_capital * pnl_pct # 複利計算
                current_capital += pnl_amount
                capital_history.append(current_capital)

                trades.append({
                    'entry_time': current_position['entry_time'],
                    'exit_time': signal_timestamp,
                    'direction': current_position['direction'],
                    'entry_price': current_position['entry_price'],
                    'exit_price': exit_price,
                    'pnl_pct': pnl_pct,
                    'pnl_amount': pnl_amount
                })
                logging.debug(f"Closed {current_position['direction']} position at {signal_timestamp} due to reversal. PnL: {pnl_pct*100:.2f}%. Capital: {current_capital:.2f}")
                current_position = None # Clear position before opening new one

        # Open new position
        current_position = {
            'entry_time': signal_timestamp,
            'direction': signal_direction,
            'entry_price': signal_entry_price
        }
        logging.debug(f"Opened {signal_direction} position at {signal_timestamp} with entry price {signal_entry_price}. Capital: {current_capital:.2f}")

        # Simulate trade for TP/SL/Time Limit
        entry_candle_idx = df.index.get_loc(signal_timestamp) + 1
        trade_df = df.iloc[entry_candle_idx : entry_candle_idx + (move_window_hours * 4)] # 15min candles, 4 per hour

        if trade_df.empty:
            continue # Not enough data after precursor

        trade_closed = False
        for _, current_candle in trade_df.iterrows():
            current_price = current_candle['close']
            pnl_pct = 0

            if current_position['direction'] == 'buy':
                pnl_pct = (current_price - current_position['entry_price']) / current_position['entry_price']
                # Check TP
                if pnl_pct >= tp:
                    pnl_amount = current_capital * tp # 複利計算
                    current_capital += pnl_amount
                    capital_history.append(current_capital)
                    trades.append({
                        'entry_time': current_position['entry_time'],
                        'exit_time': current_candle.name,
                        'direction': current_position['direction'],
                        'entry_price': current_position['entry_price'],
                        'exit_price': current_price,
                        'pnl_pct': tp,
                        'pnl_amount': pnl_amount
                    })
                    logging.debug(f"Closed BUY position at {current_candle.name} (TP hit). PnL: {tp*100:.2f}%. Capital: {current_capital:.2f}")
                    trade_closed = True
                    current_position = None
                    break
                # Check SL
                if pnl_pct <= sl:
                    pnl_amount = current_capital * sl # 複利計算
                    current_capital += pnl_amount
                    capital_history.append(current_capital)
                    trades.append({
                        'entry_time': current_position['entry_time'],
                        'exit_time': current_candle.name,
                        'direction': current_position['direction'],
                        'entry_price': current_position['entry_price'],
                        'exit_price': current_price,
                        'pnl_pct': sl,
                        'pnl_amount': pnl_amount
                    })
                    logging.debug(f"Closed BUY position at {current_candle.name} (SL hit). PnL: {sl*100:.2f}%. Capital: {current_capital:.2f}")
                    trade_closed = True
                    current_position = None
                    break
            elif current_position['direction'] == 'sell':
                pnl_pct = (current_position['entry_price'] - current_price) / current_position['entry_price']
                # Check TP
                if pnl_pct >= tp:
                    pnl_amount = current_capital * tp # 複利計算
                    current_capital += pnl_amount
                    capital_history.append(current_capital)
                    trades.append({
                        'entry_time': current_position['entry_time'],
                        'exit_time': current_candle.name,
                        'direction': current_position['direction'],
                        'entry_price': current_position['entry_price'],
                        'exit_price': current_price,
                        'pnl_pct': tp,
                        'pnl_amount': pnl_amount
                    })
                    logging.debug(f"Closed SELL position at {current_candle.name} (TP hit). PnL: {tp*100:.2f}%. Capital: {current_capital:.2f}")
                    trade_closed = True
                    current_position = None
                    break
                # Check SL
                if pnl_pct <= sl:
                    pnl_amount = current_capital * sl # 複利計算
                    current_capital += pnl_amount
                    capital_history.append(current_capital)
                    trades.append({
                        'entry_time': current_position['entry_time'],
                        'exit_time': current_candle.name,
                        'direction': current_position['direction'],
                        'entry_price': current_position['entry_price'],
                        'exit_price': current_price,
                        'pnl_pct': sl,
                        'pnl_amount': pnl_amount
                    })
                    logging.debug(f"Closed SELL position at {current_candle.name} (SL hit). PnL: {sl*100:.2f}%. Capital: {current_capital:.2f}")
                    trade_closed = True
                    current_position = None
                    break
        
        # If trade not closed by TP/SL and current_position is still active (not reversed by next signal)
        if not trade_closed and current_position and current_position['entry_time'] == signal_timestamp:
            # Close at the end of move_window_hours
            final_price = trade_df.iloc[-1]['close'] if not trade_df.empty else current_position['entry_price']
            pnl_pct = 0
            if current_position['direction'] == 'buy':
                pnl_pct = (final_price - current_position['entry_price']) / current_position['entry_price']
            else: # sell
                pnl_pct = (current_position['entry_price'] - final_price) / current_position['entry_price']
            
            pnl_amount = current_capital * pnl_pct # 複利計算
            current_capital += pnl_amount
            capital_history.append(current_capital)

            trades.append({
                'entry_time': current_position['entry_time'],
                'exit_time': trade_df.iloc[-1].name if not trade_df.empty else signal_timestamp,
                'direction': current_position['direction'],
                'entry_price': current_position['entry_price'],
                'exit_price': final_price,
                'pnl_pct': pnl_pct,
                'pnl_amount': pnl_amount
            })
            logging.debug(f"Closed {current_position['direction']} position at {trade_df.iloc[-1].name if not trade_df.empty else signal_timestamp} due to time limit. PnL: {pnl_pct*100:.2f}%. Capital: {current_capital:.2f}")
            current_position = None # Clear position

    # --- Calculate Performance Metrics ---
    if not trades:
        logging.info("No trades executed.")
        return

    final_capital = current_capital
    total_pnl_compounded = (final_capital / initial_capital - 1) * 100 # 複利ベースの総利益率

    pnl_series = pd.Series([t['pnl_pct'] for t in trades])
    
    num_trades = len(trades)
    num_wins = (pnl_series > 0).sum()
    num_losses = (pnl_series < 0).sum()
    win_rate = num_wins / num_trades if num_trades > 0 else 0

    avg_win = pnl_series[pnl_series > 0].mean() if num_wins > 0 else 0
    avg_loss = pnl_series[pnl_series < 0].mean() if num_losses > 0 else 0

    gross_profit = pnl_series[pnl_series > 0].sum()
    gross_loss = pnl_series[pnl_series < 0].sum()
    profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else np.inf

    # --- Calculate Performance Metrics ---
    if not trades:
        logging.info("No trades executed.")
        return

    final_capital = current_capital
    total_pnl_compounded = (final_capital / initial_capital - 1) * 100 # 複利ベースの総利益率

    pnl_series = pd.Series([t['pnl_pct'] for t in trades])
    
    num_trades = len(trades)
    num_wins = (pnl_series > 0).sum()
    num_losses = (pnl_series < 0).sum()
    win_rate = num_wins / num_trades if num_trades > 0 else 0

    avg_win = pnl_series[pnl_series > 0].mean() if num_wins > 0 else 0
    avg_loss = pnl_series[pnl_series < 0].mean() if num_losses > 0 else 0

    gross_profit = pnl_series[pnl_series > 0].sum()
    gross_loss = pnl_series[pnl_series < 0].sum()
    profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else np.inf

    # Calculate Drawdown (based on capital_history)
    capital_series = pd.Series(capital_history)
    peak = capital_series.expanding(min_periods=1).max()
    drawdown = (capital_series / peak) - 1
    max_drawdown = drawdown.min()

    # Calculate Sharpe Ratio
    # Period returns are percentage changes in capital
    period_returns = capital_series.pct_change().dropna()
    std_dev_returns = period_returns.std()
    
    sharpe_ratio = 0
    if std_dev_returns != 0:
        # Calculate total_days from the df used for backtesting
        total_days = (df.index.max() - df.index.min()).days
        if total_days == 0: total_days = 1
        
        # Annualize Sharpe Ratio (e.g., for 15-min data, 252 trading days * 24 hours * 4 candles/hour)
        # len(df) / total_days gives candles per day
        annualization_factor = np.sqrt(len(df) / total_days * 252) 
        sharpe_ratio = (period_returns.mean() / std_dev_returns) * annualization_factor

    logging.info("\n--- Backtest Performance Summary (Compounding) ---") # ログを変更
    logging.info(f"Initial Capital: {initial_capital:.2f} JPY")
    logging.info(f"Final Capital: {final_capital:.2f} JPY")
    logging.info(f"Total PnL (Compounded): {total_pnl_compounded:.2f}%") # 複利ベースの総利益率
    logging.info(f"Total Trades: {num_trades}")
    logging.info(f"Win Rate: {win_rate*100:.2f}%")
    logging.info(f"Average Win: {avg_win*100:.2f}%")
    logging.info(f"Average Loss: {avg_loss*100:.2f}%")
    logging.info(f"Profit Factor: {profit_factor:.2f}")
    logging.info(f"Max Drawdown: {max_drawdown*100:.2f}%")
    logging.info(f"Sharpe Ratio (Annualized): {sharpe_ratio:.2f}") # シャープレシオを追加

if __name__ == '__main__':
    run_backtest(end_date='2024-11-15')
