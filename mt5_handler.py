"""
MT5 Handler Module - FIXED ORDER EXECUTION
Handles MT5 connection, data fetching, and order placement with proper retry logic
"""

import time
import math
from datetime import datetime, timedelta
import pandas as pd
import logging
from config import CONFIG, MT5_AVAILABLE, mt5, MT5_TIMEFRAMES

logger = logging.getLogger(__name__)

# --------------------------- MT5 CONNECTION ----------------------------

def ensure_mt5_initialized():
    """Initialize MT5 connection"""
    if not MT5_AVAILABLE:
        raise RuntimeError('MetaTrader5 package not available')
    
    if not mt5.initialize():
        err = mt5.last_error()
        raise RuntimeError(f"MT5 initialization failed: {err}")

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

# --------------------------- DATA FETCHING ----------------------------

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

def fetch_live_data(symbol, timeframe, num_bars=500):
    """Fetch live data from MT5"""
    ensure_mt5_initialized()
    
    tf_const = MT5_TIMEFRAMES.get(timeframe)
    if tf_const is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    
    bars = mt5.copy_rates_from_pos(symbol, tf_const, 0, num_bars)
    
    if bars is None:
        raise RuntimeError(f"Failed to fetch live data for {symbol}")
    
    df = pd.DataFrame(bars)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    if 'tick_volume' not in df.columns:
        df['tick_volume'] = 1
    
    return df

# --------------------------- ORDER EXECUTION (FIXED) ----------------------------

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
    
    max_lot = si.volume_max if si.volume_max else 100.0
    lots = min(lots, max_lot)
    
    return round(lots, 2)

def get_current_price(symbol, side):
    """Get current price for order execution"""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Failed to get tick data for {symbol}")
    
    # Use ASK for BUY, BID for SELL
    price = tick.ask if side == 'buy' else tick.bid
    return price

def determine_filling_type(symbol):
    """
    Determine the appropriate filling type for the symbol
    CRITICAL FIX: Different brokers require different filling types
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return mt5.ORDER_FILLING_FOK
    
    filling = symbol_info.filling_mode
    
    # Check available filling modes
    if filling & 1:  # FOK is available (bit 0)
        return mt5.ORDER_FILLING_FOK
    elif filling & 2:  # IOC is available (bit 1)
        return mt5.ORDER_FILLING_IOC
    else:  # Return is available
        return mt5.ORDER_FILLING_RETURN

def normalize_price(symbol, price):
    """Normalize price to symbol's digits"""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return round(price, 5)
    
    digits = symbol_info.digits
    return round(price, digits)

