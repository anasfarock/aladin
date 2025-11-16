"""
ICT Fibonacci Trading Bot - Main Entry Point with ADX & Macro Analysis Integration

Usage:
    # Run backtest
    python main.py --backtest
    
    # Run live trading with ADX filter enabled
    python main.py --live --adx
    
    # Run with custom ADX threshold
    python main.py --live --adx --adx-threshold 30
    
    # Run with ADX disabled
    python main.py --live --no-adx
    
    # Run with ADX and macro analysis
    python main.py --live --adx --fundamental-only
"""

import argparse
import sys
from config import CONFIG, validate_config, MT5_AVAILABLE, logger
from backtest import backtest
from live_trading import start_live_trading

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='ICT Fibonacci Trading Bot with ADX & Macro Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run backtest with default settings
  python main.py --backtest
  
  # Run live trading with ADX filter enabled
  python main.py --live --adx
  
  # Run live trading with custom ADX threshold
  python main.py --live --adx --adx-threshold 30
  
  # Run live trading without ADX filter
  python main.py --live --no-adx
  
  # Run with custom ADX period
  python main.py --live --adx --adx-period 21
  
  # Run with ADX and DI crossover check disabled
  python main.py --live --adx --no-di-check
  
  # Run with custom symbol
  python main.py --live --symbol EURUSD
  
  # Run with manual trend override
  python main.py --live --manual-trend bullish
  
  # Run with ADX and macro analysis
  python main.py --live --adx --fundamental-only
  
  # Run backtest with custom dates
  python main.py --backtest --start 2024-01-01 --end 2024-12-31
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
    
    # Trading parameters
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
    
    # ADX Filter Options
    adx_group = parser.add_argument_group('ADX Filter Options')
    
    adx_group.add_argument(
        '--adx',
        action='store_true',
        help='Enable ADX filter for trend confirmation'
    )
    
    adx_group.add_argument(
        '--no-adx',
        action='store_true',
        help='Disable ADX filter'
    )
    
    adx_group.add_argument(
        '--adx-period',
        type=int,
        help=f'ADX calculation period (default: {CONFIG["adx_period"]})'
    )
    
    adx_group.add_argument(
        '--adx-threshold',
        type=float,
        help=f'ADX strength threshold (default: {CONFIG["adx_strength_threshold"]})'
    )
    
    adx_group.add_argument(
        '--adx-extreme',
        type=float,
        help=f'ADX extreme threshold (default: {CONFIG["adx_extreme_threshold"]})'
    )
    
    adx_group.add_argument(
        '--adx-weak',
        type=float,
        help=f'ADX weak threshold (default: {CONFIG["adx_weak_threshold"]})'
    )
    
    adx_group.add_argument(
        '--no-di-check',
        action='store_true',
        help='Disable +DI/-DI crossover check'
    )
    
    adx_group.add_argument(
        '--verbose-adx',
        action='store_true',
        help='Enable verbose ADX logging'
    )
    
    # Trend Analysis
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
    
    # Macro Analysis Options
    macro_group = parser.add_argument_group('Macro Analysis Options')
    
    macro_group.add_argument(
        '--no-macro-analysis',
        action='store_true',
        help='Disable both fundamental and sentiment analysis'
    )
    
    macro_group.add_argument(
        '--fundamental-only',
        action='store_true',
        help='Enable only fundamental analysis (COT, interest rates, etc.)'
    )
    
    macro_group.add_argument(
        '--sentiment-only',
        action='store_true',
        help='Enable only sentiment analysis (news, social media)'
    )
    
    macro_group.add_argument(
        '--no-macro-filter',
        action='store_true',
        help='Disable macro filter (display analysis but don\'t skip trades)'
    )
    
    macro_group.add_argument(
        '--skip-against-macro',
        action='store_true',
        help='Skip trades that go against strong macro bias'
    )
    
    macro_group.add_argument(
        '--macro-confidence',
        type=float,
        help=f'Macro confidence threshold (default: {CONFIG["macro_confidence_min"]}%)'
    )
    
    macro_group.add_argument(
        '--verbose-macro',
        action='store_true',
        help='Enable verbose macro analysis logging'
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
    
    # ADX Filter Options
    if args.adx:
        CONFIG['use_adx_filter'] = True
        logger.info("✓ ADX filter ENABLED")
    
    if args.no_adx:
        CONFIG['use_adx_filter'] = False
        logger.info("🔇 ADX filter DISABLED")
    
    if args.adx_period:
        CONFIG['adx_period'] = args.adx_period
        logger.info(f"✓ ADX period set to {args.adx_period}")
    
    if args.adx_threshold:
        CONFIG['adx_strength_threshold'] = args.adx_threshold
        logger.info(f"✓ ADX strength threshold set to {args.adx_threshold}")
    
    if args.adx_extreme:
        CONFIG['adx_extreme_threshold'] = args.adx_extreme
        logger.info(f"✓ ADX extreme threshold set to {args.adx_extreme}")
    
    if args.adx_weak:
        CONFIG['adx_weak_threshold'] = args.adx_weak
        logger.info(f"✓ ADX weak threshold set to {args.adx_weak}")
    
    if args.no_di_check:
        CONFIG['adx_di_crossover_check'] = False
        logger.info("🔇 +DI/-DI crossover check DISABLED")
    
    if args.verbose_adx:
        CONFIG['verbose_adx_analysis'] = True
        logger.info("🔊 Verbose ADX logging ENABLED")
    
    # Trend Analysis
    if args.manual_trend:
        CONFIG['use_manual_trend'] = True
        CONFIG['manual_trend'] = args.manual_trend
        logger.info(f"\n{'='*70}")
        logger.info(f"Manual Trend Override Enabled via CLI")
        logger.info(f"Trend Direction: {args.manual_trend.upper()}")
        logger.info(f"{'='*70}\n")
    
    if args.auto_trend:
        CONFIG['use_manual_trend'] = False
        logger.info("\nAutomatic trend analysis enabled (manual trend disabled)")
    
    # Macro Analysis Options
    if args.no_macro_analysis:
        CONFIG['use_fundamental_analysis'] = False
        CONFIG['use_sentiment_analysis'] = False
        CONFIG['use_macro_filter'] = False
        logger.info("🔇 Macro analysis DISABLED")
    
    if args.fundamental_only:
        CONFIG['use_fundamental_analysis'] = True
        CONFIG['use_sentiment_analysis'] = False
        logger.info("📊 Fundamental analysis ONLY")
    
    if args.sentiment_only:
        CONFIG['use_fundamental_analysis'] = False
        CONFIG['use_sentiment_analysis'] = True
        logger.info("📰 Sentiment analysis ONLY")
    
    if args.no_macro_filter:
        CONFIG['use_macro_filter'] = False
        CONFIG['verbose_macro_analysis'] = True
        logger.info("📊 Macro filter DISABLED (info only)")
    
    if args.skip_against_macro:
        CONFIG['skip_trades_against_macro'] = True
        logger.info("⛔ Skip trades against strong macro bias: ENABLED")
    
    if args.macro_confidence:
        CONFIG['macro_confidence_min'] = args.macro_confidence
        logger.info(f"📊 Macro confidence threshold: {args.macro_confidence}%")
    
    if args.verbose_macro:
        CONFIG['verbose_macro_analysis'] = True
        logger.info("🔊 Verbose macro logging: ENABLED")

def main():
    """Main function"""
    print("\n" + "="*70)
    print("ICT FIBONACCI TRADING BOT")
    print("Enhanced with ADX Trend Confirmation & Macro Analysis")
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
    
    # Check MT5 availability for live trading
    if not MT5_AVAILABLE and not CONFIG['backtest']:
        logger.error("MetaTrader5 package not available!")
        logger.error("Install with: pip install MetaTrader5")
        sys.exit(1)
    
    # Display configuration summary
    print(f"\n{'='*70}")
    print("⚙️  CONFIGURATION SUMMARY")
    print(f"{'='*70}")
    
    if CONFIG.get('use_manual_trend', False):
        print(f"🎯 Trend Mode: MANUAL ({CONFIG['manual_trend'].upper()})")
    else:
        print(f"📊 Trend Mode: AUTOMATIC (Point-Based System)")
    
    # Display ADX configuration
    if CONFIG.get('use_adx_filter', False):
        print(f"\n✓ ADX FILTER: ENABLED")
        print(f"   Period: {CONFIG['adx_period']}")
        print(f"   Strength Threshold: {CONFIG['adx_strength_threshold']}")
        print(f"   Extreme Threshold: {CONFIG['adx_extreme_threshold']}")
        print(f"   Weak Threshold: {CONFIG['adx_weak_threshold']}")
        print(f"   DI Crossover Check: {'YES' if CONFIG['adx_di_crossover_check'] else 'NO'}")
    else:
        print(f"\n🔇 ADX FILTER: DISABLED")
    
    if CONFIG['use_fundamental_analysis'] or CONFIG['use_sentiment_analysis']:
        print("\n🌍 MACRO ANALYSIS MODULES:")
        if CONFIG['use_fundamental_analysis']:
            modules = []
            if CONFIG['analyze_cot_reports']:
                modules.append("COT Reports")
            if CONFIG['analyze_interest_rates']:
                modules.append("Interest Rates")
            if CONFIG['analyze_economic_events']:
                modules.append("Economic Calendar")
            if CONFIG['analyze_macro_factors']:
                modules.append("Macro Factors")
            print(f"   Fundamental: {', '.join(modules)}")
        
        if CONFIG['use_sentiment_analysis']:
            modules = []
            if CONFIG['analyze_news']:
                modules.append("News")
            if CONFIG['analyze_twitter']:
                modules.append("Twitter")
            if CONFIG['analyze_reddit']:
                modules.append("Reddit")
            print(f"   Sentiment: {', '.join(modules)}")
        
        if CONFIG['use_macro_filter']:
            print(f"   Filter: ACTIVE (skip trades against macro bias)")
        else:
            print(f"   Filter: DISPLAY ONLY (no trade skipping)")
    else:
        print("🔇 Macro Analysis: DISABLED")
    
    print(f"\nRisk per Trade: {CONFIG['risk_pct']}%")
    print(f"Min R:R Ratio: {CONFIG['min_rr_ratio']}")
    print(f"Max Concurrent Trades: {CONFIG['max_concurrent_trades']}")
    print(f"{'='*70}\n")
    
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