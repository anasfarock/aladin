"""
Configuration Module for Aladin - MT5 Trading Bot
Updated with Point-Based Trend System, Manual Trend Override, Fundamental Analysis, and ADX
"""

import logging
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Optional MT5 import
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not available. Install with: pip install MetaTrader5")

# Load environment variables from a .env file if python-dotenv is installed.
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Loaded environment variables from .env (if present)")
except Exception:
    logger.info("python-dotenv not available; falling back to OS environment variables")

# ----------------------------- CONFIG -----------------------------
CONFIG = {
    # Trading Parameters
    'symbol': 'USDCAD',
    'backtest': False,
    'start': '2025-11-10',
    'end': '2025-11-16',
    'capital': 5000.0,
    'risk_pct': 0.5,
    
    # Timeframes
    'timeframe_entry': 'M15',
    'trend_timeframes': ['D1', 'H4', 'H1'],
    
    # Technical Indicators
    'boll_period': 20,
    'boll_std': 2,
    'rsi_period': 14,
    'vwap_period': 20,
    'ma_fast': 9,
    'ma_slow': 18,
    
    # ===== ADX SETTINGS =====
    'adx_period': 30,                          # ADX calculation period
    'use_adx_filter': True,                    # Enable/disable ADX filter
    'adx_strength_threshold': 25,              # Minimum ADX value to confirm strong trend
    'adx_extreme_threshold': 80,               # ADX value indicating very strong trend
    'adx_weak_threshold': 20,                  # ADX value below which trend is weak
    'adx_di_crossover_check': True,            # Check if +DI > -DI for bullish, -DI > +DI for bearish
    'adx_confirmation_bars': 2,                # Number of bars ADX must stay above threshold
    
    # Manual Trend Override
    'use_manual_trend': False,
    'manual_trend': 'bullish',
    
    # Trend Analysis Toggles
    'use_rsi_for_trend': True,
    'use_vwap_for_trend': True,
    'use_bollinger_for_trend': True,
    'use_ma_for_trend': True,
    
    # Point-Based Trend System
    'trend_bullish_threshold': 10,
    'trend_bearish_threshold': -10,
    
    # Fibonacci Settings
    'fib_lookback': 30,
    'min_fib_candles': 5,
    'fib_levels': [0.618, 0.705, 0.786],
    'fib_tolerance': 0.0001,
    'min_swing_size': 0.0005,
    'max_fib_age': 100,
    'fib_confirmation_bars': 2,
    
    # Chart Visualization Settings
    'export_fib_charts': True,
    'chart_output_dir': 'fib_charts',
    
    # ===== FUNDAMENTAL & SENTIMENT ANALYSIS SETTINGS =====
    'use_fundamental_analysis': False,
    'use_sentiment_analysis': False,
    'use_macro_filter': False,
    
    # Macro Analysis Weights
    'macro_weight': 0.35,
    'technical_weight': 0.65,
    
    # Macro Signal Thresholds
    'macro_bullish_threshold': 15,
    'macro_bearish_threshold': -15,
    'macro_confidence_min': 40,
    
    # Sentiment Analysis Settings
    'sentiment_lookback_hours': 24,
    'sentiment_min_articles': 3,
    'sentiment_confidence_required': 30,
    
    # Fundamental Analysis Settings
    'fundamental_lookback_days': 7,
    'interest_rate_update_freq': 'weekly',
    'cot_extreme_threshold': 0.75,
    
    # API Configuration
    'newsapi_key': os.getenv('NEWSAPI_KEY', ''),
    'alpha_vantage_key': os.getenv('ALPHA_VANTAGE_KEY', ''),
    'twitter_api_key': os.getenv('TWITTER_API_KEY', ''),
    'twitter_api_secret': os.getenv('TWITTER_API_SECRET', ''),
    'reddit_client_id': os.getenv('REDDIT_CLIENT_ID', ''),
    'reddit_client_secret': os.getenv('REDDIT_CLIENT_SECRET', ''),
    
    # Macro Analysis Features Toggle
    'analyze_cot_reports': True,
    'analyze_interest_rates': True,
    'analyze_economic_events': True,
    'analyze_macro_factors': True,
    
    # News & Social Media Analysis Toggle
    'analyze_news': True,
    'analyze_twitter': False,
    'analyze_reddit': False,
    
    # Macro Bias Filtering
    'skip_trades_against_macro': False,
    'macro_bias_confidence_required': 60,
    
    # Risk Management
    'max_concurrent_trades': 8,                    # Max total concurrent trades across all pairs
    'max_concurrent_trades_of_same_pair': 3,      # Max concurrent trades on a single pair
    'min_bars_required': 50,
    'trailing_stop': False,
    'trailing_levels': {
        1.0: 0.5,
        2.0: 1.0,
        3.0: 2.0,
        4.0: 3.0,
    },
    'min_rr_ratio': 1.5,
    
    # Order Execution Settings
    'slippage_points': 50,
    'max_retries': 3,
    'retry_delay': 0.5,
    'use_market_execution': True,
    
    # Logging & Display
    'verbose_macro_analysis': True,
    'show_macro_divergence_warnings': True,
    'verbose_adx_analysis': True,
}

