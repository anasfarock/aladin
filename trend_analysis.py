"""
Trend Analysis Module - POINT-BASED SYSTEM with ADX Confirmation
Multi-timeframe trend determination with ADX strength validation
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

# --------------------------- ADX ANALYSIS ----------------------------

def check_adx_confirmation(df, trend):
    """
    Check if ADX confirms the trend strength
    
    Args:
        df: DataFrame with ADX, +DI, -DI columns
        trend: 'bullish', 'bearish', or 'neutral'
    
    Returns:
        dict: {
            'confirmed': bool,
            'adx_value': float,
            'strength': str,  # 'strong', 'moderate', 'weak', 'absent'
            '+DI': float,
            '-DI': float,
            'di_aligned': bool,  # True if DI lines align with trend
            'reason': str
        }
    """
    if df.empty or len(df) == 0:
        return {
            'confirmed': False,
            'adx_value': np.nan,
            'strength': 'absent',
            '+DI': np.nan,
            '-DI': np.nan,
            'di_aligned': False,
            'reason': 'No data available'
        }
    
    import numpy as np
    
    last = df.iloc[-1]
    adx_value = last.get('adx', np.nan)
    plus_di = last.get('+DI', np.nan)
    minus_di = last.get('-DI', np.nan)
    
    # Check if values are valid
    if pd.isna(adx_value) or pd.isna(plus_di) or pd.isna(minus_di):
        return {
            'confirmed': False,
            'adx_value': adx_value,
            'strength': 'absent',
            '+DI': plus_di,
            '-DI': minus_di,
            'di_aligned': False,
            'reason': 'ADX not yet calculated'
        }
    
    threshold = CONFIG.get('adx_strength_threshold', 25)
    extreme = CONFIG.get('adx_extreme_threshold', 40)
    weak = CONFIG.get('adx_weak_threshold', 20)
    
    # Determine ADX strength
    if adx_value >= extreme:
        strength = 'strong'
    elif adx_value >= threshold:
        strength = 'moderate'
    elif adx_value >= weak:
        strength = 'weak'
    else:
        strength = 'absent'
    
    # Check if +DI and -DI align with trend
    di_aligned = False
    if CONFIG.get('adx_di_crossover_check', True):
        if trend == 'bullish':
            di_aligned = plus_di > minus_di
        elif trend == 'bearish':
            di_aligned = minus_di > plus_di
        else:
            di_aligned = True  # Neutral doesn't require DI alignment
    else:
        di_aligned = True  # If not checking DI, consider it aligned
    
    # Determine if trend is confirmed
    confirmed = (adx_value >= threshold) and di_aligned
    
    # Build reason string
    if not di_aligned:
        reason = f"DI lines misaligned (+DI: {plus_di:.2f}, -DI: {minus_di:.2f})"
    elif adx_value < threshold:
        reason = f"ADX too weak ({adx_value:.2f} < {threshold})"
    else:
        reason = f"ADX confirms {trend.upper()} trend ({adx_value:.2f} {strength})"
    
    return {
        'confirmed': confirmed,
        'adx_value': adx_value,
        'strength': strength,
        '+DI': plus_di,
        '-DI': minus_di,
        'di_aligned': di_aligned,
        'reason': reason
    }

def check_adx_across_timeframes(df_d1, df_h4, df_h1, trend):
    """
    Check ADX confirmation across multiple timeframes
    
    Returns:
        dict with ADX status for each timeframe
    """
    timeframes = [
        ('D1', df_d1),
        ('H4', df_h4),
        ('H1', df_h1)
    ]
    
    adx_data = {}
    all_confirmed = True
    
    for tf_name, df in timeframes:
        adx_check = check_adx_confirmation(df, trend)
        adx_data[tf_name] = adx_check
        
        # For strong trend confirmation, at least D1 should confirm
        if tf_name == 'D1' and not adx_check['confirmed']:
            all_confirmed = False
    
    return {
        'timeframes': adx_data,
        'all_confirmed': all_confirmed,
        'highest_adx': max(adx_data[tf]['adx_value'] for tf in ['D1', 'H4', 'H1']),
        'lowest_adx': min(adx_data[tf]['adx_value'] for tf in ['D1', 'H4', 'H1'])
    }

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
        
        if abs(ma_diff_pct) > 0.3:
            ma_points = 3 if ma_diff > 0 else -3
        elif abs(ma_diff_pct) > 0.15:
            ma_points = 2 if ma_diff > 0 else -2
        elif abs(ma_diff_pct) > 0.05:
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
        
        if rsi_val > 70:
            rsi_points = 3
        elif rsi_val > 60:
            rsi_points = 2
        elif rsi_val > 55:
            rsi_points = 1
        elif rsi_val < 30:
            rsi_points = -3
        elif rsi_val < 40:
            rsi_points = -2
        elif rsi_val < 45:
            rsi_points = -1
        else:
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
        
        if abs(price_diff_pct) > 0.2:
            vwap_points = 2 if price_diff > 0 else -2
        elif abs(price_diff_pct) > 0.05:
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
        
        if position_in_bb > 0.8:
            bb_points = 2
        elif position_in_bb > 0.6:
            bb_points = 1
        elif position_in_bb < 0.2:
            bb_points = -2
        elif position_in_bb < 0.4:
            bb_points = -1
        else:
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
    Otherwise uses automatic point-based system with optional ADX confirmation
    
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
    bullish_threshold = CONFIG.get('trend_bullish_threshold', 8)
    bearish_threshold = CONFIG.get('trend_bearish_threshold', -8)
    
    if total_points >= bullish_threshold:
        trend = 'bullish'
    elif total_points <= bearish_threshold:
        trend = 'bearish'
    else:
        trend = 'neutral'
    
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
    Calculate trend confidence percentage (0-100)
    
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
        'D1': 10 * 3,
        'H4': 10 * 2,
        'H1': 10 * 1
    }
    
    max_total = sum(max_points_per_tf.values())
    confidence = (abs(details['total_points']) / max_total) * 100
    
    return min(100, confidence)