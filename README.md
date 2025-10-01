# ICT Fibonacci Trading Bot

A modular MT5 trading bot implementing the ICT (Inner Circle Trader) Fibonacci strategy with multi-timeframe trend analysis.

## Project Structure

```
trading_bot/
├── main.py                 # Entry point
├── config.py              # Configuration & settings
├── indicators.py          # Technical indicators (RSI, VWAP, BB, MA)
├── fibonacci.py           # ICT Fibonacci strategy logic
├── trend_analysis.py      # Multi-timeframe trend detection
├── mt5_handler.py         # MT5 connection & order execution (FIXED)
├── risk_management.py     # Position sizing & trailing stops
├── live_trading.py        # Live trading engine (FIXED)
└── backtest.py           # Backtesting module
```

## Key Features

### Strategy Components
- **ICT Fibonacci Retracements**: 0.618, 0.705, 0.786 levels
- **Multi-Timeframe Trend Analysis**: D1, H4, H1
- **Technical Indicators**: RSI, VWAP, Bollinger Bands, Moving Averages
- **Dynamic Risk Management**: Position sizing, trailing stops
- **Backtesting**: Historical simulation with detailed metrics

### Critical Fixes (Live Trading)
1. **Current Market Price**: Orders now use actual tick prices (ASK/BID) instead of bar close
2. **Filling Type Detection**: Automatically determines correct order filling mode
3. **Price Normalization**: Prices rounded to symbol's digit precision
4. **Retry Logic**: 3 attempts with fresh prices on failure
5. **Proper Error Handling**: Handles requotes and price changes

## Installation

```bash
# Install required packages
pip install MetaTrader5 pandas numpy

# Verify MT5 is installed and running
```

## Usage

### Backtest Mode
```bash
# Run with default settings
python main.py --backtest

# Custom date range
python main.py --backtest --start 2024-01-01 --end 2024-12-31

# Custom symbol
python main.py --backtest --symbol EURUSD.raw

# With trailing stops
python main.py --backtest --trailing
```

### Live Trading Mode
```bash
# Start live trading
python main.py --live

# Custom symbol
python main.py --live --symbol GBPUSD.raw

# Custom risk settings
python main.py --live --risk 1.0 --capital 10000

# With trailing stops
python main.py --live --trailing
```

## Configuration

Edit `config.py` to customize:

### Trading Parameters
```python
CONFIG = {
    'symbol': 'USDCAD.raw',
    'capital': 4950.0,
    'risk_pct': 0.5,           # Risk per trade
    'min_rr_ratio': 1.5,       # Minimum Risk:Reward
}
```

### Timeframes
```python
'timeframe_entry': 'M15',      # Entry signals
'trend_timeframes': ['D1', 'H4', 'H1'],  # Trend analysis
```

### Indicators
```python
'use_rsi_for_trend': True,
'use_vwap_for_trend': True,
'use_bollinger_for_trend': True,
'use_ma_for_trend': True,
```

### Fibonacci Settings
```python
'fib_levels': [0.618, 0.705, 0.786],
'fib_tolerance': 0.0001,
'fib_confirmation_bars': 2,
```

### Order Execution (NEW)
```python
'slippage_points': 50,         # Allowed slippage
'max_retries': 3,              # Retry attempts
'retry_delay': 0.5,            # Seconds between retries
```

### Trailing Stops
```python
'trailing_stop': False,
'trailing_levels': {
    1.0: 0.5,  # At 1R profit, trail to 0.5R
    2.0: 1.0,  # At 2R profit, trail to 1R
    3.0: 2.0,  # At 3R profit, trail to 2R
    4.0: 3.0,  # At 4R profit, trail to 3R
}
```

## Modules Overview

### 1. config.py
- Global configuration settings
- MT5 timeframe mappings
- Configuration validation

### 2. indicators.py
- Simple Moving Average (SMA)
- Relative Strength Index (RSI)
- Volume Weighted Average Price (VWAP)
- Bollinger Bands
- Batch indicator computation

### 3. fibonacci.py
- Swing point identification
- Fibonacci level calculation
- Setup detection and validation
- Entry signal generation
- `FibonacciTracker` class for live trading

### 4. trend_analysis.py
- Multi-timeframe trend determination
- Weighted voting system
- Trend detail breakdown

### 5. mt5_handler.py (FIXED)
- MT5 connection management
- Data fetching (live & historical)
- **Order execution with retry logic**
- **Proper price handling (tick prices)**
- **Filling type detection**
- Position management

### 6. risk_management.py
- Position sizing calculation
- Trailing stop logic
- Trade validation
- Maximum position checks

### 7. live_trading.py (FIXED)
- Main live trading loop
- **Uses current market prices**
- Signal detection
- Order placement
- Position monitoring

### 8. backtest.py
- Historical simulation
- Performance metrics
- Trade logging
- Equity curve analysis

### 9. main.py
- Command-line interface
- Argument parsing
- Mode selection (backtest/live)

## Trading Logic Flow

### Entry Logic
1. **Fibonacci Setup Detection**
   - Identify swing highs/lows
   - Calculate retracement levels
   - Track price reactions

2. **Trend Confirmation**
   - Analyze D1, H4, H1 timeframes
   - Vote with RSI, VWAP, BB, MA
   - Determine overall bias

3. **Entry Signal**
   - Price touches Fib level
   - Closes beyond level (pullback complete)
   - Aligned with trend direction

4. **Order Execution** (FIXED)
   - Get current tick price (ASK/BID)
   - Calculate stop/target
   - Validate R:R ratio
   - Place market order with retry

### Exit Logic
- **Stop Loss**: Below/above Fib level
- **Take Profit**: Minimum 1.5R
- **Trailing Stop**: Move to profit levels

## Performance Metrics

Backtest provides:
- Total Profit/Loss
- Win Rate
- Profit Factor
- Average Win/Loss
- Risk:Reward Ratio
- Maximum Drawdown
- Trades by Fib Level
- Exit Reason Breakdown

## Risk Disclaimer

This bot is for educational purposes. Trading involves substantial risk. Always:
- Test thoroughly in demo accounts
- Start with small position sizes
- Monitor performance regularly
- Understand the strategy completely
- Never risk more than you can afford to lose

## Troubleshooting

### "Invalid filling type" error
The fixed version automatically detects the correct filling type (FOK/IOC/RETURN)

### Orders not executing
- Check MT5 is running and logged in
- Verify symbol is correct (e.g., "USDCAD.raw" vs "USDCAD")
- Ensure sufficient margin
- Check broker allows automated trading
- Review MT5 logs for details

### "Requote" errors
The retry logic now handles this automatically with fresh prices

### No signals generated
- Check if trend indicators are enabled
- Verify sufficient historical data
- Review Fibonacci setup parameters
- Ensure market is trending

## Logging

Logs show:
- Connection status
- Fibonacci setups found
- Trend direction
- Entry signals
- Order execution details
- Position updates
- Performance metrics

## Updates in This Version

### Fixed Order Execution
- Uses current tick prices instead of bar close
- Automatic filling type detection
- Retry logic with price refresh
- Proper error handling
- Price normalization

### Improved Code Structure
- Modular design (9 separate files)
- Clear separation of concerns
- Easy to maintain and extend
- Better error messages
- Comprehensive logging

## Support

For issues or questions:
1. Check MT5 connection first
2. Review logs for error messages
3. Verify configuration settings
4. Test in backtest mode first

## License

Use at your own risk. No warranty provided.