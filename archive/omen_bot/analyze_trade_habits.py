import pandas as pd

# Read the trade log
trade_log_df = pd.read_csv("/Users/mucbook/バシャール/omen_bot/data/backtest_trade_log_1h.csv")

# Separate sell trades and sort by profit
sell_trades = trade_log_df[trade_log_df['type'] == 'SELL'].copy()
sorted_sells = sell_trades.sort_values(by='profit_usdt', ascending=False)

# Get top 50 winners and losers
top_50_winners = sorted_sells.head(50)
top_50_losers = sorted_sells.tail(50)

print("--- Analysis of Top 50 Most Profitable Trades ---")
print("\nSignal Quality Distribution:")
print(top_50_winners['signal_quality'].value_counts())
print("\nProfit Statistics (USDT):")
print(top_50_winners['profit_usdt'].describe())

print("\n--- Analysis of Top 50 Most Loss-Making Trades ---")
print("\nSignal Quality Distribution:")
print(top_50_losers['signal_quality'].value_counts())
print("\nLoss Statistics (USDT):")
print(top_50_losers['profit_usdt'].describe())
