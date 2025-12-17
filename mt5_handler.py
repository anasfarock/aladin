import time
import math
from datetime import datetime, timedelta  # <-- MAKE SURE THIS IS HERE
import pandas as pd
import logging
from config import CONFIG, MT5_AVAILABLE, mt5, MT5_TIMEFRAMES

logger = logging.getLogger(__name__)

# --------------------------- MT5 CONNECTION ----------------------------

def check_trading_permissions():
    """Check if automated trading is allowed"""
    try:
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            return False, "Cannot get terminal info"
        
        if not terminal_info.trade_allowed:
            return False, "Trading not allowed in terminal"
        
        account_info = mt5.account_info()
        if account_info is None:
            return False, "Cannot get account info"
        
        if not account_info.trade_allowed:
            return False, "Trading not allowed for this account"
        
        if not account_info.trade_expert:
            return False, "Expert Advisor trading not allowed"
        
        return True, "All permissions OK"
    
    except Exception as e:
        logger.error(f"Error checking trading permissions: {e}")
        return False, f"Error: {str(e)}"


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
    """
    Get account balance with error handling
    
    Returns:
        float: Account balance
    
    Raises:
        RuntimeError: If balance cannot be retrieved
    """
    try:
        info = mt5.account_info()
        if info is None:
            raise RuntimeError('Could not get account info')
        
        if info.balance <= 0:
            logger.warning(f"Account balance is {info.balance} (unexpected)")
        
        logger.debug(f"Account balance: ${info.balance:.2f}")
        return info.balance
    
    except Exception as e:
        logger.error(f"Error getting account balance: {e}")
        raise RuntimeError(f'Cannot get account balance: {e}')


def get_symbol_info(symbol):
    """
    Get symbol information with proper error handling
    
    Returns:
        SymbolInfo: Symbol info object
    
    Raises:
        RuntimeError: If symbol not available
    """
    try:
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error(f"Symbol {symbol} not found in MT5")
            raise RuntimeError(f'Symbol {symbol} not available')
        
        # Enable symbol if not visible
        if not info.visible:
            logger.debug(f"Symbol {symbol} not visible, attempting to select...")
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Failed to select symbol {symbol}")
                raise RuntimeError(f'Failed to select symbol {symbol}')
            
            # Fetch info again after selecting
            info = mt5.symbol_info(symbol)
            if info is None:
                raise RuntimeError(f'Failed to get info for {symbol} after selection')
        
        logger.debug(f"Symbol info retrieved: {symbol}, digits={info.digits}, point={info.point}")
        return info
    
    except Exception as e:
        logger.error(f"Error getting symbol info for {symbol}: {e}")
        raise


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
    """
    Fetch live data from MT5 with error handling
    
    Args:
        symbol: Trading pair
        timeframe: Timeframe string (M15, H1, etc.)
        num_bars: Number of bars to fetch
    
    Returns:
        DataFrame: OHLC data
    
    Raises:
        ValueError: If timeframe unsupported
        RuntimeError: If data fetch fails
    """
    try:
        ensure_mt5_initialized()
        
        tf_const = MT5_TIMEFRAMES.get(timeframe)
        if tf_const is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        logger.debug(f"Fetching {num_bars} bars of {symbol} {timeframe}...")
        bars = mt5.copy_rates_from_pos(symbol, tf_const, 0, num_bars)
        
        if bars is None:
            raise RuntimeError(f"Failed to fetch live data for {symbol}")
        
        if len(bars) < num_bars:
            logger.warning(f"Requested {num_bars} bars but only got {len(bars)}")
        
        df = pd.DataFrame(bars)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        if 'tick_volume' not in df.columns:
            df['tick_volume'] = 1
        
        logger.debug(f"Data fetch successful: {len(df)} bars")
        return df
    
    except Exception as e:
        logger.error(f"Error fetching live data for {symbol} {timeframe}: {e}")
        raise

# --------------------------- PRICE UTILITIES ----------------------------

def get_current_price(symbol, side):
    """Get current price for order execution"""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Failed to get tick data for {symbol}")
    
    # Use ASK for BUY, BID for SELL
    price = tick.ask if side == 'buy' else tick.bid
    return price


