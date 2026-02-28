from .core.backtester import DerivativesBacktester
import os

# このスクリプトは、設定ファイル(config.py)とコアモジュール(core/)を
# 使って、デリバティブ戦略のバックテストを実行します。

if __name__ == '__main__':
    print("Initializing and running the derivatives backtest...")
    
    # バックテスターのインスタンスを作成
    backtester = DerivativesBacktester()
    
    # バックテストを実行
    backtester.run()
    
    print("Backtest finished.")
