"""
ICT Fibonacci Trading Bot - Main Entry Point

Usage:
    # Run backtest
    python main.py --backtest
    
    # Run live trading
    python main.py --live
    
    # Run with custom symbol
    python main.py --live --symbol EURUSD
    
    # Run with manual trend (NEW)
    python main.py --live --manual-trend bullish
    python main.py --backtest --manual-trend bearish
"""

import argparse
import sys
from config import CONFIG, validate_config, MT5_AVAILABLE, logger
from backtest import backtest
from live_trading import start_live_trading

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='ICT Fibonacci Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run backtest with default settings
  python main.py --backtest
  
  # Run live trading
  python main.py --live
  
  # Run with custom symbol
  python main.py --live --symbol EURUSD.raw
  
  # Run backtest with custom dates
  python main.py --backtest --start 2024-01-01 --end 2024-12-31
  
  # Run with manual trend override (NEW)
  python main.py --live --manual-trend bullish
  python main.py --backtest --manual-trend bearish
  python main.py --live --manual-trend neutral
        """
    )
    
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--backtest',
        action='store_true',
        help='Run in backtest mode'
    )
    mode_group.add_argument(
        '--live',
        action='store_true',
        help='Run in live trading mode'
    )
    
    parser.add_argument(
        '--symbol',
        type=str,
        help=f'Trading symbol (default: {CONFIG["symbol"]})'
    )
    
    parser.add_argument(
        '--start',
        type=str,
        help=f'Backtest start date YYYY-MM-DD (default: {CONFIG["start"]})'
    )
    
    parser.add_argument(
        '--end',
        type=str,
        help=f'Backtest end date YYYY-MM-DD (default: {CONFIG["end"]})'
    )
    
    parser.add_argument(
        '--timeframe',
        type=str,
        help=f'Entry timeframe (default: {CONFIG["timeframe_entry"]})'
    )
    
    parser.add_argument(
        '--capital',
        type=float,
        help=f'Starting capital (default: {CONFIG["capital"]})'
    )
    
    parser.add_argument(
        '--risk',
        type=float,
        help=f'Risk per trade percentage (default: {CONFIG["risk_pct"]})'
    )
    
    parser.add_argument(
        '--trailing',
        action='store_true',
        help='Enable trailing stops'
    )
    
    # Manual trend arguments (NEW)
    parser.add_argument(
        '--manual-trend',
        type=str,
        choices=['bullish', 'bearish', 'neutral'],
        help='Manually set trend direction (overrides automatic analysis)'
    )
    
    parser.add_argument(
        '--auto-trend',
        action='store_true',
        help='Force automatic trend analysis (disables manual trend if set in config)'
    )
    
    return parser.parse_args()

def update_config_from_args(args):
    """Update CONFIG based on command line arguments"""
    if args.backtest:
        CONFIG['backtest'] = True
    else:
        CONFIG['backtest'] = False
    
    if args.symbol:
        CONFIG['symbol'] = args.symbol
    
    if args.start:
        CONFIG['start'] = args.start
    
    if args.end:
        CONFIG['end'] = args.end
    
    if args.timeframe:
        CONFIG['timeframe_entry'] = args.timeframe
    
    if args.capital:
        CONFIG['capital'] = args.capital
    
    if args.risk:
        CONFIG['risk_pct'] = args.risk
    
    if args.trailing:
        CONFIG['trailing_stop'] = True
    
    # Handle manual trend override (NEW)
    if args.manual_trend:
        CONFIG['use_manual_trend'] = True
        CONFIG['manual_trend'] = args.manual_trend
        logger.info(f"\n{'='*70}")
        logger.info(f"Manual Trend Override Enabled via CLI")
        logger.info(f"Trend Direction: {args.manual_trend.upper()}")
        logger.info(f"{'='*70}\n")
    
    # Force automatic trend if requested
    if args.auto_trend:
        CONFIG['use_manual_trend'] = False
        logger.info("\nAutomatic trend analysis enabled (manual trend disabled)")

def main():
    """Main function"""
    print("\n" + "="*70)
    print("ICT FIBONACCI TRADING BOT")
    print("="*70 + "\n")
    
    # Parse arguments
    args = parse_arguments()
    
    # Update configuration
    update_config_from_args(args)
    
    # Validate configuration
    try:
        validate_config()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Check MT5 availability
    if not MT5_AVAILABLE and not CONFIG['backtest']:
        logger.error("MetaTrader5 package not available!")
        logger.error("Install with: pip install MetaTrader5")
        sys.exit(1)
    
    # Display trend mode info
    if CONFIG.get('use_manual_trend', False):
        print(f"🎯 Trend Mode: MANUAL ({CONFIG['manual_trend'].upper()})")
    else:
        print(f"📊 Trend Mode: AUTOMATIC (Point-Based System)")
    print("="*70 + "\n")
    
    try:
        if CONFIG['backtest']:
            # Run backtest
            logger.info("Starting backtest mode...")
            trades_df, summary = backtest(
                CONFIG['symbol'],
                CONFIG['start'],
                CONFIG['end'],
                CONFIG['timeframe_entry']
            )
            
            # Optionally save results
            if len(trades_df) > 0:
                output_file = f"backtest_results_{CONFIG['symbol']}_{CONFIG['start']}_{CONFIG['end']}.csv"
                trades_df.to_csv(output_file, index=False)
                logger.info(f"\nTrade details saved to: {output_file}")
        
        else:
            # Run live trading
            logger.info("Starting live trading mode...")
            start_live_trading(CONFIG['symbol'])
    
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("\nBot terminated.")

if __name__ == '__main__':
    main()