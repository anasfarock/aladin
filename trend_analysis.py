"""
Trend Analysis Module - POINT-BASED SYSTEM with Manual Override
Multi-timeframe trend determination using weighted point scoring
More transparent, configurable, and reliable than voting system
"""

import pandas as pd
import logging
from config import CONFIG

logger = logging.getLogger(__name__)

# --------------------------- MANUAL TREND OVERRIDE ----------------------------

def get_manual_trend():
    """
    Return the manually configured trend
    
    Returns: 'bullish', 'bearish', or 'neutral'
    """
    trend = CONFIG.get('manual_trend', 'neutral').lower()
    
    logger.info(f"\n{'='*70}")
    logger.info(f"MANUAL TREND MODE")
    logger.info(f"{'='*70}")
    logger.info(f"Trend Direction: {trend.upper()}")
    logger.info(f"Note: Automatic trend analysis is BYPASSED")
    logger.info(f"{'='*70}\n")
    
    return trend

# --------------------------- POINT-BASED TREND ANALYSIS ----------------------------

def calculate_indicator_points(df, timeframe_weight):
    """
    Calculate trend points from indicators for a single timeframe
    
    Returns:
        dict: {
            'ma_points': int,
            'rsi_points': int,
            'vwap_points': int,
            'bb_points': int,
            'total_points': int,
            'details': dict
        }
    """
    if df.empty or len(df) == 0:
        return {
            'ma_points': 0,
            'rsi_points': 0,
            'vwap_points': 0,
            'bb_points': 0,
            'total_points': 0,
            'details': {}
        }
    
    last = df.iloc[-1]
    points = {
        'ma_points': 0,
        'rsi_points': 0,
        'vwap_points': 0,
        'bb_points': 0,
        'details': {}
    }
    
    # Moving Average Points (Max: ±3 points per timeframe)
    if CONFIG['use_ma_for_trend'] and not (pd.isna(last['ma_fast']) or pd.isna(last['ma_slow'])):
        ma_diff = last['ma_fast'] - last['ma_slow']
        ma_diff_pct = (ma_diff / last['ma_slow']) * 100
        
        if abs(ma_diff_pct) > 0.3:  # Strong trend
            ma_points = 3 if ma_diff > 0 else -3
        elif abs(ma_diff_pct) > 0.15:  # Moderate trend
            ma_points = 2 if ma_diff > 0 else -2
        elif abs(ma_diff_pct) > 0.05:  # Weak trend
            ma_points = 1 if ma_diff > 0 else -1
        else:
            ma_points = 0
        
        points['ma_points'] = ma_points * timeframe_weight
        points['details']['ma'] = {
            'fast': last['ma_fast'],
            'slow': last['ma_slow'],
            'diff_pct': ma_diff_pct,
            'raw_points': ma_points,
            'weighted_points': points['ma_points']
        }
    
    # RSI Points (Max: ±3 points per timeframe)
    if CONFIG['use_rsi_for_trend'] and not pd.isna(last['rsi']):
        rsi_val = last['rsi']
        
        if rsi_val > 70:  # Strongly overbought (bullish momentum)
            rsi_points = 3
        elif rsi_val > 60:  # Overbought (bullish)
            rsi_points = 2
        elif rsi_val > 55:  # Slightly bullish
            rsi_points = 1
        elif rsi_val < 30:  # Strongly oversold (bearish momentum)
            rsi_points = -3
        elif rsi_val < 40:  # Oversold (bearish)
            rsi_points = -2
        elif rsi_val < 45:  # Slightly bearish
            rsi_points = -1
        else:  # Neutral zone (45-55)
            rsi_points = 0
        
        points['rsi_points'] = rsi_points * timeframe_weight
        points['details']['rsi'] = {
            'value': rsi_val,
            'raw_points': rsi_points,
            'weighted_points': points['rsi_points']
        }
    
    # VWAP Points (Max: ±2 points per timeframe)
    if CONFIG['use_vwap_for_trend'] and not pd.isna(last['vwap']):
        price_diff = last['close'] - last['vwap']
        price_diff_pct = (price_diff / last['vwap']) * 100
        
        if abs(price_diff_pct) > 0.2:  # Strong deviation
            vwap_points = 2 if price_diff > 0 else -2
        elif abs(price_diff_pct) > 0.05:  # Moderate deviation
            vwap_points = 1 if price_diff > 0 else -1
        else:
            vwap_points = 0
        
        points['vwap_points'] = vwap_points * timeframe_weight
        points['details']['vwap'] = {
            'price': last['close'],
            'vwap': last['vwap'],
            'diff_pct': price_diff_pct,
            'raw_points': vwap_points,
            'weighted_points': points['vwap_points']
        }
    
    # Bollinger Bands Points (Max: ±2 points per timeframe)
    if (CONFIG['use_bollinger_for_trend'] and 
        not (pd.isna(last['bb_upper']) or pd.isna(last['bb_lower']) or pd.isna(last['bb_basis']))):
        
        bb_range = last['bb_upper'] - last['bb_lower']
        position_in_bb = (last['close'] - last['bb_lower']) / bb_range if bb_range > 0 else 0.5
        
        # Position: 0 = lower band, 0.5 = middle, 1 = upper band
        if position_in_bb > 0.8:  # Near upper band
            bb_points = 2
        elif position_in_bb > 0.6:  # Above middle
            bb_points = 1
        elif position_in_bb < 0.2:  # Near lower band
            bb_points = -2
        elif position_in_bb < 0.4:  # Below middle
            bb_points = -1
        else:  # Around middle
            bb_points = 0
        
        points['bb_points'] = bb_points * timeframe_weight
        points['details']['bb'] = {
            'close': last['close'],
            'upper': last['bb_upper'],
            'basis': last['bb_basis'],
            'lower': last['bb_lower'],
            'position': position_in_bb,
            'raw_points': bb_points,
            'weighted_points': points['bb_points']
        }
    
    # Calculate total
    points['total_points'] = (
        points['ma_points'] + 
        points['rsi_points'] + 
        points['vwap_points'] + 
        points['bb_points']
    )
    
    return points

