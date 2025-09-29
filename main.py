"""
MT5 Trading Bot + Backtester - Optimized Version

Features:
- Connects to MetaTrader5 (live) or runs a historical backtest.
- Strategy:
  - Trend determined by RSI, VWAP, MA(9) & MA(18) on 1D and 4H timeframes (simple voting rule).
  - Entries are taken when price interacts with Bollinger Bands (SMA basis, length=20).
  - Trades only executed in direction of trend. If entry signal is opposite, skip.
  - Stop loss placed at the Bollinger Band side (lower band for long / upper band for short).
  - Take profit = min( 3 * risk_distance, opposite Bollinger band ).
  - If opposite Bollinger band is hit, trade closes.
  - Risk per trade = 0.5% of account capital (configurable).

Usage:
- Edit CONFIG section to set symbol, timeframes, and whether to run backtest or live.
- Backtest: specify start/end dates and historical timeframe for entries (e.g., 1H/4H).
- Live: requires MetaTrader5 terminal running and logged in. Install MetaTrader5 package:
    pip install MetaTrader5 pandas numpy

Notes & Limitations:
- This is a reference implementation. Always paper-test on demo accounts before using live.
- Lot-sizing logic is approximate — broker-specific contract sizes, pip definitions, and margin rules vary.
- The bot places MARKET orders via MT5; modify as needed for limit/stop entries.
"""

import time
import math
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging

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
    'symbol': 'EURUSD.raw',
    'backtest': True,            # True = backtest mode, False = live trading
    'start': '2024-06-22',
    'end': '2024-12-31',         # Fixed end date to be more realistic
    'capital': 10000.0,          # used for backtest or initial capital
    'risk_pct': 0.5,             # percent risk per trade (0.5%)
    'timeframe_entry': 'M15',     # timeframe used to simulate entries in backtest
    'trend_timeframes': ['D1', 'H4', 'H1'],  # timeframes used for trend determination
    'boll_period': 20,
    'boll_std': 2,
    'rsi_period': 14,
    'vwap_period': 20,           # VWAP window (we'll compute rolling VWAP using typical price*volume)
    'max_concurrent_trades': 1,   # Maximum number of open positions
    'min_bars_required': 50,     # Minimum bars required for indicators
    'trailing_stop': True,       # Enable trailing stop loss
    'trailing_levels': {         # Trailing stop levels (profit_ratio: trail_to_ratio)
        1.0: 0.5,   # At 1:1 RR, move SL to 0.5:1 profit
        2.0: 1.0,   # At 2:1 RR, move SL to 1:1 profit  
        3.0: 1.5,   # At 3:1 RR, move SL to 1.5:1 profit
        4.0: 2.0,   # At 4:1 RR, move SL to 2:1 profit
    }
}

# Map timeframe strings to MT5 constants - Fixed mapping
def get_mt5_timeframes():
    """Get MT5 timeframes mapping with proper error handling"""
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
        raise RuntimeError("MT5 not available for live trading. Set backtest=True or install MetaTrader5")
    
    if CONFIG['timeframe_entry'] not in MT5_TIMEFRAMES:
        raise ValueError(f"Unsupported entry timeframe: {CONFIG['timeframe_entry']}")
    
    for tf in CONFIG['trend_timeframes']:
        if tf not in MT5_TIMEFRAMES:
            raise ValueError(f"Unsupported trend timeframe: {tf}")
    
    # Validate dates
    try:
        start_date = datetime.fromisoformat(CONFIG['start'])
        end_date = datetime.fromisoformat(CONFIG['end'])
        if start_date >= end_date:
            raise ValueError("Start date must be before end date")
    except ValueError as e:
        raise ValueError(f"Invalid date format: {e}")

def to_datetime(ts):
    """Convert timestamp to datetime"""
    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(ts)
    return ts

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
    
    # Avoid division by zero
    ma_down = ma_down.replace(0, np.nan)
    rs = ma_up / ma_down
    rsi_values = 100 - (100 / (1 + rs))
    
    # Handle edge cases
    rsi_values = rsi_values.fillna(50)  # Neutral RSI for NaN values
    return rsi_values

