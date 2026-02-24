"""
Risk Management Module - FIXED with Clear Limit Separation
Handles trailing stops, position monitoring, risk calculations, ATR stops, and daily loss tracking

KEY FIX: Clearly separated POSITION LIMITS from LOSS LIMITS
- Position limits check OPEN TRADES RIGHT NOW
- Loss limits check LOSING TRADES TODAY
"""

import logging
import pandas as pd
from datetime import datetime, date
from collections import defaultdict
from config import CONFIG, MT5_AVAILABLE, mt5

if MT5_AVAILABLE:
    from mt5_handler import update_position_sl_tp, get_open_positions

logger = logging.getLogger(__name__)

# ========================== DAILY LOSS TRACKING ==========================

class DailyLossTracker:
    """
    Tracks daily losses globally and per-symbol to enforce daily loss limits
    Resets at midnight (configurable)
    
    IMPORTANT: This tracks LOSING TRADES only, NOT position count
    """
    
    def __init__(self):
        self.daily_losses = defaultdict(float)  # 'global' -> total losses, 'EURUSD' -> pair-specific losses
        self.loss_count = defaultdict(int)      # Count of LOSING trades (not total trades)
        self.last_reset_date = date.today()
        self.closed_trades = defaultdict(list)  # Track closed trades for auditing
    
    def load_history_from_mt5(self):
        """
        Load today's closed trades from MT5 account history on startup
        This ensures we track losses even if the bot restarted
        """
        if not MT5_AVAILABLE:
            logger.debug("MT5 not available, skipping history load")
            return
        
        try:
            import MetaTrader5 as mt5
            from datetime import datetime, timedelta
            
            logger.info("")
            logger.info("="*70)
            logger.info("📊 LOADING TODAY'S TRADE HISTORY FROM MT5")
            logger.info("="*70)
            
            # Get today's date at midnight
            today_start = datetime.combine(date.today(), datetime.min.time())
            today_end = datetime.now()
            
            logger.debug(f"Fetching deals from {today_start} to {today_end}")
            
            # Fetch all deals for today
            deals = mt5.history_deals_get(today_start, today_end)
            
            if deals is None:
                logger.info("No trades found in MT5 history for today")
                return
            
            if len(deals) == 0:
                logger.info("No trades found in MT5 history for today")
                return
            
            logger.debug(f"Found {len(deals)} total deals in history")
            
            # Process deals - only count closing deals that are losses
            processed_count = 0
            loss_count = 0
            
            for deal in deals:
                # Only process our bot's trades (magic number 234000)
                if deal.magic != 234000:
                    continue
                
                processed_count += 1
                
                # Only process closing deals (exit from position)
                if deal.entry != mt5.DEAL_ENTRY_OUT:
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
            
            logger.info("")
            logger.info(f"✓ Loaded {processed_count} bot trades from history")
            logger.info(f"✓ Found {loss_count} losing trades")
            logger.info("")
            logger.info("Current Daily Loss Status:")
            logger.info(f"  Global losses: ${self.daily_losses['global']:.2f} ({self.loss_count['global']} trades)")
            
            for symbol in self.daily_losses:
                if symbol != 'global':
                    logger.info(f"  {symbol}: ${self.daily_losses[symbol]:.2f} ({self.loss_count[symbol]} trades)")
            
            logger.info("="*70)
            
        except Exception as e:
            logger.warning(f"Error loading history from MT5: {e}")
    
    def _check_and_reset_if_needed(self, simulated_date=None):
        """Check if it's a new day and reset counters"""
        if simulated_date is not None:
            # Handle pandas Timestamp
            if hasattr(simulated_date, 'date'):
                current_date = simulated_date.date()
            else:
                current_date = simulated_date
        else:
            current_date = date.today()
            
        if current_date != self.last_reset_date:
            self._reset_daily_counters(current_date)
    
    def _reset_daily_counters(self, current_date):
        """Reset daily loss tracking"""
        if self.daily_losses or self.loss_count:
            logger.info(f"")
            logger.info(f"{'='*70}")
            logger.info(f"📅 NEW DAY - RESETTING DAILY LOSS COUNTERS")
            logger.info(f"Previous day summary:")
            logger.info(f"  Global losses: ${self.daily_losses.get('global', 0):.2f}")
            logger.info(f"  Global loss count: {self.loss_count.get('global', 0)} losing trades")
            for symbol in self.daily_losses:
                if symbol != 'global':
                    logger.info(f"  {symbol}: ${self.daily_losses[symbol]:.2f} ({self.loss_count[symbol]} losing trades)")
            logger.info(f"{'='*70}")
        
        self.daily_losses.clear()
        self.loss_count.clear()
        self.closed_trades.clear()
        self.last_reset_date = current_date
        logger.info(f"Daily loss counters reset for {current_date}")
    
    def record_loss(self, symbol, loss_amount):
        """
        Record a LOSING trade (only for trades that lost money)
        
        Args:
            symbol: Trading pair (e.g., 'EURUSD')
            loss_amount: Loss amount (positive value, e.g., 50.00 not -50.00)
        """
        self._check_and_reset_if_needed()
        
        if loss_amount <= 0:
            logger.warning(f"Invalid loss amount: {loss_amount}. Skipping record.")
            return
        
        # Update global losses
        self.daily_losses['global'] += loss_amount
        self.loss_count['global'] += 1
        
        # Update symbol-specific losses
        self.daily_losses[symbol] += loss_amount
        self.loss_count[symbol] += 1
        
        # Track for auditing
        self.closed_trades['global'].append({
            'timestamp': datetime.now(),
            'symbol': symbol,
            'loss': loss_amount,
            'type': 'loss'
        })
        self.closed_trades[symbol].append({
            'timestamp': datetime.now(),
            'loss': loss_amount,
            'type': 'loss'
        })
        
        logger.info(f"")
        logger.info(f"{'='*70}")
        logger.info(f"💔 LOSS RECORDED")
        logger.info(f"  Symbol: {symbol}")
        logger.info(f"  Loss Amount: ${loss_amount:.2f}")
        logger.info(f"  Global Losses Today: ${self.daily_losses['global']:.2f} ({self.loss_count['global']} losses)")
        logger.info(f"  {symbol} Losses Today: ${self.daily_losses[symbol]:.2f} ({self.loss_count[symbol]} losses)")
        logger.info(f"{'='*70}")
    
    def can_trade(self, symbol, simulated_date=None):
        """
        Check if trading is allowed based on daily LOSS limits
        
        This checks if we've hit our maximum losing trades for the day
        NOT about position count!
        
        Returns:
            tuple: (is_allowed, reason_string)
        """
        self._check_and_reset_if_needed(simulated_date)
        
        max_daily_losses = CONFIG.get('max_daily_losses', -1)
        max_daily_loss_count = CONFIG.get('max_daily_loss_count', -1)
        max_daily_losses_per_symbol = CONFIG.get('max_daily_losses_per_symbol', -1)
        max_daily_loss_count_per_symbol = CONFIG.get('max_daily_loss_count_per_symbol', -1)
        
        current_daily_losses = self.daily_losses.get('global', 0)
        current_loss_count = self.loss_count.get('global', 0)
        symbol_daily_losses = self.daily_losses.get(symbol, 0)
        symbol_loss_count = self.loss_count.get(symbol, 0)

        logger.debug(f"Daily Loss Limit Check for {symbol}:")
        logger.debug(f"  Global: ${current_daily_losses:.2f}/{max_daily_losses if max_daily_losses > 0 else 'unlimited'} | {current_loss_count}/{max_daily_loss_count if max_daily_loss_count > 0 else 'unlimited'} losses")
        logger.debug(f"  {symbol}: ${symbol_daily_losses:.2f}/{max_daily_losses_per_symbol if max_daily_losses_per_symbol > 0 else 'unlimited'} | {symbol_loss_count}/{max_daily_loss_count_per_symbol if max_daily_loss_count_per_symbol > 0 else 'unlimited'} losses")
        
        # -1 means unlimited
        if (max_daily_losses == -1 and max_daily_losses_per_symbol == -1 and
            max_daily_loss_count == -1 and max_daily_loss_count_per_symbol == -1):
            return True, "✓ No daily loss limits configured"
        
        # Check global daily loss limit
        if max_daily_losses != -1 and current_daily_losses >= max_daily_losses:
            return False, (f"⛔ Global daily loss limit reached: "
                         f"${current_daily_losses:.2f}/${max_daily_losses:.2f}")
        
        # Check global daily loss count limit (THIS IS THE LOSING TRADE COUNT)
        if max_daily_loss_count != -1 and current_loss_count >= max_daily_loss_count:
            return False, (f"⛔ Global daily loss count limit reached: "
                         f"{current_loss_count}/{max_daily_loss_count} losing trades")
        
        # Check per-symbol daily loss limit
        if max_daily_losses_per_symbol != -1 and symbol_daily_losses >= max_daily_losses_per_symbol:
            return False, (f"⛔ Daily loss limit for {symbol} reached: "
                         f"${symbol_daily_losses:.2f}/${max_daily_losses_per_symbol:.2f}")
        
        # Check per-symbol daily loss count limit (THIS IS THE LOSING TRADE COUNT FOR THE SYMBOL)
        if max_daily_loss_count_per_symbol != -1 and symbol_loss_count >= max_daily_loss_count_per_symbol:
            return False, (f"⛔ Daily loss count limit for {symbol} reached: "
                         f"{symbol_loss_count}/{max_daily_loss_count_per_symbol} losing trades")
        
        return True, "✓ Trading allowed (loss limits OK)"
    
    def get_daily_summary(self):
        """
        Get current day's loss summary
        
        Returns:
            dict with global and per-symbol stats
        """
        self._check_and_reset_if_needed()
        
        summary = {
            'date': str(self.last_reset_date),
            'global': {
                'total_losses': self.daily_losses.get('global', 0),
                'loss_count': self.loss_count.get('global', 0),
                'max_allowed': CONFIG.get('max_daily_losses', -1),
                'max_allowed_count': CONFIG.get('max_daily_loss_count', -1),
            },
            'per_symbol': {}
        }
        
        for symbol in self.daily_losses:
            if symbol != 'global':
                summary['per_symbol'][symbol] = {
                    'total_losses': self.daily_losses[symbol],
                    'loss_count': self.loss_count[symbol],
                    'max_allowed': CONFIG.get('max_daily_losses_per_symbol', -1),
                    'max_allowed_count': CONFIG.get('max_daily_loss_count_per_symbol', -1),
                }
        
        return summary
    
    def log_daily_summary(self):
        """Log the current day's summary"""
        summary = self.get_daily_summary()
        logger.info("")
        logger.info("="*70)
        logger.info("📊 DAILY LOSS SUMMARY (Losing Trades Only)")
        logger.info(f"Date: {summary['date']}")
        logger.info("-"*70)
        
        global_stats = summary['global']
        logger.info(f"GLOBAL:")

        # Total Losses line
        if global_stats['max_allowed'] > 0:
            logger.info(f"  Total Losses: ${global_stats['total_losses']:.2f} / ${global_stats['max_allowed']:.2f}")
        else:
            logger.info(f"  Total Losses: ${global_stats['total_losses']:.2f} (unlimited)")
        
        # Losing Trades line
        if global_stats['max_allowed_count'] > 0:
            logger.info(f"  Losing Trades: {global_stats['loss_count']} / {global_stats['max_allowed_count']}")
        else:
            logger.info(f"  Losing Trades: {global_stats['loss_count']} (unlimited)")
        
        if summary['per_symbol']:
            logger.info("-"*70)
            logger.info("PER-SYMBOL:")
            for symbol, stats in summary['per_symbol'].items():
                logger.info(f"  {symbol}:")
                
                # Losses line
                if stats['max_allowed'] > 0:
                    logger.info(f"    Losses: ${stats['total_losses']:.2f} / ${stats['max_allowed']:.2f}")
                else:
                    logger.info(f"    Losses: ${stats['total_losses']:.2f} (unlimited)")
                
                # Losing Trades line
                if stats['max_allowed_count'] > 0:
                    logger.info(f"    Losing Trades: {stats['loss_count']} / {stats['max_allowed_count']}")
                else:
                    logger.info(f"    Losing Trades: {stats['loss_count']} (unlimited)")
        
        logger.info("="*70)

