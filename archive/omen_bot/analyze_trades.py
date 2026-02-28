import pandas as pd

# Read the trade log
trade_log_df = pd.read_csv("/Users/mucbook/バシャール/omen_bot/data/backtest_trade_log_1h.csv")

# Sort the trades by profit in descending order
sorted_trades = trade_log_df.sort_values(by='profit_usdt', ascending=False)

# Display the top 5 most profitable trades
print("Top 5 Most Profitable Trades:")
print(sorted_trades.head(5).to_string())
