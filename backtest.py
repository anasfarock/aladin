"""
Backtesting Module
Historical simulation with detailed performance metrics
"""

from datetime import datetime, timedelta
import pandas as pd
import logging
from config import CONFIG, MT5_TIMEFRAMES, logger
from indicators import compute_indicators
from fibonacci import identify_swing_points, find_fibonacci_setups, check_fibonacci_entry
from trend_analysis import determine_trend
from risk_management import update_trailing_stop
from mt5_handler import fetch_mt5_df

# --------------------------- BACKTEST ----------------------------

def calculate_max_drawdown(equity_curve):
    """Calculate maximum drawdown from equity curve"""
    if len(equity_curve) == 0:
        return 0
    
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak * 100
    return abs(drawdown.min())

def backtest(symbol, start, end, timeframe):
    """
    Run ICT Fibonacci backtest
    
    Args:
        symbol: Trading symbol
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        timeframe: Entry timeframe
    
    Returns:
        tuple: (trades_df, summary_dict)
    """
    import os
    
    # Create results directory if it doesn't exist
    os.makedirs('results', exist_ok=True)
    
    logger.info(f"Starting ICT Fibonacci backtest: {symbol} from {start} to {end}")
    
    tf = MT5_TIMEFRAMES.get(timeframe)
    if tf is None:
        raise ValueError(f'Unsupported timeframe: {timeframe}')
    
    utc_from = datetime.fromisoformat(start)
    utc_to = datetime.fromisoformat(end)
    extended_from = utc_from - timedelta(days=90)
    
    # Fetch data
    try:
        logger.info("Fetching historical data...")
        df = fetch_mt5_df(symbol, tf, extended_from, utc_to, min_bars_expected=CONFIG['min_bars_required'])
        df_d1 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['D1'], extended_from, utc_to, min_bars_expected=10)
        df_h4 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['H4'], extended_from, utc_to, min_bars_expected=10)
        df_h1 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['H1'], extended_from, utc_to, min_bars_expected=10)
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        raise
    
    # Compute indicators
    logger.info("Computing technical indicators...")
    df = compute_indicators(df)
    df_d1 = compute_indicators(df_d1)
    df_h4 = compute_indicators(df_h4)
    df_h1 = compute_indicators(df_h1)
    
    # Filter to backtest period
    df = df[df['time'] >= utc_from].reset_index(drop=True)
    
    if df.empty:
        raise RuntimeError(f"No data available for backtest period")
    
    # Initialize backtest variables
    balance = CONFIG['capital']
    trades = []
    open_positions = []
    current_fib_setups = []
    
    logger.info(f"Running backtest on {len(df)} bars...")
    
    # Main backtest loop
    for idx, current_bar in df.iterrows():
        current_time = current_bar['time']
        
        # Get timeframe slices up to current time
        d1_slice = df_d1[df_d1['time'] <= current_time]
        h4_slice = df_h4[df_h4['time'] <= current_time]
        h1_slice = df_h1[df_h1['time'] <= current_time]
        
        if d1_slice.empty or h4_slice.empty or h1_slice.empty:
            continue
        
        # Check exits for open positions
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
                        'setup_type': pos.get('setup_type', 'unknown')
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
                        'setup_type': pos.get('setup_type', 'unknown')
                    })
                    open_positions.remove(pos)
                    continue
            
            elif pos['side'] == 'short':
                if current_bar['high'] >= pos['stop']:
                    exit_price = pos['stop']
                    pl = (pos['entry'] - exit_price) * pos['units']
                    balance += pl
                    
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
                        'setup_type': pos.get('setup_type', 'unknown')
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
                        'setup_type': pos.get('setup_type', 'unknown')
                    })
                    open_positions.remove(pos)
                    continue
        
        # Check for new entries
        if len(open_positions) >= CONFIG['max_concurrent_trades']:
            continue
        
        # Update Fibonacci setups periodically
        if idx % 5 == 0 or idx < 100:
            fib_start = max(0, idx - CONFIG['fib_lookback'] * 2)
            current_slice = df.iloc[fib_start:idx+1].copy()
            
            if len(current_slice) > CONFIG['fib_lookback']:
                swing_points = identify_swing_points(current_slice, lookback=8)
                fib_setups = find_fibonacci_setups(current_slice, swing_points)
                current_fib_setups = fib_setups
            else:
                current_fib_setups = []
        
        # Check for entry signals
        if current_fib_setups:
            trend = determine_trend(d1_slice, h4_slice, h1_slice)
            
            fib_start_idx = max(0, idx - CONFIG['fib_lookback'] * 2)
            
            entry_signal = check_fibonacci_entry(
                current_fib_setups, 
                df.iloc[fib_start_idx:idx+1], 
                idx - fib_start_idx, 
                trend
            )
            
            if entry_signal:
                entry_price = entry_signal['entry_price']
                signal_type = entry_signal['type']
                fib_level = entry_signal['fib_level']
                fib_price = entry_signal['fib_price']
                setup_type = entry_signal['setup']['type']
                
                # Calculate stops and targets
                if signal_type == 'long':
                    stop_price = fib_price - (CONFIG['fib_tolerance'] * 3)
                    risk_per_unit = entry_price - stop_price
                    
                    if risk_per_unit <= 0:
                        continue
                    
                    tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
                    tp_price = entry_price + tp_distance
                
                else:
                    stop_price = fib_price + (CONFIG['fib_tolerance'] * 3)
                    risk_per_unit = stop_price - entry_price
                    
                    if risk_per_unit <= 0:
                        continue
                    
                    tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
                    tp_price = entry_price - tp_distance
                
                # Calculate position size
                risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
                units = risk_amount / risk_per_unit
                
                # Create position
                position = {
                    'entry_time': current_time,
                    'side': signal_type,
                    'entry': entry_price,
                    'stop': stop_price,
                    'original_stop': stop_price,
                    'tp': tp_price,
                    'units': units,
                    'trailing_active': False,
                    'trail_level': None,
                    'fib_level': fib_level,
                    'setup_type': setup_type
                }
                
                open_positions.append(position)
                logger.debug(f"Opened {signal_type} at {entry_price:.5f} Fib {fib_level}")
    
    # Close any remaining positions at end
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
            'setup_type': pos.get('setup_type', 'unknown')
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
        
        max_dd = calculate_max_drawdown(trades_df['pl'].cumsum() + CONFIG['capital'])
        
        winning_trades = trades_df[trades_df['pl'] > 0]
        if not winning_trades.empty and avg_loss != 0:
            avg_rr = winning_trades['pl'].mean() / abs(avg_loss)
        else:
            avg_rr = 0
        
    else:
        wins = losses = 0
        win_rate = avg_win = avg_loss = profit_factor = total_profit = max_dd = avg_rr = 0
        fib_618_trades = fib_705_trades = fib_786_trades = 0
        trailing_stops = take_profits = stop_losses = 0
    
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
        'stop_losses': stop_losses
    }
    
    # Print results
    print('\n' + '='*60)
    print('ICT FIBONACCI BACKTEST RESULTS')
    print('='*60)
    for key, value in summary.items():
        if isinstance(value, float):
            if 'pct' in key or 'rate' in key:
                print(f'{key.replace("_", " ").title()}: {value:.2f}%')
            else:
                print(f'{key.replace("_", " ").title()}: {value:.2f}')
        else:
            print(f'{key.replace("_", " ").title()}: {value}')
    print('='*60)
    
    return trades_df, summary