
import pandas as pd
import matplotlib.pyplot as plt
import sys
import os

# Add src to path to import engine
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../engines')))
try:
    from renko_engine import RenkoChart
except ImportError:
    # Fallback if running from root
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/engines')))
    from renko_engine import RenkoChart

def main():
    # Load 1m data (Recent chunk for visualization)
    file_path = 'data/bybit_btc_usdt_linear_1m_full.csv'
    if not os.path.exists(file_path):
        print(f"Data file not found: {file_path}")
        return

    print("Loading data...")
    # Load last 10000 rows for speed, or a specific interesting period
    df = pd.read_csv(file_path) # Load all to find index then slice
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Slice last 3 days for clear visualization
    # last_timestamp = df['timestamp'].iloc[-1]
    # start_timestamp = last_timestamp - pd.Timedelta(days=3)
    # df = df[df['timestamp'] >= start_timestamp].copy()
    
    # Slice last 5000 rows
    df = df.tail(5000).copy()
    
    print(f"Data loaded: {len(df)} rows. ({df['timestamp'].min()} - {df['timestamp'].max()})")

    # ATR Calculation for Brick Size (Optional, or fixed)
    # For prototype, use fixed size. 
    # Bitcoin price ~80k-90k. 
    # 0.1% = ~80-90 USD. Let's try 100 USD bricks.
    BRICK_SIZE = 100
    
    print(f"Generating Renko Bricks (Size: {BRICK_SIZE})...")
    renko = RenkoChart(brick_size=BRICK_SIZE)
    renko_df = renko.process_data(df)
    
    if renko_df.empty:
        print("No bricks formed.")
        return

    print(f"Bricks formed: {len(renko_df)}")
    
    # Calculate Precursors
    renko_df = renko.calculate_precursors(renko_df)
    
    # Visualization
    plot_renko(renko_df, title=f"Project Ura-Mono: Renko Precursor Analysis (Brick: {BRICK_SIZE})")

def plot_renko(df, title):
    plt.figure(figsize=(14, 8))
    
    # Main Chart: Price bricks
    ax1 = plt.subplot(2, 1, 1)
    
    # Reset index to use as X-axis (Timeless)
    df = df.reset_index(drop=True)
    
    up_bricks = df[df['type'] == 'UP']
    down_bricks = df[df['type'] == 'DOWN']
    
    # Plot 'Close' of bricks
    # Ideally Renko is patches, but scatter/line is easier for MPB validation
    ax1.plot(df.index, df['price'], color='gray', alpha=0.3, label='Price Flow')
    
    ax1.scatter(up_bricks.index, up_bricks['price'], color='green', marker='s', s=20, label='UP Brick')
    ax1.scatter(down_bricks.index, down_bricks['price'], color='red', marker='s', s=20, label='DOWN Brick')
    
    # Highlight Volume Lag (High volume needed to move brick)
    # Vol Lag > 3 (3x average volume)
    vol_anomalies = df[df['vol_lag'] > 3.0]
    ax1.scatter(vol_anomalies.index, vol_anomalies['price'], 
                color='yellow', edgecolors='black', s=100, marker='*', zorder=5, label='Volume "Lag" (Energy)')

    ax1.set_title(title)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Sub Chart: Precursors
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    
    # Volume Lag
    ax2.bar(df.index, df['vol_lag'], color='purple', alpha=0.5, label='Volume Energy Ratio')
    ax2.axhline(y=1.0, color='gray', linestyle='--')
    ax2.axhline(y=3.0, color='red', linestyle='--', label='Explosion Threshold')
    
    # Squeeze overlay?
    # Normalize squeeze score
    
    ax2.set_title("Precursor 1: Volume Energy (The 'Delayed Sound')")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    output_file = "renko_precursors_vis.png"
    plt.tight_layout()
    plt.savefig(output_file)
    print(f"Chart saved to {output_file}")

if __name__ == "__main__":
    main()
