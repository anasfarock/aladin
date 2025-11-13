"""
Live Trading Engine - Enhanced with Fundamental & Sentiment Analysis
Shows complete Fibonacci swing range with macro analysis confirmation
Updated to integrate f_analysis module for news, social media, and fundamental factors
"""

import time
import logging
from config import CONFIG, MT5_AVAILABLE, logger
from indicators import compute_indicators
from fibonacci import FibonacciTracker, check_fibonacci_entry
from trend_analysis import determine_trend, get_trend_details, get_trend_confidence
from risk_management import (
    monitor_live_positions, 
    calculate_position_size,
    validate_trade_setup,
    check_max_positions_reached
)

# Import fundamental & sentiment analysis
try:
    from f_analysis import get_combined_sentiment_fundamental_score
    F_ANALYSIS_AVAILABLE = True
except ImportError:
    F_ANALYSIS_AVAILABLE = False
    logger.warning("f_analysis module not available. Fundamental analysis disabled.")

# Import chart exporter
try:
    from fib_visual_export import export_fibonacci_chart
    CHART_EXPORTER_AVAILABLE = True
except ImportError:
    logger.warning("Chart exporter not available. Install with: pip install plotly kaleido")
    CHART_EXPORTER_AVAILABLE = False

if MT5_AVAILABLE:
    from mt5_handler import (
        connect_mt5,
        disconnect_mt5,
        fetch_live_data,
        place_market_order,
        get_account_balance
    )

# Global Fibonacci tracker
fib_tracker = FibonacciTracker()

# Macro analysis cache (to avoid repeated API calls)
macro_analysis_cache = {'timestamp': None, 'data': None, 'symbol': None}
MACRO_CACHE_MINUTES = 60

def _get_macro_analysis(symbol):
    """
    Get macro analysis with caching to reduce API calls
    """
    import time as time_module
    
    if not CONFIG['use_fundamental_analysis'] and not CONFIG['use_sentiment_analysis']:
        return None
    
    if not F_ANALYSIS_AVAILABLE:
        return None
    
    current_time = time_module.time()
    
    # Check cache validity
    if (macro_analysis_cache['data'] is not None and 
        macro_analysis_cache['symbol'] == symbol and
        macro_analysis_cache['timestamp'] is not None and
        (current_time - macro_analysis_cache['timestamp']) < (MACRO_CACHE_MINUTES * 60)):
        logger.debug("Using cached macro analysis")
        return macro_analysis_cache['data']
    
    # Fetch fresh analysis
    try:
        logger.debug("Fetching fresh macro analysis...")
        macro_data = get_combined_sentiment_fundamental_score(symbol)
        macro_analysis_cache['data'] = macro_data
        macro_analysis_cache['timestamp'] = current_time
        macro_analysis_cache['symbol'] = symbol
        return macro_data
    except Exception as e:
        logger.warning(f"Error fetching macro analysis: {e}")
        return None

def _check_macro_filter(symbol, technical_trend, macro_analysis):
    """
    Check if macro analysis aligns with technical trend
    
    Returns:
        {
            'pass_filter': bool,
            'reason': str,
            'should_skip': bool
        }
    """
    if macro_analysis is None:
        return {
            'pass_filter': True,
            'reason': 'No macro analysis available',
            'should_skip': False
        }
    
    macro_direction = macro_analysis.get('overall_direction', 'neutral')
    macro_confidence = macro_analysis.get('confidence', 0)
    
    # Check if macro and technical align
    aligned = (macro_direction == technical_trend or macro_direction == 'neutral')
    
    if not aligned and CONFIG['show_macro_divergence_warnings']:
        logger.warning("⚠️  MACRO/TECHNICAL DIVERGENCE DETECTED")
        logger.warning(f"    Technical Trend: {technical_trend.upper()}")
        logger.warning(f"    Macro Direction: {macro_direction.upper()}")
        logger.warning(f"    Macro Confidence: {macro_confidence:.1f}%")
    
    # Decide if we should skip the trade
    should_skip = False
    if (not aligned and 
        CONFIG['skip_trades_against_macro'] and 
        macro_confidence > CONFIG['macro_bias_confidence_required']):
        should_skip = True
        reason = f"Strong macro bias ({macro_direction.upper()}) against technical signal"
    elif aligned:
        reason = "Macro and technical signals aligned ✓"
    else:
        reason = f"Macro divergence detected but trade allowed (confidence: {macro_confidence:.1f}%)"
    
    return {
        'pass_filter': not should_skip,
        'reason': reason,
        'should_skip': should_skip,
        'macro_direction': macro_direction,
        'macro_confidence': macro_confidence,
        'aligned': aligned
    }

