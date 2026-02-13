"""
Live Trading Engine - Enhanced with ADX Strength Validation, ATR Stops, and Macro Analysis
Shows ADX strength validation and ATR stop comparison before executing trades
"""
from risk_management import (
    # ... existing imports ...
    initialize_daily_loss_tracker  # <-- ADD THIS
)
import json # For config reloading
import time
import logging
from datetime import datetime  # <-- ADD THIS LINE
from config import CONFIG, MT5_AVAILABLE, logger
from indicators import compute_indicators
from fibonacci import FibonacciTracker, check_fibonacci_entry
from trend_analysis import (
    determine_trend, 
    get_trend_details, 
    get_trend_confidence,
    check_adx_confirmation,
    check_adx_across_timeframes
)
from risk_management import (
    monitor_live_positions, 
    calculate_position_size,
    validate_trade_setup,
    check_max_positions_reached,
    check_max_positions_reached_for_symbol,
    compare_stop_loss_methods,
    check_daily_loss_limit,
    record_trade_loss,
    log_daily_loss_summary
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

# --- Daily Loss Tracking Globals ---
processed_deals = set() # Keep track of deals we've already recorded
# -----------------------------------

# Macro analysis cache
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
        logger.warning("[!]  MACRO/TECHNICAL DIVERGENCE DETECTED")
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

def _check_adx_filter(adx_dataframes_dict, trend):
    """
    Check if ADX filter validates the trend STRENGTH
    
    ADX only validates trend strength, not direction.
    Direction comes from your MA/BB/RSI indicators.
    
    Args:
        adx_dataframes_dict: dict with keys from CONFIG['adx_timeframes'] and dataframe values
        trend: 'bullish', 'bearish', or 'neutral' (from your indicators)
    
    Returns:
        {
            'pass_filter': bool,
            'reason': str,
            'adx_analysis': dict,
            'should_skip': bool
        }
    """
    if not CONFIG.get('use_adx_filter', False):
        return {
            'pass_filter': True,
            'reason': 'ADX filter disabled',
            'should_skip': False,
            'adx_analysis': None
        }
    
    # Check ADX across timeframes
    adx_analysis = check_adx_across_timeframes(adx_dataframes_dict, trend)
    
    # Log ADX analysis if verbose mode enabled
    if CONFIG.get('verbose_adx_analysis', True):
        logger.info("")
        logger.info("="*70)
        logger.info("📊 ADX TREND STRENGTH ANALYSIS")
        logger.info("="*70)
        
        for tf_name in CONFIG['adx_timeframes']:
            adx_check = adx_analysis['timeframes'][tf_name]
            logger.info(f"\n{tf_name} Timeframe:")
            logger.info(f"  ADX Value: {adx_check['adx_value']:.2f}")
            logger.info(f"  Strength: {adx_check['strength'].upper()}")
            logger.info(f"  +DI: {adx_check['+DI']:.2f}")
            logger.info(f"  -DI: {adx_check['-DI']:.2f}")
            logger.info(f"  Status: {adx_check['reason']}")
    
    threshold = CONFIG.get('adx_strength_threshold', 25)
    primary_tf = CONFIG['adx_timeframes'][0]  # Usually M15
    
    # Check if primary ADX timeframe is above threshold (most important)
    primary_adx = adx_analysis['timeframes'][primary_tf]
    
    if primary_adx['adx_value'] < threshold:
        should_skip = True
        reason = f"[!] {primary_tf} ADX too weak ({primary_adx['adx_value']:.2f} < {threshold}) - Market ranging"
    else:
        should_skip = False
        reason = f"[OK] ADX confirms trend strength ({primary_tf} ADX: {primary_adx['adx_value']:.2f})"
    
    return {
        'pass_filter': not should_skip,
        'reason': reason,
        'should_skip': should_skip,
        'adx_analysis': adx_analysis
    }

"""
FIXED _monitor_closed_trades function for live_trading.py

Replace the existing _monitor_closed_trades function with this corrected version
This properly filters deals by symbol and magic number
"""

def _monitor_closed_trades(symbol):
    """
    Monitor and record losses from closed positions.
    Called at each cycle to track new closed trades.
    
    FIXED: Properly filters deals by symbol and magic number
    """
    if not MT5_AVAILABLE:
        return

    try:
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta

        # Fetch deals from the last 24 hours to be safe
        from_date = datetime.now() - timedelta(days=1)
        
        # CRITICAL FIX: Use group parameter to filter by symbol
        # This is the correct way to filter deals in MT5 Python API
        deals = mt5.history_deals_get(from_date, datetime.now(), group=symbol)

        if deals is None:
            logger.debug(f"No deals found for {symbol} in history.")
            return

        if len(deals) == 0:
            logger.debug(f"No deals found for {symbol} in the last 24 hours.")
            return

        # Filter for:
        # 1. Our bot's trades (magic == 234000)
        # 2. Closing deals (entry == DEAL_ENTRY_OUT)
        # 3. Losing trades (profit < 0)
        deals_to_process = []
        
        for deal in deals:
            # Skip if already processed
            if deal.ticket in processed_deals:
                continue
            
            # Only process our bot's trades
            if deal.magic != 234000:
                continue
            
            # Only process closing deals (exit from position)
            if deal.entry != mt5.DEAL_ENTRY_OUT:
                continue
            
            # Only process losing trades
            if deal.profit >= 0:
                continue
            
            deals_to_process.append(deal)

        if not deals_to_process:
            logger.debug(f"No new closing losses found for {symbol}")
            return

        logger.debug(f"Found {len(deals_to_process)} new losing deals for {symbol}")

        for deal in deals_to_process:
            # Mark deal as processed immediately
            processed_deals.add(deal.ticket)

            loss_amount = abs(deal.profit)
            
            # Log detailed info about the loss
            logger.info(f"")
            logger.info(f"{'='*70}")
            logger.info(f"[-] CLOSED POSITION - LOSS RECORDED")
            logger.info(f"{'='*70}")
            logger.info(f"  Symbol: {deal.symbol}")
            logger.info(f"  Deal Ticket: {deal.ticket}")
            logger.info(f"  Entry Type: {deal.entry}")
            logger.info(f"  Volume: {deal.volume} lots")
            logger.info(f"  Entry Price: {deal.price:.5f}")
            logger.info(f"  Profit/Loss: -${loss_amount:.2f}")
            logger.info(f"  Time: {datetime.fromtimestamp(deal.time)}")
            logger.info(f"{'='*70}")
            
            # Record the loss
            record_trade_loss(deal.symbol, loss_amount)

    except Exception as e:
        # Use debug level to avoid spamming logs if MT5 connection is temporarily down
        logger.debug(f"Error monitoring closed trades: {e}")


# ALTERNATIVE if the above doesn't work (fallback method):
# Use this if the group parameter doesn't work with your MT5 build

def _monitor_closed_trades_fallback(symbol):
    """
    Fallback version that fetches all deals and filters manually
    Use this if the group parameter doesn't work
    """
    if not MT5_AVAILABLE:
        return

    try:
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta

        # Fetch deals from the last 24 hours
        from_date = datetime.now() - timedelta(days=1)
        
        # Get ALL deals (no filtering)
        all_deals = mt5.history_deals_get(from_date, datetime.now())

        if all_deals is None or len(all_deals) == 0:
            logger.debug("No deals found in history")
            return

        # Manually filter deals
        deals_to_process = []
        
        for deal in all_deals:
            # Skip if already processed
            if deal.ticket in processed_deals:
                continue
            
            # Only process this specific symbol
            if deal.symbol != symbol:
                continue
            
            # Only process our bot's trades (magic number 234000)
            if deal.magic != 234000:
                continue
            
            # Only process closing deals (exit from position)
            if deal.entry != mt5.DEAL_ENTRY_OUT:
                continue
            
            # Only process losing trades
            if deal.profit >= 0:
                continue
            
            deals_to_process.append(deal)

        if not deals_to_process:
            logger.debug(f"No new closing losses found for {symbol}")
            return

        logger.debug(f"Found {len(deals_to_process)} new losing deals for {symbol}")

        for deal in deals_to_process:
            # Mark deal as processed immediately
            processed_deals.add(deal.ticket)

            loss_amount = abs(deal.profit)
            
            logger.info(f"")
            logger.info(f"{'='*70}")
            logger.info(f"📊 CLOSED POSITION - LOSS RECORDED")
            logger.info(f"{'='*70}")
            logger.info(f"  Symbol: {deal.symbol}")
            logger.info(f"  Deal Ticket: {deal.ticket}")
            logger.info(f"  Volume: {deal.volume} lots")
            logger.info(f"  Entry Price: {deal.price:.5f}")
            logger.info(f"  Profit/Loss: -${loss_amount:.2f}")
            logger.info(f"  Time: {datetime.fromtimestamp(deal.time)}")
            logger.info(f"{'='*70}")
            
            # Record the loss
            record_trade_loss(deal.symbol, loss_amount)

    except Exception as e:
        logger.debug(f"Error monitoring closed trades (fallback): {e}")

def live_run_once(symbol):
    """
    Execute one live trading cycle with ADX, ATR stops, and macro analysis
    FIXED: Proper order of ALL checks - loss limits AND position limits
    """
    logger.info("="*70)
    logger.info("🔍 PRE-TRADE VALIDATION CHECKS")
    logger.info("="*70)
    
    # ===== CHECK 1: DAILY LOSS LIMITS =====
    can_trade, loss_limit_reason = check_daily_loss_limit(symbol)
    logger.info(f"1️⃣  Daily Loss Limit: {loss_limit_reason}")
    if not can_trade:
        logger.warning(f"   ⛔ BLOCKED - {loss_limit_reason}")
        logger.info("="*70)
        return None
    
    # ===== CHECK 2: GLOBAL MAX POSITIONS =====
    if check_max_positions_reached():
        max_trades = CONFIG['max_concurrent_trades']
        logger.warning(f"2️⃣  Global Position Limit: ⛔ BLOCKED")
        logger.warning(f"   Max concurrent trades ({max_trades}) already reached")
        logger.info("="*70)
        return None
    logger.info(f"2️⃣  Global Position Limit: ✓ OK ({CONFIG['max_concurrent_trades']} max)")
    
    # ===== CHECK 3: PER-SYMBOL MAX POSITIONS =====
    symbol_limit_reached, current_count, max_allowed = check_max_positions_reached_for_symbol(symbol)
    if symbol_limit_reached:
        logger.warning(f"[3]  Per-Symbol Position Limit: BLOCKED")
        logger.warning(f"   {symbol}: {current_count}/{max_allowed} trades (limit reached)")
        logger.info("="*70)
        return None
    logger.info(f"[3]  Per-Symbol Position Limit: OK ({current_count}/{max_allowed} on {symbol})")
    
    logger.info("="*70)
    logger.info("[OK] ALL PRE-TRADE CHECKS PASSED - Proceeding with analysis")
    logger.info("="*70)
    
    # Monitor existing positions
    monitor_live_positions(symbol)
    
    try:
        # Fetch live data for all timeframes
        logger.debug("Fetching live market data...")
        df_entry = fetch_live_data(symbol, CONFIG['timeframe_entry'], 500)
        
        # Fetch trend timeframes
        df_trend = {}
        for tf in CONFIG['trend_timeframes']:
            df_trend[tf] = fetch_live_data(symbol, tf, 500)
            df_trend[tf] = compute_indicators(df_trend[tf])
        
        # Fetch ADX-specific timeframes
        adx_dataframes = {}
        for tf in CONFIG['adx_timeframes']:
            if tf not in adx_dataframes:
                adx_dataframes[tf] = fetch_live_data(symbol, tf, 500)
                adx_dataframes[tf] = compute_indicators(adx_dataframes[tf])
        
        # Compute entry timeframe indicators
        df_entry = compute_indicators(df_entry)
        
        # Update Fibonacci setups
        fib_tracker.update_fibonacci_setups(df_entry)
        valid_setups = fib_tracker.get_valid_setups()
        
        # Determine technical trend (uses trend_timeframes)
        trend = determine_trend(df_trend['D1'], df_trend['H4'], df_trend['H1'])
        trend_details = get_trend_details(df_trend['D1'], df_trend['H4'], df_trend['H1'])
        trend_confidence = get_trend_confidence(df_trend['D1'], df_trend['H4'], df_trend['H1'])
        
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
        
        # ===== ADX FILTER CHECK =====
        adx_filter_result = _check_adx_filter(adx_dataframes, trend)
        
        if adx_filter_result['should_skip']:
            logger.warning(f"\n{adx_filter_result['reason']}")
            logger.info("="*70)
            return None
        else:
            logger.info(f"\n{adx_filter_result['reason']}")
        
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
                logger.warning(f"\n[!] TRADE SKIPPED: {macro_filter['reason']}")
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
        logger.info(f"[*] FIBONACCI ENTRY SIGNAL DETECTED")
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
        
        # ===== CALCULATE STOPS AND TARGETS WITH ATR =====
        entry_approx = df_entry.iloc[-1]['close']
        
        if signal_type == 'long':
            # Original Fibonacci stop
            fib_stop = fib_price - (CONFIG['fib_tolerance'] * 3)
            
            # ===== ATR-BASED STOP LOSS =====
            if CONFIG.get('use_atr_stops', False):
                stop_comparison = compare_stop_loss_methods(
                    df_entry, 
                    entry_approx, 
                    'long', 
                    fib_stop
                )
                
                stop_price = stop_comparison['stop_price']
                stop_method = stop_comparison['selected_method']
                
                if CONFIG.get('verbose_atr_analysis', True):
                    logger.info("")
                    logger.info("="*70)
                    logger.info("💰 STOP LOSS ANALYSIS")
                    logger.info("="*70)
                    atr_val = stop_comparison.get('atr_value')
                    atr_stop_val = stop_comparison.get('atr_stop')
                    if atr_val is not None and atr_stop_val is not None:
                        logger.info(f"ATR Value: {atr_val:.5f}")
                        logger.info(f"ATR Stop ({CONFIG['atr_stop_multiplier']}x): {atr_stop_val:.5f}")
                    logger.info(f"Fibonacci Stop: {stop_comparison['fib_stop']:.5f}")
                    logger.info(f"Selected: {stop_method} Stop @ {stop_price:.5f}")
                    logger.info(f"Reason: {stop_comparison['reason']}")
                    logger.info("="*70)
            else:
                stop_price = fib_stop
                stop_method = 'Fibonacci'
            
            risk_per_unit = entry_approx - stop_price
            
            if risk_per_unit <= 0:
                logger.warning("Invalid risk calculation, skipping trade")
                return None
            
            tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
            tp_price = entry_approx + tp_distance
            side = 'buy'
        
        else:  # SHORT
            # Original Fibonacci stop
            fib_stop = fib_price + (CONFIG['fib_tolerance'] * 3)
            
            # ===== ATR-BASED STOP LOSS =====
            if CONFIG.get('use_atr_stops', False):
                stop_comparison = compare_stop_loss_methods(
                    df_entry, 
                    entry_approx, 
                    'short', 
                    fib_stop
                )
                
                stop_price = stop_comparison['stop_price']
                stop_method = stop_comparison['selected_method']
                
                if CONFIG.get('verbose_atr_analysis', True):
                    logger.info("")
                    logger.info("="*70)
                    logger.info("💰 STOP LOSS ANALYSIS")
                    logger.info("="*70)
                    atr_val = stop_comparison.get('atr_value')
                    atr_stop_val = stop_comparison.get('atr_stop')
                    if atr_val is not None and atr_stop_val is not None:
                        logger.info(f"ATR Value: {atr_val:.5f}")
                        logger.info(f"ATR Stop ({CONFIG['atr_stop_multiplier']}x): {atr_stop_val:.5f}")
                    logger.info(f"Fibonacci Stop: {stop_comparison['fib_stop']:.5f}")
                    logger.info(f"Selected: {stop_method} Stop @ {stop_price:.5f}")
                    logger.info(f"Reason: {stop_comparison['reason']}")
                    logger.info("="*70)
            else:
                stop_price = fib_stop
                stop_method = 'Fibonacci'
            
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
        logger.info(f"  Stop Loss Method: {stop_method}")
        logger.info(f"  Volume: {volume} lots")
        logger.info(f"  Entry (approx): {entry_approx:.5f}")
        logger.info(f"  Stop Loss: {stop_price:.5f} ({stop_distance_pips:.1f} pips)")
        logger.info(f"  Take Profit: {tp_price:.5f} ({tp_distance_pips:.1f} pips)")
        logger.info(f"  Risk Amount: ${risk_amount:.2f} ({CONFIG['risk_pct']}% of balance)")
        logger.info(f"  Risk/Reward: 1:{CONFIG['min_rr_ratio']}")
        
        # Place order
        if not CONFIG.get('trading_enabled', False):
            logger.info(f"⚠️  Trading DISABLED in Config - Skipping Execution")
            logger.info(f"   Would have placed: {side.upper()} {volume} lots @ {entry_approx:.5f}")
            return None
            
        logger.info("\n📤 Placing market order...")
        result = place_market_order(symbol, side, volume, stop_price, tp_price)
        
        if result and result.retcode == 10009:
            logger.info("="*70)
            logger.info(f"[+] TRADE EXECUTED SUCCESSFULLY!")
            logger.info("="*70)
            logger.info(f"  Order ID: {result.order}")
            logger.info(f"  Deal ID: {result.deal}")
            logger.info(f"  Actual Entry: {result.price:.5f}")
            logger.info(f"  Volume: {result.volume} lots")
            logger.info(f"  Slippage: {abs(result.price - entry_approx) * 10000:.1f} pips")
            logger.info(f"  Stop Method: {stop_method}")
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
def start_live_trading(symbols=None):
    """
    Start the live trading bot with ADX, ATR stops, and macro analysis
    Supports MULTI-SYMBOL trading
    """
    if not MT5_AVAILABLE:
        logger.error("MetaTrader5 not available. Cannot start live trading.")
        return
    
    # Handle symbols argument
    if symbols is None:
        symbols = CONFIG.get('symbols', [CONFIG.get('symbol', 'USDCAD')])
    elif isinstance(symbols, str):
        symbols = [symbols]
    
    # Ensure items are strings and unique
    active_symbols = sorted(list(set([str(s) for s in symbols])))
    
    logger.info("="*60)
    logger.info("ICT FIBONACCI LIVE TRADING BOT")
    logger.info("="*60)
    logger.info(f"Active Symbols ({len(active_symbols)}): {', '.join(active_symbols)}")
    logger.info(f"Entry Timeframe: {CONFIG['timeframe_entry']}")
    logger.info(f"Trend Timeframes: {', '.join(CONFIG['trend_timeframes'])}")
    
    if CONFIG.get('use_manual_trend', False):
        logger.info(f"Trend Mode: MANUAL ({CONFIG['manual_trend'].upper()})")
    else:
        logger.info(f"Trend Mode: AUTOMATIC (Point-Based)")
    
    logger.info(f"Risk per Trade: {CONFIG['risk_pct']}%")
    logger.info(f"Min R:R Ratio: {CONFIG['min_rr_ratio']}")
    
    # Display ADX status
    if CONFIG.get('use_adx_filter', False):
        logger.info(f"\n[+] ADX FILTER: ENABLED")
        logger.info(f"   ADX Timeframes: {', '.join(CONFIG['adx_timeframes'])}")
        logger.info(f"   Strength Threshold: {CONFIG['adx_strength_threshold']}")
    else:
        logger.info(f"\n[-] ADX FILTER: DISABLED")
    
    # Display ATR stops status
    if CONFIG.get('use_atr_stops', False):
        logger.info(f"\n[+] ATR STOPS: ENABLED")
        logger.info(f"   Multiplier: {CONFIG['atr_stop_multiplier']}x")
        logger.info(f"   Method: {CONFIG['atr_stop_method'].upper()}")
    else:
        logger.info(f"\n[-] ATR STOPS: DISABLED (using Fibonacci stops)")
    
    # Display macro analysis status
    if CONFIG['use_fundamental_analysis'] or CONFIG['use_sentiment_analysis']:
        logger.info("")
        if F_ANALYSIS_AVAILABLE:
            logger.info("[+] MACRO ANALYSIS: ENABLED")
            if CONFIG['use_macro_filter']:
                logger.info(f"   Filter Mode: ACTIVE (skip trades against strong macro)")
            else:
                logger.info(f"   Filter Mode: INFO ONLY (no trade skipping)")
        else:
            logger.warning("[!] Macro analysis requested but f_analysis not available")
    
    # Display position limits
    logger.info(f"\n[!] POSITION & LOSS LIMITS:")
    logger.info(f"   Max Concurrent Trades (Global): {CONFIG['max_concurrent_trades']}")
    logger.info(f"   Max Concurrent Trades (Per Symbol): {CONFIG['max_concurrent_trades_of_same_pair']}")
    
    # Display daily loss limits
    logger.info(f"\n[!] DAILY LOSS LIMITS:")
    if CONFIG['max_daily_losses'] > 0:
        logger.info(f"   Max Daily Loss (Account): ${CONFIG['max_daily_losses']:.2f}")
    else:
        logger.info(f"   Max Daily Loss (Account): UNLIMITED")
    
    if CONFIG['max_daily_loss_count'] > 0:
        logger.info(f"   Max Daily Losing Trades (Account): {CONFIG['max_daily_loss_count']} trades")
    else:
        logger.info(f"   Max Daily Losing Trades (Account): UNLIMITED")
    
    if CONFIG['max_daily_losses_per_symbol'] > 0:
        logger.info(f"   Max Daily Loss (Per Symbol): ${CONFIG['max_daily_losses_per_symbol']:.2f}")
    else:
        logger.info(f"   Max Daily Loss (Per Symbol): UNLIMITED")
    
    if CONFIG['max_daily_loss_count_per_symbol'] > 0:
        logger.info(f"   Max Daily Loss (Per Symbol Count): {CONFIG['max_daily_loss_count_per_symbol']} trades")
    else:
        logger.info(f"   Max Daily Loss (Per Symbol Count): UNLIMITED")
    
    logger.info("="*60 + "\n")
    
    try:
        connect_mt5()
        
        # Initialize daily loss tracker
        initialize_daily_loss_tracker()
        
        logger.info(f"Waiting for next candle close... (checking every 60s)")
        
        while True:
            # Monitor closed trades for ALL symbols we are tracking
            # We also check for global account history generally
            # But the function takes a symbol argument.
            # We should probably check all active symbols
            
            # Reload config dynamically to check trading_enabled status
            try:
                import json
                if os.path.exists('config.json'):
                    with open('config.json', 'r') as f:
                        new_conf = json.load(f)
                        if 'trading_enabled' in new_conf:
                            current_status = new_conf['trading_enabled']
                            if current_status != CONFIG.get('trading_enabled'):
                                logger.info(f"STATUS CHANGE: Trading is now {'ENABLED' if current_status else 'DISABLED'}")
                            CONFIG['trading_enabled'] = current_status
            except Exception:
                pass # Ignore file read errors momentarily
            
            # Check if enabled for this cycle
            trading_is_enabled = CONFIG.get('trading_enabled', False)
            
            if not trading_is_enabled:
                logger.info("[INFO] Trading Execution is DISABLED. Waiting for switch to be ENABLED...")
            
            for symbol in active_symbols:
                try:
                    # 1. Update daily loss stats for this symbol
                    _monitor_closed_trades(symbol)
                    
                    # 2. Run trading logic for this symbol ONLY if trading is enabled
                    if trading_is_enabled:
                        live_run_once(symbol)
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                
                # Small pause between symbols to not hammer CPU/API
                if trading_is_enabled:
                    time.sleep(1)
                
            # Sleep until next cycle
            # 60s is standard for M1/M5+ based bots checking once per bar or minute
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("Stopping...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        disconnect_mt5()
if __name__ == '__main__':
    start_live_trading()