def normalize_price(symbol, price):
    """Normalize price to symbol's digits"""
    symbol_info = get_symbol_info(symbol)
    digits = symbol_info.digits
    return round(price, digits)


def determine_filling_type(symbol):
    """
    Determine the appropriate filling type for the symbol
    Different brokers require different filling types
    """
    symbol_info = get_symbol_info(symbol)
    filling = symbol_info.filling_mode
    
    # Check available filling modes (bitwise flags)
    if filling & 1:  # FOK is available (bit 0)
        return mt5.ORDER_FILLING_FOK
    elif filling & 2:  # IOC is available (bit 1)
        return mt5.ORDER_FILLING_IOC
    else:  # Return is available
        return mt5.ORDER_FILLING_RETURN

# --------------------------- STOP VALIDATION ----------------------------

def adjust_stops_to_broker_limits(symbol, side, entry_price, stop_price, tp_price):
    """
    Adjust SL and TP to meet broker's minimum stop levels
    
    CRITICAL FIX: Ensures stops are valid according to broker requirements
    Handles brokers with no minimum (stops_level = 0)
    
    Returns:
        tuple: (adjusted_stop, adjusted_tp, is_valid, error_msg)
    """
    symbol_info = get_symbol_info(symbol)
    point = symbol_info.point
    
    # Try to get stops level from broker
    stops_level = None
    stop_level_attrs = ['trade_stops_level', 'stops_level', 'stoplevel', 'stop_level']
    
    for attr in stop_level_attrs:
        try:
            value = getattr(symbol_info, attr, None)
            if value is not None:
                stops_level = value
                logger.debug(f"Found stops_level via '{attr}': {stops_level}")
                break
        except (AttributeError, TypeError):
            continue
    
    # If broker has NO minimum requirement (stops_level = 0)
    if stops_level == 0:
        logger.info("Broker has no minimum stop level requirement")
        
        # Just validate basic logic (SL/TP on correct side of entry)
        if side.lower() in ['buy', 'long']:
            if stop_price >= entry_price:
                return stop_price, tp_price, False, "SL must be below entry for BUY"
            if tp_price <= entry_price:
                return stop_price, tp_price, False, "TP must be above entry for BUY"
        else:  # SELL
            if stop_price <= entry_price:
                return stop_price, tp_price, False, "SL must be above entry for SELL"
            if tp_price >= entry_price:
                return stop_price, tp_price, False, "TP must be below entry for SELL"
        
        # No adjustment needed - broker accepts any distance
        return stop_price, tp_price, True, "Valid stops (no minimum required)"
    
    # If no stops_level found, use safe defaults
    if stops_level is None:
        stops_level = 30 if symbol_info.digits == 5 else 3
        logger.warning(f"No stops_level attribute for {symbol}, using default: {stops_level} points")
    
    # Convert to price distance
    min_distance = stops_level * point
    logger.debug(f"Minimum stop level: {stops_level} points ({min_distance:.5f} price)")
    
    # Add buffer (20% extra for safety)
    safe_distance = min_distance * 1.2
    
    if side.lower() in ['buy', 'long']:
        # For BUY orders:
        # SL must be below entry by at least min_distance
        # TP must be above entry by at least min_distance
        
        # Check and adjust SL
        current_sl_distance = entry_price - stop_price
        if current_sl_distance < safe_distance:
            logger.warning(f"SL too close! Current: {current_sl_distance:.5f}, Required: {safe_distance:.5f}")
            stop_price = entry_price - safe_distance
            logger.warning(f"Adjusted SL to: {stop_price:.5f}")
        
        # Check and adjust TP
        current_tp_distance = tp_price - entry_price
        if current_tp_distance < safe_distance:
            logger.warning(f"TP too close! Current: {current_tp_distance:.5f}, Required: {safe_distance:.5f}")
            tp_price = entry_price + safe_distance
            logger.warning(f"Adjusted TP to: {tp_price:.5f}")
        
        # Final validation
        if stop_price >= entry_price:
            return stop_price, tp_price, False, "SL must be below entry for BUY"
        if tp_price <= entry_price:
            return stop_price, tp_price, False, "TP must be above entry for BUY"
    
    else:  # SELL
        # For SELL orders:
        # SL must be above entry by at least min_distance
        # TP must be below entry by at least min_distance
        
        # Check and adjust SL
        current_sl_distance = stop_price - entry_price
        if current_sl_distance < safe_distance:
            logger.warning(f"SL too close! Current: {current_sl_distance:.5f}, Required: {safe_distance:.5f}")
            stop_price = entry_price + safe_distance
            logger.warning(f"Adjusted SL to: {stop_price:.5f}")
        
        # Check and adjust TP
        current_tp_distance = entry_price - tp_price
        if current_tp_distance < safe_distance:
            logger.warning(f"TP too close! Current: {current_tp_distance:.5f}, Required: {safe_distance:.5f}")
            tp_price = entry_price - safe_distance
            logger.warning(f"Adjusted TP to: {tp_price:.5f}")
        
        # Final validation
        if stop_price <= entry_price:
            return stop_price, tp_price, False, "SL must be above entry for SELL"
        if tp_price >= entry_price:
            return stop_price, tp_price, False, "TP must be below entry for SELL"
    
    return stop_price, tp_price, True, "Valid stops"


