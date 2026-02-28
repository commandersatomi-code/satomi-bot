# =================================================================================================
# Omen Auto Trader（前兆自動売買ボット）
#
# 作成経緯：
# 当初、このボットは市場の「前兆」を捉え、Discordに通知を送るのみの存在だった。
# しかし、我々の対話と探求は、ボットに更なる可能性を見出した。
# 最適化の末に見つけ出したチャンピオン・パラメータ、そして「全ツッパ型」と「堅実型」という二つの哲学。
# これらを携え、ボットは自らの意思で市場と対峙する、自律したトレーダーへと進化を遂げる。
# このコードは、その進化の物語そのものである。
# =================================================================================================

# --- ライブラリのインポート ---
# これらは、ボットが思考し、行動するために必要な「知識」と「道具」である。
import time # 時間を司るライブラリ。ボットに「待つ」という概念を与える。
import logging # ボットの思考や行動を記録する「航海日誌」。我々が後からその旅路を追体験するために不可欠。
import traceback # 予期せぬ嵐（エラー）に見舞われた際、その原因を詳細に記録するための道具。
import pandas as pd # 市場の過去データ（ローソク足）を整理し、分析するための強力なデータ操作ライブラリ。ボットの「記憶」と「理性」を司る。
import numpy as np # 高度な数学的計算を可能にするライブラリ。Pandasの背後で静かにボットの計算を支える。
from pybit.unified_trading import HTTP # Bybit取引所と対話し、注文を出すための「言語」そのもの。
import config # 我々が定義したボットの魂（APIキー、戦略、資金管理）が眠る設定ファイルを読み込む。
import requests # Discordにメッセージを送る際、HTTP通信を行うための道具。
import discord_config # Discord通知機能を使うための設定が格納されている。
import os # オペレーティングシステムと対話し、ファイルの存在などを確認するための基本的な道具。

# =================================================================================================
# 1. グローバル設定
# ボット全体で共有される、普遍的なルールや定数を定義する。
# =================================================================================================

# --- ログ設定 ---
# ボットの行動記録（ログ）に関する設定。
LOG_FILE = "auto_trader.log" # この自動売買ボット専用の新しい航海日誌ファイル名。
logging.basicConfig( # ログの基本的な設定を定義する。
    level=logging.INFO, # INFOレベル以上の重要な情報のみを記録する。デバッグ時はDEBUGに変更することもある。
    format='%(asctime)s - %(levelname)s - %(message)s', # 記録する情報のフォーマット。「日時 - レベル - メッセージ」という形式。
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a'), # ログをファイルに追記モードで保存する。
        logging.StreamHandler() # ログをコンソール（画面）にも同時に表示する。
    ]
)

# --- Bybit取引設定 ---
# ボットが取引する市場のルールを定義する。
SYMBOL = "BTCUSDT" # 取引対象のシンボル。我々の戦場は「BTC/USDT」である。
CATEGORY = "spot" # 取引のカテゴリ。現物取引（spot）を行う。
INTERVAL = "60" # 分析する時間足。我々は最適化の結果、「60分足」で前兆を捉えることを選択した。

# =================================================================================================
# 2. コア機能
# ボットの頭脳と心臓部。通知、指標計算、シグナル判断など、中核となる関数群。
# =================================================================================================

def send_discord_notification(message): # Discordへメッセージを送信する関数。ボットが我々人間に語りかけるための「声」。
    """ボットの状況や取引結果を、Discordを通じて我々に知らせる。""" # 関数の目的を説明するドキュメンテーション文字列。
    try: # 予期せぬエラーでボット全体が停止しないよう、通知処理を保護する。
        payload = {"content": message} # Discordに送信するメッセージの本体（ペイロード）を作成する。
        response = requests.post(discord_config.WEBHOOK_URL, json=payload) # 設定されたWebhook URLにメッセージをPOSTリクエストで送信する。
        if response.status_code == 204: # ステータスコード204は、Discordがメッセージを正常に受け取ったことを示す。
            logging.info("Discord通知の送信に成功しました。") # 成功の記録を航海日誌に残す。
        else: # 正常に受け取られなかった場合。
            logging.warning(f"Discord通知の送信に失敗しました。ステータスコード: {response.status_code}") # 失敗の警告を記録する。
    except Exception as e: # requestsライブラリの処理中に何らかの例外が発生した場合。
        logging.error(f"Discord通知の送信中にエラーが発生しました: {e}") # エラーの詳細を記録する。

