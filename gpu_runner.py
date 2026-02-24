import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import torch

from config import CONFIG
from mt5_handler import fetch_mt5_df
from indicators import compute_indicators
from fibonacci import identify_swing_points, find_fibonacci_setups, check_fibonacci_entry
from trend_analysis import determine_trend
from risk_management import DailyLossTracker, compare_stop_loss_methods
from backtest import calculate_max_drawdown, MT5_TIMEFRAMES, check_adx_filter_backtest

logger = logging.getLogger(__name__)

from gpu_engine import evaluate_exits_gpu

def backtest_gpu_runner(symbol, start, end, timeframe):
    """
    GPU Accelerated Backtest Runner using PyTorch.
    Separates Entry identification from Exit tracking for massive vectorization speedup.
    """
    logger.info("======================================================================")
    if CONFIG.get('use_adx_filter', False):
        logger.info("✓ ADX FILTER ENABLED")
        logger.info(f"  Timeframes: {', '.join(CONFIG['adx_timeframes'])}")
        logger.info(f"  Period: {CONFIG['adx_period']}")
        logger.info(f"  Strength Threshold: {CONFIG.get('adx_strength_threshold', 25.0)}")
        if CONFIG.get('adx_manual_control', False):
            mode = "STRICT (primary TF)" if CONFIG.get('adx_manual_control_strict', False) else "LOOSE (any TF)"
            logger.info(f"  Manual Control: ENABLED ({mode})")
    else:
        logger.info("ADX Filter: DISABLED")
        
    if CONFIG.get('use_atr_stops', False):
        logger.info(f"ATR Stops: ENABLED (Multiplier: {CONFIG['atr_stop_multiplier']}x, Method: {CONFIG['atr_stop_method']})")
    else:
        logger.info("ATR Stops: DISABLED (using Fibonacci stops)")
        
    tf = MT5_TIMEFRAMES.get(timeframe)
    if tf is None:
        raise ValueError(f'Unsupported timeframe: {timeframe}')
        
    utc_from = datetime.fromisoformat(start)
    utc_to = datetime.fromisoformat(end)
    extended_from = utc_from - timedelta(days=30)
    
    # Fetch data
    try:
        logger.info("Fetching historical data...")
        df = fetch_mt5_df(symbol, tf, extended_from, utc_to, min_bars_expected=CONFIG['min_bars_required'])
        
        trend_dataframes = {}
        for tf_name in CONFIG['trend_timeframes']:
            min_bars = 5 if tf_name == 'D1' else 10 
            trend_dataframes[tf_name] = fetch_mt5_df(
                symbol, MT5_TIMEFRAMES[tf_name], extended_from, utc_to, min_bars_expected=min_bars
            )
            
        adx_dataframes = {}
        for tf_name in CONFIG['adx_timeframes']:
            adx_dataframes[tf_name] = fetch_mt5_df(
                symbol, MT5_TIMEFRAMES[tf_name], extended_from, utc_to, min_bars_expected=10
            )
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        raise
        
    # Compute indicators
    logger.info("Computing technical indicators (including ADX and ATR)...")
    df = compute_indicators(df)
    for tf_name in trend_dataframes:
        trend_dataframes[tf_name] = compute_indicators(trend_dataframes[tf_name])
    for tf_name in adx_dataframes:
        adx_dataframes[tf_name] = compute_indicators(adx_dataframes[tf_name])
        
    df = df[df['time'] >= utc_from].reset_index(drop=True)
    if df.empty:
        raise RuntimeError(f"No data available for backtest period")
        
    trend_counts = {'bullish': 0, 'bearish': 0, 'neutral': 0}
    adx_filtered_signals = 0
    macro_filtered_signals = 0
    last_logged_trend = None
    
    logger.info(f"Extracting potential trades from {len(df)} bars natively...")
    
    potential_trades = []
    pending_entry = None
    
    # Extract Trend and ADX Slices globally to save time in loop
    df_times = df['time'].values
    
    # Pre-extract numpy arrays for fast binary search
    trend_times = { tf: trend_dataframes[tf]['time'].values for tf in CONFIG['trend_timeframes'] }
    adx_times = { tf: adx_dataframes[tf]['time'].values for tf in CONFIG['adx_timeframes'] }
    
    logger.info("Pre-calculating all swing points globally (O(N))...")
    global_swing_points = identify_swing_points(df, lookback=8)
    
    for idx in range(len(df)):
        if idx % 1000 == 0:
            logger.info(f"Extracting progress: {idx}/{len(df)} bars...")
            
        current_bar = df.iloc[idx]
        current_time = current_bar['time']
        
        # We find setups up to the current bar
        if pending_entry is not None:
            entry_price = current_bar['open']
            signal_type = pending_entry['type']
            fib_level = pending_entry['fib_level']
            fib_price = pending_entry['fib_price']
            setup_type = pending_entry['setup_type']
            trend_mode = 'manual' if CONFIG.get('use_manual_trend', False) else 'auto'
            adx_passed = pending_entry.get('adx_passed', False)
            
            if signal_type == 'long':
                fib_stop = fib_price - (CONFIG['fib_tolerance'] * 3)
                if CONFIG.get('use_atr_stops', False):
                    stop_comparison = compare_stop_loss_methods(
                        df.iloc[max(0, idx-200):idx+1].reset_index(drop=True),
                        entry_price, 'long', fib_stop
                    )
                    stop_price = stop_comparison['stop_price']
                    stop_method = stop_comparison['selected_method']
                else:
                    stop_price, stop_method = fib_stop, 'Fibonacci'
                    
                risk_per_unit = entry_price - stop_price
                if risk_per_unit > 0:
                    tp_price = entry_price + (CONFIG['min_rr_ratio'] * risk_per_unit)
                    # We store ratio to balance dynamically later
                    potential_trades.append({
                        'entry_idx': idx, 'side': 1, 'entry': entry_price, 'stop': stop_price, 'tp': tp_price,
                        'risk_per_unit': risk_per_unit, 'fib_level': fib_level, 'setup_type': setup_type,
                        'trend_mode': trend_mode, 'adx_passed': adx_passed, 'stop_method': stop_method,
                        'entry_time': current_time
                    })
            else:
                fib_stop = fib_price + (CONFIG['fib_tolerance'] * 3)
                if CONFIG.get('use_atr_stops', False):
                    stop_comparison = compare_stop_loss_methods(
                        df.iloc[max(0, idx-200):idx+1].reset_index(drop=True),
                        entry_price, 'short', fib_stop
                    )
                    stop_price = stop_comparison['stop_price']
                    stop_method = stop_comparison['selected_method']
                else:
                    stop_price, stop_method = fib_stop, 'Fibonacci'
                    
                risk_per_unit = stop_price - entry_price
                if risk_per_unit > 0:
                    tp_price = entry_price - (CONFIG['min_rr_ratio'] * risk_per_unit)
                    potential_trades.append({
                        'entry_idx': idx, 'side': -1, 'entry': entry_price, 'stop': stop_price, 'tp': tp_price,
                        'risk_per_unit': risk_per_unit, 'fib_level': fib_level, 'setup_type': setup_type,
                        'trend_mode': trend_mode, 'adx_passed': adx_passed, 'stop_method': stop_method,
                        'entry_time': current_time
                    })
            pending_entry = None
            
        if idx < CONFIG['fib_lookback']:
            continue
            
        fib_start = max(0, idx - CONFIG['fib_lookback'] * 2)
        
        # Filter global swing points for this window to prevent lookahead bias
        # A swing point is only 'confirmed' lookback(8) bars AFTER it occurs.
        valid_sp = [
            sp for sp in global_swing_points 
            if fib_start <= sp['index'] < idx and sp['index'] <= idx - 8
        ]
        
        if not valid_sp:
            continue
            
        fib_setups = find_fibonacci_setups(df, valid_sp, current_bar_index=idx)
        if not fib_setups:
            continue
            
        # extract trend and adx quickly using binary search instead of boolean masking
        ts = {}
        valid_ts = True
        current_time_np = np.datetime64(current_time)
        for tf in CONFIG['trend_timeframes']:
            idx_match = np.searchsorted(trend_times[tf], current_time_np, side='right')
            if idx_match == 0:
                valid_ts = False
                break
            # Only pass the exact last completed bar
            ts[tf] = trend_dataframes[tf].iloc[idx_match - 1:idx_match]
        if not valid_ts: continue
        
        adxs = {}
        valid_adx = True
        for tf in CONFIG['adx_timeframes']:
            idx_match = np.searchsorted(adx_times[tf], current_time_np, side='right')
            if idx_match == 0:
                valid_adx = False
                break
            # Only pass the exact last completed bar
            adxs[tf] = adx_dataframes[tf].iloc[idx_match - 1:idx_match]
        if not valid_adx: continue
            
        trend = determine_trend(ts[CONFIG['trend_timeframes'][0]], ts[CONFIG['trend_timeframes'][1]] if len(CONFIG['trend_timeframes']) > 1 else ts[CONFIG['trend_timeframes'][0]], ts[CONFIG['trend_timeframes'][2]] if len(CONFIG['trend_timeframes']) > 2 else ts[CONFIG['trend_timeframes'][0]])
        trend_counts[trend] += 1
        
        entry_signal = check_fibonacci_entry(fib_setups, df, idx, trend)
        if entry_signal:
            adx_passed = check_adx_filter_backtest(adxs, trend)
            if not adx_passed and CONFIG.get('use_adx_filter', False):
                adx_filtered_signals += 1
                continue
                
            macro_passed = True
            if CONFIG.get('use_fundamental_analysis', False) or CONFIG.get('use_sentiment_analysis', False):
                mock_macro = {'overall_direction': trend, 'confidence': 80}
                if mock_macro['overall_direction'] != trend and CONFIG.get('skip_trades_against_macro', False):
                    macro_passed = False
                    macro_filtered_signals += 1
            if not macro_passed: continue
            
            pending_entry = {
                'type': entry_signal['type'],
                'fib_level': entry_signal['fib_level'],
                'fib_price': entry_signal['fib_price'],
                'setup_type': entry_signal['setup']['type'],
                'adx_passed': adx_passed
            }

    if not potential_trades:
        logger.info("No valid setups found.")
        return pd.DataFrame(), None
        
    logger.info(f"Extracted {len(potential_trades)} potential entries. Sending to PyTorch GPU block...")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Executing Vectorized Batch on Device: {device}")
    
    h_t = torch.tensor(df['high'].values, dtype=torch.float32, device=device)
    l_t = torch.tensor(df['low'].values, dtype=torch.float32, device=device)
    c_t = torch.tensor(df['close'].values, dtype=torch.float32, device=device)
    
    p_entry_idx = [t['entry_idx'] for t in potential_trades]
    p_sides = torch.tensor([t['side'] for t in potential_trades], dtype=torch.float32, device=device)
    p_entry_prices = torch.tensor([t['entry'] for t in potential_trades], dtype=torch.float32, device=device)
    p_tps = torch.tensor([t['tp'] for t in potential_trades], dtype=torch.float32, device=device)
    p_sls = torch.tensor([t['stop'] for t in potential_trades], dtype=torch.float32, device=device)
    p_units = torch.ones_like(p_sides) # Placeholder for units, calculated later based on equity
    
    raw_exits = evaluate_exits_gpu(h_t, l_t, c_t, p_entry_idx, p_entry_prices, p_sides, p_tps, p_sls, p_units)
    
    # Merge GPU exits with trade metadata
    for i, t in enumerate(potential_trades):
        ex = raw_exits[i]
        t['exit_idx'] = ex['exit_idx']
        t['exit_price'] = ex['exit_price']
        t['exit_reason'] = ex['exit_reason']
        t['raw_pl'] = ex['pl'] # Unadjusted for dynamic sizing
    
    logger.info("GPU Evaluation Complete. Applying sequentially dependent portfolio logic (Risk, Drawdown)...")
    
    balance = CONFIG['capital']
    trades = []
    active_positions = []
    backtest_loss_tracker = DailyLossTracker()
    
    for t in potential_trades:
        entry_time = t['entry_time']
        backtest_loss_tracker._check_and_reset_if_needed(entry_time)
        
        # Clear closed trades from active limit (using exit idx)
        active_positions = [ap for ap in active_positions if ap['exit_idx'] >= t['entry_idx']]
        
        # Check Daily Loss Limit
        can_trade, reason = backtest_loss_tracker.can_trade(symbol, entry_time)
        if not can_trade:
            continue
            
        # Check Max Concurrent Trades
        if len(active_positions) >= CONFIG['max_concurrent_trades']:
            continue
            
        # We take the trade in sequence, calculate precise units based on dynamic balance
        risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
        units = risk_amount / t['risk_per_unit']
        
        actual_pl = t['raw_pl'] * units
        balance += actual_pl
        
        if actual_pl < 0:
            backtest_loss_tracker.record_loss(symbol, abs(actual_pl))
            
        active_positions.append(t)
        
        trades.append({
            'entry_time': entry_time,
            'exit_time': df.iloc[t['exit_idx']]['time'],
            'side': 'long' if t['side'] == 1 else 'short',
            'entry': t['entry'],
            'exit': t['exit_price'],
            'pl': actual_pl,
            'exit_reason': t['exit_reason'],
            'fib_level': t['fib_level'],
            'setup_type': t['setup_type'],
            'trend_mode': t['trend_mode'],
            'adx_passed': t['adx_passed'],
            'stop_method': t['stop_method']
        })
        
    trades_df = pd.DataFrame(trades)
    
    # Generate statistics (same as before)
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
        
        trades_df['cumulative_pl'] = trades_df['pl'].cumsum()
        equity_curve = CONFIG['capital'] + trades_df['cumulative_pl']
        max_dd = calculate_max_drawdown(equity_curve)
        
        winning_trades = trades_df[trades_df['pl'] > 0]
        if not winning_trades.empty and avg_loss != 0:
            avg_rr = winning_trades['pl'].mean() / abs(avg_loss)
        else:
            avg_rr = 0
            
        manual_trades = len(trades_df[trades_df.get('trend_mode', 'auto') == 'manual'])
        auto_trades = len(trades_df[trades_df.get('trend_mode', 'auto') == 'auto'])
        adx_passed_trades = len(trades_df[trades_df.get('adx_passed', False) == True])
        adx_info_trades = len(trades_df[trades_df.get('adx_passed', False) == False])
        atr_stopped_trades = len(trades_df[trades_df.get('stop_method', 'Fibonacci') == 'ATR'])
        fib_stopped_trades = len(trades_df[trades_df.get('stop_method', 'Fibonacci') == 'Fibonacci'])
    else:
        wins = losses = win_rate = avg_win = avg_loss = profit_factor = total_profit = max_dd = avg_rr = 0
        fib_618_trades = fib_705_trades = fib_786_trades = 0
        trailing_stops = take_profits = stop_losses = 0
        manual_trades = auto_trades = adx_passed_trades = adx_info_trades = atr_stopped_trades = fib_stopped_trades = 0

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
        'max_drawdown': max_dd,
        'avg_rr_ratio': avg_rr,
        'fib_levels': {
            '0.618': fib_618_trades,
            '0.705': fib_705_trades,
            '0.786': fib_786_trades
        },
        'exit_reasons': {
            'take_profit': take_profits,
            'stop_loss': stop_losses,
            'trailing_stop': trailing_stops
        },
        'trend_system': {
            'manual': manual_trades,
            'automatic': auto_trades
        },
        'adx_filter': {
            'filtered': adx_filtered_signals,
            'passed': adx_passed_trades,
            'info_only': adx_info_trades
        },
        'macro_filter': {
            'filtered': macro_filtered_signals
        },
        'stop_methods': {
            'atr': atr_stopped_trades,
            'fibonacci': fib_stopped_trades
        }
    }
    
    logger.info("\n--- BACKTEST SUMMARY (GPU) ---")
    logger.info(f"Total Trades: {total_trades}")
    logger.info(f"Win Rate: {win_rate:.2f}% ({wins}W / {losses}L)")
    logger.info(f"Starting Balance: ${CONFIG['capital']:.2f}")
    logger.info(f"Ending Balance: ${balance:.2f} (Profit: ${total_profit:.2f})")
    logger.info(f"Profit Factor: {profit_factor:.2f}")
    logger.info(f"Max Drawdown: {max_dd:.2f}%")
    logger.info(f"Avg R:R Ratio: {avg_rr:.2f}")
    logger.info("------------------------------")
    logger.info(f"Filters Active:")
    logger.info(f"- ADX Filtered {adx_filtered_signals} weak trend signals")
    logger.info(f"- Macro Filtered {macro_filtered_signals} counter-trend signals")
    logger.info("------------------------------")
    
    return trades_df, summary
