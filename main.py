"""
Enhanced MT5 Trading Bot with ICT Fibonacci Strategy + Trend Analysis

Features:
- Trend Analysis: RSI, VWAP, Bollinger Bands, Moving Averages on multiple timeframes
- Entry Strategy: ICT Fibonacci Retracements (0.618, 0.705, 0.786 levels)
- Risk Management: Dynamic stop loss, take profit, and trailing stops
- Backtesting: Historical simulation with detailed performance metrics
- Live Trading: Real-time execution with MT5 integration
"""

import time
import math
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Optional import - used only if running live mode
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not available. Install with: pip install MetaTrader5")

# ----------------------------- CONFIG -----------------------------
CONFIG = {
    'symbol': 'USDCAD.raw',
    'backtest': False,
    'start': '2024-06-25',
    'end': '2025-06-30',
    'capital': 4950.0,
    'risk_pct': 0.5,
    'timeframe_entry': 'M15',
    'trend_timeframes': ['D1', 'H4', 'H1'],
    
    'boll_period': 20,
    'boll_std': 2,
    'rsi_period': 14,
    'vwap_period': 20,
    'ma_fast': 9,
    'ma_slow': 18,
    
    'use_rsi_for_trend': True,
    'use_vwap_for_trend': True,
    'use_bollinger_for_trend': True,
    'use_ma_for_trend': True,
    
    'fib_lookback': 30,
    'fib_levels': [0.618, 0.705, 0.786],
    'fib_tolerance': 0.0001,
    'min_swing_size': 0.0005,
    'max_fib_age': 100,
    'fib_confirmation_bars': 2,
    
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

# --------------------------- UTILITIES ----------------------------

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

# --------------------------- TECHNICAL INDICATORS ----------------------------

def sma(series, length):
    """Simple Moving Average"""
    return series.rolling(window=length, min_periods=1).mean()

def std(series, length):
    """Standard deviation"""
    return series.rolling(window=length, min_periods=1).std()

def rsi(series, length=14):
    """Relative Strength Index"""
    if len(series) < length:
        return pd.Series(index=series.index, dtype=float)
    
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=length-1, adjust=False).mean()
    ma_down = down.ewm(com=length-1, adjust=False).mean()
    
    ma_down = ma_down.replace(0, np.nan)
    rs = ma_up / ma_down
    rsi_values = 100 - (100 / (1 + rs))
    rsi_values = rsi_values.fillna(50)
    return rsi_values

def vwap(df, length=None):
    """Volume Weighted Average Price"""
    if 'tick_volume' not in df.columns:
        logger.warning("tick_volume not found, using equal weights")
        df['tick_volume'] = 1
    
    df['tick_volume'] = df['tick_volume'].replace(0, 1)
    tp = (df['high'] + df['low'] + df['close']) / 3
    pv = tp * df['tick_volume']
    
    if length is None:
        cum_pv = pv.cumsum()
        cum_v = df['tick_volume'].cumsum()
        return cum_pv / cum_v
    else:
        pv_roll = pv.rolling(window=length, min_periods=1).sum()
        v_roll = df['tick_volume'].rolling(window=length, min_periods=1).sum()
        v_roll = v_roll.replace(0, 1)
        return pv_roll / v_roll

def bollinger_bands(series, length=20, stddev=2):
    """Bollinger Bands"""
    basis = sma(series, length)
    sd = std(series, length)
    upper = basis + stddev * sd
    lower = basis - stddev * sd
    return basis, upper, lower

def compute_indicators(df):
    """Compute all technical indicators"""
    if df.empty or len(df) < CONFIG['min_bars_required']:
        logger.warning(f"Insufficient data for indicators: {len(df)} bars")
        return df
    
    df = df.copy()
    
    required_cols = ['open', 'high', 'low', 'close']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found")
    
    try:
        df['ma_fast'] = sma(df['close'], CONFIG['ma_fast'])
        df['ma_slow'] = sma(df['close'], CONFIG['ma_slow'])
        df['rsi'] = rsi(df['close'], CONFIG['rsi_period'])
        df['vwap'] = vwap(df, CONFIG['vwap_period'])
        df['bb_basis'], df['bb_upper'], df['bb_lower'] = bollinger_bands(
            df['close'], CONFIG['boll_period'], CONFIG['boll_std']
        )
    except Exception as e:
        logger.error(f"Error computing indicators: {e}")
        raise
    
    return df

# --------------------------- ICT FIBONACCI ----------------------------

