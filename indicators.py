"""
Technical Indicators Module for MT5 Trading Bot
Includes: SMA, RSI, VWAP, Bollinger Bands, ADX, +DI, -DI
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

def compute_atr(df, period=14):
    """
    Calculate Average True Range (ATR)
    Required for ADX calculation
    
    Args:
        df: DataFrame with OHLC data
        period: ATR period (default 14)
    
    Returns:
        Series of ATR values
    """
    if len(df) < period + 1:
        return pd.Series([np.nan] * len(df), index=df.index)
    
    # Calculate True Range
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift(1))
    low_close = np.abs(df['low'] - df['close'].shift(1))
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # Fill first NaN value with high-low for first row
    tr.iloc[0] = tr.iloc[1] if len(tr) > 1 else df['high'].iloc[0] - df['low'].iloc[0]
    
    # Calculate ATR using EMA
    atr = tr.ewm(span=period, adjust=False).mean()
    
    return atr

def compute_adx(df, period=14):
    """
    Calculate Average Directional Index (ADX)
    Measures trend strength (0-100, typically >25 indicates strong trend)
    
    Args:
        df: DataFrame with OHLC data
        period: ADX period (default 14)
    
    Returns:
        dict with 'adx', '+DI', '-DI' Series
    """
    if len(df) < period + 1:
        return {
            'adx': pd.Series([np.nan] * len(df), index=df.index),
            '+DI': pd.Series([np.nan] * len(df), index=df.index),
            '-DI': pd.Series([np.nan] * len(df), index=df.index)
        }
    
    # Calculate ATR
    atr = compute_atr(df, period)
    
    # Calculate Directional Movement
    up = df['high'].diff()
    down = -df['low'].diff()
    
    # Determine +DM and -DM
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    
    # Smooth the directional movements using rolling sum
    plus_dm_smooth = pd.Series(plus_dm, index=df.index).rolling(window=period).sum()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).rolling(window=period).sum()
    
    # Calculate Directional Indicators
    plus_di = 100 * (plus_dm_smooth / atr)
    minus_di = 100 * (minus_dm_smooth / atr)
    
    # Replace inf values with NaN
    plus_di = plus_di.replace([np.inf, -np.inf], np.nan)
    minus_di = minus_di.replace([np.inf, -np.inf], np.nan)
    
    # Calculate DX
    di_sum = plus_di + minus_di
    di_sum = di_sum.replace(0, np.nan)  # Avoid division by zero
    
    dx = 100 * np.abs(plus_di - minus_di) / di_sum
    dx = dx.replace([np.inf, -np.inf], np.nan)
    
    # Calculate ADX (EMA of DX)
    adx = dx.ewm(span=period, adjust=False).mean()
    
    return {
        'adx': adx,
        '+DI': plus_di,
        '-DI': minus_di
    }

def compute_indicators(df):
    """
    Compute all technical indicators including ADX
    
    Args:
        df: DataFrame with OHLC data
    
    Returns:
        DataFrame with all indicators added
    """
    if df.empty:
        logger.warning("Insufficient data for indicators: DataFrame is empty")
        return df
    
    df = df.copy()
    
    required_cols = ['open', 'high', 'low', 'close']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found")
    
    try:
        # Calculate Moving Averages
        df['ma_fast'] = sma(df['close'], CONFIG['ma_fast'])
        df['ma_slow'] = sma(df['close'], CONFIG['ma_slow'])
        
        # Calculate RSI
        df['rsi'] = rsi(df['close'], CONFIG['rsi_period'])
        
        # Calculate VWAP
        df['vwap'] = vwap(df, CONFIG['vwap_period'])
        
        # Calculate Bollinger Bands
        df['bb_basis'], df['bb_upper'], df['bb_lower'] = bollinger_bands(
            df['close'], CONFIG['boll_period'], CONFIG['boll_std']
        )
        
        # Calculate ADX and Directional Indicators
        adx_period = CONFIG.get('adx_period', 14)
        adx_data = compute_adx(df, adx_period)
        df['adx'] = adx_data['adx']
        df['+DI'] = adx_data['+DI']
        df['-DI'] = adx_data['-DI']
        
    except Exception as e:
        logger.error(f"Error computing indicators: {e}")
        raise
    
    return df