def vwap(df, length=None):
    """Volume Weighted Average Price"""
    if 'tick_volume' not in df.columns:
        logger.warning("tick_volume not found, using equal weights for VWAP")
        df['tick_volume'] = 1
    
    # Replace zero or negative volumes
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
        
        # Avoid division by zero
        v_roll = v_roll.replace(0, 1)
        return pv_roll / v_roll

def bollinger_bands(series, length=20, stddev=2):
    """Bollinger Bands"""
    basis = sma(series, length)
    sd = std(series, length)
    upper = basis + stddev * sd
    lower = basis - stddev * sd
    return basis, upper, lower

# ----------------------- STRATEGY / SIGNALS -----------------------

def compute_indicators(df):
    """Compute all technical indicators"""
    if df.empty or len(df) < CONFIG['min_bars_required']:
        logger.warning(f"Insufficient data for indicators: {len(df)} bars")
        return df
    
    df = df.copy()
    
    # Ensure required columns exist
    required_cols = ['open', 'high', 'low', 'close']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in data")
    
    # Compute indicators with error handling
    try:
        df['ma9'] = sma(df['close'], 9)
        df['ma18'] = sma(df['close'], 18)
        df['rsi'] = rsi(df['close'], CONFIG['rsi_period'])
        df['vwap'] = vwap(df, CONFIG['vwap_period'])
        df['bb_basis'], df['bb_upper'], df['bb_lower'] = bollinger_bands(
            df['close'], CONFIG['boll_period'], CONFIG['boll_std']
        )
    except Exception as e:
        logger.error(f"Error computing indicators: {e}")
        raise
    
    return df

def determine_trend(df_d1, df_h4):
    """Return 'long', 'short', or 'neutral' based on voting system"""
    if df_d1.empty or df_h4.empty:
        return 'neutral'
    
    votes = 0
    
    for df_name, df in [('D1', df_d1), ('H4', df_h4)]:
        if len(df) == 0:
            continue
            
        last = df.iloc[-1]
        timeframe_votes = 0
        
        # MA vote (bullish if MA9 > MA18)
        if not (pd.isna(last['ma9']) or pd.isna(last['ma18'])):
            ma_vote = 1 if last['ma9'] > last['ma18'] else -1
            timeframe_votes += ma_vote
        
        # RSI vote (bullish > 55, bearish < 45, neutral between)
        if not pd.isna(last['rsi']):
            if last['rsi'] > 55:
                rsi_vote = 1
            elif last['rsi'] < 45:
                rsi_vote = -1
            else:
                rsi_vote = 0
            timeframe_votes += rsi_vote
        
        # VWAP vote (bullish if price > VWAP)
        if not pd.isna(last['vwap']):
            vwap_vote = 1 if last['close'] > last['vwap'] else -1
            timeframe_votes += vwap_vote
        
        votes += timeframe_votes
        logger.debug(f"{df_name} timeframe votes: {timeframe_votes}")
    
    logger.debug(f"Total trend votes: {votes}")
    
    if votes > 0:
        return 'long'
    elif votes < 0:
        return 'short'
    else:
        return 'neutral'

def entry_signal(df):
    """Detect Bollinger Band touches for entry signals"""
    if df.empty or len(df) < 2:
        return None
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Check if we have valid BB values
    if any(pd.isna([last['bb_lower'], last['bb_upper'], prev['bb_lower'], prev['bb_upper']])):
        return None
    
    # Long signal: price touches or crosses below lower BB
    if (last['close'] <= last['bb_lower'] or 
        (prev['close'] > prev['bb_lower'] and last['low'] <= last['bb_lower'])):
        return 'long'
    
    # Short signal: price touches or crosses above upper BB  
    if (last['close'] >= last['bb_upper'] or
        (prev['close'] < prev['bb_upper'] and last['high'] >= last['bb_upper'])):
        return 'short'
    
    return None

# ----------------------- TRAILING STOP FUNCTIONS -----------------------

