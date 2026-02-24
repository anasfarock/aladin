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
    
    # Run with ADX cross-timeframe confirmation (manual control)
    python main.py --live --adx --adx-manual-control
    
    # Run with ADX strict cross-timeframe (primary TF only)
    python main.py --live --adx --adx-manual-control --adx-manual-strict
"""

import argparse
import sys
from config import CONFIG, validate_config, MT5_AVAILABLE, logger
from gpu_runner import backtest_gpu_runner as backtest
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
  
  # Run with custom ADX timeframes
  python main.py --live --adx --adx-timeframes M15 H1 H4
  
  # Run with ADX manual control (cross-timeframe confirmation)
  python main.py --live --adx --adx-manual-control
  
  # Run with ADX manual control STRICT mode (primary TF only)
  python main.py --live --adx --adx-manual-control --adx-manual-strict
  
  # Run with custom symbol
  python main.py --live --symbol EURUSD
  
  # Run with manual trend override
  python main.py --live --manual-trend bullish
  
  # Run with ADX and macro analysis
  python main.py --live --adx --fundamental-only
  
  # Run with daily loss limits
  python main.py --live --max-daily-losses 500 --max-daily-loss-count 5
  
  # Run with per-symbol daily loss limits
  python main.py --live --max-daily-losses-per-symbol 200 --max-daily-loss-count-per-symbol 2
  
  # Run with unlimited losses (careful!)
  python main.py --live --max-daily-losses -1 --max-daily-loss-count -1
  
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
        nargs='+', # Accept one or more arguments
        help=f'Trading symbol(s) (default: {CONFIG["symbol"]})'
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
        help='Enable ADX filter for trend strength validation'
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
        '--adx-timeframes',
        type=str,
        nargs='+',
        help=f'ADX analysis timeframes (default: {" ".join(CONFIG["adx_timeframes"])}). '
             f'Example: --adx-timeframes M15 H1 H4'
    )
    
    adx_group.add_argument(
        '--adx-manual-control',
        action='store_true',
        help='Enable ADX manual control: allows ADX to confirm trends across different timeframes'
    )
    
    adx_group.add_argument(
        '--adx-manual-strict',
        action='store_true',
        help='Enable ADX manual control STRICT mode: primary timeframe must confirm (requires --adx-manual-control)'
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
    
    # Daily Loss Limit Options
    loss_limit_group = parser.add_argument_group('Daily Loss Limit Options')
    
    loss_limit_group.add_argument(
        '--max-daily-losses', type=float, help=f'Max daily loss in account currency (default: {CONFIG["max_daily_losses"]}). -1 = unlimited')
    
    loss_limit_group.add_argument(
        '--max-daily-loss-count', type=int, help=f'Max losing trades per day (default: {CONFIG["max_daily_loss_count"]}). -1 = unlimited')
    
    loss_limit_group.add_argument(
        '--max-daily-losses-per-symbol', type=float, help=f'Max daily loss per symbol (default: {CONFIG["max_daily_losses_per_symbol"]}). -1 = unlimited')
    
    loss_limit_group.add_argument(
        '--max-daily-loss-count-per-symbol', type=int, help=f'Max losing trades per symbol per day (default: {CONFIG["max_daily_loss_count_per_symbol"]}). -1 = unlimited')
    
    return parser.parse_args()

def update_config_from_args(args):
    """Update CONFIG based on command line arguments"""
    if args.backtest:
        CONFIG['backtest'] = True
    else:
        CONFIG['backtest'] = False
    
    if args.symbol:
        if isinstance(args.symbol, list):
            CONFIG['symbols'] = args.symbol
            CONFIG['symbol'] = args.symbol[0] # Backwards compat
        else:
            CONFIG['symbol'] = args.symbol
            CONFIG['symbols'] = [args.symbol]
    
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
    
    if args.adx_timeframes:
        CONFIG['adx_timeframes'] = args.adx_timeframes
        logger.info(f"✓ ADX timeframes set to: {', '.join(args.adx_timeframes)}")
    
    if args.adx_manual_control:
        CONFIG['adx_manual_control'] = True
        logger.info("✓ ADX manual control ENABLED (cross-timeframe confirmation)")
        
        if args.adx_manual_strict:
            CONFIG['adx_manual_control_strict'] = True
            logger.info("  Mode: STRICT (primary timeframe must confirm)")
        else:
            CONFIG['adx_manual_control_strict'] = False
            logger.info("  Mode: LOOSE (any timeframe can confirm)")
    
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

    # Daily Loss Limit Options
    if args.max_daily_losses is not None:
        CONFIG['max_daily_losses'] = args.max_daily_losses
        logger.info(f"Max daily losses set to: {args.max_daily_losses}")
    
    if args.max_daily_loss_count is not None:
        CONFIG['max_daily_loss_count'] = args.max_daily_loss_count
        logger.info(f"Max daily loss count set to: {args.max_daily_loss_count}")
    
    if args.max_daily_losses_per_symbol is not None:
        CONFIG['max_daily_losses_per_symbol'] = args.max_daily_losses_per_symbol
        logger.info(f"Max daily losses per symbol set to: {args.max_daily_losses_per_symbol}")
    
    if args.max_daily_loss_count_per_symbol is not None:
        CONFIG['max_daily_loss_count_per_symbol'] = args.max_daily_loss_count_per_symbol
        logger.info(f"Max daily loss count per symbol set to: {args.max_daily_loss_count_per_symbol}")
    


def main():
    """Main function"""
    print("\n" + "="*70)
    print("ICT FIBONACCI TRADING BOT")
    print("Enhanced with ADX Trend Strength Validation & Macro Analysis")
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
    print("##  CONFIGURATION SUMMARY")
    print(f"{'='*70}")
    
    if CONFIG.get('use_manual_trend', False):
        print(f"-> Trend Mode: MANUAL ({CONFIG['manual_trend'].upper()})")
    else:
        print(f"-> Trend Mode: AUTOMATIC (Point-Based System)")
    
    print(f"Trend Timeframes: {', '.join(CONFIG['trend_timeframes'])}")
    
    # Display ADX configuration
    if CONFIG.get('use_adx_filter', False):
        print(f"\n[+] ADX FILTER: ENABLED")
        print(f"   Timeframes: {', '.join(CONFIG['adx_timeframes'])}")
        print(f"   Period: {CONFIG['adx_period']}")
        print(f"   Strength Threshold: {CONFIG['adx_strength_threshold']}")
        print(f"   Extreme Threshold: {CONFIG['adx_extreme_threshold']}")
        print(f"   Weak Threshold: {CONFIG['adx_weak_threshold']}")
        
        if CONFIG.get('adx_manual_control', False):
            mode = "STRICT (primary TF)" if CONFIG.get('adx_manual_control_strict', False) else "LOOSE (any TF)"
            print(f"   Manual Control: ENABLED - {mode}")
            print(f"   ADX can confirm trends across different timeframes")
        else:
            print(f"   Manual Control: DISABLED (exact timeframe match only)")
    else:
        print(f"\n[-] ADX FILTER: DISABLED")
    
    if CONFIG['use_fundamental_analysis'] or CONFIG['use_sentiment_analysis']:
        print("\n[+] MACRO ANALYSIS MODULES:")
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
        print("[-] Macro Analysis: DISABLED")
    
    print(f"\nRisk per Trade: {CONFIG['risk_pct']}%")
    print(f"Min R:R Ratio: {CONFIG['min_rr_ratio']}")
    print(f"Max Concurrent Trades: {CONFIG['max_concurrent_trades']}")
    print(f"{'='*70}\n")

    # Add to the configuration summary display:
    
    print("\n[!] DAILY LOSS LIMITS:")
    if CONFIG['max_daily_losses'] > 0:
        print(f"   Max Daily Loss: ${CONFIG['max_daily_losses']:.2f}")
    else:
        print(f"   Max Daily Loss: UNLIMITED")
    
    if CONFIG['max_daily_loss_count'] > 0:
        print(f"   Max Daily Loss Count: {CONFIG['max_daily_loss_count']} trades")
    else:
        print(f"   Max Daily Loss Count: UNLIMITED")
    
    if CONFIG['max_daily_losses_per_symbol'] > 0:
        print(f"   Max Daily Loss Per Symbol: ${CONFIG['max_daily_losses_per_symbol']:.2f}")
    else:
        print(f"   Max Daily Loss Per Symbol: UNLIMITED")
    
    if CONFIG['max_daily_loss_count_per_symbol'] > 0:
        print(f"   Max Daily Loss Per Symbol Count: {CONFIG['max_daily_loss_count_per_symbol']} trades")
    else:
        print(f"   Max Daily Loss Per Symbol Count: UNLIMITED")
    
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
                logger.info(f"\nFound {len(trades_df)} trades. Sending payload to GUI...")
                # Format datetime column correctly for JSON dumping
                if 'entry_time' in trades_df.columns:
                    trades_df['entry_time'] = trades_df['entry_time'].astype(str)
                if 'exit_time' in trades_df.columns:
                    trades_df['exit_time'] = trades_df['exit_time'].astype(str)
                    
                import json
                payload = {
                    'trades': trades_df.to_dict('records'),
                    'summary': summary
                }
                # Important: Print to stdout so GUI picks it up
                print("___BACKTEST_RESULTS_JSON_START___")
                print(json.dumps(payload))
                print("___BACKTEST_RESULTS_JSON_END___")
        
        else:
            # Run live trading
            logger.info("Starting live trading mode...")
            start_live_trading(CONFIG.get('symbols', [CONFIG['symbol']]))
    
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("\nBot terminated.")

if __name__ == '__main__':
    main()