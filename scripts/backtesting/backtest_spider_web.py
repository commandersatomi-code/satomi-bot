import pandas as pd
import numpy as np

def load_data(filepath):
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    return df

def run_spider_backtest(df, grid_size):
    # Initial State
    initial_equity = 1000000 # 1,000,000 USDT/JPY
    equity = initial_equity
    positions = []
    total_profit = 0
    
    closes = df['close'].values
    
    if len(closes) == 0:
        return initial_equity, 0, 0
        
    current_grid_level = int(closes[0] // grid_size)
    
    max_drawdown = 0
    peak_equity = initial_equity
    
    for price in closes:
        new_grid_level = int(price // grid_size)
        
        # 境界をまたいだか？
        if new_grid_level < current_grid_level:
            # 1つ下のグリッドに落ちるごとに買う (1回あたり 0.01 BTCなど固定量とする)
            # ここではシンプルに1回あたり1万円分買うとする
            buy_unit = 10000
            positions.append(price)
            # 実際には equity は減らない（含み損になるだけ）
            
        elif new_grid_level > current_grid_level:
            # 1つ上のグリッドに昇るごとに、持っている一番安いポジションを利確
            if len(positions) > 0:
                # Spider Web ロジック: 一番古い(または一番安い)ポジションを決済
                # グリッドトレードでは通常、直近の買いを利確することが多いですが
                # 提示されたコードに従い pop(0) を使用
                bought_price = positions.pop(0)
                profit = price - bought_price
                total_profit += profit
        
        current_grid_level = new_grid_level
        
        # 含み損益の計算
        unrealized_pnl = sum([price - p for p in positions])
        current_total_value = initial_equity + total_profit + unrealized_pnl
        
        # ドローダウン計算
        if current_total_value > peak_equity:
            peak_equity = current_total_value
        dd = peak_equity - current_total_value
        if dd > max_drawdown:
            max_drawdown = dd
            
    final_value = initial_equity + total_profit + sum([closes[-1] - p for p in positions])
    return final_value, total_profit, max_drawdown

def main():
    data_path = 'data/bybit_btcusdt_linear_1m_full.csv'
    df = load_data(data_path)
    
    # Resample to 1H for speed (Spider Web logic on 1m is too slow for Python loop)
    print("Resampling to 1H...")
    df = df.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
    df.dropna(inplace=True)
    last_date = df.index[-1]
    split_date = last_date - pd.Timedelta(days=365)
    
    train_df = df[df.index < split_date]
    test_df = df[df.index >= split_date]
    
    # 訓練: 最適なグリッドサイズを探す
    # BTCの価格帯に合わせて 100から2000まで試す
    grid_sizes = [100, 250, 500, 1000, 2000, 5000]
    
    print("--- Training Spider Web ---")
    best_grid = 500
    best_score = -np.inf
    
    for gs in grid_sizes:
        final_val, realized, max_dd = run_spider_backtest(train_df, gs)
        ret = (final_val - 1000000) / 1000000 * 100
        # スコア = 利益 / (最大ドローダウン + 1)
        score = realized / (max_dd + 1)
        print(f"Grid Size: {gs:>4} | Return: {ret:>6.2f}% | Realized Profit: {realized:>10.0f} | MaxDD: {max_dd:>10.0f}")
        
        if score > best_score:
            best_score = score
            best_grid = gs
            
    print(f"\nBest Grid Size: {best_grid}")
    
    print("\n--- Testing Spider Web (Last 1 Year) ---")
    final_val, realized, max_dd = run_spider_backtest(test_df, best_grid)
    ret = (final_val - 1000000) / 1000000 * 100
    
    print(f"Test Results:")
    print(f"Grid Size: {best_grid}")
    print(f"Final Total Value: {final_val:,.0f}")
    print(f"Total Return: {ret:.2f}%")
    print(f"Realized Profit (Cash Flow): {realized:,.0f}")
    print(f"Max Drawdown: {max_dd:,.0f}")

if __name__ == "__main__":
    main()