def update_trailing_stop(position, current_price):
    """Update trailing stop loss based on profit levels"""
    if not CONFIG['trailing_stop']:
        return position
    
    entry_price = position['entry']
    original_stop = position['original_stop']  # Keep track of original stop
    current_stop = position['stop']
    side = position['side']
    
    # Calculate initial risk
    if side == 'long':
        initial_risk = entry_price - original_stop
        current_profit = current_price - entry_price
    else:  # short
        initial_risk = original_stop - entry_price
        current_profit = entry_price - current_price
    
    if initial_risk <= 0 or current_profit <= 0:
        return position  # No profit yet or invalid risk
    
    # Calculate current profit in terms of risk ratio
    profit_ratio = current_profit / initial_risk
    
    # Find the highest applicable trailing level
    applicable_level = None
    trail_to_ratio = None
    
    for level, trail_ratio in sorted(CONFIG['trailing_levels'].items(), reverse=True):
        if profit_ratio >= level:
            applicable_level = level
            trail_to_ratio = trail_ratio
            break
    
    if applicable_level is None:
        return position  # No trailing level reached yet
    
    # Calculate new stop price
    if side == 'long':
        new_stop = entry_price + (trail_to_ratio * initial_risk)
        # Only move stop up, never down
        if new_stop > current_stop:
            position['stop'] = new_stop
            position['trailing_active'] = True
            position['trail_level'] = applicable_level
            logger.debug(f"Long trailing stop updated: {current_stop:.5f} -> {new_stop:.5f} "
                        f"(profit: {profit_ratio:.2f}R, trailing to: {trail_to_ratio:.1f}R)")
    else:  # short
        new_stop = entry_price - (trail_to_ratio * initial_risk)
        # Only move stop down, never up
        if new_stop < current_stop:
            position['stop'] = new_stop
            position['trailing_active'] = True
            position['trail_level'] = applicable_level
            logger.debug(f"Short trailing stop updated: {current_stop:.5f} -> {new_stop:.5f} "
                        f"(profit: {profit_ratio:.2f}R, trailing to: {trail_to_ratio:.1f}R)")
    
    return position

# ----------------------- DATA FETCHING -----------------------

def ensure_mt5_initialized():
    """Initialize MT5 connection"""
    if not MT5_AVAILABLE:
        raise RuntimeError('MetaTrader5 package not available. Install with: pip install MetaTrader5')
    
    if not mt5.initialize():
        err = mt5.last_error()
        raise RuntimeError(f"MT5 initialization failed: {err}")
    
    logger.info("MT5 initialized successfully")

def fetch_mt5_df(symbol, tf_const, utc_from, utc_to, min_bars_expected=1):
    """Fetch data from MT5 with comprehensive error handling"""
    ensure_mt5_initialized()
    
    logger.info(f"Fetching {symbol} data from {utc_from} to {utc_to} (timeframe: {tf_const})")
    
    # Fetch data
    rates = mt5.copy_rates_range(symbol, tf_const, utc_from, utc_to)
    
    if rates is None or len(rates) < min_bars_expected:
        # Get available symbols for debugging
        all_symbols = mt5.symbols_get()
        if all_symbols:
            available_names = [s.name for s in all_symbols[:50]]
            symbol_list = ', '.join(available_names)
        else:
            symbol_list = "No symbols available"
        
        raise RuntimeError(
            f"Insufficient data for {symbol} (got {len(rates) if rates is not None else 0} bars, "
            f"expected {min_bars_expected}). Check:\n"
            f"1. Symbol spelling: '{symbol}'\n"
            f"2. Market Watch subscription\n"
            f"3. MT5 terminal login\n"
            f"4. Date range validity\n"
            f"Available symbols: {symbol_list}"
        )
    
    # Create DataFrame
    df = pd.DataFrame(rates)
    
    # Handle time column
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], unit='s')
    else:
        raise RuntimeError("No time column found in MT5 data")
    
    # Ensure tick_volume exists
    if 'tick_volume' not in df.columns:
        if 'real_volume' in df.columns:
            df['tick_volume'] = df['real_volume']
        else:
            df['tick_volume'] = 1
            logger.warning("No volume data found, using unit volume")
    
    # Clean and validate data
    df = df.sort_values('time').reset_index(drop=True)
    df = df.dropna(subset=['open', 'high', 'low', 'close'])
    
    logger.info(f"Successfully fetched {len(df)} bars for {symbol}")
    return df