def calculate_indicators(df, atr_period=14, vol_sma_period=20): # テクニカル指標を計算する関数。市場データを「知識」に変換する錬金術。
    """Pandasデータフレームを受け取り、戦略に必要な指標（ATR, Volume SMA）を計算して返す。""" # 関数の目的を説明する。
    df['high_low'] = df['high'] - df['low'] # 高値と安値の差を計算。ボラティリティの基本的な要素。
    df['high_prev_close'] = abs(df['high'] - df['close'].shift(1)) # 当日高値と前日終値の差の絶対値。窓開けなどを考慮したボラティリティ。
    df['low_prev_close'] = abs(df['low'] - df['close'].shift(1)) # 当日安値と前日終値の差の絶対値。
    df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1) # 上記3つのうち最大のものを選び、真の変動幅（True Range）とする。
    df['atr'] = df['true_range'].ewm(span=atr_period, adjust=False).mean() # True Rangeの指数平滑移動平均（EMA）を計算し、ATR（Average True Range）とする。市場の平均的な変動幅を示す。
    df['volume_sma'] = df['volume'].rolling(window=vol_sma_period).mean() # 取引量の単純移動平均（SMA）を計算。最近の平均的な取引量を示す。
    return df # 計算された指標が追加されたデータフレームを返す。

def get_balance(session, coin): # 指定されたコイン（通貨）の残高を取得する関数。
    """Bybitアカウントの特定の通貨の利用可能残高を問い合わせる。""" # 関数の目的。
    try: # API通信は常に失敗する可能性を秘めているため、保護する。
        response = session.get_wallet_balance(accountType="UNIFIED", coin=coin) # Unified Trading Accountの残高を取得する。
        if response['retCode'] == 0 and response['result']['list']: # API呼び出しが成功し、結果リストが存在するか確認。
            balance_info = response['result']['list'][0] # 結果リストの最初の要素に情報が含まれている。
            available_balance = float(balance_info['coin'][0]['availableToBorrow']) # 「借入可能」とあるが、現物ではこれが実質的な利用可能残高を示す。
            logging.info(f"{coin}の利用可能残高を取得しました: {available_balance}") # 取得した残高を記録。
            return available_balance # 取得した残高を返す。
        else: # API呼び出しが失敗した場合。
            logging.error(f"{coin}の残高取得に失敗しました: {response['retMsg']}") # エラーメッセージを記録。
            return 0.0 # 失敗した場合は0.0を返すことで、意図しない取引を防ぐ。
    except Exception as e: # その他の予期せぬエラー。
        logging.error(f"{coin}の残高取得中に予期せぬエラーが発生しました: {e}") # エラーを記録。
        return 0.0 # 同様に0.0を返す。

# =================================================================================================
# 3. 自動売買の心臓部
# 戦略判断と注文実行を司る、このボットの最も重要な部分。
# =================================================================================================