def live_run_once(symbol):
    """
    Execute one live trading cycle with macro analysis integration
    """
    # Monitor existing positions first
    monitor_live_positions(symbol)
    
    if check_max_positions_reached(symbol):
        logger.info(f"Max concurrent trades ({CONFIG['max_concurrent_trades']}) reached")
        return None
    
    try:
        # Fetch live data for all timeframes
        logger.debug("Fetching live market data...")
        df_entry = fetch_live_data(symbol, CONFIG['timeframe_entry'], 500)
        df_d1 = fetch_live_data(symbol, 'D1', 500)
        df_h4 = fetch_live_data(symbol, 'H4', 500)
        df_h1 = fetch_live_data(symbol, 'H1', 500)
        
        # Compute indicators
        df_entry = compute_indicators(df_entry)
        df_d1 = compute_indicators(df_d1)
        df_h4 = compute_indicators(df_h4)
        df_h1 = compute_indicators(df_h1)
        
        # Update Fibonacci setups
        fib_tracker.update_fibonacci_setups(df_entry)
        valid_setups = fib_tracker.get_valid_setups()
        
        # Determine technical trend
        trend = determine_trend(df_d1, df_h4, df_h1)
        trend_details = get_trend_details(df_d1, df_h4, df_h1)
        trend_confidence = get_trend_confidence(df_d1, df_h4, df_h1)
        
        # Display technical trend analysis
        logger.info("="*70)
        logger.info(f"Symbol: {symbol}")
        logger.info("="*70)
        logger.info("📊 TECHNICAL TREND ANALYSIS")
        logger.info("="*70)
        
        if CONFIG.get('use_manual_trend', False):
            logger.info(f"Trend Mode: MANUAL")
            logger.info(f"Overall Trend: {trend.upper()}")
            logger.info(f"Confidence: 100.0% (Manual Override)")
        else:
            logger.info(f"Trend Mode: AUTOMATIC (Point-Based)")
            logger.info(f"Overall Trend: {trend.upper()}")
            logger.info(f"Confidence: {trend_confidence:.1f}%")
            logger.info(f"Total Points: {trend_details['total_points']:+.1f}")
        
        # ===== MACRO ANALYSIS SECTION =====
        macro_analysis = _get_macro_analysis(symbol)
        if macro_analysis and CONFIG['verbose_macro_analysis']:
            macro_filter = _check_macro_filter(symbol, trend, macro_analysis)
            
            logger.info("")
            logger.info("="*70)
            logger.info("🌍 MACRO & FUNDAMENTAL ANALYSIS")
            logger.info("="*70)
            logger.info(f"Overall Macro Direction: {macro_analysis['overall_direction'].upper()}")
            logger.info(f"Macro Confidence: {macro_analysis['confidence']:.1f}%")
            logger.info(f"Signal: {macro_analysis['combined_signal']}")
            logger.info(f"Alignment: {macro_filter['reason']}")
            
            if macro_filter['should_skip']:
                logger.warning(f"\n⛔ TRADE SKIPPED: {macro_filter['reason']}")
                return None
        
        logger.info("="*70)
        logger.info(f"Valid Fib Setups: {len(valid_setups)}")
        logger.info("="*70)
        
        if not valid_setups:
            logger.info("No valid Fibonacci setups found")
            return None
        
        # Check for entry signal
        df_entry_reset = df_entry.reset_index(drop=True)
        entry_signal = check_fibonacci_entry(
            valid_setups, 
            df_entry_reset,
            len(df_entry_reset) - 1, 
            trend
        )
        
        if entry_signal is None:
            logger.info("No Fibonacci entry signal aligned with trend")
            return None
        
        # Extract signal details
        signal_type = entry_signal['type']
        fib_level = entry_signal['fib_level']
        fib_price = entry_signal['fib_price']
        fib_setup = entry_signal['setup']
        
        # Get Fibonacci range
        if signal_type == 'long':
            swing_low_price = fib_setup['swing_low']['price']
            swing_high_price = fib_setup['swing_high']['price']
            fib_0_price = swing_low_price
            fib_1_price = swing_high_price
        else:
            swing_high_price = fib_setup['swing_high']['price']
            swing_low_price = fib_setup['swing_low']['price']
            fib_0_price = swing_high_price
            fib_1_price = swing_low_price
        
        swing_size_pips = abs(fib_1_price - fib_0_price) * 10000
        
        # Display entry signal
        logger.info("="*70)
        logger.info(f"🎯 FIBONACCI ENTRY SIGNAL DETECTED")
        logger.info("="*70)
        logger.info(f"Signal Type: {signal_type.upper()}")
        logger.info(f"Setup: {fib_setup['type']}")
        logger.info(f"Setup Age: {fib_setup['age']} bars")
        logger.info(f"Trend Alignment: {trend.upper()} ({'Manual' if CONFIG.get('use_manual_trend', False) else 'Auto'})")
        logger.info("")
        logger.info("📊 FIBONACCI SWING RANGE:")
        logger.info(f"  Fib 0.0 (100% Retracement): {fib_0_price:.5f}")
        logger.info(f"  Fib 1.0 (0% - Swing Point):  {fib_1_price:.5f}")
        logger.info(f"  Swing Size: {abs(fib_1_price - fib_0_price):.5f} ({swing_size_pips:.1f} pips)")
        logger.info("")
        logger.info(f"🎯 ENTRY LEVEL:")
        logger.info(f"  Fib {fib_level} Level: {fib_price:.5f}")
        
        if signal_type == 'long':
            swing_low = fib_setup['swing_low']['price']
            swing_high = fib_setup['swing_high']['price']
            retracement_pct = ((swing_high - fib_price) / (swing_high - swing_low)) * 100
            logger.info(f"  ({retracement_pct:.1f}% retracement from high)")
        else:
            swing_high = fib_setup['swing_high']['price']
            swing_low = fib_setup['swing_low']['price']
            retracement_pct = ((fib_price - swing_low) / (swing_high - swing_low)) * 100
            logger.info(f"  ({retracement_pct:.1f}% retracement from low)")
        
        logger.info("="*70)
        
        # Export chart
        if CHART_EXPORTER_AVAILABLE and CONFIG.get('export_fib_charts', True):
            try:
                chart_file = export_fibonacci_chart(symbol, df_entry, valid_setups, entry_signal)
                if chart_file:
                    logger.info(f"✓ Chart exported to: {chart_file}")
            except Exception as e:
                logger.warning(f"Could not export chart: {e}")
        
        # Calculate stops and targets
        if signal_type == 'long':
            stop_price = fib_price - (CONFIG['fib_tolerance'] * 3)
            entry_approx = df_entry.iloc[-1]['close']
            risk_per_unit = entry_approx - stop_price
            
            if risk_per_unit <= 0:
                logger.warning("Invalid risk calculation, skipping trade")
                return None
            
            tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
            tp_price = entry_approx + tp_distance
            side = 'buy'
        
        else:
            stop_price = fib_price + (CONFIG['fib_tolerance'] * 3)
            entry_approx = df_entry.iloc[-1]['close']
            risk_per_unit = stop_price - entry_approx
            
            if risk_per_unit <= 0:
                logger.warning("Invalid risk calculation, skipping trade")
                return None
            
            tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
            tp_price = entry_approx - tp_distance
            side = 'sell'
        
        # Validate trade
        is_valid, error_msg = validate_trade_setup(entry_approx, stop_price, tp_price, signal_type)
        if not is_valid:
            logger.warning(f"Trade validation failed: {error_msg}")
            return None
        
        # Calculate position size
        balance = get_account_balance()
        volume, risk_amount = calculate_position_size(symbol, entry_approx, stop_price, balance)
        
        stop_distance_pips = abs(entry_approx - stop_price) * 10000
        tp_distance_pips = abs(entry_approx - tp_price) * 10000
        
        logger.info(f"\n💼 TRADE DETAILS:")
        logger.info(f"  Side: {side.upper()}")
        logger.info(f"  Volume: {volume} lots")
        logger.info(f"  Entry (approx): {entry_approx:.5f}")
        logger.info(f"  Stop Loss: {stop_price:.5f} ({stop_distance_pips:.1f} pips)")
        logger.info(f"  Take Profit: {tp_price:.5f} ({tp_distance_pips:.1f} pips)")
        logger.info(f"  Risk Amount: ${risk_amount:.2f} ({CONFIG['risk_pct']}% of balance)")
        logger.info(f"  Risk/Reward: 1:{CONFIG['min_rr_ratio']}")
        
        # Place order
        logger.info("\n📤 Placing market order...")
        result = place_market_order(symbol, side, volume, stop_price, tp_price)
        
        if result and result.retcode == 10009:
            logger.info("="*70)
            logger.info(f"✅ TRADE EXECUTED SUCCESSFULLY!")
            logger.info("="*70)
            logger.info(f"  Order ID: {result.order}")
            logger.info(f"  Deal ID: {result.deal}")
            logger.info(f"  Actual Entry: {result.price:.5f}")
            logger.info(f"  Volume: {result.volume} lots")
            logger.info(f"  Slippage: {abs(result.price - entry_approx) * 10000:.1f} pips")
            logger.info("="*70 + "\n")
            return result
        else:
            logger.error(f"❌ Trade execution failed")
            if result:
                logger.error(f"  Return code: {result.retcode}")
                logger.error(f"  Comment: {result.comment}")
            return None
    
    except Exception as e:
        logger.error(f"Error in live trading cycle: {e}", exc_info=True)
        return None