# --------------------------- BACKTEST ------------------------------

def backtest(symbol, start, end, timeframe):
    """Enhanced bar-by-bar backtester"""
    logger.info(f"Starting backtest: {symbol} from {start} to {end}")
    
    # Validate inputs
    tf = MT5_TIMEFRAMES.get(timeframe)
    if tf is None:
        raise ValueError(f'Unsupported timeframe: {timeframe}')
    
    # Parse dates
    utc_from = datetime.fromisoformat(start)
    utc_to = datetime.fromisoformat(end)
    
    # Extend date range to ensure sufficient data for indicators
    extended_from = utc_from - timedelta(days=60)
    
    # Fetch data for all timeframes
    try:
        df = fetch_mt5_df(symbol, tf, extended_from, utc_to, min_bars_expected=CONFIG['min_bars_required'])
        df_d1 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['D1'], extended_from, utc_to, min_bars_expected=10)
        df_h4 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['H4'], extended_from, utc_to, min_bars_expected=10)
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        raise
    
    # Compute indicators
    df = compute_indicators(df)
    df_d1 = compute_indicators(df_d1)
    df_h4 = compute_indicators(df_h4)
    
    # Filter to actual backtest period
    df = df[df['time'] >= utc_from].reset_index(drop=True)
    
    if df.empty:
        raise RuntimeError(f"No data available for backtest period {start} to {end}")
    
    # Initialize backtest variables
    balance = CONFIG['capital']
    trades = []
    open_positions = []
    
    logger.info(f"Running backtest on {len(df)} bars...")
    
    # Main backtest loop
    for idx, current in df.iterrows():
        current_time = current['time']
        
        # Get trend data up to current time
        d1_slice = df_d1[df_d1['time'] <= current_time]
        h4_slice = df_h4[df_h4['time'] <= current_time]
        
        if d1_slice.empty or h4_slice.empty:
            continue
        
        # Check existing positions for exits and trailing stops
        for pos in open_positions[:]:  # Create copy for safe iteration
            # Update trailing stop first
            if CONFIG['trailing_stop']:
                current_price = current['close']  # Use close price for trailing calculations
                pos = update_trailing_stop(pos, current_price)
            
            if pos['side'] == 'long':
                # Check stop loss (low <= stop)
                if current['low'] <= pos['stop']:
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
                        'trail_level': pos.get('trail_level', None)
                    })
                    open_positions.remove(pos)
                    continue
                
                # Check take profit (high >= tp)
                if current['high'] >= pos['tp']:
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
                        'trail_level': pos.get('trail_level', None)
                    })
                    open_positions.remove(pos)
                    continue
            
            else:  # short position
                # Check stop loss (high >= stop)
                if current['high'] >= pos['stop']:
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
                        'trail_level': pos.get('trail_level', None)
                    })
                    open_positions.remove(pos)
                    continue
                
                # Check take profit (low <= tp)
                if current['low'] <= pos['tp']:
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
                        'trail_level': pos.get('trail_level', None)
                    })
                    open_positions.remove(pos)
                    continue
        
        # Check for new entries (only if we have room for more positions)
        if len(open_positions) >= CONFIG['max_concurrent_trades']:
            continue
        
        # Get data slice for signal detection (need at least 2 bars)
        bar_slice = df.iloc[:idx+1]
        if len(bar_slice) < 2:
            continue
        
        trend = determine_trend(d1_slice, h4_slice)
        signal = entry_signal(bar_slice)
        
        if signal is None or (trend != signal and trend != 'neutral'):
            continue
        
        # Calculate position parameters
        entry_price = current['close']
        
        if signal == 'long':
            stop_price = current['bb_lower']
            opposite_band = current['bb_upper']
            
            if pd.isna(stop_price) or pd.isna(opposite_band) or stop_price >= entry_price:
                continue
            
            risk_per_unit = entry_price - stop_price
            tp_by_rr = entry_price + 3 * risk_per_unit
            tp = min(tp_by_rr, opposite_band)
            
        else:  # short
            stop_price = current['bb_upper']
            opposite_band = current['bb_lower']
            
            if pd.isna(stop_price) or pd.isna(opposite_band) or stop_price <= entry_price:
                continue
            
            risk_per_unit = stop_price - entry_price
            tp_by_rr = entry_price - 3 * risk_per_unit
            tp = max(tp_by_rr, opposite_band)
        
        # Position sizing
        risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
        if risk_per_unit <= 0:
            continue
        
        units = risk_amount / risk_per_unit
        
        # Create position
        position = {
            'entry_time': current_time,
            'side': signal,
            'entry': entry_price,
            'stop': stop_price,
            'original_stop': stop_price,  # Keep track of original stop for trailing calculations
            'tp': tp,
            'units': units,
            'trailing_active': False,
            'trail_level': None
        }
        
        open_positions.append(position)
        logger.debug(f"Opened {signal} position at {entry_price}")
    
    # Close any remaining open positions at final price
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
            'trail_level': pos.get('trail_level', None)
        })
    
    # Create results
    trades_df = pd.DataFrame(trades)
    
    # Calculate performance metrics
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
        
        trailing_stops = len(trades_df[trades_df['exit_reason'] == 'trailing_stop']) if total_trades > 0 else 0
        take_profits = len(trades_df[trades_df['exit_reason'] == 'take_profit']) if total_trades > 0 else 0
        stop_losses = len(trades_df[trades_df['exit_reason'] == 'stop_loss']) if total_trades > 0 else 0
        
        max_dd = calculate_max_drawdown(trades_df['pl'].cumsum() + CONFIG['capital'])
        
    else:
        wins = losses = 0
        win_rate = avg_win = avg_loss = profit_factor = total_profit = max_dd = 0
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
        'max_drawdown': max_dd,
        'return_pct': (balance - CONFIG['capital']) / CONFIG['capital'] * 100,
        'trailing_stops': trailing_stops,
        'take_profits': take_profits,
        'stop_losses': stop_losses
    }
    
    print('\n' + '='*50)
    print('BACKTEST RESULTS')
    print('='*50)
    for key, value in summary.items():
        if isinstance(value, float):
            print(f'{key.replace("_", " ").title()}: {value:.2f}')
        else:
            print(f'{key.replace("_", " ").title()}: {value}')
    print('='*50)
    
    return trades_df, summary