def identify_swing_points(df, lookback=10):
    """Identify swing highs and lows"""
    if len(df) < lookback * 2 + 1:
        return []
    
    swing_points = []
    
    for i in range(lookback, len(df) - lookback):
        current_high = df.iloc[i]['high']
        current_low = df.iloc[i]['low']
        
        is_swing_high = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and df.iloc[j]['high'] > current_high:
                is_swing_high = False
                break
        
        if is_swing_high:
            swing_points.append({
                'index': i,
                'time': df.iloc[i]['time'],
                'price': current_high,
                'type': 'high'
            })
        
        is_swing_low = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and df.iloc[j]['low'] < current_low:
                is_swing_low = False
                break
        
        if is_swing_low:
            swing_points.append({
                'index': i,
                'time': df.iloc[i]['time'],
                'price': current_low,
                'type': 'low'
            })
    
    return swing_points

def calculate_fibonacci_levels(high_price, low_price, direction='bullish'):
    """Calculate Fibonacci retracement levels"""
    price_range = high_price - low_price
    
    if abs(price_range) < CONFIG['min_swing_size']:
        return None
    
    fib_levels = {}
    
    if direction == 'bullish':
        for level in CONFIG['fib_levels']:
            fib_levels[level] = high_price - (price_range * level)
    else:
        for level in CONFIG['fib_levels']:
            fib_levels[level] = low_price + (price_range * level)
    
    return fib_levels

def find_fibonacci_setups(df, swing_points):
    """Find valid Fibonacci setups"""
    if len(swing_points) < 2:
        return []
    
    fib_setups = []
    current_index = len(df) - 1
    swing_points = sorted(swing_points, key=lambda x: x['index'])
    
    for i in range(len(swing_points) - 1):
        for j in range(i + 1, len(swing_points)):
            point1 = swing_points[i]
            point2 = swing_points[j]
            
            if current_index - point2['index'] > CONFIG['max_fib_age']:
                continue
            
            if point1['type'] == 'low' and point2['type'] == 'high':
                high_price = point2['price']
                low_price = point1['price']
                fib_levels = calculate_fibonacci_levels(high_price, low_price, 'bullish')
                
                if fib_levels:
                    fib_setups.append({
                        'type': 'bullish_retracement',
                        'swing_low': point1,
                        'swing_high': point2,
                        'fib_levels': fib_levels,
                        'age': current_index - point2['index'],
                        'valid': True,
                        'tested_levels': set()
                    })
            
            elif point1['type'] == 'high' and point2['type'] == 'low':
                high_price = point1['price']
                low_price = point2['price']
                fib_levels = calculate_fibonacci_levels(high_price, low_price, 'bearish')
                
                if fib_levels:
                    fib_setups.append({
                        'type': 'bearish_retracement',
                        'swing_high': point1,
                        'swing_low': point2,
                        'fib_levels': fib_levels,
                        'age': current_index - point2['index'],
                        'valid': True,
                        'tested_levels': set()
                    })
    
    return fib_setups

def check_fibonacci_reaction(df, fib_setup, current_index):
    """Check if price is reacting at Fibonacci levels"""
    if current_index < CONFIG['fib_confirmation_bars']:
        return None
    
    recent_bars = df.iloc[max(0, current_index - CONFIG['fib_confirmation_bars']):current_index + 1]
    current_bar = df.iloc[current_index]
    
    fib_levels = fib_setup['fib_levels']
    setup_type = fib_setup['type']
    
    for level_value, fib_price in fib_levels.items():
        if level_value in fib_setup['tested_levels']:
            continue
        
        price_touched = False
        for _, bar in recent_bars.iterrows():
            if abs(bar['low'] - fib_price) <= CONFIG['fib_tolerance'] or \
               abs(bar['high'] - fib_price) <= CONFIG['fib_tolerance'] or \
               (bar['low'] <= fib_price <= bar['high']):
                price_touched = True
                break
        
        if not price_touched:
            continue
        
        fib_setup['tested_levels'].add(level_value)
        
        if setup_type == 'bullish_retracement':
            if (current_bar['close'] > fib_price and 
                any(bar['low'] <= fib_price + CONFIG['fib_tolerance'] for _, bar in recent_bars.iterrows())):
                
                return {
                    'type': 'long',
                    'fib_level': level_value,
                    'fib_price': fib_price,
                    'entry_price': current_bar['close'],
                    'setup': fib_setup
                }
        
        elif setup_type == 'bearish_retracement':
            if (current_bar['close'] < fib_price and 
                any(bar['high'] >= fib_price - CONFIG['fib_tolerance'] for _, bar in recent_bars.iterrows())):
                
                return {
                    'type': 'short',
                    'fib_level': level_value,
                    'fib_price': fib_price,
                    'entry_price': current_bar['close'],
                    'setup': fib_setup
                }
    
    return None

