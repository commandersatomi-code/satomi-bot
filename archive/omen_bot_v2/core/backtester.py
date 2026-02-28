# ==============================================================================
# Omen Bot - Core Derivatives Backtesting Engine
# ==============================================================================
# This module contains the backtesting engine for derivatives, incorporating
# leverage, fees, funding rates, and liquidation logic.
# ==============================================================================

import pandas as pd
import numpy as np
import logging

# Import the central configuration and core modules
try:
    from omen_bot_v2 import config
    from . import strategy
except ImportError:
    print("Error: Could not import config or strategy. Make sure they are in the 'omen_bot' directory/package.")
    exit()

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class DerivativesBacktester:
    """
    A class to run a backtest for a derivatives trading strategy.
    """
    def __init__(self):
        """Initializes the backtester with settings from the config file."""
        self.initial_capital = config.INITIAL_CAPITAL_USDT
        print(f"DEBUG: __init__ - self.initial_capital set to {self.initial_capital:,.2f}")
        logging.debug(f"__init__: self.initial_capital set to {self.initial_capital:,.2f}")
        self.leverage = config.LEVERAGE
        self.taker_fee_rate = config.DERIVATIVES_TAKER_FEE
        self.take_profit_pct = config.TAKE_PROFIT_PCT
        self.stop_loss_pct = config.STOP_LOSS_PCT
        self.profit_lock_pct = config.PROFIT_LOCK_PCT
        
        # For liquidation price calculation. 0.5% is a common value for BTC.
        # This is the maintenance margin rate as a percentage of notional value.
        self.maintenance_margin_rate = 0.005 

        self.load_data()

    def load_data(self):
        """Loads and prepares price and funding rate data."""
        logging.info("Loading and preparing data...") # Changed from print to logging.info
        try:
            price_df = pd.read_csv(config.PRICE_DATA_PATH, parse_dates=['timestamp'], index_col='timestamp')
            funding_df = pd.read_csv(config.FUNDING_RATE_DATA_PATH, parse_dates=['fundingRateTimestamp'])
            
            # Rename funding timestamp for merging
            funding_df.rename(columns={'fundingRateTimestamp': 'timestamp', 'fundingRate': 'funding_rate'}, inplace=True)
            
            # Merge price data with funding data. Funding rates are published every 8 hours.
            # We forward-fill the funding rate until the next one is published.
            # Use 'outer' merge to keep all price data, then ffill funding rates.
            self.df = pd.merge(price_df, funding_df[['timestamp', 'funding_rate']], on='timestamp', how='left')
            self.df.set_index('timestamp', inplace=True) # Ensure DatetimeIndex after merge
            self.df['funding_rate'].fillna(method='ffill', inplace=True)
            
            # Calculate indicators
            self.df = strategy.calculate_indicators(self.df, long_sma_period=config.LONG_SMA_PERIOD)
            
            # Drop rows with NaN values after indicator calculation
            self.df.dropna(inplace=True)

            # Filter data up to BACKTEST_END_DATE for holdout
            backtest_end_datetime = pd.to_datetime(config.BACKTEST_END_DATE)
            self.df = self.df[self.df.index <= backtest_end_datetime]
            
            logging.info(f"Data loaded and prepared successfully. Backtest data range: {self.df.index.min()} to {self.df.index.max()}.")
            
        except FileNotFoundError as e:
            logging.error(f"Error: Data file not found. {e}")
            logging.error("Please run the data_utils script first to download the data.")
            self.df = pd.DataFrame() # Empty df to prevent errors
        except Exception as e:
            logging.error(f"An unexpected error occurred during data loading: {e}") # Changed from print to logging.error
            self.df = pd.DataFrame()

    def run(self):
        """
        Executes the backtest loop.
        """
        if self.df.empty:
            logging.error("Cannot run backtest, data is not loaded.") # Changed from print to logging.error
            return

        logging.info(f"Starting Derivatives Backtest: {self.df.index.min()} to {self.df.index.max()}")
        logging.info(f"Initial Capital: {self.initial_capital:,.2f} USDT, Leverage: {self.leverage}x")
        logging.info(f"TP: {self.take_profit_pct*100:.2f}%, SL: {self.stop_loss_pct*100:.2f}%, Profit Lock: {self.profit_lock_pct*100:.2f}%")

        # --- State Variables ---
        margin_balance = self.initial_capital # This is total account equity
        logging.debug(f"Initial margin_balance: {margin_balance:,.2f}")
        position_state = None  # 'LONG' or 'SHORT'
        position_size_btc = 0.0 # Size in BTC
        entry_price = 0.0
        liquidation_price = 0.0
        initial_margin_for_position = 0.0 # Margin specifically allocated for the current open position
        
        # For TP/SL management
        current_take_profit_price = 0.0
        current_stop_loss_price = 0.0
        
        my_strategy = strategy.MyStrategy()
        
        trade_log = []
        equity_curve = [{'date': self.df.index[0], 'equity': margin_balance}]

        for index, row in self.df.iterrows():
            # If bankrupt, stop the test
            if margin_balance <= 0:
                logging.warning(f"Account balance is zero or negative at {index}. Stopping backtest.")
                break

            # --- 1. Check for Liquidation ---
            logging.debug(f"Before Liquidation Check. margin_balance: {margin_balance:,.2f}")
            # Only check if there's an open position
            if position_state is not None:
                # For long position, liquidation happens if price drops to or below liq price
                if position_state == 'LONG' and row['low'] <= liquidation_price:
                    logging.error(f"!!! LIQUIDATION (LONG) at {index} !!! Price hit {row['low']:,.2f}, liquidation price was {liquidation_price:,.2f}.")
                    
                    # Loss is the initial margin for the position
                    margin_balance -= initial_margin_for_position 
                    
                    trade_log.append({'date': index, 'type': 'LIQUIDATION_LONG', 'price': liquidation_price, 'profit_usdt': -initial_margin_for_position})
                    
                    # Reset position state
                    position_state = None
                    position_size_btc = 0.0
                    entry_price = 0.0
                    liquidation_price = 0.0
                    initial_margin_for_position = 0.0
                    current_take_profit_price = 0.0
                    current_stop_loss_price = 0.0

                    if margin_balance <= 0:
                        logging.warning(f"Account balance is zero or negative after liquidation at {index}. Stopping backtest.")
                        break
                    logging.debug(f"After LONG Liquidation. margin_balance: {margin_balance:,.2f}")
                    continue # Skip to next candle, position is closed

                # For short position, liquidation happens if price rises to or above liq price
                if position_state == 'SHORT' and row['high'] >= liquidation_price:
                    logging.error(f"!!! LIQUIDATION (SHORT) at {index} !!! Price hit {row['high']:,.2f}, liquidation price was {liquidation_price:,.2f}.")
                    
                    # Loss is the initial margin for the position
                    margin_balance -= initial_margin_for_position
                    
                    trade_log.append({'date': index, 'type': 'LIQUIDATION_SHORT', 'price': liquidation_price, 'profit_usdt': -initial_margin_for_position})
                    
                    # Reset position state
                    position_state = None
                    position_size_btc = 0.0
                    entry_price = 0.0
                    liquidation_price = 0.0
                    initial_margin_for_position = 0.0
                    current_take_profit_price = 0.0
                    current_stop_loss_price = 0.0

                    if margin_balance <= 0:
                        logging.warning(f"Account balance is zero or negative after liquidation at {index}. Stopping backtest.")
                        break
                    logging.debug(f"After SHORT Liquidation. margin_balance: {margin_balance:,.2f}")
                    continue # Skip to next candle, position is closed
            logging.debug(f"After Liquidation Check. margin_balance: {margin_balance:,.2f}")

            # --- 2. Apply Funding Rate ---
            logging.debug(f"Before Funding Rate. margin_balance: {margin_balance:,.2f}")
            if pd.notna(row['funding_rate']) and position_state is not None:
                # Check if this is a new funding rate event (funding timestamps are unique)
                # This logic assumes funding_df has unique timestamps for funding events
                # And that funding rates are applied at specific times (e.g., 00:00, 08:00, 16:00 UTC)
                # The funding rate is typically applied to the notional value of the position.
                
                # Calculate notional value based on current price
                notional_value = position_size_btc * row['close'] 
                funding_fee = notional_value * row['funding_rate']
                
                # Funding fee affects total margin balance
                if position_state == 'LONG':
                    margin_balance -= funding_fee
                else: # SHORT
                    margin_balance += funding_fee
                
                # logging.info(f"Funding at {index}. Rate: {row['funding_rate']:.4%}. Fee: {-funding_fee if position_state == 'LONG' else funding_fee:,.2f}. New Margin: {margin_balance:,.2f}")
                trade_log.append({'date': index, 'type': 'FUNDING', 'price': row['close'], 'profit_usdt': -funding_fee if position_state == 'LONG' else funding_fee})

                if margin_balance <= 0: # Check for account liquidation due to funding
                    logging.warning(f"Account balance is zero or negative due to funding at {index}. Stopping backtest.")
                    break
            logging.debug(f"After Funding Rate. margin_balance: {margin_balance:,.2f}")

            # --- 3. Check for Take Profit / Stop Loss ---
            current_price = row['close'] # Use close for signal, but high/low for TP/SL hit
            
            if position_state == 'LONG':
                # Check Take Profit for LONG
                if current_take_profit_price > 0 and row['high'] >= current_take_profit_price:
                    pnl = (current_take_profit_price - entry_price) * position_size_btc
                    margin_balance += pnl
                    logging.info(f"TAKE PROFIT (LONG) at {current_take_profit_price:,.2f}. PnL: {pnl:,.2f}. New Margin: {margin_balance:,.2f}")
                    trade_log.append({'date': index, 'type': 'TP_LONG', 'price': current_take_profit_price, 'profit_usdt': pnl})
                    
                    position_state = None
                    position_size_btc = 0.0
                    entry_price = 0.0
                    liquidation_price = 0.0
                    initial_margin_for_position = 0.0
                    current_take_profit_price = 0.0
                    current_stop_loss_price = 0.0
                    continue # Position closed, skip signal processing for this candle

                # Check Stop Loss for LONG
                if current_stop_loss_price > 0 and row['low'] <= current_stop_loss_price:
                    pnl = (current_stop_loss_price - entry_price) * position_size_btc
                    margin_balance += pnl
                    logging.info(f"STOP LOSS (LONG) at {current_stop_loss_price:,.2f}. PnL: {pnl:,.2f}. New Margin: {margin_balance:,.2f}")
                    trade_log.append({'date': index, 'type': 'SL_LONG', 'price': current_stop_loss_price, 'profit_usdt': pnl})
                    
                    position_state = None
                    position_size_btc = 0.0
                    entry_price = 0.0
                    liquidation_price = 0.0
                    initial_margin_for_position = 0.0
                    current_take_profit_price = 0.0
                    current_stop_loss_price = 0.0
                    continue # Position closed, skip signal processing for this candle

            elif position_state == 'SHORT':
                # Check Take Profit for SHORT
                if current_take_profit_price > 0 and row['low'] <= current_take_profit_price:
                    pnl = (entry_price - current_take_profit_price) * position_size_btc
                    margin_balance += pnl
                    logging.info(f"TAKE PROFIT (SHORT) at {current_take_profit_price:,.2f}. PnL: {pnl:,.2f}. New Margin: {margin_balance:,.2f}")
                    trade_log.append({'date': index, 'type': 'TP_SHORT', 'price': current_take_profit_price, 'profit_usdt': pnl})
                    
                    position_state = None
                    position_size_btc = 0.0
                    entry_price = 0.0
                    liquidation_price = 0.0
                    initial_margin_for_position = 0.0
                    current_take_profit_price = 0.0
                    current_stop_loss_price = 0.0
                    continue # Position closed, skip signal processing for this candle

                # Check Stop Loss for SHORT
                if current_stop_loss_price > 0 and row['high'] >= current_stop_loss_price:
                    pnl = (entry_price - current_stop_loss_price) * position_size_btc
                    margin_balance += pnl
                    logging.info(f"STOP LOSS (SHORT) at {current_stop_loss_price:,.2f}. PnL: {pnl:,.2f}. New Margin: {margin_balance:,.2f}")
                    trade_log.append({'date': index, 'type': 'SL_SHORT', 'price': current_stop_loss_price, 'profit_usdt': pnl})
                    
                    position_state = None
                    position_size_btc = 0.0
                    entry_price = 0.0
                    liquidation_price = 0.0
                    initial_margin_for_position = 0.0
                    current_take_profit_price = 0.0
                    current_stop_loss_price = 0.0
                    continue # Position closed, skip signal processing for this candle

            # --- 4. Trailing Stop Loss Logic ---
            if position_state is not None:
                # Calculate current profit percentage
                if position_state == 'LONG':
                    current_profit_pct = (current_price - entry_price) / entry_price
                else: # SHORT
                    current_profit_pct = (entry_price - current_price) / entry_price

                # Activate trailing stop if profit_lock_pct is reached
                if current_profit_pct >= self.profit_lock_pct:
                    if position_state == 'LONG':
                        # Trailing stop for LONG: move SL up if price rises
                        new_trailing_stop_price = current_price * (1 - self.stop_loss_pct)
                        if new_trailing_stop_price > current_stop_loss_price:
                            current_stop_loss_price = new_trailing_stop_price
                            logging.info(f"TRAILING STOP (LONG) at {index}. SL moved to: {current_stop_loss_price:,.2f}")
                    elif position_state == 'SHORT':
                        # Trailing stop for SHORT: move SL down if price falls
                        new_trailing_stop_price = current_price * (1 + self.stop_loss_pct)
                        if new_trailing_stop_price < current_stop_loss_price:
                            current_stop_loss_price = new_trailing_stop_price
                            logging.info(f"TRAILING STOP (SHORT) at {index}. SL moved to: {current_stop_loss_price:,.2f}")

            # --- 5. Check for Signal ---
            signal = my_strategy.check_for_signal(row)
            current_price = row['close']

            # --- 6. Execute Trades (Doten Logic with TP/SL) ---
            if signal == "BUY" and position_state != 'LONG':
                # Close existing short position (if any)
                if position_state == 'SHORT':
                    pnl = (entry_price - current_price) * position_size_btc
                    margin_balance += pnl # Realize PnL
                    logging.info(f"CLOSE SHORT (Signal) at {current_price:,.2f}. PnL: {pnl:,.2f}. New Margin: {margin_balance:,.2f}")
                    trade_log.append({'date': index, 'type': 'CLOSE_SHORT_SIGNAL', 'price': current_price, 'profit_usdt': pnl})
                    
                    # Reset position state
                    position_state = None
                    position_size_btc = 0.0
                    entry_price = 0.0
                    liquidation_price = 0.0
                    initial_margin_for_position = 0.0
                    current_take_profit_price = 0.0
                    current_stop_loss_price = 0.0

                # Open new long position
                logging.debug(f"Attempting to GO LONG. Current margin_balance: {margin_balance:,.2f}")
                # Check if enough capital to open new position (considering initial margin and fees)
                if margin_balance <= 0: 
                    logging.warning(f"Not enough capital to open new long position at {index}. Stopping backtest.")
                    break

                # Calculate initial margin required for the new position
                initial_margin_for_position = margin_balance * config.TRADE_CAPITAL_PERCENTAGE
                
                # Calculate notional value and fee for the new position
                notional_value = initial_margin_for_position * self.leverage
                fee = notional_value * self.taker_fee_rate
                
                logging.debug(f"GO LONG: initial_margin_for_position: {initial_margin_for_position:,.2f}, notional_value: {notional_value:,.2f}, fee: {fee:,.2f}")
                logging.debug(f"GO LONG: margin_balance before fee deduction: {margin_balance:,.2f}")

                # Check if enough capital for fee
                if margin_balance < fee:
                    logging.warning(f"Not enough capital for fee ({fee:,.2f}) to open long position at {index}. Stopping backtest.")
                    # If not enough for fee, we can't open position, and effectively bankrupt
                    margin_balance = 0 
                    break

                margin_balance -= fee # Deduct fee from total equity
                logging.debug(f"GO LONG: margin_balance after fee deduction: {margin_balance:,.2f}")
                
                position_state = 'LONG'
                entry_price = current_price
                position_size_btc = notional_value / entry_price
                
                # Calculate liquidation price for long position
                # Formula: EntryPrice * (1 - (1 / Leverage) + MaintenanceMarginRate)
                liquidation_price = entry_price * (1 - (1 / self.leverage) + self.maintenance_margin_rate)

                # Set initial TP/SL prices
                current_take_profit_price = entry_price * (1 + self.take_profit_pct)
                current_stop_loss_price = entry_price * (1 - self.stop_loss_pct)
                
                logging.info(f"GO LONG at {entry_price:,.2f}. Size: {position_size_btc:.4f} BTC. Liq. Price: {liquidation_price:,.2f}. TP: {current_take_profit_price:,.2f}, SL: {current_stop_loss_price:,.2f}. Fee: {fee:,.2f}")
                trade_log.append({'date': index, 'type': 'GO_LONG', 'price': entry_price, 'size_btc': position_size_btc, 'initial_margin': initial_margin_for_position})

            elif signal == "SELL" and position_state != 'SHORT':
                # Close existing long position (if any)
                if position_state == 'LONG':
                    pnl = (current_price - entry_price) * position_size_btc
                    margin_balance += pnl # Realize PnL
                    logging.info(f"CLOSE LONG (Signal) at {current_price:,.2f}. PnL: {pnl:,.2f}. New Margin: {margin_balance:,.2f}")
                    trade_log.append({'date': index, 'type': 'CLOSE_LONG_SIGNAL', 'price': current_price, 'profit_usdt': pnl})

                    # Reset position state
                    position_state = None
                    position_size_btc = 0.0
                    entry_price = 0.0
                    liquidation_price = 0.0
                    initial_margin_for_position = 0.0
                    current_take_profit_price = 0.0
                    current_stop_loss_price = 0.0

                # Open new short position
                logging.debug(f"Attempting to GO SHORT. Current margin_balance: {margin_balance:,.2f}")
                if margin_balance <= 0: 
                    logging.warning(f"Not enough capital to open new short position at {index}. Stopping backtest.")
                    break

                position_state = 'SHORT'
                entry_price = current_price
                
                # Calculate initial margin required for the new position
                initial_margin_for_position = margin_balance * config.TRADE_CAPITAL_PERCENTAGE
                
                # Calculate notional value and fee for the new position
                notional_value = initial_margin_for_position * self.leverage
                fee = notional_value * self.taker_fee_rate
                
                logging.debug(f"GO SHORT: initial_margin_for_position: {initial_margin_for_position:,.2f}, notional_value: {notional_value:,.2f}, fee: {fee:,.2f}")
                logging.debug(f"GO SHORT: margin_balance before fee deduction: {margin_balance:,.2f}")

                # Check if enough capital for fee
                if margin_balance < fee:
                    logging.warning(f"Not enough capital for fee ({fee:,.2f}) to open short position at {index}. Stopping backtest.")
                    margin_balance = 0 
                    break

                margin_balance -= fee # Deduct fee from total equity
                logging.debug(f"GO SHORT: margin_balance after fee deduction: {margin_balance:,.2f}")
                
                position_size_btc = notional_value / entry_price
                
                # Calculate liquidation price for short position
                # Formula: EntryPrice * (1 + (1 / Leverage) - MaintenanceMarginRate)
                liquidation_price = entry_price * (1 + (1 / self.leverage) - self.maintenance_margin_rate)

                # Set initial TP/SL prices
                current_take_profit_price = entry_price * (1 - self.take_profit_pct)
                current_stop_loss_price = entry_price * (1 + self.stop_loss_pct)

                logging.info(f"GO SHORT at {entry_price:,.2f}. Size: {position_size_btc:.4f} BTC. Liq. Price: {liquidation_price:,.2f}. TP: {current_take_profit_price:,.2f}, SL: {current_stop_loss_price:,.2f}. Fee: {fee:,.2f}")
                trade_log.append({'date': index, 'type': 'GO_SHORT', 'price': entry_price, 'size_btc': position_size_btc, 'initial_margin': initial_margin_for_position})

            # --- 5. Update Equity Curve ---
            # This part needs to be careful. Equity is margin_balance + unrealized PnL
            current_equity = margin_balance
            if position_state == 'LONG':
                current_equity += (row['close'] - entry_price) * position_size_btc
            elif position_state == 'SHORT':
                current_equity += (entry_price - row['close']) * position_size_btc
            equity_curve.append({'date': index, 'equity': current_equity})

        # --- Final Calculation ---
        # If there's an open position at the end, close it at the last price
        if position_state == 'LONG':
            pnl = (self.df.iloc[-1]['close'] - entry_price) * position_size_btc
            margin_balance += pnl
            trade_log.append({'date': self.df.index[-1], 'type': 'FINAL_CLOSE_LONG', 'price': self.df.iloc[-1]['close'], 'profit_usdt': pnl})
        elif position_state == 'SHORT':
            pnl = (entry_price - self.df.iloc[-1]['close']) * position_size_btc
            margin_balance += pnl
            trade_log.append({'date': self.df.index[-1], 'type': 'FINAL_CLOSE_SHORT', 'price': self.df.iloc[-1]['close'], 'profit_usdt': pnl})

        final_equity = margin_balance # This is the final realized equity
        total_pnl = final_equity - self.initial_capital
        total_pnl_pct = (total_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        num_trades = len([t for t in trade_log if 'GO_' in t['type']])

        logging.info("="*50)
        logging.info("Derivatives Backtest Finished")
        logging.info(f"Final Equity: {final_equity:,.2f} USDT")
        logging.info(f"Total PnL: {total_pnl:,.2f} USDT ({total_pnl_pct:,.2f}%)")
        logging.info(f"Number of Entry Trades: {num_trades}")
        logging.info("="*50)

        # Save logs
        pd.DataFrame(trade_log).to_csv(config.TRADE_LOG_PATH, index=False)
        logging.info(f"Trade log saved to {config.TRADE_LOG_PATH}")
        
        # Optional: Save equity curve
        # pd.DataFrame(equity_curve).to_csv('equity_curve.csv', index=False)

if __name__ == '__main__':
    # To run the backtest directly
    backtester = DerivativesBacktester()
    backtester.run()