def calculate_max_drawdown(equity_curve):
    """Calculate maximum drawdown from equity curve"""
    if len(equity_curve) == 0:
        return 0
    
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak * 100
    return abs(drawdown.min())

# --------------------------- LIVE TRADING --------------------------

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
        raise RuntimeError('Could not get account info; ensure MT5 terminal is logged in')
    return info.balance

def get_symbol_info(symbol):
    """Get symbol information"""
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f'Symbol {symbol} not available in Market Watch')
    return info

def calc_volume(symbol, entry_price, stop_price, risk_amount):
    """Calculate position size"""
    si = get_symbol_info(symbol)
    
    contract_size = si.trade_contract_size if si.trade_contract_size else 100000
    risk_in_price_units = abs(entry_price - stop_price)
    
    if risk_in_price_units == 0:
        return si.volume_min
    
    lots = risk_amount / (risk_in_price_units * contract_size)
    
    # Round to broker step
    step = si.volume_step if si.volume_step else 0.01
    lots = math.floor(lots / step) * step
    
    # Ensure minimum lot size
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
        'comment': 'Python MT5 bot',
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': mt5.ORDER_FILLING_FOK,
    }
    
    result = mt5.order_send(request)
    return result

def update_live_trailing_stop(position_ticket, symbol, new_sl):
    """Update stop loss for live position via MT5"""
    try:
        # Get current position info
        positions = mt5.positions_get(ticket=position_ticket)
        if not positions:
            logger.error(f"Position {position_ticket} not found")
            return False
        
        position = positions[0]
        
        # Prepare modification request
        request = {
            'action': mt5.TRADE_ACTION_SLTP,
            'symbol': symbol,
            'position': position_ticket,
            'sl': new_sl,
            'tp': position.tp,  # Keep existing TP
        }
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Trailing stop updated for position {position_ticket}: SL = {new_sl:.5f}")
            return True
        else:
            logger.error(f"Failed to update trailing stop: {result.retcode} - {result.comment}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating trailing stop: {e}")
        return False