# --------------------------- TREND ANALYSIS ----------------------------

def determine_trend(df_d1, df_h4, df_h1):
    """Determine overall trend"""
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
        
        if CONFIG['use_ma_for_trend'] and not (pd.isna(last['ma_fast']) or pd.isna(last['ma_slow'])):
            ma_vote = 1 if last['ma_fast'] > last['ma_slow'] else -1
            tf_votes += ma_vote
        
        if CONFIG['use_rsi_for_trend'] and not pd.isna(last['rsi']):
            if last['rsi'] > 60:
                rsi_vote = 1
            elif last['rsi'] < 40:
                rsi_vote = -1
            else:
                rsi_vote = 0
            tf_votes += rsi_vote
        
        if CONFIG['use_vwap_for_trend'] and not pd.isna(last['vwap']):
            vwap_vote = 1 if last['close'] > last['vwap'] else -1
            tf_votes += vwap_vote
        
        if (CONFIG['use_bollinger_for_trend'] and 
            not (pd.isna(last['bb_upper']) or pd.isna(last['bb_lower']) or pd.isna(last['bb_basis']))):
            if last['close'] > last['bb_basis']:
                bb_vote = 1
            elif last['close'] < last['bb_basis']:
                bb_vote = -1
            else:
                bb_vote = 0
            tf_votes += bb_vote
        
        weighted_votes = tf_votes * weight
        total_votes += weighted_votes
    
    threshold = max(2, total_indicators_enabled)
    
    if total_votes > threshold:
        return 'bullish'
    elif total_votes < -threshold:
        return 'bearish'
    else:
        return 'neutral'

def check_fibonacci_entry(fib_setups, df, current_index, trend):
    """Check for Fibonacci entry signals"""
    if not fib_setups:
        return None
    
    for setup in fib_setups:
        if not setup['valid']:
            continue
        
        fib_reaction = check_fibonacci_reaction(df, setup, current_index)
        
        if fib_reaction is None:
            continue
        
        signal_type = fib_reaction['type']
        
        if trend == 'bullish' and signal_type != 'long':
            continue
        elif trend == 'bearish' and signal_type != 'short':
            continue
        
        return fib_reaction
    
    return None

# --------------------------- TRAILING STOPS ----------------------------

def update_trailing_stop(position, current_price):
    """Update trailing stop loss"""
    if not CONFIG['trailing_stop']:
        return position
    
    entry_price = position['entry']
    original_stop = position['original_stop']
    current_stop = position['stop']
    side = position['side']
    
    if side == 'long':
        initial_risk = entry_price - original_stop
        current_profit = current_price - entry_price
    else:
        initial_risk = original_stop - entry_price
        current_profit = entry_price - current_price
    
    if initial_risk <= 0 or current_profit <= 0:
        return position
    
    profit_ratio = current_profit / initial_risk
    
    applicable_level = None
    trail_to_ratio = None
    
    for level, trail_ratio in sorted(CONFIG['trailing_levels'].items(), reverse=True):
        if profit_ratio >= level:
            applicable_level = level
            trail_to_ratio = trail_ratio
            break
    
    if applicable_level is None:
        return position
    
    if side == 'long':
        new_stop = entry_price + (trail_to_ratio * initial_risk)
        if new_stop > current_stop:
            position['stop'] = new_stop
            position['trailing_active'] = True
            position['trail_level'] = applicable_level
    else:
        new_stop = entry_price - (trail_to_ratio * initial_risk)
        if new_stop < current_stop:
            position['stop'] = new_stop
            position['trailing_active'] = True
            position['trail_level'] = applicable_level
    
    return position

# --------------------------- DATA FETCHING ----------------------------

def ensure_mt5_initialized():
    """Initialize MT5 connection"""
    if not MT5_AVAILABLE:
        raise RuntimeError('MetaTrader5 package not available')
    
    if not mt5.initialize():
        err = mt5.last_error()
        raise RuntimeError(f"MT5 initialization failed: {err}")

