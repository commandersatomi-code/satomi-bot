import pandas as pd
import numpy as np

# ==========================================
# 1. 指標計算 (RSI)
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    # Fill NaN
    return rsi.fillna(50)

# ==========================================
# 2. バックテストロジック (Smart Spider)
# ==========================================
def run_smart_spider(closes, rsi_values, grid_size, rsi_limit):
    """
    rsi_limit: この値を下回っている時だけ「買い」を実行する (100なら無条件)
    """
    initial_equity = 1000000 
    positions = []
    total_profit = 0
    
    # グリッドレベルの計算（高速化のため）
    # ただし、エントリー判断にRSIが必要なため、ループ内で動的に判断
    
    current_grid_level = int(closes[0] // grid_size)
    max_drawdown = 0
    peak_equity = initial_equity
    
    # 統計用
    buy_count = 0
    skip_count = 0 # RSIフィルターで回避した回数
    
    for i in range(1, len(closes)):
        price = closes[i]
        rsi = rsi_values[i]
        new_grid_level = int(price // grid_size)
        
        # --- 下落局面 (買いチャンス) ---
        if new_grid_level < current_grid_level:
            diff = current_grid_level - new_grid_level
            
            # グリッドをまたいだ回数分判定
            for _ in range(diff):
                # ★ ここがSmart Spiderの脳 (RSIフィルター)
                if rsi < rsi_limit:
                    positions.append(price)
                    buy_count += 1
                else:
                    # RSIが高すぎる(まだ下落の勢いが弱い、あるいは暴落初動)ので見送る
                    skip_count += 1
            
        # --- 上昇局面 (売りチャンス) ---
        elif new_grid_level > current_grid_level:
            diff = new_grid_level - current_grid_level
            for _ in range(diff):
                if len(positions) > 0:
                    # 利益確定 (FIFO: First In First Out for simplicity/tax logic, 
                    # usually LIFO is better for grid but let's stick to simple)
                    bought_price = positions.pop(0)
                    profit = price - bought_price
                    total_profit += profit
        
        current_grid_level = new_grid_level
        
        # --- ドローダウン計算 (簡易版: ポジションがある時のみ計算して高速化) ---
        if len(positions) > 0:
            unrealized = sum(price - p for p in positions)
            current_val = initial_equity + total_profit + unrealized
            if current_val > peak_equity:
                peak_equity = current_val
            dd = peak_equity - current_val
            if dd > max_drawdown:
                max_drawdown = dd
        else:
            # ポジションなし＝現金100%
            current_val = initial_equity + total_profit
            if current_val > peak_equity:
                peak_equity = current_val

    # 最終評価額
    final_unrealized = sum(closes[-1] - p for p in positions)
    final_value = initial_equity + total_profit + final_unrealized
    
    return final_value, total_profit, max_drawdown, buy_count, skip_count

# ==========================================
# 3. メイン処理
# ==========================================
def main():
    filepath = "data/bybit_btc_usdt_linear_5m_full.csv"
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    
    # RSI計算
    print("Calculating RSI...")
    df['rsi'] = calculate_rsi(df['close'], period=14)
    
    # データ分割 (最新1年をテスト、その前の2年を訓練)
    # 5分足はデータ量が多いので、直近3年分くらいに絞る
    last_date = df.index[-1]
    split_date = last_date - pd.Timedelta(days=365)
    start_train_date = split_date - pd.Timedelta(days=365*2)
    
    train_df = df[(df.index >= start_train_date) & (df.index < split_date)]
    test_df = df[df.index >= split_date]
    
    print(f"Train Data: {train_df.index[0]} ~ {train_df.index[-1]} ({len(train_df)} rows)")
    print(f"Test Data : {test_df.index[0]} ~ {test_df.index[-1]} ({len(test_df)} rows)")
    
    # Numpy配列化 (高速化)
    train_closes = train_df['close'].values
    train_rsis = train_df['rsi'].values
    
    # --- 最適化 (Grid Search) ---
    grid_sizes = [500, 1000, 2000, 3000, 5000]
    rsi_limits = [30, 40, 50, 60, 70, 100] # 100 = No Filter
    
    print("\n--- Optimization Results (Score = Profit / MaxDD) ---")
    print(f"{ 'Grid':<6} | { 'RSI <':<6} | { 'Return':<8} | { 'MaxDD':<10} | { 'Score':<6} | { 'Buy/Skip':<12}")
    print("-" * 65)
    
    best_score = -np.inf
    best_params = (1000, 100) # Default
    
    for gs in grid_sizes:
        for rl in rsi_limits:
            final, profit, dd, buys, skips = run_smart_spider(train_closes, train_rsis, gs, rl)
            ret_pct = (final - 1000000) / 1000000 * 100
            
            # スコア計算: 安定性重視 (利益 / (ドローダウン + 1))
            # ただし、取引回数が極端に少ない(0回など)場合は除外
            if buys == 0:
                score = 0
            else:
                score = profit / (dd + 1)
            
            # 見やすく表示
            print(f"{gs:<6} | {rl:<6} | {ret_pct:>7.2f}% | {dd:>10.0f} | {score:>6.2f} | {buys}/{skips}")
            
            if score > best_score:
                best_score = score
                best_params = (gs, rl)
                
    print("-" * 65)
    print(f"Best Parameters: Grid Size = {best_params[0]}, RSI Limit = {best_params[1]}")
    
    # --- テスト (未知のデータ) ---
    print("\n--- Validation on Test Data (Last 1 Year) ---")
    test_closes = test_df['close'].values
    test_rsis = test_df['rsi'].values
    
    final, profit, dd, buys, skips = run_smart_spider(test_closes, test_rsis, best_params[0], best_params[1])
    ret_pct = (final - 1000000) / 1000000 * 100
    
    print(f"Final Equity: {final:,.0f} JPY")
    print(f"Total Return: {ret_pct:.2f}%")
    print(f"Max Drawdown: {dd:,.0f} JPY")
    print(f"Realized Profit: {profit:,.0f} JPY")
    print(f"Trades Executed (Buys): {buys}")
    print(f"Trades Skipped (Filter): {skips}")

    # 比較のため、フィルターなし(RSI<100)の場合も表示
    if best_params[1] != 100:
        print("\n(Reference: Without RSI Filter)")
        final_no, profit_no, dd_no, buys_no, skips_no = run_smart_spider(test_closes, test_rsis, best_params[0], 100)
        ret_no = (final_no - 1000000) / 1000000 * 100
        print(f"Return: {ret_no:.2f}% | MaxDD: {dd_no:,.0f}")

if __name__ == "__main__":
    main()
