"""
Configuration Module for MT5 ICT Fibonacci Trading Bot
Updated with Point-Based Trend System, Manual Trend Override, and Fundamental Analysis
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
# This lets you put keys in a .env file (e.g. NEWSAPI_KEY=...) or set them
# in your OS environment and the config will pick them up.
try:
    from dotenv import load_dotenv
    load_dotenv()  # will load variables from a .env file if present
    logger.info("Loaded environment variables from .env (if present)")
except Exception:
    # If python-dotenv is not installed, environment variables must be set
    logger.info("python-dotenv not available; falling back to OS environment variables")

# ----------------------------- CONFIG -----------------------------
CONFIG = {
    # Trading Parameters
    'symbol': 'USDCAD',  # Trading Symbol
    'backtest': False,  # Set to True for Backtesting, False for Live Trading
    'start': '2024-06-25',  # Start Date For Backtest, Format: YYYY-MM-DD
    'end': '2025-06-30',    # End Date For Backtest, Format: YYYY-MM-DD
    'capital': 5000.0,  # Initial Capital for Backtesting
    'risk_pct': 0.5,  # Risk per trade in percentage
    
    # Timeframes
    'timeframe_entry': 'M15',  # Entry timeframe
    'trend_timeframes': ['D1', 'H4', 'H1'],  # Timeframes used for trend analysis
    
    # Technical Indicators
    'boll_period': 20,
    'boll_std': 2,
    'rsi_period': 14,
    'vwap_period': 20,
    'ma_fast': 9,
    'ma_slow': 18,
    
    # Manual Trend Override
    'use_manual_trend': False,  # Set to True to override automatic trend analysis
    'manual_trend': 'bullish',  # Options: 'bullish', 'bearish', 'neutral'
    
    # Trend Analysis Toggles (Used only when use_manual_trend=False)
    'use_rsi_for_trend': True,
    'use_vwap_for_trend': True,
    'use_bollinger_for_trend': True,
    'use_ma_for_trend': True,
    
    # Point-Based Trend System
    'trend_bullish_threshold': 10,   # Points needed for bullish trend
    'trend_bearish_threshold': -10,  # Points needed for bearish trend
    
    # Fibonacci Settings
    'fib_lookback': 30,              # Number of candles to look back for swing points
    'min_fib_candles': 5,            # Minimum candles between swing points
    'fib_levels': [0.618, 0.705, 0.786],
    'fib_tolerance': 0.0001,
    'min_swing_size': 0.0005,        # Minimum price distance for valid swing
    'max_fib_age': 100,              # Maximum bars ago for Fibonacci setup to be valid
    'fib_confirmation_bars': 2,      # Bars to confirm Fibonacci level touch
    
    # Chart Visualization Settings
    'export_fib_charts': True,       # Export Fibonacci charts as HTML files
    'chart_output_dir': 'fib_charts', # Directory to save charts
    
    # ===== FUNDAMENTAL & SENTIMENT ANALYSIS SETTINGS (NEW) =====
    'use_fundamental_analysis': True,      # Enable/disable fundamental analysis
    'use_sentiment_analysis': False,        # Enable/disable news/social sentiment
    'use_macro_filter': True,              # Use macro analysis as trade filter
    
    # Macro Analysis Weights (how important macro vs technical)
    'macro_weight': 0.35,                  # 35% macro analysis influence
    'technical_weight': 0.65,              # 65% technical analysis influence
    
    # Macro Signal Thresholds
    'macro_bullish_threshold': 15,         # Score needed for bullish macro signal
    'macro_bearish_threshold': -15,        # Score needed for bearish macro signal
    'macro_confidence_min': 40,            # Minimum confidence to use macro filter
    
    # Sentiment Analysis Settings
    'sentiment_lookback_hours': 24,        # Hours to look back for news
    'sentiment_min_articles': 3,           # Minimum articles for valid sentiment
    'sentiment_confidence_required': 30,   # Min confidence to use sentiment
    
    # Fundamental Analysis Settings
    'fundamental_lookback_days': 7,        # Days for fundamental data
    'interest_rate_update_freq': 'weekly', # How often to update rates
    'cot_extreme_threshold': 0.75,         # COT positioning extreme threshold
    
    # API Configuration for F_Analysis (empty = disabled).
    # Prefer setting these in your environment or a .env file. Example .env keys:
    # NEWSAPI_KEY, ALPHA_VANTAGE_KEY, TWITTER_API_KEY, TWITTER_API_SECRET,
    # REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
    'newsapi_key': os.getenv('NEWSAPI_KEY', ''),
    'alpha_vantage_key': os.getenv('ALPHA_VANTAGE_KEY', ''),
    'twitter_api_key': os.getenv('TWITTER_API_KEY', ''),
    'twitter_api_secret': os.getenv('TWITTER_API_SECRET', ''),
    'reddit_client_id': os.getenv('REDDIT_CLIENT_ID', ''),
    'reddit_client_secret': os.getenv('REDDIT_CLIENT_SECRET', ''),
    
    # Macro Analysis Features Toggle
    'analyze_cot_reports': True,           # Analyze COT positioning
    'analyze_interest_rates': True,        # Analyze rate differentials
    'analyze_economic_events': True,       # Watch economic calendar
    'analyze_macro_factors': True,         # Analyze GDP, inflation, etc.
    
    # News & Social Media Analysis Toggle
    'analyze_news': True,                  # Analyze financial news
    'analyze_twitter': False,              # Analyze Twitter (requires API key)
    'analyze_reddit': False,               # Analyze Reddit (requires API key)
    
    # Macro Bias Filtering (skip trades against strong macro signals)
    'skip_trades_against_macro': False,    # If True, skip trades against macro bias
    'macro_bias_confidence_required': 60,  # Confidence level required to skip
    
    # Risk Management
    'max_concurrent_trades': 8,
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
    'verbose_macro_analysis': True,        # Detailed macro analysis logging
    'show_macro_divergence_warnings': True, # Warn on tech/macro divergence
}

def get_mt5_timeframes():
    """Get MT5 timeframes mapping"""
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
    """Validate configuration settings"""
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