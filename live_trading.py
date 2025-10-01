"""
Live Trading Engine - ENHANCED FIBONACCI DISPLAY
Shows complete Fibonacci swing range (0.0 and 1.0 levels) with entry level
"""

import time
import logging
from config import CONFIG, MT5_AVAILABLE, logger
from indicators import compute_indicators
from fibonacci import FibonacciTracker, check_fibonacci_entry
from trend_analysis import determine_trend
from risk_management import (
    monitor_live_positions, 
    calculate_position_size,
    validate_trade_setup,
    check_max_positions_reached
)

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

def live_run_once(symbol):
    """
    Execute one live trading cycle
    
    ENHANCED: Now displays complete Fibonacci swing information
    """
    # Monitor existing positions first
    monitor_live_positions(symbol)
    
    # Check if max positions reached
    if check_max_positions_reached(symbol):
        logger.info(f"Max concurrent trades ({CONFIG['max_concurrent_trades']}) reached")
        return None
    
    try:
        # Fetch live data for all timeframes
        logger.debug("Fetching live market data...")
        df_entry = fetch_live_data(symbol, CONFIG['timeframe_entry'], 500)
        df_d1 = fetch_live_data(symbol, 'D1', 500)
        df_h4 = fetch_live_data(symbol, 'H4', 500)
        df_h1 = fetch_live_data(symbol, 'H1', 500)
        
        # Compute indicators
        df_entry = compute_indicators(df_entry)
        df_d1 = compute_indicators(df_d1)
        df_h4 = compute_indicators(df_h4)
        df_h1 = compute_indicators(df_h1)
        
        # Update Fibonacci setups
        fib_tracker.update_fibonacci_setups(df_entry)
        valid_setups = fib_tracker.get_valid_setups()
        
        # Determine trend
        trend = determine_trend(df_d1, df_h4, df_h1)
        
        logger.info(f"Trend: {trend}, Valid Fib Setups: {len(valid_setups)}")
        
        if not valid_setups:
            logger.info("No valid Fibonacci setups found")
            return None
        
        # Check for entry signal
        entry_signal = check_fibonacci_entry(
            valid_setups, 
            df_entry, 
            len(df_entry) - 1, 
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
        
        # Get the complete Fibonacci range from swing points
        if signal_type == 'long':
            # For bullish setup
            swing_low_price = fib_setup['swing_low']['price']
            swing_high_price = fib_setup['swing_high']['price']
            fib_0_price = swing_low_price  # 0.0 = swing low (start of move)
            fib_1_price = swing_high_price  # 1.0 = swing high (end of move)
        else:
            # For bearish setup
            swing_high_price = fib_setup['swing_high']['price']
            swing_low_price = fib_setup['swing_low']['price']
            fib_0_price = swing_high_price  # 0.0 = swing high (start of move)
            fib_1_price = swing_low_price  # 1.0 = swing low (end of move)
        
        # Display entry signal with complete Fibonacci information
        logger.info("="*70)
        logger.info(f"🎯 FIBONACCI ENTRY SIGNAL DETECTED")
        logger.info("="*70)
        logger.info(f"Signal Type: {signal_type.upper()}")
        logger.info(f"Setup: {fib_setup['type']}")
        logger.info("")
        logger.info("📊 FIBONACCI SWING RANGE:")
        logger.info(f"  Fib 0.0 (100% Retracement): {fib_0_price:.5f}")
        logger.info(f"  Fib 1.0 (0% - Swing Point):  {fib_1_price:.5f}")
        logger.info(f"  Swing Size: {abs(fib_1_price - fib_0_price):.5f} ({abs(fib_1_price - fib_0_price) * 10000:.1f} pips)")
        logger.info("")
        logger.info(f"🎯 ENTRY LEVEL:")
        logger.info(f"  Fib {fib_level} Level: {fib_price:.5f}")
        
        # Calculate percentage from swing low/high
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
        
        # Calculate stops and targets
        if signal_type == 'long':
            # For long: Stop below Fib level
            stop_price = fib_price - (CONFIG['fib_tolerance'] * 3)
            
            # Entry will be at CURRENT ASK price (not bar close!)
            entry_approx = df_entry.iloc[-1]['close']
            risk_per_unit = entry_approx - stop_price
            
            if risk_per_unit <= 0:
                logger.warning("Invalid risk calculation, skipping trade")
                return None
            
            tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
            tp_price = entry_approx + tp_distance
            
            side = 'buy'
        
        else:  # short
            # For short: Stop above Fib level
            stop_price = fib_price + (CONFIG['fib_tolerance'] * 3)
            
            entry_approx = df_entry.iloc[-1]['close']
            risk_per_unit = stop_price - entry_approx
            
            if risk_per_unit <= 0:
                logger.warning("Invalid risk calculation, skipping trade")
                return None
            
            tp_distance = CONFIG['min_rr_ratio'] * risk_per_unit
            tp_price = entry_approx - tp_distance
            
            side = 'sell'
        
        # Validate trade setup
        is_valid, error_msg = validate_trade_setup(entry_approx, stop_price, tp_price, signal_type)
        if not is_valid:
            logger.warning(f"Trade validation failed: {error_msg}")
            return None
        
        # Get account balance and calculate position size
        balance = get_account_balance()
        volume, risk_amount = calculate_position_size(symbol, entry_approx, stop_price, balance)
        
        logger.info(f"\n💼 TRADE DETAILS:")
        logger.info(f"  Side: {side.upper()}")
        logger.info(f"  Volume: {volume} lots")
        logger.info(f"  Stop Loss: {stop_price:.5f}")
        logger.info(f"  Take Profit: {tp_price:.5f}")
        logger.info(f"  Risk Amount: ${risk_amount:.2f}")
        logger.info(f"  Risk/Reward: 1:{CONFIG['min_rr_ratio']}")
        
        # Place order - THIS NOW USES CURRENT MARKET PRICE
        logger.info("\n📤 Placing market order...")
        result = place_market_order(symbol, side, volume, stop_price, tp_price)
        
        if result and result.retcode == 10009:  # TRADE_RETCODE_DONE
            logger.info("="*70)
            logger.info(f"✅ TRADE EXECUTED SUCCESSFULLY!")
            logger.info("="*70)
            logger.info(f"  Order ID: {result.order}")
            logger.info(f"  Deal ID: {result.deal}")
            logger.info(f"  Actual Entry: {result.price:.5f}")
            logger.info(f"  Volume: {result.volume} lots")
            logger.info("="*70 + "\n")
            return result
        else:
            logger.error(f"❌ Trade execution failed")
            return None
    
    except Exception as e:
        logger.error(f"Error in live trading cycle: {e}", exc_info=True)
        return None

def start_live_trading(symbol=None):
    """
    Start the live trading bot
    
    Args:
        symbol: Trading symbol (uses CONFIG if None)
    """
    if not MT5_AVAILABLE:
        logger.error("MetaTrader5 not available. Cannot start live trading.")
        return
    
    if symbol is None:
        symbol = CONFIG['symbol']
    
    logger.info("="*60)
    logger.info("ICT FIBONACCI LIVE TRADING BOT")
    logger.info("="*60)
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Entry Timeframe: {CONFIG['timeframe_entry']}")
    logger.info(f"Trend Timeframes: {', '.join(CONFIG['trend_timeframes'])}")
    logger.info(f"Risk per Trade: {CONFIG['risk_pct']}%")
    logger.info(f"Min R:R Ratio: {CONFIG['min_rr_ratio']}")
    logger.info(f"Trailing Stop: {'Enabled' if CONFIG['trailing_stop'] else 'Disabled'}")
    logger.info("="*60)
    
    try:
        # Connect to MT5
        connect_mt5()
        logger.info("✓ Connected to MetaTrader5")
        
        # Get account info
        balance = get_account_balance()
        logger.info(f"✓ Account Balance: ${balance:.2f}")
        
        logger.info("\n🤖 Bot is now running...")
        logger.info("Press Ctrl+C to stop\n")
        
        cycle_count = 0
        
        while True:
            cycle_count += 1
            logger.info(f"\n--- Cycle {cycle_count} ---")
            
            try:
                live_run_once(symbol)
            except Exception as e:
                logger.error(f"Error in trading cycle: {e}", exc_info=True)
            
            # Wait before next cycle
            logger.debug(f"Waiting 60 seconds before next cycle...")
            time.sleep(60)
    
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Keyboard interrupt detected")
        logger.info("Stopping bot...")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    
    finally:
        disconnect_mt5()
        logger.info("✓ Disconnected from MetaTrader5")
        logger.info("Bot stopped.")

if __name__ == '__main__':
    # Can be run directly for testing
    start_live_trading()