import pandas as pd

def analyze_performance(trade_log_path):
    """Analyzes drawdown and trade duration from a backtest trade log."""

    trade_log_df = pd.read_csv(trade_log_path)
    trade_log_df['date'] = pd.to_datetime(trade_log_df['date'])

    # --- 1. Calculate Drawdown ---
    # First, we need to construct the equity curve. 
    # The log contains USDT capital only after SELLs. We need to fill in the gaps.
    equity = trade_log_df.set_index('date')['usdt_capital_after_trade'].copy()
    equity = equity[equity > 0] # Filter out the zero capital entries during trades
    
    # Forward-fill the equity values to represent holding periods
    equity = equity.resample('h').ffill()
    
    # Back-fill any initial NaN values
    equity.bfill(inplace=True)

    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_drawdown = drawdown.min()
    
    end_of_max_drawdown = drawdown.idxmin()
    start_of_max_drawdown = running_max.loc[:end_of_max_drawdown][running_max == running_max.loc[end_of_max_drawdown]].index[0]

    print("--- Performance Analysis ---")
    print(f"\nMaximum Drawdown: {max_drawdown:.2%}")
    print(f"Drawdown Period: {start_of_max_drawdown.strftime('%Y-%m-%d')} to {end_of_max_drawdown.strftime('%Y-%m-%d')}")

    # --- 2. Calculate Average Trade Duration ---
    buy_trades = trade_log_df[trade_log_df['type'] == 'BUY']
    sell_trades = trade_log_df[trade_log_df['type'] == 'SELL']

    if len(buy_trades) == 0 or len(sell_trades) == 0:
        print("\nCould not calculate average trade duration: No trades found.")
        return

    # Assuming each BUY is followed by a SELL
    durations = []
    # Make sure we have the same number of buys and sells to pair them up
    num_trades = min(len(buy_trades), len(sell_trades))
    for i in range(num_trades):
        buy_time = buy_trades.iloc[i]['date']
        sell_time = sell_trades.iloc[i]['date']
        durations.append(sell_time - buy_time)

    if durations:
        average_duration = sum(durations, pd.Timedelta(0)) / len(durations)
        print(f"\nAverage Trade Duration: {average_duration}")

if __name__ == "__main__":
    # We will use the log from the profitable 1-hour backtest
    # First, we need to re-run the original backtest to ensure the log is correct
    import os
    os.system("python3 /Users/mucbook/バシャール/omen_bot/backtest_1h.py")
    
    trade_log_path = "/Users/mucbook/バシャール/omen_bot/data/backtest_trade_log_1h.csv"
    if os.path.exists(trade_log_path):
        analyze_performance(trade_log_path)
    else:
        print(f"Error: Trade log file not found at {trade_log_path}")