# Global instance
daily_loss_tracker = DailyLossTracker()

# Initialize tracker from MT5 history on startup
def initialize_daily_loss_tracker():
    """
    Initialize the daily loss tracker by loading history from MT5
    Call this at bot startup AFTER MT5 connection is established
    """
    logger.info("Initializing daily loss tracker from MT5 history...")
    daily_loss_tracker.load_history_from_mt5()

def check_daily_loss_limit(symbol):
    """
    Check if trading is allowed based on daily LOSS limits
    
    This checks if we've exceeded our maximum losing trades for the day
    NOT about how many positions are open!
    
    Args:
        symbol: Trading pair
    
    Returns:
        tuple: (is_allowed, reason)
    """
    return daily_loss_tracker.can_trade(symbol)


def record_trade_loss(symbol, loss_amount):
    """
    Record a LOSING trade
    
    Args:
        symbol: Trading pair
        loss_amount: Loss amount (positive value, e.g., 50.00)
    """
    daily_loss_tracker.record_loss(symbol, loss_amount)


def get_daily_loss_summary():
    """Get current day's loss summary"""
    return daily_loss_tracker.get_daily_summary()


def log_daily_loss_summary():
    """Log the current day's summary"""
    daily_loss_tracker.log_daily_summary()


# ========================== ATR-BASED STOP LOSS ==========================