# --------------------------- ORDER EXECUTION ----------------------------

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


def place_market_order(symbol, side, volume, sl, tp):
    """
    Place market order with FIXED execution logic
    
    CRITICAL FIXES:
    1. Uses current tick price (not bar close)
    2. Validates stops against broker minimum levels
    3. Proper filling type detection
    4. Price normalization
    5. Retry logic with fresh prices
    6. Safe CONFIG access with defaults
    7. Better error logging
    """
    try:
        symbol_info = get_symbol_info(symbol)
        
        # Determine proper filling type
        filling_type = determine_filling_type(symbol)
        
        # Safe CONFIG access with defaults
        max_retries = CONFIG.get('max_retries', 3)
        retry_delay = CONFIG.get('retry_delay', 0.5)
        slippage = CONFIG.get('slippage_points', 50)
        
        logger.debug(f"Order config - Max retries: {max_retries}, Retry delay: {retry_delay}s, Slippage: {slippage}")
        logger.debug(f"Target SL: {sl:.5f}, TP: {tp:.5f}")
        
        # Retry loop for order placement
        for attempt in range(max_retries):
            try:
                # Get FRESH tick price for this attempt
                current_price = get_current_price(symbol, side)
                
                logger.debug(f"Attempt {attempt + 1}/{max_retries}: Current price = {current_price:.5f}")
                
                # CRITICAL: Adjust stops based on ACTUAL entry price
                adjusted_sl, adjusted_tp, is_valid, error_msg = adjust_stops_to_broker_limits(
                    symbol, side, current_price, sl, tp
                )
                
                if not is_valid:
                    logger.error(f"Stop adjustment failed: {error_msg}")
                    raise RuntimeError(f"Cannot adjust stops to valid levels: {error_msg}")
                
                # Log adjustments if made
                if abs(adjusted_sl - sl) > symbol_info.point:
                    logger.info(f"Stop Loss adjusted: {sl:.5f} → {adjusted_sl:.5f}")
                if abs(adjusted_tp - tp) > symbol_info.point:
                    logger.info(f"Take Profit adjusted: {tp:.5f} → {adjusted_tp:.5f}")
                
                # Normalize all prices
                price = normalize_price(symbol, current_price)
                adjusted_sl = normalize_price(symbol, adjusted_sl)
                adjusted_tp = normalize_price(symbol, adjusted_tp)
                
                logger.info(f"Attempt {attempt + 1}: {side.upper()} {volume} lots @ {price:.5f}")
                logger.info(f"  SL: {adjusted_sl:.5f}, TP: {adjusted_tp:.5f}, Filling: {filling_type}")
                
                # Build request with safe CONFIG access
                request = {
                    'action': mt5.TRADE_ACTION_DEAL,
                    'symbol': symbol,
                    'volume': volume,
                    'type': mt5.ORDER_TYPE_BUY if side == 'buy' else mt5.ORDER_TYPE_SELL,
                    'price': price,
                    'sl': adjusted_sl,
                    'tp': adjusted_tp,
                    'deviation': slippage,
                    'magic': 234000,
                    'comment': 'ICT Fibonacci Bot',
                    'type_time': mt5.ORDER_TIME_GTC,
                    'type_filling': filling_type,
                }
                
                logger.debug(f"Sending order: {request}")
                
                # Send order
                result = mt5.order_send(request)
                
                if result is None:
                    error = mt5.last_error()
                    logger.error(f"Order send returned None: {error}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise RuntimeError(f"Order failed after {max_retries} attempts: {error}")
                
                logger.debug(f"Order result - retcode: {result.retcode}, order: {result.order}, deal: {result.deal}")
                
                # Check result
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"✓ Order executed successfully: {result.order}")
                    logger.info(f"  Deal: {result.deal}, Volume: {result.volume}, Price: {result.price:.5f}")
                    return result
                
                elif result.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_OFF]:
                    logger.warning(f"Price changed (code {result.retcode}), retrying...")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                
                elif result.retcode == mt5.TRADE_RETCODE_INVALID_FILL:
                    logger.warning(f"Invalid fill type {filling_type}, trying alternative...")
                    if filling_type == mt5.ORDER_FILLING_FOK:
                        filling_type = mt5.ORDER_FILLING_IOC
                    elif filling_type == mt5.ORDER_FILLING_IOC:
                        filling_type = mt5.ORDER_FILLING_RETURN
                    
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                
                elif result.retcode == 10016:  # Invalid stops
                    logger.error("❌ Stop levels are invalid even after adjustment")
                    logger.error(f"Entry: {price:.5f}")
                    logger.error(f"SL: {adjusted_sl:.5f} (distance: {abs(price - adjusted_sl):.5f})")
                    logger.error(f"TP: {adjusted_tp:.5f} (distance: {abs(price - adjusted_tp):.5f})")
                    
                    try:
                        min_level = symbol_info.trade_stops_level
                        logger.error(f"Min stop level: {min_level} points")
                    except:
                        pass
                    
                    raise RuntimeError(f"Order failed: {result.retcode} - {result.comment}")
                
                else:
                    error_msg = f"Order failed: {result.retcode} - {result.comment}"
                    logger.error(error_msg)
                    
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise RuntimeError(error_msg)
            
            except Exception as e:
                logger.error(f"Exception during order placement attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    raise
        
        raise RuntimeError(f"Order failed after {max_retries} attempts")
    
    except Exception as e:
        logger.error(f"Fatal error in place_market_order: {e}", exc_info=True)
        raise

"""
FIXED load_history_from_mt5() - Handles timezone properly
MT5 uses UTC, so we need to convert to local time or use UTC consistently
"""

def load_history_from_mt5(self):
    """
    Load today's closed trades from MT5 account history on startup
    FIXED: Handles timezone properly (MT5 uses UTC)
    """
    if not MT5_AVAILABLE:
        logger.debug("MT5 not available, skipping history load")
        return
    
    try:
        from datetime import datetime, date, time as dt_time
        import pytz
        import MetaTrader5 as mt5_api
        
        logger.info("")
        logger.info("="*70)
        logger.info("📊 LOADING TODAY'S TRADE HISTORY FROM MT5")
        logger.info("="*70)
        
        # MT5 uses UTC timezone
        # Get today's start and end in UTC
        utc_tz = pytz.UTC
        local_tz = pytz.timezone('UTC')  # Change this to your timezone if needed
        # Examples:
        # pytz.timezone('America/New_York')  # EST/EDT
        # pytz.timezone('Europe/London')     # GMT/BST
        # pytz.timezone('Asia/Dubai')        # GST
        # pytz.timezone('Asia/Karachi')      # PKT (Pakistan)

        # Get today's date in local time
        today_local = date.today()
        
        # Convert to UTC for MT5 query
        today_start_local = datetime.combine(today_local, dt_time.min)
        today_end_local = datetime.combine(today_local, dt_time.max)
        
        # Localize to your timezone
        today_start_local = local_tz.localize(today_start_local)
        today_end_local = local_tz.localize(today_end_local)
        
        # Convert to UTC for MT5
        today_start_utc = today_start_local.astimezone(utc_tz)
        today_end_utc = today_end_local.astimezone(utc_tz)
        
        logger.info(f"Local timezone: {local_tz}")
        logger.info(f"Fetching deals from {today_start_utc} to {today_end_utc} (UTC)")
        logger.debug(f"Local time: {today_start_local} to {today_end_local}")
        
        # Fetch all deals for today (MT5 expects UTC)
        deals = mt5_api.history_deals_get(today_start_utc, today_end_utc)
        
        if deals is None:
            logger.info("No trades found in MT5 history for today")
            logger.info("="*70)
            return
        
        if len(deals) == 0:
            logger.info("No trades found in MT5 history for today")
            logger.info("="*70)
            return
        
        logger.debug(f"Found {len(deals)} total deals in history")
        
        # Process deals - only count closing deals that are losses
        processed_count = 0
        loss_count = 0
        
        for deal in deals:
            try:
                # Only process our bot's trades (magic number 234000)
                if deal.magic != 234000:
                    continue
                
                processed_count += 1
                
                # Only process closing deals (exit from position)
                # DEAL_ENTRY_OUT = 1
                if deal.entry != 1:  # 1 = DEAL_ENTRY_OUT
                    continue
                
                # Only process losing trades
                if deal.profit >= 0:
                    continue
                
                # This is a loss
                loss_count += 1
                loss_amount = abs(deal.profit)
                symbol = deal.symbol
                
                # Add to trackers
                self.daily_losses['global'] += loss_amount
                self.loss_count['global'] += 1
                
                self.daily_losses[symbol] += loss_amount
                self.loss_count[symbol] += 1
                
                logger.debug(f"Loaded loss: {symbol} -${loss_amount:.2f}")
            
            except Exception as e:
                logger.debug(f"Error processing deal: {e}")
                continue
        
        logger.info("")
        logger.info(f"✓ Loaded {processed_count} bot trades from history")
        logger.info(f"✓ Found {loss_count} losing trades")
        logger.info("")
        
        if loss_count > 0:
            logger.info("Current Daily Loss Status:")
            logger.info(f"  Global losses: ${self.daily_losses['global']:.2f} ({self.loss_count['global']} trades)")
            
            for symbol in self.daily_losses:
                if symbol != 'global':
                    logger.info(f"  {symbol}: ${self.daily_losses[symbol]:.2f} ({self.loss_count[symbol]} trades)")
        else:
            logger.info("No losing trades found in history")
        
        logger.info("="*70)
        
    except ImportError as e:
        logger.warning(f"Required module not available: {e}")
        logger.warning("Install pytz: pip install pytz")
    except Exception as e:
        logger.warning(f"Error loading history from MT5: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        logger.info("="*70)

# --------------------------- POSITION MANAGEMENT ----------------------------

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
    """
    Get all open positions, optionally filtered by symbol
    
    CRITICAL FIX: Ensures consistent return type (always list or empty list)
    Never returns None
    
    Returns:
        list: List of open positions (empty list if none found)
    """
    if not MT5_AVAILABLE:
        logger.debug("MT5 not available, returning empty position list")
        return []
    
    try:
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
            logger.debug(f"Fetched positions for {symbol}: {type(positions)}, {len(positions) if positions else 0} positions")
        else:
            positions = mt5.positions_get()
            logger.debug(f"Fetched all positions: {type(positions)}, {len(positions) if positions else 0} positions")
        
        # Handle None return from MT5
        if positions is None:
            logger.debug(f"mt5.positions_get() returned None for symbol={symbol}")
            return []
        
        # Handle empty tuple/list
        if len(positions) == 0:
            logger.debug(f"No positions found for symbol={symbol}")
            return []
        
        # Convert tuple to list if needed
        position_list = list(positions)
        logger.debug(f"Returning {len(position_list)} positions")
        return position_list
    
    except Exception as e:
        logger.error(f"Error fetching positions (symbol={symbol}): {e}")
        return []


def count_open_positions(symbol=None):
    """
    Get count of open positions
    
    Args:
        symbol: Optional symbol to filter by
    
    Returns:
        int: Number of open positions
    """
    try:
        positions = get_open_positions(symbol=symbol)
        
        if not positions:
            return 0
        
        # Filter for our bot's trades only (magic number 234000)
        our_positions = [p for p in positions if p.magic == 234000]
        
        count = len(our_positions)
        logger.debug(f"Count open positions (symbol={symbol}): {count}/{len(positions)} are ours")
        
        return count
    
    except Exception as e:
        logger.error(f"Error counting positions: {e}")
        return 0


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
            'deviation': CONFIG.get('slippage_points', 50),
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