def get_mt5_timeframes():
    """
    Returns a dictionary mapping of string representations of timeframes to their
    corresponding MetaTrader 5 constants. This is used to easily convert between
    human-readable timeframes (e.g., 'H1') and the format required by the MT5 API.
    If the MT5 library is not available, it returns an empty dictionary.
    """
    if not MT5_AVAILABLE:
        return {}
    return {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }

MT5_TIMEFRAMES = get_mt5_timeframes()

def validate_config():
    """
    Performs a series of checks to validate the integrity and correctness of the
    settings defined in the CONFIG dictionary. This function ensures that the bot
    operates with valid parameters, preventing common configuration errors at runtime.
    It checks for the availability of MT5, validates timeframe settings, Fibonacci
    parameters, concurrent trade limits, trend analysis settings, and ADX parameters.
    """
    if not MT5_AVAILABLE and not CONFIG['backtest']:
        raise RuntimeError("MT5 not available for live trading")
    
    if CONFIG['timeframe_entry'] not in MT5_TIMEFRAMES:
        raise ValueError(f"Unsupported entry timeframe: {CONFIG['timeframe_entry']}")
    
    for tf in CONFIG['trend_timeframes']:
        if tf not in MT5_TIMEFRAMES:
            raise ValueError(f"Unsupported trend timeframe: {tf}")
    
    # Validate Fibonacci settings
    if CONFIG['min_fib_candles'] < 1:
        raise ValueError("min_fib_candles must be at least 1")
    
    if CONFIG['fib_lookback'] <= CONFIG['min_fib_candles']:
        raise ValueError(f"fib_lookback ({CONFIG['fib_lookback']}) must be greater than "
                        f"min_fib_candles ({CONFIG['min_fib_candles']})")
    
    if CONFIG['max_fib_age'] <= 0:
        raise ValueError("max_fib_age must be positive")
    
    # Validate concurrent trades settings
    if CONFIG['max_concurrent_trades'] <= 0:
        raise ValueError("max_concurrent_trades must be positive")
    
    if CONFIG['max_concurrent_trades_of_same_pair'] <= 0:
        raise ValueError("max_concurrent_trades_of_same_pair must be positive")
    
    if CONFIG['max_concurrent_trades_of_same_pair'] > CONFIG['max_concurrent_trades']:
        raise ValueError(f"max_concurrent_trades_of_same_pair ({CONFIG['max_concurrent_trades_of_same_pair']}) "
                        f"cannot exceed max_concurrent_trades ({CONFIG['max_concurrent_trades']})")
    
    # Validate ADX settings
    if CONFIG['use_adx_filter']:
        if CONFIG['adx_period'] <= 0:
            raise ValueError("adx_period must be positive")
        if CONFIG['adx_strength_threshold'] <= 0:
            raise ValueError("adx_strength_threshold must be positive")
        if CONFIG['adx_strength_threshold'] > 100:
            raise ValueError("adx_strength_threshold must be <= 100")
        if CONFIG['adx_extreme_threshold'] <= CONFIG['adx_strength_threshold']:
            raise ValueError(f"adx_extreme_threshold ({CONFIG['adx_extreme_threshold']}) must be > "
                           f"adx_strength_threshold ({CONFIG['adx_strength_threshold']})")
        if CONFIG['adx_confirmation_bars'] < 1:
            raise ValueError("adx_confirmation_bars must be at least 1")
        
        logger.info("="*70)
        logger.info("✓ ADX FILTER ENABLED")
        logger.info(f"  Period: {CONFIG['adx_period']}")
        logger.info(f"  Strength Threshold: {CONFIG['adx_strength_threshold']}")
        logger.info(f"  Extreme Threshold: {CONFIG['adx_extreme_threshold']}")
        logger.info(f"  Weak Threshold: {CONFIG['adx_weak_threshold']}")
        logger.info(f"  +DI/-DI Crossover Check: {'YES' if CONFIG['adx_di_crossover_check'] else 'NO'}")
        logger.info(f"  Confirmation Bars: {CONFIG['adx_confirmation_bars']}")
        logger.info("="*70)
    
    # Validate manual trend settings
    if CONFIG['use_manual_trend']:
        valid_trends = ['bullish', 'bearish', 'neutral']
        if CONFIG['manual_trend'].lower() not in valid_trends:
            raise ValueError(f"Invalid manual_trend value: {CONFIG['manual_trend']}. "
                           f"Must be one of: {', '.join(valid_trends)}")
        
        CONFIG['manual_trend'] = CONFIG['manual_trend'].lower()
        logger.info("="*70)
        logger.info("⚠️  MANUAL TREND MODE ENABLED")
        logger.info(f"   Trend set to: {CONFIG['manual_trend'].upper()}")
        logger.info("   Automatic trend analysis will be BYPASSED")
        logger.info("="*70)
    else:
        # Validate trend indicators only if automatic trend is used
        trend_indicators_enabled = [
            CONFIG['use_ma_for_trend'],
            CONFIG['use_rsi_for_trend'],
            CONFIG['use_vwap_for_trend'],
            CONFIG['use_bollinger_for_trend']
        ]
        
        if not any(trend_indicators_enabled):
            logger.warning("⚠️  No trend indicators enabled!")
        
        enabled_indicators = []
        if CONFIG['use_ma_for_trend']:
            enabled_indicators.append('Moving Averages')
        if CONFIG['use_rsi_for_trend']:
            enabled_indicators.append('RSI')
        if CONFIG['use_vwap_for_trend']:
            enabled_indicators.append('VWAP')
        if CONFIG['use_bollinger_for_trend']:
            enabled_indicators.append('Bollinger Bands')
        
        logger.info(f"Trend analysis using: {', '.join(enabled_indicators) if enabled_indicators else 'None'}")
        
        # Validate trend thresholds
        if CONFIG['trend_bullish_threshold'] <= 0:
            raise ValueError("Bullish threshold must be positive")
        if CONFIG['trend_bearish_threshold'] >= 0:
            raise ValueError("Bearish threshold must be negative")
        
        # Calculate max possible points
        active_indicators = []
        if CONFIG['use_ma_for_trend']:
            active_indicators.append('ma')
        if CONFIG['use_rsi_for_trend']:
            active_indicators.append('rsi')
        if CONFIG['use_vwap_for_trend']:
            active_indicators.append('vwap')
        if CONFIG['use_bollinger_for_trend']:
            active_indicators.append('bb')
        
        max_points_per_indicator = {'ma': 3, 'rsi': 3, 'vwap': 2, 'bb': 2}
        max_points_per_tf = sum(max_points_per_indicator[ind] for ind in active_indicators)
        max_total_points = max_points_per_tf * 6
        
        logger.info(f"Point-Based Trend System:")
        logger.info(f"  Max possible points: ±{max_total_points}")
        logger.info(f"  Bullish threshold: {CONFIG['trend_bullish_threshold']} points")
        logger.info(f"  Bearish threshold: {CONFIG['trend_bearish_threshold']} points")
        
        if abs(CONFIG['trend_bullish_threshold']) > max_total_points * 0.7:
            logger.warning(f"⚠️  Bullish threshold is high ({CONFIG['trend_bullish_threshold']}). "
                          f"May result in fewer trades.")
        if abs(CONFIG['trend_bearish_threshold']) > max_total_points * 0.7:
            logger.warning(f"⚠️  Bearish threshold is high ({abs(CONFIG['trend_bearish_threshold'])}). "
                          f"May result in fewer trades.")
    
    # Validate macro analysis settings
    if CONFIG['use_fundamental_analysis'] or CONFIG['use_sentiment_analysis']:
        logger.info("="*70)
        logger.info("📊 FUNDAMENTAL & SENTIMENT ANALYSIS ENABLED")
        logger.info("="*70)
        
        if CONFIG['use_sentiment_analysis']:
            logger.info("✓ News & Social Sentiment Analysis: ACTIVE")
            if CONFIG['newsapi_key']:
                logger.info("  - NewsAPI configured")
            if CONFIG['alpha_vantage_key']:
                logger.info("  - Alpha Vantage configured")
            if CONFIG['twitter_api_key']:
                logger.info("  - Twitter API configured")
            if CONFIG['reddit_client_id']:
                logger.info("  - Reddit API configured")
        
        if CONFIG['use_fundamental_analysis']:
            logger.info("✓ Fundamental Analysis: ACTIVE")
            if CONFIG['analyze_cot_reports']:
                logger.info("  - COT Reports: YES")
            if CONFIG['analyze_interest_rates']:
                logger.info("  - Interest Rate Differential: YES")
            if CONFIG['analyze_economic_events']:
                logger.info("  - Economic Calendar: YES")
            if CONFIG['analyze_macro_factors']:
                logger.info("  - Macro Factors: YES")
        
        if CONFIG['use_macro_filter']:
            logger.info(f"✓ Macro Filter: ACTIVE (Confidence threshold: {CONFIG['macro_confidence_min']}%)")
        
        logger.info("="*70)
    
    # Log Fibonacci configuration
    logger.info(f"Fibonacci Settings:")
    logger.info(f"  Lookback period: {CONFIG['fib_lookback']} candles")
    logger.info(f"  Min candles between swings: {CONFIG['min_fib_candles']} candles")
    logger.info(f"  Max setup age: {CONFIG['max_fib_age']} bars")
    logger.info(f"  Fibonacci levels: {CONFIG['fib_levels']}")
    
    # Log risk management configuration
    logger.info(f"Risk Management Settings:")
    logger.info(f"  Max concurrent trades (total): {CONFIG['max_concurrent_trades']}")
    logger.info(f"  Max concurrent trades (per pair): {CONFIG['max_concurrent_trades_of_same_pair']}")