def start_live_trading(symbol=None):
    """
    Start the live trading bot with macro analysis
    """
    if not MT5_AVAILABLE:
        logger.error("MetaTrader5 not available. Cannot start live trading.")
        return
    
    if symbol is None:
        symbol = CONFIG['symbol']
    
    logger.info("="*60)
    logger.info("ICT FIBONACCI LIVE TRADING BOT")
    logger.info("="*60)
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Entry Timeframe: {CONFIG['timeframe_entry']}")
    logger.info(f"Trend Timeframes: {', '.join(CONFIG['trend_timeframes'])}")
    
    if CONFIG.get('use_manual_trend', False):
        logger.info(f"Trend Mode: MANUAL ({CONFIG['manual_trend'].upper()})")
    else:
        logger.info(f"Trend Mode: AUTOMATIC (Point-Based)")
    
    logger.info(f"Risk per Trade: {CONFIG['risk_pct']}%")
    logger.info(f"Min R:R Ratio: {CONFIG['min_rr_ratio']}")
    
    # Display macro analysis status
    if CONFIG['use_fundamental_analysis'] or CONFIG['use_sentiment_analysis']:
        logger.info("")
        if F_ANALYSIS_AVAILABLE:
            logger.info("🌍 MACRO ANALYSIS: ENABLED")
            if CONFIG['use_macro_filter']:
                logger.info(f"   Filter Mode: ACTIVE (skip trades against strong macro)")
            else:
                logger.info(f"   Filter Mode: INFO ONLY (no trade skipping)")
        else:
            logger.warning("⚠️  Macro analysis requested but f_analysis not available")
    
    logger.info(f"Max Concurrent Trades: {CONFIG['max_concurrent_trades']}")
    logger.info("="*60)
    
    try:
        connect_mt5()
        logger.info("✓ Connected to MetaTrader5")
        
        balance = get_account_balance()
        logger.info(f"✓ Account Balance: ${balance:.2f}")
        
        logger.info("\n🤖 Bot is now running...")
        logger.info("Press Ctrl+C to stop\n")
        
        cycle_count = 0
        
        while True:
            cycle_count += 1
            logger.info(f"\n--- Cycle {cycle_count} ---")
            
            try:
                live_run_once(symbol)
            except Exception as e:
                logger.error(f"Error in trading cycle: {e}", exc_info=True)
            
            logger.debug(f"Waiting 60 seconds before next cycle...")
            time.sleep(60)
    
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Keyboard interrupt detected")
        logger.info("Stopping bot...")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    
    finally:
        disconnect_mt5()
        logger.info("✓ Disconnected from MetaTrader5")
        logger.info("Bot stopped.")

if __name__ == '__main__':
    start_live_trading()