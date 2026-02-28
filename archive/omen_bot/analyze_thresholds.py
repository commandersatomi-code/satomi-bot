import pandas as pd

# Define the thresholds in JPY
thresholds = {
    "1,000,000 JPY": 1000000,
    "5,000,000 JPY": 5000000,
    "10,000,000 JPY": 10000000,
    "50,000,000 JPY": 50000000,
}

# JPY/USDT rate used in the backtest
JPY_USDT_RATE = 150

# Read the trade log
trade_log_df = pd.read_csv("/Users/mucbook/バシャール/omen_bot/data/backtest_trade_log_1h.csv")

# Convert the 'date' column to datetime objects
trade_log_df['date'] = pd.to_datetime(trade_log_df['date'])

print("Dates when capital exceeded thresholds:")

for name, threshold_jpy in thresholds.items():
    threshold_usdt = threshold_jpy / JPY_USDT_RATE
    first_time_exceeded = trade_log_df[trade_log_df['usdt_capital_after_trade'] > threshold_usdt].iloc[0]
    
    date_exceeded = first_time_exceeded['date']
    capital_jpy = first_time_exceeded['usdt_capital_after_trade'] * JPY_USDT_RATE
    
    print(f"- {name}: {date_exceeded.strftime('%Y-%m-%d')} (Capital: {capital_jpy:,.0f} JPY)")