def monitor_live_positions():
    """Monitor and update trailing stops for live positions"""
    if not CONFIG['trailing_stop']:
        return
    
    try:
        positions = mt5.positions_get(symbol=CONFIG['symbol'])
        if not positions:
            return
        
        for position in positions:
            # Check if this is our bot's position (by magic number)
            if position.magic != 234000:
                continue
            
            symbol = position.symbol
            ticket = position.ticket
            entry_price = position.price_open
            current_sl = position.sl
            current_tp = position.tp
            volume = position.volume
            position_type = position.type
            
            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue
            
            current_price = tick.bid if position_type == mt5.POSITION_TYPE_BUY else tick.ask
            
            # Calculate if we need to update trailing stop
            is_long = position_type == mt5.POSITION_TYPE_BUY
            
            if is_long:
                # For long positions, calculate profit from entry
                profit_points = current_price - entry_price
                original_risk = entry_price - current_sl  # Assuming current SL is original
            else:
                # For short positions
                profit_points = entry_price - current_price
                original_risk = current_sl - entry_price  # Assuming current SL is original
            
            if original_risk <= 0 or profit_points <= 0:
                continue  # No profit yet or invalid setup
            
            # Calculate profit ratio
            profit_ratio = profit_points / original_risk
            
            # Find applicable trailing level
            new_sl = None
            for level, trail_ratio in sorted(CONFIG['trailing_levels'].items(), reverse=True):
                if profit_ratio >= level:
                    if is_long:
                        calculated_sl = entry_price + (trail_ratio * original_risk)
                        # Only move SL up
                        if calculated_sl > current_sl:
                            new_sl = calculated_sl
                    else:
                        calculated_sl = entry_price - (trail_ratio * original_risk)
                        # Only move SL down
                        if calculated_sl < current_sl:
                            new_sl = calculated_sl
                    break
            
            # Update if needed
            if new_sl is not None:
                logger.info(f"Updating trailing stop for {symbol} position {ticket}: "
                           f"{current_sl:.5f} -> {new_sl:.5f} (profit: {profit_ratio:.2f}R)")
                update_live_trailing_stop(ticket, symbol, new_sl)
    
    except Exception as e:
        logger.error(f"Error monitoring positions: {e}")

