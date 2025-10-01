"""
Configuration Module for MT5 ICT Fibonacci Trading Bot
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
    'symbol': 'USDCAD.raw',
    'backtest': False,
    'start': '2024-06-25',
    'end': '2025-06-30',
    'capital': 4950.0,
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
    
    # Trend Analysis Toggles
    'use_rsi_for_trend': True,
    'use_vwap_for_trend': True,
    'use_bollinger_for_trend': True,
    'use_ma_for_trend': True,
    
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
    
    # Order Execution Settings (NEW - Critical for live trading)
    'slippage_points': 50,  # Allowed slippage in points
    'max_retries': 3,  # Number of retry attempts for failed orders
    'retry_delay': 0.5,  # Seconds between retries
    'use_market_execution': True,  # Use market execution vs instant
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
    
    trend_indicators_enabled = [
        CONFIG['use_ma_for_trend'],
        CONFIG['use_rsi_for_trend'],
        CONFIG['use_vwap_for_trend'],
        CONFIG['use_bollinger_for_trend']
    ]
    
    if not any(trend_indicators_enabled):
        logger.warning("No trend indicators enabled!")
    
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