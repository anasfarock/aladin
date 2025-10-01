"""
Risk Management Module
Handles trailing stops, position monitoring, and risk calculations
"""

import logging
from config import CONFIG, MT5_AVAILABLE, mt5

if MT5_AVAILABLE:
    from mt5_handler import update_position_sl_tp, get_open_positions

logger = logging.getLogger(__name__)

# --------------------------- TRAILING STOPS ----------------------------

def update_trailing_stop(position, current_price):
    """
    Update trailing stop loss based on profit levels
    
    Args:
        position: dict with entry, stop, side, etc.
        current_price: current market price
    
    Returns:
        Updated position dict
    """
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
    
    # Find highest applicable trailing level
    for level, trail_ratio in sorted(CONFIG['trailing_levels'].items(), reverse=True):
        if profit_ratio >= level:
            applicable_level = level
            trail_to_ratio = trail_ratio
            break
    
    if applicable_level is None:
        return position
    
    # Calculate new stop
    if side == 'long':
        new_stop = entry_price + (trail_to_ratio * initial_risk)
        if new_stop > current_stop:
            position['stop'] = new_stop
            position['trailing_active'] = True
            position['trail_level'] = applicable_level
            logger.info(f"Trailing stop updated: {current_stop:.5f} -> {new_stop:.5f} (Level: {applicable_level}R)")
    else:
        new_stop = entry_price - (trail_to_ratio * initial_risk)
        if new_stop < current_stop:
            position['stop'] = new_stop
            position['trailing_active'] = True
            position['trail_level'] = applicable_level
            logger.info(f"Trailing stop updated: {current_stop:.5f} -> {new_stop:.5f} (Level: {applicable_level}R)")
    
    return position

def monitor_live_positions(symbol):
    """
    Monitor and update trailing stops for live positions
    
    This function checks all open positions and applies trailing stop logic
    """
    if not CONFIG['trailing_stop'] or not MT5_AVAILABLE:
        return
    
    try:
        positions = get_open_positions(symbol=symbol)
        
        if not positions:
            return
        
        for position in positions:
            # Only manage our bot's positions
            if position.magic != 234000:
                continue
            
            ticket = position.ticket
            entry_price = position.price_open
            current_sl = position.sl
            position_type = position.type
            
            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue
            
            current_price = tick.bid if position_type == mt5.POSITION_TYPE_BUY else tick.ask
            is_long = position_type == mt5.POSITION_TYPE_BUY
            
            # Calculate profit and risk
            if is_long:
                profit_points = current_price - entry_price
                original_risk = entry_price - current_sl
            else:
                profit_points = entry_price - current_price
                original_risk = current_sl - entry_price
            
            if original_risk <= 0 or profit_points <= 0:
                continue
            
            profit_ratio = profit_points / original_risk
            
            # Find applicable trailing level
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
            
            # Update if new stop is better
            if new_sl is not None:
                logger.info(f"Updating trailing stop for position {ticket}: {current_sl:.5f} -> {new_sl:.5f}")
                update_position_sl_tp(ticket, symbol, new_sl, position.tp)
    
    except Exception as e:
        logger.error(f"Error monitoring positions: {e}")

def calculate_position_size(symbol, entry_price, stop_price, account_balance):
    """
    Calculate position size based on risk percentage
    
    Returns:
        tuple: (volume, risk_amount)
    """
    from mt5_handler import calc_volume
    
    risk_amount = (CONFIG['risk_pct'] / 100.0) * account_balance
    volume = calc_volume(symbol, entry_price, stop_price, risk_amount)
    
    return volume, risk_amount

def validate_trade_setup(entry_price, stop_price, tp_price, side):
    """
    Validate that trade setup makes sense
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if side == 'long':
        if stop_price >= entry_price:
            return False, "Stop loss must be below entry for long trades"
        
        if tp_price <= entry_price:
            return False, "Take profit must be above entry for long trades"
        
        risk = entry_price - stop_price
        reward = tp_price - entry_price
    
    else:  # short
        if stop_price <= entry_price:
            return False, "Stop loss must be above entry for short trades"
        
        if tp_price >= entry_price:
            return False, "Take profit must be below entry for short trades"
        
        risk = stop_price - entry_price
        reward = entry_price - tp_price
    
    if risk <= 0:
        return False, "Invalid risk calculation"
    
    if reward <= 0:
        return False, "Invalid reward calculation"
    
    rr_ratio = reward / risk
    
    if rr_ratio < CONFIG['min_rr_ratio']:
        return False, f"Risk/Reward ratio {rr_ratio:.2f} below minimum {CONFIG['min_rr_ratio']}"
    
    return True, None

def check_max_positions_reached(symbol):
    """
    Check if maximum number of concurrent positions is reached
    
    Returns:
        bool: True if max reached
    """
    if not MT5_AVAILABLE:
        return False
    
    positions = get_open_positions(symbol=symbol)
    
    # Count only our bot's positions
    our_positions = [p for p in positions if p.magic == 234000]
    
    return len(our_positions) >= CONFIG['max_concurrent_trades']