def fetch_mt5_df(symbol, tf_const, utc_from, utc_to, min_bars_expected=1):
    """Fetch data from MT5"""
    ensure_mt5_initialized()
    
    rates = mt5.copy_rates_range(symbol, tf_const, utc_from, utc_to)
    
    if rates is None or len(rates) < min_bars_expected:
        raise RuntimeError(f"Insufficient data for {symbol}")
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    if 'tick_volume' not in df.columns:
        df['tick_volume'] = 1
    
    df = df.sort_values('time').reset_index(drop=True)
    df = df.dropna(subset=['open', 'high', 'low', 'close'])
    
    return df

# --------------------------- BACKTEST ----------------------------

def calculate_max_drawdown(equity_curve):
    """Calculate maximum drawdown"""
    if len(equity_curve) == 0:
        return 0
    
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak * 100
    return abs(drawdown.min())

def backtest(symbol, start, end, timeframe):
    """Enhanced backtest with ICT Fibonacci Strategy"""
    logger.info(f"Starting ICT Fibonacci backtest: {symbol} from {start} to {end}")
    
    tf = MT5_TIMEFRAMES.get(timeframe)
    if tf is None:
        raise ValueError(f'Unsupported timeframe: {timeframe}')
    
    utc_from = datetime.fromisoformat(start)
    utc_to = datetime.fromisoformat(end)
    extended_from = utc_from - timedelta(days=90)
    
    try:
        df = fetch_mt5_df(symbol, tf, extended_from, utc_to, min_bars_expected=CONFIG['min_bars_required'])
        df_d1 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['D1'], extended_from, utc_to, min_bars_expected=10)
        df_h4 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['H4'], extended_from, utc_to, min_bars_expected=10)
        df_h1 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['H1'], extended_from, utc_to, min_bars_expected=10)
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        raise
    
    df = compute_indicators(df)
    df_d1 = compute_indicators(df_d1)
    df_h4 = compute_indicators(df_h4)
    df_h1 = compute_indicators(df_h1)
    
    df = df[df['time'] >= utc_from].reset_index(drop=True)
    
    if df.empty:
        raise RuntimeError(f"No data available for backtest period")
    
    balance = CONFIG['capital']
    trades = []
    open_positions = []
    current_fib_setups = []
    
    logger.info(f"Running ICT Fibonacci backtest on {len(df)} bars...")
    
    for idx, current_bar in df.iterrows():
        current_time = current_bar['time']
        
        d1_slice = df_d1[df_d1['time'] <= current_time]
        h4_slice = df_h4[df_h4['time'] <= current_time]
        h1_slice = df_h1[df_h1['time'] <= current_time]
        
        if d1_slice.empty or h4_slice.empty or h1_slice.empty:
            continue
        
        for pos in open_positions[:]:
            if CONFIG['trailing_stop']:
                current_price = current_bar['close']
                pos = update_trailing_stop(pos, current_price)
            
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
        
        if len(open_positions) >= CONFIG['max_concurrent_trades']:
            continue
        
        if idx % 5 == 0 or idx < 100:
            fib_start = max(0, idx - CONFIG['fib_lookback'] * 2)
            current_slice = df.iloc[fib_start:idx+1].copy()
            
            if len(current_slice) > CONFIG['fib_lookback']:
                swing_points = identify_swing_points(current_slice, lookback=8)
                fib_setups = find_fibonacci_setups(current_slice, swing_points)
                current_fib_setups = fib_setups
            else:
                current_fib_setups = []
        
        if current_fib_setups:
            trend = determine_trend(d1_slice, h4_slice, h1_slice)
            
            fib_start_idx = max(0, idx - CONFIG['fib_lookback'] * 2)
            
            entry_signal = check_fibonacci_entry(current_fib_setups, df.iloc[fib_start_idx:idx+1], 
                                               idx - fib_start_idx, trend)
            
            if entry_signal:
                entry_price = entry_signal['entry_price']
                signal_type = entry_signal['type']
                fib_level = entry_signal['fib_level']
                fib_price = entry_signal['fib_price']
                setup_type = entry_signal['setup']['type']
                
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
                
                risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
                units = risk_amount / risk_per_unit
                
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

# --------------------------- LIVE TRADING ----------------------------

def connect_mt5(path=None):
    """Connect to MT5"""
    ensure_mt5_initialized()
    logger.info('MT5 connected successfully')

def disconnect_mt5():
    """Disconnect from MT5"""
    if MT5_AVAILABLE and mt5:
        mt5.shutdown()
        logger.info('MT5 disconnected')

def get_account_balance():
    """Get account balance"""
    info = mt5.account_info()
    if info is None:
        raise RuntimeError('Could not get account info')
    return info.balance

