"""
Trend Analysis Module
Multi-timeframe trend determination using RSI, VWAP, Bollinger Bands, and Moving Averages
"""

import pandas as pd
import logging
from config import CONFIG

logger = logging.getLogger(__name__)

# --------------------------- TREND ANALYSIS ----------------------------

def determine_trend(df_d1, df_h4, df_h1):
    """
    Determine overall trend using multiple timeframes and indicators
    
    Returns: 'bullish', 'bearish', or 'neutral'
    """
    if df_d1.empty or df_h4.empty or df_h1.empty:
        return 'neutral'
    
    timeframe_data = [('D1', df_d1), ('H4', df_h4), ('H1', df_h1)]
    total_votes = 0
    timeframe_weights = {'D1': 3, 'H4': 2, 'H1': 1}
    
    total_indicators_enabled = sum([
        CONFIG['use_ma_for_trend'],
        CONFIG['use_rsi_for_trend'],
        CONFIG['use_vwap_for_trend'],
        CONFIG['use_bollinger_for_trend']
    ])
    
    if total_indicators_enabled == 0:
        return 'neutral'
    
    for tf_name, df in timeframe_data:
        if len(df) == 0:
            continue
        
        last = df.iloc[-1]
        tf_votes = 0
        weight = timeframe_weights[tf_name]
        
        # Moving Average voting
        if CONFIG['use_ma_for_trend'] and not (pd.isna(last['ma_fast']) or pd.isna(last['ma_slow'])):
            ma_vote = 1 if last['ma_fast'] > last['ma_slow'] else -1
            tf_votes += ma_vote
        
        # RSI voting
        if CONFIG['use_rsi_for_trend'] and not pd.isna(last['rsi']):
            if last['rsi'] > 60:
                rsi_vote = 1
            elif last['rsi'] < 40:
                rsi_vote = -1
            else:
                rsi_vote = 0
            tf_votes += rsi_vote
        
        # VWAP voting
        if CONFIG['use_vwap_for_trend'] and not pd.isna(last['vwap']):
            vwap_vote = 1 if last['close'] > last['vwap'] else -1
            tf_votes += vwap_vote
        
        # Bollinger Bands voting
        if (CONFIG['use_bollinger_for_trend'] and 
            not (pd.isna(last['bb_upper']) or pd.isna(last['bb_lower']) or pd.isna(last['bb_basis']))):
            if last['close'] > last['bb_basis']:
                bb_vote = 1
            elif last['close'] < last['bb_basis']:
                bb_vote = -1
            else:
                bb_vote = 0
            tf_votes += bb_vote
        
        # Apply timeframe weight
        weighted_votes = tf_votes * weight
        total_votes += weighted_votes
    
    # Determine threshold based on enabled indicators
    threshold = max(2, total_indicators_enabled)
    
    if total_votes > threshold:
        return 'bullish'
    elif total_votes < -threshold:
        return 'bearish'
    else:
        return 'neutral'

def get_trend_details(df_d1, df_h4, df_h1):
    """
    Get detailed trend information for logging/debugging
    
    Returns: dict with trend breakdown by timeframe
    """
    details = {}
    
    for tf_name, df in [('D1', df_d1), ('H4', df_h4), ('H1', df_h1)]:
        if df.empty:
            details[tf_name] = 'no_data'
            continue
        
        last = df.iloc[-1]
        votes = []
        
        if CONFIG['use_ma_for_trend'] and not (pd.isna(last['ma_fast']) or pd.isna(last['ma_slow'])):
            votes.append('bullish' if last['ma_fast'] > last['ma_slow'] else 'bearish')
        
        if CONFIG['use_rsi_for_trend'] and not pd.isna(last['rsi']):
            if last['rsi'] > 60:
                votes.append('bullish')
            elif last['rsi'] < 40:
                votes.append('bearish')
        
        if CONFIG['use_vwap_for_trend'] and not pd.isna(last['vwap']):
            votes.append('bullish' if last['close'] > last['vwap'] else 'bearish')
        
        if CONFIG['use_bollinger_for_trend'] and not pd.isna(last['bb_basis']):
            if last['close'] > last['bb_basis']:
                votes.append('bullish')
            elif last['close'] < last['bb_basis']:
                votes.append('bearish')
        
        bullish_count = votes.count('bullish')
        bearish_count = votes.count('bearish')
        
        if bullish_count > bearish_count:
            details[tf_name] = 'bullish'
        elif bearish_count > bullish_count:
            details[tf_name] = 'bearish'
        else:
            details[tf_name] = 'neutral'
    
    return details