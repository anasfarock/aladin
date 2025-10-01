"""
Technical Indicators Module for MT5 Trading Bot
Includes: SMA, RSI, VWAP, Bollinger Bands
"""

import pandas as pd
import numpy as np
import logging
from config import CONFIG

logger = logging.getLogger(__name__)

# --------------------------- TECHNICAL INDICATORS ----------------------------

def sma(series, length):
    """Simple Moving Average"""
    return series.rolling(window=length, min_periods=1).mean()

def std(series, length):
    """Standard deviation"""
    return series.rolling(window=length, min_periods=1).std()

def rsi(series, length=14):
    """Relative Strength Index"""
    if len(series) < length:
        return pd.Series(index=series.index, dtype=float)
    
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=length-1, adjust=False).mean()
    ma_down = down.ewm(com=length-1, adjust=False).mean()
    
    ma_down = ma_down.replace(0, np.nan)
    rs = ma_up / ma_down
    rsi_values = 100 - (100 / (1 + rs))
    rsi_values = rsi_values.fillna(50)
    return rsi_values

def vwap(df, length=None):
    """Volume Weighted Average Price"""
    if 'tick_volume' not in df.columns:
        logger.warning("tick_volume not found, using equal weights")
        df['tick_volume'] = 1
    
    df['tick_volume'] = df['tick_volume'].replace(0, 1)
    tp = (df['high'] + df['low'] + df['close']) / 3
    pv = tp * df['tick_volume']
    
    if length is None:
        cum_pv = pv.cumsum()
        cum_v = df['tick_volume'].cumsum()
        return cum_pv / cum_v
    else:
        pv_roll = pv.rolling(window=length, min_periods=1).sum()
        v_roll = df['tick_volume'].rolling(window=length, min_periods=1).sum()
        v_roll = v_roll.replace(0, 1)
        return pv_roll / v_roll

def bollinger_bands(series, length=20, stddev=2):
    """Bollinger Bands"""
    basis = sma(series, length)
    sd = std(series, length)
    upper = basis + stddev * sd
    lower = basis - stddev * sd
    return basis, upper, lower

def compute_indicators(df):
    """Compute all technical indicators"""
    if df.empty or len(df) < CONFIG['min_bars_required']:
        logger.warning(f"Insufficient data for indicators: {len(df)} bars")
        return df
    
    df = df.copy()
    
    required_cols = ['open', 'high', 'low', 'close']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found")
    
    try:
        df['ma_fast'] = sma(df['close'], CONFIG['ma_fast'])
        df['ma_slow'] = sma(df['close'], CONFIG['ma_slow'])
        df['rsi'] = rsi(df['close'], CONFIG['rsi_period'])
        df['vwap'] = vwap(df, CONFIG['vwap_period'])
        df['bb_basis'], df['bb_upper'], df['bb_lower'] = bollinger_bands(
            df['close'], CONFIG['boll_period'], CONFIG['boll_std']
        )
    except Exception as e:
        logger.error(f"Error computing indicators: {e}")
        raise
    
    return df