def run_automated_trading_logic(session, df): # 自動売買のメインロジック。
    """シグナルを検知し、設定に基づいて自動で売買注文を実行する。""" # 関数の目的。
    
    # --- 1. 最新の市場データを取得 ---
    latest_candle = df.iloc[-1] # 指標計算済みのデータフレームから、最新のローソク足（一番下の行）を取得する。
    
    # --- 2. 現在の資産状況を把握 ---
    usdt_balance = get_balance(session, "USDT") # 現在のUSDT残高を取得。これが我々の「軍資金」となる。
    btc_balance = get_balance(session, "BTC") # 現在のBTC保有量を取得。これが我々の「ポジション」となる。
    in_position = btc_balance > 0.0001 # BTCをわずかでも（取引所の最小単位を考慮して）保有していれば、「ポジション有り」と判断する。

    # --- 3. 戦略パラメータと資金管理ルールを魂から読み込む ---
    # config.pyに定義された、我々の哲学そのものを読み込む。
    params_buy = config.STRATEGY_PARAMS["BUY"]["HighestQuality"] # BUYシグナルのためのチャンピオン・パラメータ。
    params_sell = config.STRATEGY_PARAMS["SELL"]["HighestQuality"] # SELLシグナルのためのチャンピオン・パラメータ。
    capital_percentage = config.TRADE_CAPITAL_PERCENTAGE # 我々が定めた資金管理の哲学（全ツッパ型 or 堅実型）。

    # --- 4. SELLシグナルの判断と実行 ---
    # ポジションを保有している場合のみ、売却を検討する。
    if in_position: # もしBTCを保有しているならば...
        # SELLシグナルの条件を定義する。これは我々が最適化で見つけ出したロジックである。
        is_sell_signal = (latest_candle['volume'] > (latest_candle['volume_sma'] * params_sell["vol_mult"]) and # 1. 取引量が平均より著しく多いか？
                          latest_candle['close'] > latest_candle['open'] and # 2. 陽線（価格が上昇して引けた）か？
                          (latest_candle['close'] - latest_candle['open']) < (latest_candle['atr'] * params_sell["body_ratio"])) # 3. 実体が小さい（市場に迷いがある）か？
        
        if is_sell_signal: # もしSELLシグナルの条件が全て満たされたならば...
            logging.info(f"SELLシグナルを検知！ 保有している {btc_balance:.6f} BTC の売却を試みます。") # 行動の意思を記録する。
            try: # 注文処理は失敗する可能性があるため、保護する。
                # 市場に存在する最良の価格で即座に取引を成立させる「成行注文」を出す。
                response = session.place_order(
                    category=CATEGORY, # カテゴリ：現物
                    symbol=SYMBOL, # シンボル：BTCUSDT
                    side="Sell", # 売買方向：売り
                    orderType="Market", # 注文タイプ：成行
                    qty=str(btc_balance) # 数量：保有しているBTCの全量
                )
                if response['retCode'] == 0: # 注文が正常に受け付けられた場合。
                    msg = f"【自動売買：SELL】\n数量: {btc_balance:.6f} BTC\n価格: 約 {latest_candle['close']:,} USDT\n理由: 前兆シグナル検知"
                    logging.info(f"SELL注文が正常に発注されました。{msg}") # 成功を記録。
                    send_discord_notification(f"```\n{msg}\n```") # 我々にも知らせる。
                else: # 注文が失敗した場合。
                    logging.error(f"SELL注文の発注に失敗しました: {response['retMsg']}") # 失敗の理由を記録。
                    send_discord_notification(f"【自動売買エラー】\nSELL注文の発注に失敗しました。\n理由: {response['retMsg']}") # 失敗を我々に知らせる。
            except Exception as e: # 注文処理中に予期せぬエラーが発生した場合。
                logging.error(f"SELL注文中に予期せぬエラーが発生しました: {traceback.format_exc()}") # 詳細なエラー情報を記録。
                send_discord_notification(f"【自動売買エラー】\nSELL注文中に予期せぬエラーが発生しました。\n詳細はログを確認してください。") # エラーを我々に知らせる。
            return # SELLシグナルを処理したので、このサイクルの判断を終了する。

    # --- 5. BUYシグナルの判断と実行 ---
    # ポジションを保有していない場合のみ、購入を検討する。
    if not in_position: # もしBTCを保有していないならば...
        # BUYシグナルの条件を定義する。これもまた、我々の最適化の旅の成果である。
        is_buy_signal = (latest_candle['volume'] > (latest_candle['volume_sma'] * params_buy["vol_mult"]) and # 1. 取引量が平均より著しく多いか？
                         latest_candle['close'] < latest_candle['open'] and # 2. 陰線（価格が下落して引けた）か？
                         abs(latest_candle['close'] - latest_candle['open']) < (latest_candle['atr'] * params_buy["body_ratio"])) # 3. 実体が小さい（市場に迷いがある）か？

        if is_buy_signal: # もしBUYシグナルの条件が全て満たされたならば...
            if usdt_balance > 10: # 最低限の軍資金（例: 10 USDT）があるか確認する。
                # config.pyで設定した哲学に基づき、投資額を決定する。
                usdt_to_invest = usdt_balance * capital_percentage # 「全ツッパ型」なら全額、「堅実型」ならその一部。
                logging.info(f"BUYシグナルを検知！ {usdt_to_invest:,.2f} USDT を使ってBTCの購入を試みます。") # 行動の意思を記録。
                
                # Bybit APIでは、成行の買い注文はUSDTの金額で指定する。
                # そのため、手数料を考慮して、実際に購入できるBTCの数量ではなく、支払うUSDTの額を直接指定する。
                try: # 注文処理を保護する。
                    response = session.place_order(
                        category=CATEGORY, # カテゴリ：現物
                        symbol=SYMBOL, # シンボル：BTCUSDT
                        side="Buy", # 売買方向：買い
                        orderType="Market", # 注文タイプ：成行
                        marketUnit="quoteCoin", # 注文サイズを支払う通貨（USDT）で指定するモード。
                        qty=str(usdt_to_invest) # 数量：先ほど計算した、投資するUSDTの額。
                    )
                    if response['retCode'] == 0: # 注文が正常に受け付けられた場合。
                        msg = f"【自動売買：BUY】\n投資額: {usdt_to_invest:,.2f} USDT\n価格: 約 {latest_candle['close']:,} USDT\n哲学: {capital_percentage*100}%ルール適用"
                        logging.info(f"BUY注文が正常に発注されました。{msg}") # 成功を記録。
                        send_discord_notification(f"```\n{msg}\n```") # 我々にも知らせる。
                    else: # 注文が失敗した場合。
                        logging.error(f"BUY注文の発注に失敗しました: {response['retMsg']}") # 失敗の理由を記録。
                        send_discord_notification(f"【自動売買エラー】\nBUY注文の発注に失敗しました。\n理由: {response['retMsg']}") # 失敗を我々に知らせる。
                except Exception as e: # 注文処理中に予期せぬエラーが発生した場合。
                    logging.error(f"BUY注文中に予期せぬエラーが発生しました: {traceback.format_exc()}") # 詳細なエラー情報を記録。
                    send_discord_notification(f"【自動売買エラー】\nBUY注文中に予期せぬエラーが発生しました。\n詳細はログを確認してください。") # エラーを我々に知らせる。
            else: # 軍資金が足りない場合。
                warning_msg = "BUYシグナルを検知しましたが、USDT残高が不足しているため、注文を見送ります。" # 見送りの理由を記録。
                logging.warning(warning_msg)
                send_discord_notification(f"【自動売買警告】\n{warning_msg}\n現在のUSDT残高: {usdt_balance:,.2f}") # 重要な警告を我々に知らせる。