def determine_trend(df_d1, df_h4, df_h1):
    """
    Determine overall trend using point-based scoring system or manual override
    
    If use_manual_trend is True, returns the manual_trend value from CONFIG
    Otherwise uses automatic point-based system:
    
    Timeframe Weights:
    - D1: 3x (most important - overall trend)
    - H4: 2x (intermediate trend)
    - H1: 1x (short-term trend)
    
    Max Points Per Indicator Per Timeframe:
    - MA: ±3 points
    - RSI: ±3 points
    - VWAP: ±2 points
    - BB: ±2 points
    
    Total Max Points: (3+3+2+2) * (3+2+1) = 10 * 6 = 60 points
    
    Returns: 'bullish', 'bearish', or 'neutral'
    """
    # Check if manual trend override is enabled
    if CONFIG.get('use_manual_trend', False):
        return get_manual_trend()
    
    # Automatic trend analysis
    timeframes = [
        ('D1', df_d1, 3),
        ('H4', df_h4, 2),
        ('H1', df_h1, 1)
    ]
    
    total_points = 0
    timeframe_breakdown = {}
    
    # Calculate points for each timeframe
    for tf_name, df, weight in timeframes:
        tf_points = calculate_indicator_points(df, weight)
        timeframe_breakdown[tf_name] = tf_points
        total_points += tf_points['total_points']
    
    # Determine trend based on total points
    # Thresholds are configurable
    bullish_threshold = CONFIG.get('trend_bullish_threshold', 8)
    bearish_threshold = CONFIG.get('trend_bearish_threshold', -8)
    
    if total_points >= bullish_threshold:
        trend = 'bullish'
    elif total_points <= bearish_threshold:
        trend = 'bearish'
    else:
        trend = 'neutral'
    
    # Log detailed breakdown
    logger.debug(f"\n{'='*70}")
    logger.debug(f"TREND ANALYSIS - POINT-BASED SYSTEM")
    logger.debug(f"{'='*70}")
    
    for tf_name in ['D1', 'H4', 'H1']:
        tf_data = timeframe_breakdown[tf_name]
        logger.debug(f"\n{tf_name} Timeframe:")
        logger.debug(f"  MA Points:   {tf_data['ma_points']:+6.1f}")
        logger.debug(f"  RSI Points:  {tf_data['rsi_points']:+6.1f}")
        logger.debug(f"  VWAP Points: {tf_data['vwap_points']:+6.1f}")
        logger.debug(f"  BB Points:   {tf_data['bb_points']:+6.1f}")
        logger.debug(f"  Subtotal:    {tf_data['total_points']:+6.1f}")
    
    logger.debug(f"\n{'='*70}")
    logger.debug(f"TOTAL POINTS: {total_points:+.1f}")
    logger.debug(f"TREND: {trend.upper()}")
    logger.debug(f"{'='*70}\n")
    
    return trend

