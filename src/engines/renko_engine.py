
import pandas as pd
import numpy as np

class RenkoChart:
    def __init__(self, brick_size):
        self.brick_size = brick_size
        self.bricks = []          # Internal brick list (for incremental mode)
        self.current_price = None
        self.last_brick_price = None
        self._cumulative_volume = 0
        self._initialized = False
    
    def process_data(self, df):
        """
        Ingest a DataFrame with 'close', 'high', 'low', 'volume', 'timestamp'.
        Returns a DataFrame of Renko Bricks.
        """
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
             df['timestamp'] = pd.to_datetime(df['timestamp'])

        brick_data = []

        first_price = df.iloc[0]['close']
        self.last_brick_price = first_price - (first_price % self.brick_size)
        self._cumulative_volume = 0
        self._initialized = True
        
        for idx, row in df.iterrows():
            close = row['close']
            volume = row['volume']
            timestamp = row['timestamp']
            
            self._cumulative_volume += volume
            
            diff = close - self.last_brick_price
            num_bricks = int(diff // self.brick_size)
            
            if num_bricks == 0:
                continue
            
            direction = 1 if num_bricks > 0 else -1
            num_bricks = abs(num_bricks)
            
            for i in range(num_bricks):
                if direction == 1:
                    new_brick_price = self.last_brick_price + self.brick_size
                    type_str = 'UP'
                else:
                    new_brick_price = self.last_brick_price - self.brick_size
                    type_str = 'DOWN'
                
                brick_info = {
                    'timestamp': timestamp,
                    'price': new_brick_price,
                    'type': type_str,
                    'volume': self._cumulative_volume / num_bricks,
                    'brick_size': self.brick_size
                }
                brick_data.append(brick_info)
                self.last_brick_price = new_brick_price
            
            self._cumulative_volume = 0

        self.bricks = brick_data  # Store for incremental use
        return pd.DataFrame(brick_data)

    def process_incremental(self, new_candles):
        """
        Process only NEW candles against existing Renko state.
        Returns list of newly formed bricks (may be empty).
        Used by live bot to avoid reprocessing full history each cycle.
        """
        if not self._initialized:
            raise RuntimeError("Call process_data() with initial history first.")
        
        new_bricks = []
        
        for _, row in new_candles.iterrows():
            close = float(row['close'])
            volume = float(row['volume'])
            timestamp = row['timestamp']
            
            self._cumulative_volume += volume
            diff = close - self.last_brick_price
            num_bricks = int(diff // self.brick_size)
            
            if num_bricks == 0:
                continue
            
            direction = 1 if num_bricks > 0 else -1
            num_bricks = abs(num_bricks)
            
            for i in range(num_bricks):
                if direction == 1:
                    new_brick_price = self.last_brick_price + self.brick_size
                    type_str = 'UP'
                else:
                    new_brick_price = self.last_brick_price - self.brick_size
                    type_str = 'DOWN'
                
                brick_info = {
                    'timestamp': timestamp,
                    'price': new_brick_price,
                    'type': type_str,
                    'volume': self._cumulative_volume / num_bricks,
                    'brick_size': self.brick_size
                }
                new_bricks.append(brick_info)
                self.bricks.append(brick_info)
                self.last_brick_price = new_brick_price
            
            self._cumulative_volume = 0
        
        return new_bricks

    def get_latest_vol_lag(self, window=14):
        """
        Calculate vol_lag for the most recent brick using internal state.
        Returns (vol_lag, timestamp) or (0, None) if not enough data.
        """
        if len(self.bricks) < window + 1:
            return 0, None
        
        recent = self.bricks[-(window + 1):]
        volumes = [b['volume'] for b in recent]
        vol_ma = np.mean(volumes[:-1])  # MA of previous `window` bricks
        
        if vol_ma == 0:
            return 0, None
        
        latest = recent[-1]
        vol_lag = latest['volume'] / vol_ma
        return vol_lag, latest['timestamp']

    def calculate_precursors(self, renko_df, window=14):
        """
        Add 'Ura-Mono' specific metrics to the Renko DataFrame.
        """
        if renko_df.empty:
            return renko_df
            
        renko_df['vol_ma'] = renko_df['volume'].rolling(window=window).mean()
        renko_df['vol_lag'] = renko_df['volume'] / renko_df['vol_ma']
        
        renko_df['direction'] = renko_df['type'].apply(lambda x: 1 if x == 'UP' else -1)
        renko_df['flip'] = (renko_df['direction'] != renko_df['direction'].shift(1)).astype(int)
        renko_df['squeeze_score'] = renko_df['flip'].rolling(window=5).sum()
        
        renko_df['brick_burst'] = renko_df.groupby('timestamp')['price'].transform('count')
        
        return renko_df