def live_run_once():
    """Execute one live trading cycle"""
    # First, monitor existing positions for trailing stops
    monitor_live_positions()
    
    symbol = CONFIG['symbol']
    
    # Fetch current data
    bars_entry = mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAMES[CONFIG['timeframe_entry']], 0, 500)
    bars_d1 = mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAMES['D1'], 0, 500)
    bars_h4 = mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAMES['H4'], 0, 500)
    
    if any(data is None for data in [bars_entry, bars_d1, bars_h4]):
        logger.error("Failed to fetch live data")
        return
    
    # Create DataFrames
    df_entry = pd.DataFrame(bars_entry)
    df_entry['time'] = pd.to_datetime(df_entry['time'], unit='s')
    df_entry = compute_indicators(df_entry)
    
    df_d1 = pd.DataFrame(bars_d1)
    df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
    df_d1 = compute_indicators(df_d1)
    
    df_h4 = pd.DataFrame(bars_h4)
    df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
    df_h4 = compute_indicators(df_h4)
    
    # Analyze market
    trend = determine_trend(df_d1, df_h4)
    signal = entry_signal(df_entry)
    
    logger.info(f'Trend: {trend}, Signal: {signal}')
    
    if signal is None:
        logger.info('No entry signal detected')
        return
    
    if trend != signal and trend != 'neutral':
        logger.info('Signal opposite to trend; skipping entry')
        return
    
    # Calculate trade parameters
    last = df_entry.iloc[-1]
    entry_price = last['close']
    
    if signal == 'long':
        stop_price = last['bb_lower']
        opposite_band = last['bb_upper']
        risk_per_unit = entry_price - stop_price
        tp_by_rr = entry_price + 3 * risk_per_unit
        tp = min(tp_by_rr, opposite_band)
        side = 'buy'
    else:
        stop_price = last['bb_upper']
        opposite_band = last['bb_lower']
        risk_per_unit = stop_price - entry_price
        tp_by_rr = entry_price - 3 * risk_per_unit
        tp = max(tp_by_rr, opposite_band)
        side = 'sell'
    
    # Position sizing
    balance = get_account_balance()
    risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
    volume = calc_volume(CONFIG['symbol'], entry_price, stop_price, risk_amount)
    
    logger.info(f'Placing {side} order: volume={volume}, entry={entry_price:.5f}, sl={stop_price:.5f}, tp={tp:.5f}')
    
    # Place order
    result = place_market_order(CONFIG['symbol'], side, volume, stop_price, tp)
    
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f'Order executed successfully: {result.order}')
    else:
        logger.error(f'Order failed: {result.retcode} - {result.comment}')
    
    return result

# ----------------------------- MAIN -------------------------------

def main():
    """Main execution function"""
    try:
        # Validate configuration
        validate_config()
        
        if CONFIG['backtest']:
            logger.info('Starting backtest mode...')
            trades, summary = backtest(
                CONFIG['symbol'], 
                CONFIG['start'], 
                CONFIG['end'], 
                CONFIG['timeframe_entry']
            )
            
            # Display sample trades
            if not trades.empty:
                print(f'\nSample trades (first 10):')
                print(trades.head(10).to_string(index=False))
                
                # Show trailing stop statistics if enabled
                if CONFIG['trailing_stop']:
                    trailing_count = len(trades[trades['exit_reason'] == 'trailing_stop'])
                    print(f'\nTrailing Stop Performance:')
                    print(f'Trades closed by trailing stop: {trailing_count}')
                    if trailing_count > 0:
                        trailing_trades = trades[trades['exit_reason'] == 'trailing_stop']
                        avg_trailing_profit = trailing_trades['pl'].mean()
                        print(f'Average trailing stop profit: {avg_trailing_profit:.2f}')
                
                # Save trades to CSV
                filename = f"backtest_results_{CONFIG['symbol']}_{CONFIG['start']}_{CONFIG['end']}.csv"
                trades.to_csv(filename, index=False)
                logger.info(f'Trades saved to {filename}')
        
        else:
            logger.info('Starting live trading mode...')
            connect_mt5()
            try:
                # Run trading cycle
                result = live_run_once()
                
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info('Live trade executed successfully')
                else:
                    logger.info('No trades executed this cycle')
                    
            except Exception as e:
                logger.error(f'Live trading error: {e}')
            finally:
                disconnect_mt5()
    
    except Exception as e:
        logger.error(f'Application error: {e}')
        raise

def run_live_bot(interval_seconds=60):
    """Run live bot in continuous mode with trailing stop monitoring"""
    logger.info(f'Starting continuous live trading (interval: {interval_seconds}s)...')
    logger.info(f'Trailing stops enabled: {CONFIG["trailing_stop"]}')
    if CONFIG['trailing_stop']:
        logger.info(f'Trailing levels: {CONFIG["trailing_levels"]}')
    
    connect_mt5()
    
    try:
        while True:
            try:
                live_run_once()  # This now includes position monitoring
                logger.info(f'Sleeping for {interval_seconds} seconds...')
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                logger.info('Bot stopped by user')
                break
            except Exception as e:
                logger.error(f'Error in trading cycle: {e}')
                time.sleep(interval_seconds)
    finally:
        disconnect_mt5()

if __name__ == '__main__':
    main()