def get_symbol_info(symbol):
    """Get symbol information"""
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f'Symbol {symbol} not available')
    return info

def calc_volume(symbol, entry_price, stop_price, risk_amount):
    """Calculate position size"""
    si = get_symbol_info(symbol)
    
    contract_size = si.trade_contract_size if si.trade_contract_size else 100000
    risk_in_price_units = abs(entry_price - stop_price)
    
    if risk_in_price_units == 0:
        return si.volume_min
    
    lots = risk_amount / (risk_in_price_units * contract_size)
    
    step = si.volume_step if si.volume_step else 0.01
    lots = math.floor(lots / step) * step
    
    min_lot = si.volume_min if si.volume_min else 0.01
    lots = max(lots, min_lot)
    
    return round(lots, 2)

def place_market_order(symbol, side, volume, sl, tp):
    """Place market order"""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise RuntimeError('Symbol not found')
    
    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)
    
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if side == 'buy' else tick.bid
    
    request = {
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': symbol,
        'volume': volume,
        'type': mt5.ORDER_TYPE_BUY if side == 'buy' else mt5.ORDER_TYPE_SELL,
        'price': price,
        'sl': sl,
        'tp': tp,
        'deviation': 20,
        'magic': 234000,
        'comment': 'ICT Fibonacci Bot',
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': mt5.ORDER_FILLING_FOK,
    }
    
    result = mt5.order_send(request)
    return result

class FibonacciTracker:
    """Track Fibonacci setups in live trading"""
    
    def __init__(self):
        self.fib_setups = []
        self.last_analysis_time = None
    
    def update_fibonacci_setups(self, df):
        """Update Fibonacci setups"""
        if len(df) < CONFIG['fib_lookback'] * 2:
            return
        
        current_time = df.iloc[-1]['time']
        if (self.last_analysis_time is None or 
            (current_time - self.last_analysis_time).total_seconds() > 300):
            
            recent_df = df.tail(CONFIG['fib_lookback'] * 3).copy()
            swing_points = identify_swing_points(recent_df, lookback=8)
            new_fib_setups = find_fibonacci_setups(recent_df, swing_points)
            
            self.fib_setups = new_fib_setups
            self.last_analysis_time = current_time
    
    def get_valid_setups(self):
        """Get valid Fibonacci setups"""
        return [setup for setup in self.fib_setups if setup['valid']]

fib_tracker = FibonacciTracker()

def live_run_once():
    """Execute one live trading cycle"""
    global fib_tracker
    
    monitor_live_positions()
    
    symbol = CONFIG['symbol']
    
    bars_entry = mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAMES[CONFIG['timeframe_entry']], 0, 500)
    bars_d1 = mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAMES['D1'], 0, 500)
    bars_h4 = mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAMES['H4'], 0, 500)
    bars_h1 = mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAMES['H1'], 0, 500)
    
    if any(data is None for data in [bars_entry, bars_d1, bars_h4, bars_h1]):
        logger.error("Failed to fetch live data")
        return
    
    df_entry = pd.DataFrame(bars_entry)
    df_entry['time'] = pd.to_datetime(df_entry['time'], unit='s')
    df_entry = compute_indicators(df_entry)
    
    df_d1 = pd.DataFrame(bars_d1)
    df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
    df_d1 = compute_indicators(df_d1)
    
    df_h4 = pd.DataFrame(bars_h4)
    df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
    df_h4 = compute_indicators(df_h4)
    
    df_h1 = pd.DataFrame(bars_h1)
    df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
    df_h1 = compute_indicators(df_h1)
    
    fib_tracker.update_fibonacci_setups(df_entry)
    valid_setups = fib_tracker.get_valid_setups()
    
    trend = determine_trend(df_d1, df_h4, df_h1)
    
    logger.info(f'Trend: {trend}, Valid Fib Setups: {len(valid_setups)}')
    
    if not valid_setups:
        logger.info('No valid Fibonacci setups')
        return
    
    entry_signal = check_fibonacci_entry(valid_setups, df_entry, len(df_entry) - 1, trend)
    
    if entry_signal is None:
        logger.info('No Fibonacci entry signal')
        return
    
    entry_price = entry_signal['entry_price']
    signal_type = entry_signal['type']
    fib_level = entry_signal['fib_level']
    fib_price = entry_signal['fib_price']
    
    if signal_type == 'long':
        stop_price = fib_price - (CONFIG['fib_tolerance'] * 3)
        risk_per_unit = entry_price - stop_price
        tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
        tp_price = entry_price + tp_distance
        side = 'buy'
    else:
        stop_price = fib_price + (CONFIG['fib_tolerance'] * 3)
        risk_per_unit = stop_price - entry_price
        tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
        tp_price = entry_price - tp_distance
        side = 'sell'
    
    balance = get_account_balance()
    risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
    volume = calc_volume(symbol, entry_price, stop_price, risk_amount)
    
    logger.info(f'Placing {side} order Fib {fib_level}')
    logger.info(f'Vol: {volume}, Entry: {entry_price:.5f}, SL: {stop_price:.5f}, TP: {tp_price:.5f}')
    
    result = place_market_order(symbol, side, volume, stop_price, tp_price)
    
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f'Trade executed: {result.order}')
    else:
        logger.error(f'Order failed: {result.retcode}')
    
    return result

