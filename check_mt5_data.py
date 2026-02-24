import MetaTrader5 as mt5
from datetime import datetime
import pandas as pd

if not mt5.initialize():
    print("initialize() failed")
    mt5.shutdown()
    exit()

symbol = "USDCAD"
timeframe = mt5.TIMEFRAME_M15

print(f"Checking data for {symbol} on M15...")
rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1000)

if rates is None or len(rates) == 0:
    print(f"Failed to get rates for {symbol}")
else:
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    print(f"Found {len(df)} bars.")
    print(f"Oldest: {df['time'].iloc[0]}")
    print(f"Newest: {df['time'].iloc[-1]}")

mt5.shutdown()