# =================================================================================================
# 4. メイン実行ブロック
# プログラムが起動したときに、最初に実行される部分。「点火スイッチ」に相当する。
# =================================================================================================

if __name__ == "__main__": # このスクリプトが直接実行された場合にのみ、以下のコードが動く。
    
    # --- 起動メッセージ ---
    # ボットが新たな生を受けたことを、我々に知らせる。
    start_message = "=== Omen Auto Trader 起動 ===\n設定ファイル `config.py` から魂を読み込み、市場の監視を開始します。"
    logging.info(start_message) # 航海日誌に記録。
    send_discord_notification(start_message) # Discordにも通知。

    # --- Bybitセッションの確立 ---
    # これから始まる市場との対話のため、取引所との接続を確立する。
    session = HTTP(
        testnet=False, # 本番環境(False)か、テスト環境(True)かを選択する。我々は本番の市場で戦う。
        api_key=config.BYBIT_API_KEY, # config.pyから読み込んだAPIキー。
        api_secret=config.BYBIT_API_SECRET # config.pyから読み込んだAPIシークレット。
    )
    
    # --- 無限ループによる市場の継続監視 ---
    # ボットは眠らない。市場が続く限り、永遠に「前兆」を探し続ける。
    last_processed_timestamp = None # 最後に処理したローソク足のタイムスタンプを記録する変数。最初は空。

    while True: # 無限ループの開始。
        try: # ループ全体を保護し、一部のエラーでボット全体が落ちることを防ぐ。
            # --- 市場データの取得 ---
            # Bybitに最新のローソク足データを要求する。
            response = session.get_kline(
                category=CATEGORY, # カテゴリ：現物
                symbol=SYMBOL, # シンボル：BTCUSDT
                interval=INTERVAL, # 時間足：60分
                limit=30 # 取得する本数。指標計算（SMA20など）のために十分な数を取得する。
            )

            # --- データ取得成功時の処理 ---
            if response['retCode'] == 0 and response['result']['list']: # API呼び出しが成功し、データリストが存在するか確認。
                data = response['result']['list'] # ローソク足データのリストを取得。
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']) # Pandasデータフレームに変換。
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms') # タイムスタンプを人間が読める日時に変換。
                df.set_index('timestamp', inplace=True) # タイムスタンプをデータの「インデックス」に設定する。
                df = df.astype(float).sort_index() # 全ての列を数値（float）に変換し、念のため時系列でソートする。

                latest_candle_timestamp = df.index[-1] # 最新のローソク足のタイムスタンプを取得。

                if last_processed_timestamp is None: # ボット起動後、最初のサイクルの場合。
                    last_processed_timestamp = latest_candle_timestamp # 現在の最新足を「処理済み」として記録するだけ。
                    logging.info(f"初期化完了。最新のローソク足 {last_processed_timestamp} を基準とします。次の足の確定を待ちます。")
                
                elif latest_candle_timestamp > last_processed_timestamp: # 新しいローソク足が確定した場合。
                    logging.info(f"新しいローソク足 {latest_candle_timestamp} が確定しました。分析を開始します。") # 新しい足の確定を記録。
                    df_with_indicators = calculate_indicators(df) # 指標を計算し、市場データを「知識」に変換する。
                    
                    # 自動売買の心臓部を実行する。
                    run_automated_trading_logic(session, df_with_indicators)
                    
                    last_processed_timestamp = latest_candle_timestamp # この足を「処理済み」として記録を更新する。
                
                # else: # 新しい足がまだ確定していない場合。
                    # print(".", end="", flush=True) # 待機中であることを示すドットを出力しても良いが、ログが煩雑になるため省略。

            else: # データ取得に失敗した場合。
                logging.warning(f"データ取得に失敗しました: {response['retMsg']}") # 失敗を記録。

        except Exception as e: # 無限ループ内で予期せぬエラーが発生した場合。
            logging.error(f"メインループで予期せぬエラーが発生しました: {traceback.format_exc()}") # 詳細なエラー情報を記録。
            send_discord_notification("【重大エラー】\nボットのメインループで予期せぬエラーが発生しました。ボットは動作を続けていますが、ログの確認が必要です。")

        # --- 待機 ---
        # 次のチェックまで待機する。60分足なので、1分ごとにチェックすれば十分。
        time.sleep(60) # 60秒間、ボットは次の行動まで静かに待機する。