def calculate_atr_stop_loss(df, entry_price, side, atr_multiplier=None):
    """
    Calculate stop loss based on ATR (Average True Range)
    
    Args:
        df: DataFrame with OHLC and ATR data
        entry_price: Entry price of the trade
        side: 'long' or 'short'
        atr_multiplier: Optional multiplier override (uses CONFIG if None)
    
    Returns:
        dict: {
            'stop_price': float,
            'atr_value': float,
            'distance_pips': float,
            'method': str
        }
        or None if ATR cannot be calculated
    """
    if df.empty or len(df) == 0:
        return None
    
    if not CONFIG.get('use_atr_stops', False):
        return None
    
    try:
        # Get ATR value from last bar
        atr_value = df.iloc[-1].get('atr')
        
        # Check if ATR exists and is valid
        if atr_value is None or pd.isna(atr_value) or atr_value <= 0:
            logger.debug("ATR value not available or invalid")
            return None
        
        # Use provided multiplier or CONFIG value
        if atr_multiplier is None:
            atr_multiplier = CONFIG.get('atr_stop_multiplier', 2.0)
        
        # Calculate stop distance based on ATR
        atr_stop_distance = atr_value * atr_multiplier
        
        # Calculate stop price
        if side == 'long':
            stop_price = entry_price - atr_stop_distance
        else:  # short
            stop_price = entry_price + atr_stop_distance
        
        distance_pips = atr_stop_distance * 10000
        
        return {
            'stop_price': stop_price,
            'atr_value': atr_value,
            'distance_pips': distance_pips,
            'method': 'ATR'
        }
    
    except Exception as e:
        logger.debug(f"Error calculating ATR stop loss: {e}")
        return None


