"""
Backtesting Module - With ADX Trend Strength Validation and ATR Stop Loss
Historical simulation with ADX validation, ATR stops, and corrected dataframe slicing
Updated to support Manual Trend Override, ADX Filter, ATR Stop Loss Strategy, and ADX Manual Control
"""

from datetime import datetime, timedelta
import pandas as pd
import logging
import numpy as np
from config import CONFIG, MT5_TIMEFRAMES, logger
from indicators import compute_indicators
from fibonacci import identify_swing_points, find_fibonacci_setups, check_fibonacci_entry
from trend_analysis import determine_trend, check_adx_across_timeframes
from risk_management import update_trailing_stop, compare_stop_loss_methods, DailyLossTracker
from mt5_handler import fetch_mt5_df
from f_analysis import get_combined_sentiment_fundamental_score

def calculate_max_drawdown(equity_curve):
    """Calculate maximum drawdown from equity curve"""
    if len(equity_curve) == 0:
        return 0
    
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak * 100
    return abs(drawdown.min())

def check_adx_filter_backtest(adx_dataframes_dict, trend):
    """
    Check if ADX filter validates the trend STRENGTH during backtest
    
    ADX only validates trend strength, not direction.
    Direction comes from your MA/BB/RSI indicators.
    
    Supports ADX manual control for cross-timeframe confirmation.
    
    Args:
        adx_dataframes_dict: dict with keys from CONFIG['adx_timeframes'] and dataframe values
        trend: 'bullish', 'bearish', or 'neutral' (from your indicators)
    
    Returns:
        bool: True if ADX confirms trend strength, False otherwise
    """
    if not CONFIG.get('use_adx_filter', False):
        return True  # ADX filter disabled, pass all trades
    
    try:
        adx_analysis = check_adx_across_timeframes(adx_dataframes_dict, trend)
        
        # The check_adx_across_timeframes function now handles manual control logic
        # It returns 'all_confirmed' based on the configuration mode
        adx_confirms = adx_analysis['all_confirmed']
        
        return adx_confirms
    
    except Exception as e:
        logger.warning(f"Error checking ADX filter in backtest: {e}")
        return True  # On error, allow the trade