def get_trend_details(df_d1, df_h4, df_h1):
    """
    Get detailed trend information for logging/debugging
    
    Returns: dict with complete trend breakdown
    """
    # Check if manual trend override is enabled
    if CONFIG.get('use_manual_trend', False):
        manual_trend = CONFIG.get('manual_trend', 'neutral').lower()
        return {
            'mode': 'manual',
            'trend': manual_trend,
            'trend_strength': 100.0,
            'timeframes': {},
            'total_points': 0
        }
    
    # Automatic trend analysis
    timeframes = [
        ('D1', df_d1, 3),
        ('H4', df_h4, 2),
        ('H1', df_h1, 1)
    ]
    
    details = {
        'mode': 'automatic',
        'timeframes': {},
        'total_points': 0,
        'trend': 'neutral'
    }
    
    total_points = 0
    
    for tf_name, df, weight in timeframes:
        tf_points = calculate_indicator_points(df, weight)
        details['timeframes'][tf_name] = {
            'weight': weight,
            'ma_points': tf_points['ma_points'],
            'rsi_points': tf_points['rsi_points'],
            'vwap_points': tf_points['vwap_points'],
            'bb_points': tf_points['bb_points'],
            'total_points': tf_points['total_points'],
            'indicator_details': tf_points['details']
        }
        total_points += tf_points['total_points']
    
    details['total_points'] = total_points
    
    # Determine trend
    bullish_threshold = CONFIG.get('trend_bullish_threshold', 8)
    bearish_threshold = CONFIG.get('trend_bearish_threshold', -8)
    
    if total_points >= bullish_threshold:
        details['trend'] = 'bullish'
        details['trend_strength'] = min(100, (total_points / bullish_threshold) * 100)
    elif total_points <= bearish_threshold:
        details['trend'] = 'bearish'
        details['trend_strength'] = min(100, (abs(total_points) / abs(bearish_threshold)) * 100)
    else:
        details['trend'] = 'neutral'
        details['trend_strength'] = 0
    
    return details

def get_trend_confidence(df_d1, df_h4, df_h1):
    """
    Calculate trend confidence percentage
    
    Returns: float (0-100)
    """
    # Manual trend always has 100% confidence
    if CONFIG.get('use_manual_trend', False):
        return 100.0
    
    details = get_trend_details(df_d1, df_h4, df_h1)
    
    # Calculate max possible points with current config
    indicators_enabled = sum([
        CONFIG['use_ma_for_trend'],
        CONFIG['use_rsi_for_trend'],
        CONFIG['use_vwap_for_trend'],
        CONFIG['use_bollinger_for_trend']
    ])
    
    if indicators_enabled == 0:
        return 0
    
    # Max points per timeframe
    max_points_per_tf = {
        'D1': 10 * 3,  # (3+3+2+2) * weight
        'H4': 10 * 2,
        'H1': 10 * 1
    }
    
    max_total = sum(max_points_per_tf.values())
    confidence = (abs(details['total_points']) / max_total) * 100
    
    return min(100, confidence)