def compare_stop_loss_methods(df, entry_price, side, fib_stop_price):
    """
    Compare ATR-based stop loss with Fibonacci stop loss
    Returns the one that provides better risk management
    
    Args:
        df: DataFrame with OHLC and ATR data
        entry_price: Entry price
        side: 'long' or 'short'
        fib_stop_price: Stop price from Fibonacci analysis
    
    Returns:
        dict: {
            'stop_price': float (selected),
            'atr_stop': float or None,
            'fib_stop': float,
            'selected_method': str,
            'reason': str
        }
    """
    if not CONFIG.get('use_atr_stops', False):
        return {
            'stop_price': fib_stop_price,
            'atr_stop': None,
            'fib_stop': fib_stop_price,
            'selected_method': 'Fibonacci',
            'reason': 'ATR stops disabled'
        }
    
    atr_result = calculate_atr_stop_loss(df, entry_price, side)
    
    # If ATR calculation fails, fall back to Fibonacci
    if atr_result is None:
        return {
            'stop_price': fib_stop_price,
            'atr_stop': None,
            'fib_stop': fib_stop_price,
            'selected_method': 'Fibonacci',
            'reason': 'ATR calculation failed, using Fibonacci'
        }
    
    atr_stop = atr_result['stop_price']
    method_preference = CONFIG.get('atr_stop_method', 'wider')
    
    try:
        if side == 'long':
            atr_distance = entry_price - atr_stop
            fib_distance = entry_price - fib_stop_price
            
            if atr_distance <= 0 or fib_distance <= 0:
                return {
                    'stop_price': fib_stop_price,
                    'atr_stop': atr_stop,
                    'fib_stop': fib_stop_price,
                    'selected_method': 'Fibonacci',
                    'reason': 'Invalid ATR distance, using Fibonacci'
                }
            
            if method_preference == 'wider':
                if atr_stop < fib_stop_price:
                    selected_stop = atr_stop
                    selected_method = 'ATR'
                    reason = f"ATR stop is wider (less risk): {atr_distance:.5f} vs {fib_distance:.5f}"
                else:
                    selected_stop = fib_stop_price
                    selected_method = 'Fibonacci'
                    reason = f"Fibonacci stop is wider: {fib_distance:.5f} vs {atr_distance:.5f}"
            
            elif method_preference == 'tighter':
                if atr_stop > fib_stop_price:
                    selected_stop = atr_stop
                    selected_method = 'ATR'
                    reason = f"ATR stop is tighter (more precise): {atr_distance:.5f} vs {fib_distance:.5f}"
                else:
                    selected_stop = fib_stop_price
                    selected_method = 'Fibonacci'
                    reason = f"Fibonacci stop is tighter: {fib_distance:.5f} vs {atr_distance:.5f}"
            
            else:
                selected_stop = fib_stop_price
                selected_method = 'Fibonacci'
                reason = "Using Fibonacci stop (preference)"
        
        else:  # short
            atr_distance = atr_stop - entry_price
            fib_distance = fib_stop_price - entry_price
            
            if atr_distance <= 0 or fib_distance <= 0:
                return {
                    'stop_price': fib_stop_price,
                    'atr_stop': atr_stop,
                    'fib_stop': fib_stop_price,
                    'selected_method': 'Fibonacci',
                    'reason': 'Invalid ATR distance, using Fibonacci'
                }
            
            if method_preference == 'wider':
                if atr_stop > fib_stop_price:
                    selected_stop = atr_stop
                    selected_method = 'ATR'
                    reason = f"ATR stop is wider (less risk): {atr_distance:.5f} vs {fib_distance:.5f}"
                else:
                    selected_stop = fib_stop_price
                    selected_method = 'Fibonacci'
                    reason = f"Fibonacci stop is wider: {fib_distance:.5f} vs {atr_distance:.5f}"
            
            elif method_preference == 'tighter':
                if atr_stop < fib_stop_price:
                    selected_stop = atr_stop
                    selected_method = 'ATR'
                    reason = f"ATR stop is tighter (more precise): {atr_distance:.5f} vs {fib_distance:.5f}"
                else:
                    selected_stop = fib_stop_price
                    selected_method = 'Fibonacci'
                    reason = f"Fibonacci stop is tighter: {fib_distance:.5f} vs {atr_distance:.5f}"
            
            else:
                selected_stop = fib_stop_price
                selected_method = 'Fibonacci'
                reason = "Using Fibonacci stop (preference)"
        
        return {
            'stop_price': selected_stop,
            'atr_stop': atr_stop,
            'fib_stop': fib_stop_price,
            'selected_method': selected_method,
            'reason': reason,
            'atr_value': atr_result.get('atr_value') if atr_result else None
        }
    
    except Exception as e:
        logger.debug(f"Error comparing stop loss methods: {e}")
        return {
            'stop_price': fib_stop_price,
            'atr_stop': atr_stop,
            'fib_stop': fib_stop_price,
            'selected_method': 'Fibonacci',
            'reason': f'Error in comparison: {str(e)}'
        }


