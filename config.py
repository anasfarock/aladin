"""
Configuration Module for MT5 ICT Fibonacci Trading Bot
Updated with Point-Based Trend System and Manual Trend Override
"""

import logging

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
    
    # Manual Trend Override (NEW)
    'use_manual_trend': False,  # Set to True to override automatic trend analysis
    'manual_trend': 'bullish',  # Options: 'bullish', 'bearish', 'neutral'
    
    # Trend Analysis Toggles (Used only when use_manual_trend=False)
    'use_rsi_for_trend': True,
    'use_vwap_for_trend': True,
    'use_bollinger_for_trend': True,
    'use_ma_for_trend': True,
    
    # Point-Based Trend System
    # Total max points: (3+3+2+2) * (3+2+1) = 60 points
    # Recommended thresholds:
    # - Conservative: ±12 points (strong trend required)
    # - Moderate: ±8 points (balanced)
    # - Aggressive: ±5 points (trade more setups)
    'trend_bullish_threshold': 10,   # Points needed for bullish trend
    'trend_bearish_threshold': -10,  # Points needed for bearish trend
    
    # Fibonacci Settings
    'fib_lookback': 30,
    'fib_levels': [0.618, 0.705, 0.786],
    'fib_tolerance': 0.0001,
    'min_swing_size': 0.0005,
    'max_fib_age': 100,
    'fib_confirmation_bars': 2,
    
    # Risk Management
    'max_concurrent_trades': 10,
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
        indicators_count = sum(trend_indicators_enabled)
        max_points_per_indicator = {
            'ma': 3,
            'rsi': 3,
            'vwap': 2,
            'bb': 2
        }
        
        active_indicators = []
        if CONFIG['use_ma_for_trend']:
            active_indicators.append('ma')
        if CONFIG['use_rsi_for_trend']:
            active_indicators.append('rsi')
        if CONFIG['use_vwap_for_trend']:
            active_indicators.append('vwap')
        if CONFIG['use_bollinger_for_trend']:
            active_indicators.append('bb')
        
        max_points_per_tf = sum(max_points_per_indicator[ind] for ind in active_indicators)
        max_total_points = max_points_per_tf * 6  # (D1*3 + H4*2 + H1*1)
        
        logger.info(f"Point-Based Trend System:")
        logger.info(f"  Max possible points: ±{max_total_points}")
        logger.info(f"  Bullish threshold: {CONFIG['trend_bullish_threshold']} points")
        logger.info(f"  Bearish threshold: {CONFIG['trend_bearish_threshold']} points")
        
        # Warn if thresholds are too high
        if abs(CONFIG['trend_bullish_threshold']) > max_total_points * 0.7:
            logger.warning(f"⚠️  Bullish threshold is high ({CONFIG['trend_bullish_threshold']}). "
                          f"May result in fewer trades.")
        if abs(CONFIG['trend_bearish_threshold']) > max_total_points * 0.7:
            logger.warning(f"⚠️  Bearish threshold is high ({abs(CONFIG['trend_bearish_threshold'])}). "
                          f"May result in fewer trades.")