def backtest(symbol, start, end, timeframe):
    """
    Run ICT Fibonacci backtest with ADX strength validation, ATR stops, and corrected logic
    
    FEATURES:
    - ADX trend strength validation (configurable threshold)
    - ADX manual control for cross-timeframe confirmation
    - ATR-based stop loss with Fibonacci comparison
    - Proper index synchronization for Fibonacci setups
    - Entry on next bar open (no lookahead bias)
    - Manual trend override support
    - Trailing stops
    
    Args:
        symbol: Trading symbol
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        timeframe: Entry timeframe
    
    Returns:
        tuple: (trades_df, summary_dict)
    """
    import os
    
    os.makedirs('results', exist_ok=True)
    
    logger.info(f"Starting ICT Fibonacci backtest: {symbol} from {start} to {end}")
    
    # Display trend mode
    if CONFIG.get('use_manual_trend', False):
        logger.info(f"Trend Mode: MANUAL ({CONFIG['manual_trend'].upper()})")
        logger.info("Note: Automatic trend analysis will be BYPASSED")
    else:
        logger.info("Trend Mode: AUTOMATIC (Point-Based System)")
    
    # Display ADX filter status
    if CONFIG.get('use_adx_filter', False):
        logger.info(f"ADX Filter: ENABLED (Timeframes: {', '.join(CONFIG['adx_timeframes'])}, "
                   f"Threshold: {CONFIG['adx_strength_threshold']})")
        
        if CONFIG.get('adx_manual_control', False):
            mode = "STRICT (primary TF)" if CONFIG.get('adx_manual_control_strict', False) else "LOOSE (any TF)"
            logger.info(f"ADX Manual Control: ENABLED - {mode}")
            logger.info(f"ADX can confirm trends across different timeframes")
        else:
            logger.info("ADX Manual Control: DISABLED (exact timeframe match only)")
    else:
        logger.info("ADX Filter: DISABLED")
    
    # Display ATR stops status
    if CONFIG.get('use_atr_stops', False):
        logger.info(f"ATR Stops: ENABLED (Multiplier: {CONFIG['atr_stop_multiplier']}x, Method: {CONFIG['atr_stop_method']})")
    else:
        logger.info("ATR Stops: DISABLED (using Fibonacci stops)")
    
    tf = MT5_TIMEFRAMES.get(timeframe)
    if tf is None:
        raise ValueError(f'Unsupported timeframe: {timeframe}')
    
    utc_from = datetime.fromisoformat(start)
    utc_to = datetime.fromisoformat(end)
    # Reduced from 90 to 30 to allow backtesting on smaller datasets
    extended_from = utc_from - timedelta(days=30)
    
    # Fetch data for trend timeframes
    try:
        logger.info("Fetching historical data...")
        df = fetch_mt5_df(symbol, tf, extended_from, utc_to, min_bars_expected=CONFIG['min_bars_required'])
        
        # Fetch trend timeframes
        trend_dataframes = {}
        for tf_name in CONFIG['trend_timeframes']:
            # We don't strictly *need* an exact amount for higher timeframes unless MA requires it
            # But making it too high causes errors if data is short
            min_bars = 5 if tf_name == 'D1' else 10 
            trend_dataframes[tf_name] = fetch_mt5_df(
                symbol, 
                MT5_TIMEFRAMES[tf_name], 
                extended_from, 
                utc_to, 
                min_bars_expected=min_bars
            )
        
        # Fetch ADX-specific timeframes
        adx_dataframes = {}
        for tf_name in CONFIG['adx_timeframes']:
            if tf_name not in adx_dataframes:
                adx_dataframes[tf_name] = fetch_mt5_df(
                    symbol, 
                    MT5_TIMEFRAMES[tf_name], 
                    extended_from, 
                    utc_to, 
                    min_bars_expected=10
                )
    
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        raise
    
    # Compute indicators (including ADX and ATR)
    logger.info("Computing technical indicators (including ADX and ATR)...")
    df = compute_indicators(df)
    
    # Compute indicators for trend timeframes
    for tf_name in trend_dataframes:
        trend_dataframes[tf_name] = compute_indicators(trend_dataframes[tf_name])
    
    # Compute indicators for ADX timeframes
    for tf_name in adx_dataframes:
        adx_dataframes[tf_name] = compute_indicators(adx_dataframes[tf_name])
    
    # Filter to backtest period
    df = df[df['time'] >= utc_from].reset_index(drop=True)
    
    if df.empty:
        raise RuntimeError(f"No data available for backtest period")
    
    # Initialize backtest variables
    balance = CONFIG['capital']
    trades = []
    open_positions = []
    pending_entry = None  # Store signal for next bar entry
    
    # Initialize a daily loss tracker specifically for backtesting
    backtest_loss_tracker = DailyLossTracker()
    
    # Trend tracking for statistics
    trend_counts = {'bullish': 0, 'bearish': 0, 'neutral': 0}
    adx_filtered_signals = 0
    macro_filtered_signals = 0
    
    logger.info(f"Running backtest on {len(df)} bars...")
    
    # Track trend changes for logging (only in automatic mode)
    last_logged_trend = None
    
    # Main backtest loop
    for idx in range(len(df)):
        current_bar = df.iloc[idx]
        current_time = current_bar['time']
        
        # Manually manage daily loss tracker date
        backtest_loss_tracker._check_and_reset_if_needed(current_time)
        
        # Get timeframe slices up to current time
        trend_slices = {}
        for tf_name in CONFIG['trend_timeframes']:
            trend_slices[tf_name] = trend_dataframes[tf_name][trend_dataframes[tf_name]['time'] <= current_time].copy()
        
        # Check all trend slices have data
        if any(len(trend_slices[tf]) == 0 for tf in CONFIG['trend_timeframes']):
            continue
        
        # Get ADX timeframe slices up to current time
        adx_slices = {}
        for tf_name in CONFIG['adx_timeframes']:
            adx_slices[tf_name] = adx_dataframes[tf_name][adx_dataframes[tf_name]['time'] <= current_time].copy()
        
        # Check all ADX slices have data
        if any(len(adx_slices[tf]) == 0 for tf in CONFIG['adx_timeframes']):
            continue
        
        # STEP 1: Execute pending entry from previous bar (avoid lookahead bias)
        if pending_entry is not None:
            entry_price = current_bar['open']  # Enter at open of current bar
            signal_type = pending_entry['type']
            fib_level = pending_entry['fib_level']
            fib_price = pending_entry['fib_price']
            setup_type = pending_entry['setup_type']
            trend_mode = 'manual' if CONFIG.get('use_manual_trend', False) else 'auto'
            adx_passed = pending_entry.get('adx_passed', False)
            
            # Calculate stops and targets
            if signal_type == 'long':
                # Original Fibonacci stop
                fib_stop = fib_price - (CONFIG['fib_tolerance'] * 3)
                
                # ===== ATR-BASED STOP LOSS =====
                if CONFIG.get('use_atr_stops', False):
                    stop_comparison = compare_stop_loss_methods(
                        df.iloc[max(0, idx-200):idx+1].reset_index(drop=True),
                        entry_price,
                        'long',
                        fib_stop
                    )
                    
                    stop_price = stop_comparison['stop_price']
                    stop_method = stop_comparison['selected_method']
                    atr_stop_val = stop_comparison.get('atr_stop')
                    if atr_stop_val is not None:
                        logger.debug(f"LONG Stop Loss: {stop_method} @ {stop_price:.5f} "
                                   f"(Fib: {fib_stop:.5f}, ATR: {atr_stop_val:.5f})")
                    else:
                        logger.debug(f"LONG Stop Loss: {stop_method} @ {stop_price:.5f} (Fib: {fib_stop:.5f})")
                else:
                    stop_price = fib_stop
                    stop_method = 'Fibonacci'
                
                risk_per_unit = entry_price - stop_price
                
                if risk_per_unit > 0:
                    tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
                    tp_price = entry_price + tp_distance
                    
                    # Calculate position size
                    risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
                    units = risk_amount / risk_per_unit
                    
                    # Create position
                    position = {
                        'entry_time': current_time,
                        'side': 'long',
                        'entry': entry_price,
                        'stop': stop_price,
                        'original_stop': stop_price,
                        'tp': tp_price,
                        'units': units,
                        'trailing_active': False,
                        'trail_level': None,
                        'fib_level': fib_level,
                        'setup_type': setup_type,
                        'trend_mode': trend_mode,
                        'adx_passed': adx_passed,
                        'stop_method': stop_method
                    }
                    
                    open_positions.append(position)
                    logger.debug(f"Entered LONG at {entry_price:.5f}, SL: {stop_price:.5f} ({stop_method}), "
                               f"TP: {tp_price:.5f}, Fib: {fib_level}, Trend: {trend_mode}")
            
            else:  # SHORT
                # Original Fibonacci stop
                fib_stop = fib_price + (CONFIG['fib_tolerance'] * 3)
                
                # ===== ATR-BASED STOP LOSS =====
                if CONFIG.get('use_atr_stops', False):
                    stop_comparison = compare_stop_loss_methods(
                        df.iloc[max(0, idx-200):idx+1].reset_index(drop=True),
                        entry_price,
                        'short',
                        fib_stop
                    )
                    
                    stop_price = stop_comparison['stop_price']
                    stop_method = stop_comparison['selected_method']
                    atr_stop_val = stop_comparison.get('atr_stop')
                    if atr_stop_val is not None:
                        logger.debug(f"SHORT Stop Loss: {stop_method} @ {stop_price:.5f} "
                                   f"(Fib: {fib_stop:.5f}, ATR: {atr_stop_val:.5f})")
                    else:
                        logger.debug(f"SHORT Stop Loss: {stop_method} @ {stop_price:.5f} (Fib: {fib_stop:.5f})")
                else:
                    stop_price = fib_stop
                    stop_method = 'Fibonacci'
                
                risk_per_unit = stop_price - entry_price
                
                if risk_per_unit > 0:
                    tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
                    tp_price = entry_price - tp_distance
                    
                    risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
                    units = risk_amount / risk_per_unit
                    
                    position = {
                        'entry_time': current_time,
                        'side': 'short',
                        'entry': entry_price,
                        'stop': stop_price,
                        'original_stop': stop_price,
                        'tp': tp_price,
                        'units': units,
                        'trailing_active': False,
                        'trail_level': None,
                        'fib_level': fib_level,
                        'setup_type': setup_type,
                        'trend_mode': trend_mode,
                        'adx_passed': adx_passed,
                        'stop_method': stop_method
                    }
                    
                    open_positions.append(position)
                    logger.debug(f"Entered SHORT at {entry_price:.5f}, SL: {stop_price:.5f} ({stop_method}), "
                               f"TP: {tp_price:.5f}, Fib: {fib_level}, Trend: {trend_mode}")
            
            pending_entry = None
        
        # STEP 2: Check exits for open positions
        for pos in open_positions[:]:
            # Update trailing stop
            if CONFIG['trailing_stop']:
                current_price = current_bar['close']
                pos = update_trailing_stop(pos, current_price)
            
            # Check stop loss
            if pos['side'] == 'long':
                if current_bar['low'] <= pos['stop']:
                    exit_price = pos['stop']
                    pl = (exit_price - pos['entry']) * pos['units']
                    balance += pl
                    
                    if pl < 0:
                        backtest_loss_tracker.record_loss(symbol, abs(pl))
                    
                    exit_reason = 'trailing_stop' if pos.get('trailing_active', False) else 'stop_loss'
                    
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_time,
                        'side': 'long',
                        'entry': pos['entry'],
                        'exit': exit_price,
                        'pl': pl,
                        'exit_reason': exit_reason,
                        'fib_level': pos.get('fib_level', 0),
                        'setup_type': pos.get('setup_type', 'unknown'),
                        'trend_mode': pos.get('trend_mode', 'auto'),
                        'adx_passed': pos.get('adx_passed', False),
                        'stop_method': pos.get('stop_method', 'Fibonacci')
                    })
                    open_positions.remove(pos)
                    continue
                
                # Check take profit
                if current_bar['high'] >= pos['tp']:
                    exit_price = pos['tp']
                    pl = (exit_price - pos['entry']) * pos['units']
                    balance += pl
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_time,
                        'side': 'long',
                        'entry': pos['entry'],
                        'exit': exit_price,
                        'pl': pl,
                        'exit_reason': 'take_profit',
                        'fib_level': pos.get('fib_level', 0),
                        'setup_type': pos.get('setup_type', 'unknown'),
                        'trend_mode': pos.get('trend_mode', 'auto'),
                        'adx_passed': pos.get('adx_passed', False),
                        'stop_method': pos.get('stop_method', 'Fibonacci')
                    })
                    open_positions.remove(pos)
                    continue
            
            elif pos['side'] == 'short':
                if current_bar['high'] >= pos['stop']:
                    exit_price = pos['stop']
                    pl = (pos['entry'] - exit_price) * pos['units']
                    balance += pl
                    
                    if pl < 0:
                        backtest_loss_tracker.record_loss(symbol, abs(pl))
                    
                    exit_reason = 'trailing_stop' if pos.get('trailing_active', False) else 'stop_loss'
                    
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_time,
                        'side': 'short',
                        'entry': pos['entry'],
                        'exit': exit_price,
                        'pl': pl,
                        'exit_reason': exit_reason,
                        'fib_level': pos.get('fib_level', 0),
                        'setup_type': pos.get('setup_type', 'unknown'),
                        'trend_mode': pos.get('trend_mode', 'auto'),
                        'adx_passed': pos.get('adx_passed', False),
                        'stop_method': pos.get('stop_method', 'Fibonacci')
                    })
                    open_positions.remove(pos)
                    continue
                
                if current_bar['low'] <= pos['tp']:
                    exit_price = pos['tp']
                    pl = (pos['entry'] - exit_price) * pos['units']
                    balance += pl
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': current_time,
                        'side': 'short',
                        'entry': pos['entry'],
                        'exit': exit_price,
                        'pl': pl,
                        'exit_reason': 'take_profit',
                        'fib_level': pos.get('fib_level', 0),
                        'setup_type': pos.get('setup_type', 'unknown'),
                        'trend_mode': pos.get('trend_mode', 'auto'),
                        'adx_passed': pos.get('adx_passed', False),
                        'stop_method': pos.get('stop_method', 'Fibonacci')
                    })
                    open_positions.remove(pos)
                    continue
        
        # STEP 3: Check for new entry signals
        if len(open_positions) >= CONFIG['max_concurrent_trades']:
            continue
            
        # Check Daily Loss Limit (pass current_time to simulate that date)
        can_trade, reason = backtest_loss_tracker.can_trade(symbol, current_time)
        if not can_trade:
            continue
        
        if pending_entry is not None:
            continue  # Already have a pending entry
        
        # Need enough historical data
        if idx < CONFIG['fib_lookback']:
            continue
        
        # Get data slice for Fibonacci analysis (up to PREVIOUS bar to avoid lookahead)
        fib_start = max(0, idx - CONFIG['fib_lookback'] * 2)
        hist_slice = df.iloc[fib_start:idx].copy()  # Up to but NOT including current bar
        
        if len(hist_slice) < CONFIG['fib_lookback']:
            continue
        
        # CRITICAL FIX: Reset indices for clean calculation
        hist_slice = hist_slice.reset_index(drop=True)
        
        # Identify swing points and setups
        swing_points = identify_swing_points(hist_slice, lookback=8)
        if not swing_points:
            continue
        
        # FIXED: Pass current bar index explicitly (last bar of hist_slice)
        fib_setups = find_fibonacci_setups(
            hist_slice, 
            swing_points,
            current_bar_index=len(hist_slice) - 1
        )
        if not fib_setups:
            continue
        
        # Determine trend (using trend timeframes)
        trend = determine_trend(
            trend_slices[CONFIG['trend_timeframes'][0]],
            trend_slices[CONFIG['trend_timeframes'][1]] if len(CONFIG['trend_timeframes']) > 1 else trend_slices[CONFIG['trend_timeframes'][0]],
            trend_slices[CONFIG['trend_timeframes'][2]] if len(CONFIG['trend_timeframes']) > 2 else trend_slices[CONFIG['trend_timeframes'][0]]
        )
        trend_counts[trend] += 1
        
        # Log trend changes (only in automatic mode and when trend changes)
        if not CONFIG.get('use_manual_trend', False) and trend != last_logged_trend:
            logger.debug(f"Bar {idx}: Trend changed to {trend.upper()}")
            last_logged_trend = trend
        
        # Check for entry signal (using last index of hist_slice)
        entry_signal = check_fibonacci_entry(
            fib_setups, 
            hist_slice, 
            len(hist_slice) - 1,  # Last bar of historical slice
            trend
        )
        
        if entry_signal:
            # Check ADX filter (using ADX timeframes with manual control support)
            adx_passed = check_adx_filter_backtest(adx_slices, trend)
            
            if not adx_passed and CONFIG.get('use_adx_filter', False):
                adx_filtered_signals += 1
                logger.debug(f"Signal filtered by ADX at bar {idx}")
                continue
            
            # Check Macro Filter
            macro_passed = True
            if CONFIG.get('use_fundamental_analysis', False) or CONFIG.get('use_sentiment_analysis', False):
                # We mock the macro structure since we can't reliably backtest historical news
                # But we simulate the logic flow
                mock_macro = {'overall_direction': trend, 'confidence': 80}
                
                # Check alignment
                aligned = (mock_macro['overall_direction'] == trend)
                if not aligned and CONFIG.get('skip_trades_against_macro', False):
                    macro_passed = False
                    macro_filtered_signals += 1
                    logger.debug(f"Signal filtered by MACRO at bar {idx}")
            
            if not macro_passed:
                continue
            
            # Store for entry on NEXT bar
            pending_entry = {
                'type': entry_signal['type'],
                'fib_level': entry_signal['fib_level'],
                'fib_price': entry_signal['fib_price'],
                'setup_type': entry_signal['setup']['type'],
                'adx_passed': adx_passed
            }
            logger.debug(f"Signal detected at bar {idx}, will enter on next bar (ADX: {'PASS' if adx_passed else 'INFO'})")
    
    # Close any remaining positions at end
    if len(df) > 0:
        final_price = df.iloc[-1]['close']
        final_time = df.iloc[-1]['time']
        
        for pos in open_positions:
            if pos['side'] == 'long':
                pl = (final_price - pos['entry']) * pos['units']
            else:
                pl = (pos['entry'] - final_price) * pos['units']
            
            balance += pl
            trades.append({
                'entry_time': pos['entry_time'],
                'exit_time': final_time,
                'side': pos['side'],
                'entry': pos['entry'],
                'exit': final_price,
                'pl': pl,
                'exit_reason': 'backtest_end',
                'fib_level': pos.get('fib_level', 0),
                'setup_type': pos.get('setup_type', 'unknown'),
                'trend_mode': pos.get('trend_mode', 'auto'),
                'adx_passed': pos.get('adx_passed', False),
                'stop_method': pos.get('stop_method', 'Fibonacci')
            })
    
    # Generate statistics
    trades_df = pd.DataFrame(trades)
    
    total_trades = len(trades_df)
    if total_trades > 0:
        wins = len(trades_df[trades_df['pl'] > 0])
        losses = len(trades_df[trades_df['pl'] <= 0])
        win_rate = wins / total_trades * 100
        
        total_profit = trades_df['pl'].sum()
        avg_win = trades_df[trades_df['pl'] > 0]['pl'].mean() if wins > 0 else 0
        avg_loss = trades_df[trades_df['pl'] <= 0]['pl'].mean() if losses > 0 else 0
        
        profit_factor = abs(trades_df[trades_df['pl'] > 0]['pl'].sum() / 
                           trades_df[trades_df['pl'] <= 0]['pl'].sum()) if losses > 0 else float('inf')
        
        fib_618_trades = len(trades_df[trades_df['fib_level'] == 0.618])
        fib_705_trades = len(trades_df[trades_df['fib_level'] == 0.705])
        fib_786_trades = len(trades_df[trades_df['fib_level'] == 0.786])
        
        trailing_stops = len(trades_df[trades_df['exit_reason'] == 'trailing_stop'])
        take_profits = len(trades_df[trades_df['exit_reason'] == 'take_profit'])
        stop_losses = len(trades_df[trades_df['exit_reason'] == 'stop_loss'])
        
        # Calculate equity curve for drawdown
        trades_df['cumulative_pl'] = trades_df['pl'].cumsum()
        equity_curve = CONFIG['capital'] + trades_df['cumulative_pl']
        max_dd = calculate_max_drawdown(equity_curve)
        
        winning_trades = trades_df[trades_df['pl'] > 0]
        if not winning_trades.empty and avg_loss != 0:
            avg_rr = winning_trades['pl'].mean() / abs(avg_loss)
        else:
            avg_rr = 0
        
        # Count manual vs auto trades
        manual_trades = len(trades_df[trades_df.get('trend_mode', 'auto') == 'manual'])
        auto_trades = len(trades_df[trades_df.get('trend_mode', 'auto') == 'auto'])
        
        # Count ADX passed vs info trades
        adx_passed_trades = len(trades_df[trades_df.get('adx_passed', False) == True])
        adx_info_trades = len(trades_df[trades_df.get('adx_passed', False) == False])
        
        # Count ATR vs Fibonacci stops
        atr_stopped_trades = len(trades_df[trades_df.get('stop_method', 'Fibonacci') == 'ATR'])
        fib_stopped_trades = len(trades_df[trades_df.get('stop_method', 'Fibonacci') == 'Fibonacci'])
    
    else:
        wins = losses = 0
        win_rate = avg_win = avg_loss = profit_factor = total_profit = max_dd = avg_rr = 0
        fib_618_trades = fib_705_trades = fib_786_trades = 0
        trailing_stops = take_profits = stop_losses = 0
        manual_trades = auto_trades = 0
        adx_passed_trades = adx_info_trades = 0
        atr_stopped_trades = fib_stopped_trades = 0
    
    summary = {
        'starting_balance': CONFIG['capital'],
        'ending_balance': balance,
        'total_profit': total_profit,
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'avg_risk_reward': avg_rr,
        'max_drawdown': max_dd,
        'return_pct': (balance - CONFIG['capital']) / CONFIG['capital'] * 100,
        'fib_618_trades': fib_618_trades,
        'fib_705_trades': fib_705_trades,
        'fib_786_trades': fib_786_trades,
        'trailing_stops': trailing_stops,
        'take_profits': take_profits,
        'stop_losses': stop_losses,
        'trend_bullish_bars': trend_counts['bullish'],
        'trend_bearish_bars': trend_counts['bearish'],
        'trend_neutral_bars': trend_counts['neutral'],
        'trend_mode': 'manual' if CONFIG.get('use_manual_trend', False) else 'automatic',
        'trend_timeframes': CONFIG['trend_timeframes'],
        'manual_trend_trades': manual_trades,
        'auto_trend_trades': auto_trades,
        'adx_filter_enabled': CONFIG.get('use_adx_filter', False),
        'adx_timeframes': CONFIG['adx_timeframes'],
        'adx_manual_control': CONFIG.get('adx_manual_control', False),
        'adx_manual_control_strict': CONFIG.get('adx_manual_control_strict', False),
        'adx_signals_filtered': adx_filtered_signals,
        'adx_passed_trades': adx_passed_trades,
        'adx_info_trades': adx_info_trades,
        'atr_stops_enabled': CONFIG.get('use_atr_stops', False),
        'atr_multiplier': CONFIG.get('atr_stop_multiplier', 2.0),
        'atr_stop_method': CONFIG.get('atr_stop_method', 'wider'),
        'atr_stopped_trades': atr_stopped_trades,
        'fib_stopped_trades': fib_stopped_trades
    }
    
    # Print results
    print('\n' + '='*70)
    print('ICT FIBONACCI BACKTEST RESULTS')
    print('='*70)
    
    # Print trend mode info first
    if CONFIG.get('use_manual_trend', False):
        print(f'Trend Mode: MANUAL ({CONFIG["manual_trend"].upper()})')
    else:
        print(f'Trend Mode: AUTOMATIC (Point-Based System)')
    print(f'Trend Timeframes: {", ".join(CONFIG["trend_timeframes"])}')
    
    # Print ADX filter info
    if CONFIG.get('use_adx_filter', False):
        print(f'ADX Filter: ENABLED')
        print(f'ADX Timeframes: {", ".join(CONFIG["adx_timeframes"])}')
        print(f'ADX Threshold: {CONFIG["adx_strength_threshold"]}')
        
        # Print ADX manual control info
        if CONFIG.get('adx_manual_control', False):
            mode = "STRICT (primary TF)" if CONFIG.get('adx_manual_control_strict', False) else "LOOSE (any TF)"
            print(f'ADX Manual Control: ENABLED - {mode}')
        else:
            print(f'ADX Manual Control: DISABLED')
        
        print(f'Signals Filtered by ADX: {adx_filtered_signals}')
    else:
        print(f'ADX Filter: DISABLED')
    
    # Print ATR stops info
    if CONFIG.get('use_atr_stops', False):
        print(f'ATR Stops: ENABLED (Multiplier: {CONFIG["atr_stop_multiplier"]}x, Method: {CONFIG["atr_stop_method"].upper()})')
    else:
        print(f'ATR Stops: DISABLED')
    
    print('='*70)
    print(f'Starting Balance: ${CONFIG["capital"]:.2f}')
    print(f'Ending Balance: ${balance:.2f}')
    print(f'Total Profit: ${total_profit:.2f}')
    print(f'Return: {(balance - CONFIG["capital"]) / CONFIG["capital"] * 100:.2f}%')
    print('='*70)
    print(f'Total Trades: {total_trades}')
    print(f'Wins: {wins} | Losses: {losses} | Win Rate: {win_rate:.2f}%')
    print(f'Avg Win: ${avg_win:.2f} | Avg Loss: ${avg_loss:.2f}')
    print(f'Profit Factor: {profit_factor:.2f}')
    print(f'Avg Risk/Reward: {avg_rr:.2f}')
    print(f'Max Drawdown: {max_dd:.2f}%')
    
    if CONFIG.get('use_adx_filter', False):
        print('='*70)
        print(f'ADX Passed Trades: {adx_passed_trades}')
        print(f'ADX Info Trades: {adx_info_trades}')
    
    if CONFIG.get('use_atr_stops', False):
        print('='*70)
        print(f'Trades Using ATR Stops: {atr_stopped_trades}')
        print(f'Trades Using Fibonacci Stops: {fib_stopped_trades}')
    
    print('='*70)
    
    return trades_df, summary