def monitor_live_positions():
    """Monitor and update trailing stops"""
    if not CONFIG['trailing_stop']:
        return
    
    try:
        positions = mt5.positions_get(symbol=CONFIG['symbol'])
        if not positions:
            return
        
        for position in positions:
            if position.magic != 234000:
                continue
            
            symbol = position.symbol
            ticket = position.ticket
            entry_price = position.price_open
            current_sl = position.sl
            position_type = position.type
            
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue
            
            current_price = tick.bid if position_type == mt5.POSITION_TYPE_BUY else tick.ask
            is_long = position_type == mt5.POSITION_TYPE_BUY
            
            if is_long:
                profit_points = current_price - entry_price
                original_risk = entry_price - current_sl
            else:
                profit_points = entry_price - current_price
                original_risk = current_sl - entry_price
            
            if original_risk <= 0 or profit_points <= 0:
                continue
            
            profit_ratio = profit_points / original_risk
            
            new_sl = None
            for level, trail_ratio in sorted(CONFIG['trailing_levels'].items(), reverse=True):
                if profit_ratio >= level:
                    if is_long:
                        calculated_sl = entry_price + (trail_ratio * original_risk)
                        if calculated_sl > current_sl:
                            new_sl = calculated_sl
                    else:
                        calculated_sl = entry_price - (trail_ratio * original_risk)
                        if calculated_sl < current_sl:
                            new_sl = calculated_sl
                    break
            
            if new_sl is not None:
                logger.info(f"Updating trailing stop: {current_sl:.5f} -> {new_sl:.5f}")
                update_live_trailing_stop(ticket, symbol, new_sl)
    
    except Exception as e:
        logger.error(f"Error monitoring positions: {e}")

def update_live_trailing_stop(position_ticket, symbol, new_sl):
    """Update stop loss for position"""
    try:
        positions = mt5.positions_get(ticket=position_ticket)
        if not positions:
            logger.error(f"Position {position_ticket} not found")
            return False
        
        position = positions[0]
        
        request = {
            'action': mt5.TRADE_ACTION_SLTP,
            'symbol': symbol,
            'position': position_ticket,
            'sl': new_sl,
            'tp': position.tp,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Trailing stop updated: {position_ticket}")
            return True
        else:
            logger.error(f"Failed to update: {result.retcode}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating trailing stop: {e}")
        return False

# ----------------------------- MAIN -------------------------------

def main():
    """Main function"""
    try:
        validate_config()
        
        if CONFIG['backtest']:
            if not MT5_AVAILABLE:
                logger.error("Cannot run backtest without MT5")
                return
            
            results, trades_df = backtest(
                CONFIG['symbol'], 
                CONFIG['start'], 
                CONFIG['end'], 
                CONFIG['timeframe_entry']
            )
            
        else:
            if not MT5_AVAILABLE:
                logger.error("Cannot run live trading without MT5")
                return
            
            connect_mt5()
            logger.info("Starting live trading...")
            logger.info("Press Ctrl+C to stop")
            
            try:
                while True:
                    live_run_once()
                    time.sleep(60)
            except KeyboardInterrupt:
                logger.info("Stopping...")
            finally:
                disconnect_mt5()
            
    except RuntimeError as e:
        logger.error(f"Critical error: {e}")
    except ValueError as e:
        logger.error(f"Config error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

if __name__ == '__main__':
    if MT5_AVAILABLE:
        try:
            if not mt5.initialize():
                logger.error("Failed to initialize MT5")
        except Exception as e:
            logger.error(f"MT5 init error: {e}")
    
    main()