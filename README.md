# 🧞 Aladin Trading Bot

An advanced, modular MetaTrader 5 (MT5) trading bot implementing the **ICT (Inner Circle Trader) Fibonacci strategy** with multi-timeframe trend analysis, ADX filtering, macro analysis, and a full-featured GUI control panel.

---

## 📋 Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [GUI Control Panel](#gui-control-panel)
- [MT5 Integration](#mt5-integration)
- [Configuration](#configuration)
- [Trading Strategy](#trading-strategy)
- [Running Modes](#running-modes)
- [Troubleshooting](#troubleshooting)
- [Risk Disclaimer](#risk-disclaimer)

---

## ✨ Features

| Feature | Description |
|---|---|
| **ICT Fibonacci Strategy** | 0.618, 0.705, 0.786 retracement levels |
| **Multi-Symbol Trading** | Trade multiple forex pairs simultaneously |
| **GUI Control Panel** | Full desktop interface built with CustomTkinter |
| **Live MT5 Charts** | Real-time candlestick charts with Fibonacci overlays |
| **Backtesting Engine** | Historical simulation with equity curve + trade log |
| **Multi-Timeframe Trend** | D1, H4, H1 with RSI, VWAP, MA, Bollinger Bands |
| **ADX Filter** | Trend strength confirmation across multiple timeframes |
| **ATR-Based Stops** | Dynamic stop loss sizing based on market volatility |
| **Daily Loss Limits** | Per-account and per-symbol daily loss limits |
| **Macro Analysis** | Optional fundamental/sentiment analysis layer |
| **Trailing Stops** | Configurable step-based trailing stop system |

---

## 📁 Project Structure

```
aladin/
├── gui_app.py            # GUI Control Panel (CustomTkinter)
├── main.py               # CLI entry point
├── config.py             # All settings & config validation
├── config.json           # Saved GUI settings (auto-generated)
├── fibonacci.py          # ICT Fibonacci detection & tracking
├── trend_analysis.py     # Multi-timeframe trend scoring
├── indicators.py         # RSI, VWAP, Bollinger Bands, SMA
├── mt5_handler.py        # MT5 connection, data fetch, order execution
├── risk_management.py    # Position sizing, trailing stops, limits
├── live_trading.py       # Live trading loop
├── backtest.py           # Backtesting engine
├── f_analysis.py         # Fundamental & sentiment analysis
├── gpu_engine.py         # GPU-accelerated computation support
├── gpu_runner.py         # GPU batch runner
├── setup.py              # Environment setup helper
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
└── README.md
```

---

## ⚙️ Prerequisites

- **Python** 3.8+
- **MetaTrader 5** terminal installed and running
- **MT5 account** (demo or live) logged in
- **Automated trading** enabled in MT5 (`Tools → Options → Expert Advisors → Allow automated trading`)

---

## 🚀 Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd aladin

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables (optional, for macro/news APIs)
copy .env.example .env
# Edit .env with your API keys
```

### Dependencies

```
MetaTrader5
pandas
numpy
customtkinter
mplfinance
matplotlib
python-dotenv
```

---

## ⚡ Quick Start

### Option A — GUI (Recommended)

```bash
python gui_app.py
```

The GUI will launch and automatically attempt to connect to MT5 and fetch available symbols.

### Option B — Command Line

```bash
# Backtest mode
python main.py --backtest --start 2025-01-01 --end 2025-12-31

# Live trading mode
python main.py --live --symbol USDCAD
```

> **See [Running Modes](#running-modes) for full CLI reference.**

---

## 🖥️ GUI Control Panel

The GUI is the primary way to interact with Aladin. Launch it with `python gui_app.py`.

For a detailed guide to each tab, see **[GUI_GUIDE.md](GUI_GUIDE.md)**.

### Sidebar

| Element | Description |
|---|---|
| **Bot Status** | Shows `RUNNING` (green) or `STOPPED` (red) |
| **Server Time** | Live MT5 broker server clock |
| **Start Bot** | Launches the live trading process |
| **Stop Bot** | Gracefully terminates the trading process |
| **Trading Execution toggle** | Master switch — must be `ENABLED` for real orders to be placed |
| **Save Config** | Persists all settings to `config.json` |

### Tabs Overview

| Tab | Purpose |
|---|---|
| **Log Output** | Live scrolling log from the bot process |
| **Trading** | Symbol selection, entry timeframe, trend analysis toggles |
| **Indicators** | Fine-tune RSI, VWAP, MA, and Bollinger Band parameters |
| **Risk** | Capital, risk %, R:R ratio, ATR stops, trailing stops, concurrent trade limits |
| **ADX Filter** | ADX period, thresholds, timeframes, and cross-TF matching mode |
| **Macro** | Fundamental/sentiment analysis toggles and weights |
| **Daily Limits** | Max daily loss ($ and trade count), per-symbol limits |
| **Charts** | Live candlestick chart with Fibonacci overlay, per-symbol, per-timeframe |
| **Backtest** | Date range picker, run backtest, equity curve graph, trade log table |

---

## 📡 MT5 Integration

The bot connects to MT5 using the official **MetaTrader5 Python package**. MT5 must be running on the same machine.

### Connection Flow

```
gui_app.py / main.py
    ↓
config.py (loads & validates settings)
    ↓
mt5_handler.py (connects via mt5.initialize())
    ↓
Fetches OHLCV data → fibonacci.py / trend_analysis.py
    ↓
live_trading.py (places orders via mt5.order_send())
```

### Symbol Names

MT5 symbols vary by broker. Check your broker's Market Watch for exact names:

| Common Format | Example |
|---|---|
| Standard | `EURUSD`, `GBPUSD` |
| Raw/ECN spread | `EURUSD.raw`, `USDCAD.raw` |
| Others | `XAUUSD`, `US30` |

Set the correct symbol name in the **Trading tab** of the GUI, or in `config.py`.

### Order Execution

- Uses **live tick prices** (ASK for buy, BID for sell) — never bar close prices
- **Automatic filling type detection** (FOK/IOC/RETURN) per broker
- **3-retry logic** with fresh prices on requote or failure
- All prices normalized to the symbol's pip precision

### Required MT5 Settings

In MetaTrader 5:
1. Go to `Tools → Options → Expert Advisors`
2. ✅ Check **"Allow automated trading"**
3. ✅ Check **"Allow DLL imports"** (if required by your broker)
4. Ensure the symbol is added to **Market Watch** (`Ctrl+U`)
5. Keep MT5 **logged in** and **connected** during bot operation

---

## ⚙️ Configuration

All settings are controlled via the GUI or directly in `config.py`. When you click **Save Config** in the GUI, settings are written to `config.json` which overrides the defaults in `config.py`.

### Core Trading Settings

| Key | Default | Description |
|---|---|---|
| `symbols` | `['USDCAD']` | List of forex pairs to trade |
| `trading_enabled` | `false` | Master on/off switch for real order placement |
| `capital` | `2500.0` | Account capital used for position sizing |
| `risk_pct` | `0.25` | % of capital risked per trade |
| `timeframe_entry` | `M15` | Timeframe for entry signal detection |
| `trend_timeframes` | `['D1','H4','H1']` | Timeframes used for trend analysis |

### Fibonacci Settings

| Key | Default | Description |
|---|---|---|
| `fib_levels` | `[0.618, 0.705, 0.786]` | Retracement levels to watch |
| `fib_lookback` | `57` | Candles to look back for swing points |
| `fib_tolerance` | `0.0001` | Price tolerance for level touch |
| `max_fib_age` | `100` | Max bars before a setup is discarded |
| `min_fib_candles` | `5` | Min candles between swing high and low |

### ADX Filter

| Key | Default | Description |
|---|---|---|
| `use_adx_filter` | `true` | Enable ADX trend strength filter |
| `adx_period` | `20` | ADX calculation period |
| `adx_strength_threshold` | `25` | Minimum ADX for trend confirmation |
| `adx_timeframes` | `['M5','H4']` | Timeframes to compute ADX on |

### ATR-Based Stop Loss

| Key | Default | Description |
|---|---|---|
| `use_atr_stops` | `true` | Use ATR for dynamic stop placement |
| `atr_stop_multiplier` | `1.5` | ATR multiplier (e.g., 1.5 = 1.5× ATR) |
| `atr_stop_method` | `wider` | `wider`, `tighter`, or `fibonacci` |

### Risk & Position Limits

| Key | Default | Description |
|---|---|---|
| `min_rr_ratio` | `1.5` | Minimum Risk:Reward before taking a trade |
| `max_concurrent_trades` | `8` | Max open positions across all symbols |
| `max_concurrent_trades_of_same_pair` | `4` | Max open positions per symbol |
| `trailing_stop` | `false` | Enable trailing stop |

### Daily Loss Limits

| Key | Default | Description |
|---|---|---|
| `max_daily_losses` | `-1` | Max daily $ loss (account-wide), `-1` = unlimited |
| `max_daily_loss_count` | `8` | Max losing trades per day |
| `max_daily_losses_per_symbol` | `-1` | Max daily $ loss per symbol |
| `max_daily_loss_count_per_symbol` | `3` | Max losing trades per symbol per day |

### Trailing Stop Levels

```python
'trailing_levels': {
    1.0: 0.5,   # At 1R profit, move stop to 0.5R
    2.0: 1.0,   # At 2R profit, move stop to 1R
    3.0: 2.0,   # At 3R profit, move stop to 2R
    4.0: 3.0,   # At 4R profit, move stop to 3R
}
```

### API Keys (Optional — for Macro Analysis)

Copy `.env.example` to `.env` and fill in:

```
NEWSAPI_KEY=your_key
ALPHA_VANTAGE_KEY=your_key
TWITTER_API_KEY=your_key
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
```

---

## 📈 Trading Strategy

### Entry Logic

```
1. Fibonacci Setup Detection
   └─ Scan last N candles for swing high / swing low
   └─ Calculate 0.618, 0.705, 0.786 retracement levels

2. Trend Confirmation (Multi-Timeframe)
   └─ Analyze D1, H4, H1
   └─ Score: RSI + VWAP + MA + Bollinger Bands
   └─ Must exceed bullish/bearish point threshold

3. ADX Filter (Optional)
   └─ ADX must be above strength threshold
   └─ Confirms a trending, non-ranging market

4. Entry Signal
   └─ Price touches a Fib level
   └─ Closes back beyond level (retracement confirmed)
   └─ Direction aligns with overall trend bias

5. Order Placement
   └─ Get live ASK/BID tick price
   └─ Calculate SL (below/above Fib level or ATR-based)
   └─ Calculate TP (minimum 1.5R from entry)
   └─ Validate R:R ratio — skip if below minimum
   └─ Send market order with retry logic
```

### Exit Logic

| Method | Trigger |
|---|---|
| **Stop Loss** | Price moves below/above the Fibonacci stop level |
| **Take Profit** | Price reaches minimum 1.5R target |
| **Trailing Stop** | Moves stop as profit milestones (1R, 2R, 3R, 4R) are hit |

---

## 🖥️ Running Modes

### GUI Mode (Recommended)

```bash
python gui_app.py
```

### CLI — Backtest

```bash
python main.py --backtest

# With date range
python main.py --backtest --start 2025-01-01 --end 2025-12-31

# Specific symbol
python main.py --backtest --symbol EURUSD

# Enable trailing stops
python main.py --backtest --trailing
```

### CLI — Live Trading

```bash
python main.py --live

# Custom symbol and risk
python main.py --live --symbol GBPUSD --risk 1.0 --capital 10000

# With trailing stops
python main.py --live --trailing
```

---

## 🔧 Troubleshooting

### MT5 won't connect
- Ensure MetaTrader 5 is **open and logged in**
- Check the terminal shows **"Connected"** in the bottom right
- Run as administrator if needed
- Check `Tools → Options → Expert Advisors → Allow automated trading`

### "Invalid filling type" error
- The bot auto-detects FOK/IOC/RETURN filling modes
- If persistent, check your broker's execution policy

### Orders not executing
- Verify `trading_enabled` is **ON** (toggle in sidebar or in config)
- Check MT5 logs under `View → Terminal → Experts`
- Ensure sufficient margin and no trading restrictions on the account

### "Requote" errors
- The retry logic handles requotes automatically (3 attempts with fresh prices)

### No signals generated
- Ensure at least one trend indicator is enabled
- Lower the `trend_bullish_threshold` / `trend_bearish_threshold` values
- Confirm the market is actively trending (ADX > 25)
- Increase `fib_lookback` if no swing points are detected

### Symbol not found
- Double-check the exact symbol name in MT5 Market Watch
- Some brokers append `.raw`, `.ecn`, or `.m`
- Add the symbol to Market Watch (`Ctrl+U` in MT5)

---

## ⚠️ Risk Disclaimer

This software is provided for **educational and research purposes only**.

- Always test thoroughly on a **demo account** before going live
- Never risk money you cannot afford to lose
- Past backtest performance does **not** guarantee future results
- Monitor the bot regularly — do not run unattended on a live account
- Understand the strategy completely before enabling live trading

**Use at your own risk. No warranty provided.**