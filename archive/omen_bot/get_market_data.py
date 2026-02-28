import pandas as pd
from pybit.unified_trading import HTTP
import config
import numpy as np

STRATEGY_PARAMS = {
    "SELL": {
        "HighestQuality": {"vol_mult": 2.0, "body_ratio": 0.3},
        "Balanced": {"vol_mult": 1.6, "body_ratio": 0.5},
        "Action": {"vol_mult": 1.2, "body_ratio": 0.6}
    },
    "BUY": {
        "HighestQuality": {"vol_mult": 2.0, "body_ratio": 0.3},
        "Balanced": {"vol_mult": 1.7, "body_ratio": 0.6},
        "Action": {"vol_mult": 1.3, "body_ratio": 0.6}
    }
}

def calculate_indicators(df, atr_period=14, vol_sma_period=20):
    df['high_low'] = df['high'] - df['low']
    df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
    df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
    df['atr'] = df['true_range'].ewm(span=atr_period, adjust=False).mean()
    df['volume_sma'] = df['volume'].rolling(window=vol_sma_period).mean()
    return df

def check_and_explain_signals():
    """Fetches data, calculates indicators, and explains why a signal was or was not triggered."""
    try:
        session = HTTP(testnet=False, api_key=config.BYBIT_API_KEY, api_secret=config.BYBIT_API_SECRET)
        
        response = session.get_kline(
            category="spot",
            symbol="BTCUSDT",
            interval="60",
            limit=30 
        )

        if not (response['retCode'] == 0 and response['result']['list']):
            print(f"データ取得エラー: {response.get('retMsg', 'Unknown error')}")
            return

        data = response['result']['list']
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df = df.astype(float).sort_index()

        df_with_indicators = calculate_indicators(df)
        latest_candle = df_with_indicators.iloc[-1]

        print("■■■■■■■■■■ 現在の状況分析 ■■■■■■■■■■")
        print(f"\n1. 直近の1時間足データ ( {latest_candle.name} )")
        print(f"  始値: {latest_candle['open']}")
        print(f"  高値: {latest_candle['high']}")
        print(f"  安値: {latest_candle['low']}")
        print(f"  終値: {latest_candle['close']}")
        print(f"  出来高: {latest_candle['volume']:.2f}")

        print(f"\n2. 計算されたテクニカル指標")
        print(f"  ATR (14): {latest_candle['atr']:.2f}")
        print(f"  出来高SMA (20): {latest_candle['volume_sma']:.2f}")

        print("\n3. シグナル判定")
        
        # --- BUYシグナルの判定 ---
        print("\n---【買いシグナル (BUY) の判定】---")
        is_bearish_candle = latest_candle['close'] < latest_candle['open']
        print(f"条件1: 陰線であるか？ -> {'はい' if is_bearish_candle else 'いいえ'}")
        print(f" (終値 {latest_candle['close']} < 始値 {latest_candle['open']})")

        if not is_bearish_candle:
            print("\n>>> 買いシグナルの条件1を満たしていないため、判定を終了します。")
        else:
            candle_body_size = abs(latest_candle['close'] - latest_candle['open'])
            print(f"\nローソク足の実体サイズ: {candle_body_size:.2f}")
            
            for quality, params in STRATEGY_PARAMS["BUY"].items():
                print(f"\n--- [{quality}] レベルの判定 ---")
                
                is_high_volume = latest_candle['volume'] > (latest_candle['volume_sma'] * params["vol_mult"])
                print(f"条件2: 出来高がSMAの{params['vol_mult']}倍より大きいか？ -> {'はい' if is_high_volume else 'いいえ'}")
                print(f" (現在の出来高 {latest_candle['volume']:.2f} > 基準値 {latest_candle['volume_sma'] * params['vol_mult']:.2f})")

                is_small_body = candle_body_size < (latest_candle['atr'] * params["body_ratio"])
                print(f"条件3: 実体がATRの{params['body_ratio']}倍より小さいか？ -> {'はい' if is_small_body else 'いいえ'}")
                print(f" (実体サイズ {candle_body_size:.2f} < 基準値 {latest_candle['atr'] * params['body_ratio']:.2f})")

                if is_high_volume and is_small_body:
                    print(f"\n>>> [{quality}] レベルの買いシグナル基準を満たしました！")
                    break
            else: # for-else loop
                print("\n>>> どの品質レベルの買いシグナル基準も満たしませんでした。")


        # --- SELLシグナルの判定 ---
        print("\n\n---【売りシグナル (SELL) の判定】---")
        is_bullish_candle = latest_candle['close'] > latest_candle['open']
        print(f"条件1: 陽線であるか？ -> {'はい' if is_bullish_candle else 'いいえ'}")
        print(f" (終値 {latest_candle['close']} > 始値 {latest_candle['open']})")

        if not is_bullish_candle:
            print("\n>>> 売りシグナルの条件1を満たしていないため、判定を終了します。")
        else:
            candle_body_size = latest_candle['close'] - latest_candle['open']
            print(f"\nローソク足の実体サイズ: {candle_body_size:.2f}")

            for quality, params in STRATEGY_PARAMS["SELL"].items():
                print(f"\n--- [{quality}] レベルの判定 ---")

                is_high_volume = latest_candle['volume'] > (latest_candle['volume_sma'] * params["vol_mult"])
                print(f"条件2: 出来高がSMAの{params['vol_mult']}倍より大きいか？ -> {'はい' if is_high_volume else 'いいえ'}")
                print(f" (現在の出来高 {latest_candle['volume']:.2f} > 基準値 {latest_candle['volume_sma'] * params['vol_mult']:.2f})")

                is_small_body = candle_body_size < (latest_candle['atr'] * params["body_ratio"])
                print(f"条件3: 実体がATRの{params['body_ratio']}倍より小さいか？ -> {'はい' if is_small_body else 'いいえ'}")
                print(f" (実体サイズ {candle_body_size:.2f} < 基準値 {latest_candle['atr'] * params['body_ratio']:.2f})")

                if is_high_volume and is_small_body:
                    print(f"\n>>> [{quality}] レベルの売りシグナル基準を満たしました！")
                    break
            else: # for-else loop
                print("\n>>> どの品質レベルの売りシグナル基準も満たしませんでした。")

        print("\n■■■■■■■■■■ 分析終了 ■■■■■■■■■■")


    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")

if __name__ == "__main__":
    check_and_explain_signals()