# ========================== TRAILING STOPS ==========================

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
    """
    if not CONFIG['trailing_stop'] or not MT5_AVAILABLE:
        return
    
    try:
        positions = get_open_positions(symbol=symbol)
        
        if not positions:
            return
        
        for position in positions:
            if position.magic != 234000:
                continue
            
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
                logger.info(f"Updating trailing stop for position {ticket}: {current_sl:.5f} -> {new_sl:.5f}")
                update_position_sl_tp(ticket, symbol, new_sl, position.tp)
    
    except Exception as e:
        logger.error(f"Error monitoring positions: {e}")


# ========================== POSITION SIZING & VALIDATION ==========================

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


# ========================== POSITION LIMITS ==========================
# IMPORTANT: These check OPEN TRADES, not losing trades!

def check_max_positions_reached():
    """
    Check if maximum number of OPEN concurrent positions is reached (global limit)
    
    This checks: How many trades are OPEN RIGHT NOW across ALL symbols?
    Limit: CONFIG['max_concurrent_trades']
    
    Returns:
        bool: True if max OPEN positions reached
    """
    if not MT5_AVAILABLE:
        return False
    
    try:
        # Get all open positions across all symbols
        positions = get_open_positions()
        
        if positions is None:
            return False
        
        # Filter for our bot's trades only
        our_positions = [p for p in positions if p.magic == 234000]
        
        current_open = len(our_positions)
        max_allowed = CONFIG['max_concurrent_trades']
        
        logger.debug(f"Global position check: {current_open}/{max_allowed} open trades")
        
        return current_open >= max_allowed
    
    except Exception as e:
        logger.error(f"Error checking global positions: {e}")
        return False


def check_max_positions_reached_for_symbol(symbol):
    """
    Check if maximum number of OPEN concurrent positions for a specific symbol is reached
    
    This checks: How many trades are OPEN RIGHT NOW on THIS symbol?
    Limit: CONFIG['max_concurrent_trades_of_same_pair']
    
    Returns:
        tuple: (limit_reached, current_count, max_allowed)
    """
    if not MT5_AVAILABLE:
        return False, 0, CONFIG['max_concurrent_trades_of_same_pair']
    
    try:
        # Get all open positions for this symbol
        positions = get_open_positions(symbol=symbol)
        
        if positions is None:
            return False, 0, CONFIG['max_concurrent_trades_of_same_pair']
        
        # Filter for our bot's trades only
        our_positions = [p for p in positions if p.magic == 234000 and p.symbol == symbol]
        
        current_open = len(our_positions)
        max_allowed = CONFIG['max_concurrent_trades_of_same_pair']
        
        logger.debug(f"Per-symbol position check ({symbol}): {current_open}/{max_allowed} open trades")
        
        return current_open >= max_allowed, current_open, max_allowed
    
    except Exception as e:
        logger.error(f"Error checking positions for symbol {symbol}: {e}")
        return False, 0, CONFIG['max_concurrent_trades_of_same_pair']