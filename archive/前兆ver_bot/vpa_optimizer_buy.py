import pandas as pd
import numpy as np
from pybit.unified_trading import HTTP
import config
import time

# ==============================================================================
# 1. DATA FETCHING & INDICATOR CALCULATION (Unaltered)
# ==============================================================================

def fetch_all_data(session, symbol, interval, start_timestamp):
    all_data = []
    end_time = int(time.time() * 1000)
    while end_time > start_timestamp:
        try:
            response = session.get_kline(
                category="linear", symbol=symbol, interval=interval,
                end=end_time, limit=1000
            )
            if response['retCode'] != 0: break
            data = response['result']['list']
            if not data: break
            all_data = data + all_data
            oldest_ts = int(data[-1][0])
            if oldest_ts < start_timestamp: break
            end_time = oldest_ts - 1
            print(f"Fetching... {len(all_data)} records so far.")
            time.sleep(0.2)
        except Exception as e:
            print(f"An error occurred: {e}")
            break
    if not all_data: return pd.DataFrame()
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df.astype(float).sort_index()
    return df[df.index >= pd.to_datetime(start_timestamp, unit='ms')]

def calculate_indicators(df, atr_period=14, vol_sma_period=20):
    df['high_low'] = df['high'] - df['low']
    df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
    df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
    df['atr'] = df['true_range'].ewm(span=atr_period, adjust=False).mean()
    df['volume_sma'] = df['volume'].rolling(window=vol_sma_period).mean()
    return df

# ==============================================================================
# 2. "BUY" STRATEGY OPTIMIZATION
# ==============================================================================

def run_analysis_for_params_buy(df, vol_multiplier, body_atr_ratio, look_forward_period=5):
    """Runs the VPA analysis for the BUY strategy."""
    # Condition A: High Volume
    is_high_volume = df['volume'] > (df['volume_sma'] * vol_multiplier)
    # Condition B: Lack of Result on a DOWN move
    is_bearish_candle = df['close'] < df['open']
    candle_body_size = abs(df['close'] - df['open'])
    is_small_body = candle_body_size < (df['atr'] * body_atr_ratio)
    
    df['omen_found'] = is_high_volume & is_bearish_candle & is_small_body
    omen_indices = df[df['omen_found']].index
    
    if len(omen_indices) == 0:
        return {"signals": 0, "win_rate": 0, "ev_pct": 0}

    trade_results_pct = []
    for idx in omen_indices:
        omen_candle = df.loc[idx]
        future_candles_end_index = df.index.get_loc(idx) + 1 + look_forward_period
        if future_candles_end_index > len(df): continue
        future_candles = df.iloc[df.index.get_loc(idx) + 1:future_candles_end_index]
        if future_candles.empty: continue
        
        # We are buying, so a rise is a win. We measure the max rise.
        max_rise_pct = (future_candles['high'].max() - omen_candle['close']) / omen_candle['close'] * 100
        trade_results_pct.append(max_rise_pct)

    if not trade_results_pct:
        return {"signals": 0, "win_rate": 0, "ev_pct": 0}

    results_series = pd.Series(trade_results_pct)
    
    # A "win" is a rise of more than 1%
    wins = results_series[results_series > 1.0]
    losses = results_series[results_series <= 1.0]
    
    win_rate = len(wins) / len(results_series) if len(results_series) > 0 else 0
    avg_win_pct = wins.mean() if not wins.empty else 0
    avg_loss_pct = abs(losses.mean()) if not losses.empty else 0

    expected_value_pct = (win_rate * avg_win_pct) - ((1 - win_rate) * avg_loss_pct)

    return {
        "signals": len(results_series),
        "win_rate": win_rate * 100,
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "ev_pct": expected_value_pct
    }

# ==============================================================================
# 3. EXECUTION: GRID SEARCH & VERIFICATION FOR "BUY" STRATEGY
# ==============================================================================

if __name__ == "__main__":
    # --- Parameters ---
    SYMBOL = "BTCUSDT"
    INTERVAL = "D"
    START_TIMESTAMP = 1534377600000
    TRAIN_TEST_SPLIT_RATIO = 0.7

    # --- Fetch Data ---
    session = HTTP(testnet=False, api_key=config.BYBIT_API_KEY, api_secret=config.BYBIT_API_SECRET)
    print("Fetching all historical data...")
    full_data = fetch_all_data(session, SYMBOL, INTERVAL, START_TIMESTAMP)
    
    if full_data.empty:
        print("Could not fetch data. Aborting.")
    else:
        print(f"Successfully fetched {len(full_data)} days of data.")
        data_with_indicators = calculate_indicators(full_data)

        # --- Split Data ---
        split_index = int(len(data_with_indicators) * TRAIN_TEST_SPLIT_RATIO)
        train_data = data_with_indicators.iloc[:split_index]
        test_data = data_with_indicators.iloc[split_index:]
        print(f"Splitting data: {len(train_data)} days for training, {len(test_data)} days for testing.")

        # --- Grid Search on Training Data ---
        print("\n--- Running Grid Search for BUY Strategy on Training Data ---")
        vol_multipliers = np.arange(1.2, 2.1, 0.1)
        body_ratios = np.arange(0.2, 0.7, 0.1)
        optimization_results = []

        for vol_mult in vol_multipliers:
            for body_ratio in body_ratios:
                params = f"Vol: {vol_mult:.1f}, Body: {body_ratio:.1f}"
                print(f"Testing parameters: {params}")
                stats = run_analysis_for_params_buy(train_data, vol_mult, body_ratio)
                if stats["signals"] > 0:
                    stats['vol_mult'] = vol_mult
                    stats['body_ratio'] = body_ratio
                    optimization_results.append(stats)

        # --- Analyze Optimization Results ---
        if not optimization_results:
            print("No signals found in any parameter combination.")
        else:
            results_df = pd.DataFrame(optimization_results)
            results_df = results_df.round(2)
            results_df.sort_values(by="ev_pct", ascending=False, inplace=True)
            
            print("\n--- BUY Strategy Optimization Results (Top 10 by EV) ---")
            print(results_df.head(10).to_string(index=False))
            results_df.to_csv("vpa_optimization_summary_buy.csv", index=False)
            print("\nFull summary saved to vpa_optimization_summary_buy.csv")

            # --- Verification on Test Data ---
            best_params = results_df.iloc[0]
            print(f"\n--- Verifying Best BUY Parameters on Unseen Test Data ---")
            print(f"Best Parameters Found (from Training): Vol Mult: {best_params['vol_mult']:.1f}, Body Ratio: {best_params['body_ratio']:.1f}")
            
            test_stats = run_analysis_for_params_buy(test_data, best_params['vol_mult'], best_params['body_ratio'])
            print("\nPerformance on Test Data:")
            print(f"  Signals: {test_stats['signals']}")
            print(f"  Win Rate: {test_stats['win_rate']:.2f}%")
            print(f"  Expected Value per Trade: {test_stats['ev_pct']:.2f}%")

            if test_stats["ev_pct"] > 0:
                print("\nCONCLUSION: The BUY strategy shows positive expected value on unseen data.")
                print("This suggests the identified edge for the BUY side is also ROBUST.")
            else:
                print("\nCONCLUSION: The BUY strategy DID NOT show positive expected value on unseen data.")
                print("This suggests the BUY side edge was likely due to overfitting.")