def place_market_order(symbol, side, volume, sl, tp):
    """
    Place market order with FIXED execution logic
    
    CRITICAL FIXES:
    1. Uses current tick price (not bar close)
    2. Proper filling type detection
    3. Price normalization
    4. Retry logic with fresh prices
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise RuntimeError(f'Symbol {symbol} not found')
    
    # Enable symbol if not visible
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f'Failed to select symbol {symbol}')
    
    # Determine proper filling type
    filling_type = determine_filling_type(symbol)
    
    # Normalize prices
    sl = normalize_price(symbol, sl)
    tp = normalize_price(symbol, tp)
    
    # Retry loop for order placement
    for attempt in range(CONFIG['max_retries']):
        try:
            # Get FRESH tick price for this attempt
            current_price = get_current_price(symbol, side)
            
            # Normalize entry price
            price = normalize_price(symbol, current_price)
            
            logger.info(f"Attempt {attempt + 1}: {side.upper()} {volume} lots @ {price}")
            logger.info(f"SL: {sl}, TP: {tp}, Filling: {filling_type}")
            
            # Build request
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol,
                'volume': volume,
                'type': mt5.ORDER_TYPE_BUY if side == 'buy' else mt5.ORDER_TYPE_SELL,
                'price': price,
                'sl': sl,
                'tp': tp,
                'deviation': CONFIG['slippage_points'],
                'magic': 234000,
                'comment': 'ICT Fibonacci Bot',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': filling_type,
            }
            
            # Send order
            result = mt5.order_send(request)
            
            if result is None:
                error = mt5.last_error()
                logger.error(f"Order send returned None: {error}")
                
                if attempt < CONFIG['max_retries'] - 1:
                    time.sleep(CONFIG['retry_delay'])
                    continue
                else:
                    raise RuntimeError(f"Order failed after {CONFIG['max_retries']} attempts: {error}")
            
            # Check result
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✓ Order executed successfully: {result.order}")
                logger.info(f"  Deal: {result.deal}, Volume: {result.volume}, Price: {result.price}")
                return result
            
            elif result.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_OFF]:
                # Price changed, retry with new price
                logger.warning(f"Price changed (code {result.retcode}), retrying...")
                if attempt < CONFIG['max_retries'] - 1:
                    time.sleep(CONFIG['retry_delay'])
                    continue
            
            elif result.retcode == mt5.TRADE_RETCODE_INVALID_FILL:
                # Try different filling type
                logger.warning(f"Invalid fill type, trying alternative...")
                if filling_type == mt5.ORDER_FILLING_FOK:
                    filling_type = mt5.ORDER_FILLING_IOC
                elif filling_type == mt5.ORDER_FILLING_IOC:
                    filling_type = mt5.ORDER_FILLING_RETURN
                
                if attempt < CONFIG['max_retries'] - 1:
                    time.sleep(CONFIG['retry_delay'])
                    continue
            
            else:
                # Other error
                error_msg = f"Order failed: {result.retcode} - {result.comment}"
                logger.error(error_msg)
                
                if attempt < CONFIG['max_retries'] - 1:
                    time.sleep(CONFIG['retry_delay'])
                    continue
                else:
                    raise RuntimeError(error_msg)
        
        except Exception as e:
            logger.error(f"Exception during order placement: {e}")
            if attempt < CONFIG['max_retries'] - 1:
                time.sleep(CONFIG['retry_delay'])
                continue
            else:
                raise
    
    raise RuntimeError(f"Order failed after {CONFIG['max_retries']} attempts")

def update_position_sl_tp(ticket, symbol, new_sl, new_tp):
    """
    Update stop loss and take profit for existing position
    Used for trailing stops
    """
    try:
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.error(f"Position {ticket} not found")
            return False
        
        position = positions[0]
        
        # Normalize prices
        new_sl = normalize_price(symbol, new_sl)
        if new_tp is not None:
            new_tp = normalize_price(symbol, new_tp)
        else:
            new_tp = position.tp
        
        request = {
            'action': mt5.TRADE_ACTION_SLTP,
            'symbol': symbol,
            'position': ticket,
            'sl': new_sl,
            'tp': new_tp,
        }
        
        result = mt5.order_send(request)
        
        if result is None:
            error = mt5.last_error()
            logger.error(f"Failed to update SL/TP: {error}")
            return False
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"✓ SL/TP updated for position {ticket}")
            return True
        else:
            logger.error(f"Failed to update SL/TP: {result.retcode} - {result.comment}")
            return False
            
    except Exception as e:
        logger.error(f"Exception updating SL/TP: {e}")
        return False

def get_open_positions(symbol=None):
    """Get all open positions, optionally filtered by symbol"""
    if symbol:
        positions = mt5.positions_get(symbol=symbol)
    else:
        positions = mt5.positions_get()
    
    if positions is None:
        return []
    
    return list(positions)

def close_position(ticket, symbol, volume=None):
    """Close position by ticket"""
    try:
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.error(f"Position {ticket} not found")
            return False
        
        position = positions[0]
        
        # Determine close parameters
        if position.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask
        
        close_volume = volume if volume else position.volume
        
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': close_volume,
            'type': order_type,
            'position': ticket,
            'price': price,
            'deviation': CONFIG['slippage_points'],
            'magic': 234000,
            'comment': 'Close by bot',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': determine_filling_type(symbol),
        }
        
        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"✓ Position {ticket} closed")
            return True
        else:
            logger.error(f"Failed to close position: {result.retcode if result else 'None'}")
            return False
            
    except Exception as e:
        logger.error(f"Exception closing position: {e}")
        return False