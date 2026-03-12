# 🖥️ Aladin GUI Guide

This guide covers every tab and control in the `gui_app.py` control panel.

Launch the GUI with:
```bash
python gui_app.py
```

---

## Sidebar

The sidebar is always visible on the left.

| Element | Description |
|---|---|
| **Bot Status** | `RUNNING` (green) or `STOPPED` (red) — reflects whether the bot process is active |
| **Server / Time** | Live MT5 broker server name and clock time (updates every second) |
| **Start Bot Process** | Spawns the `main.py` live trading subprocess |
| **Stop Bot Process** | Sends a termination signal to the running bot |
| **Trading Execution** | Toggle switch — when **DISABLED**, the bot scans for signals but places **no real orders**. Must be **ENABLED** for live trading. |
| **Save Config** | Writes all current GUI settings to `config.json` so they persist on next launch |

> **Safety tip:** Keep Trading Execution **DISABLED** while tuning settings. Only enable it when you are ready to trade live.

---

## Tab: Log Output

Real-time scrolling log from the bot process. Shows:
- MT5 connection status
- Fibonacci setups detected per symbol
- Trend direction scores
- Entry signals triggered
- Order submission results and errors
- Position monitoring updates

---

## Tab: Trading

Configure which symbols to trade and trend analysis inputs.

### Symbol Selection

- The selector automatically fetches all symbols available in your MT5 Market Watch on startup
- Use the **search bar** to filter by name (e.g., type `USD` to show all USD pairs)
- Click **All** / **None** to bulk-select/deselect
- Tick individual checkboxes to include/exclude symbols
- Click **Refresh Symbols** to re-fetch from MT5 if you have added new symbols to Market Watch

### Entry Timeframe

The timeframe the bot uses to scan for Fibonacci entry signals.

| Option | Use Case |
|---|---|
| M1, M5 | Scalping / very short-term |
| **M15** | Default — good balance of signal frequency and quality |
| M30, H1 | Longer setups, fewer signals |
| H4 | Swing trading |

### Trend Analysis

| Setting | Description |
|---|---|
| **Use Manual Trend Override** | Bypasses all automatic trend analysis and forces a fixed direction |
| **Manual Trend** | Set to `bullish` or `bearish` when override is enabled |
| **Use Moving Averages** | MA crossover (fast 9 / slow 18) contributes to trend score |
| **Use RSI** | RSI above/below 50 and extreme zones contribute to trend score |
| **Use VWAP** | Price position relative to VWAP contributes to trend score |
| **Use Bollinger Bands** | Price position within bands contributes to trend score |
| **Bullish Threshold** | Minimum point score to classify trend as bullish (default: 10) |
| **Bearish Threshold** | Maximum (negative) point score to classify trend as bearish (default: -10) |

---

## Tab: Indicators

Fine-tune technical indicator parameters.

| Setting | Default | Description |
|---|---|---|
| Bollinger Band Period | 20 | Lookback period for BB calculation |
| Bollinger Std Dev | 2 | Standard deviations for upper/lower bands |
| RSI Period | 14 | Lookback period for RSI |
| VWAP Period | 20 | Rolling period for VWAP |
| MA Fast | 9 | Fast moving average period |
| MA Slow | 18 | Slow moving average period |

---

## Tab: Risk

Control position sizing, stop loss methodology, and trade limits.

| Setting | Default | Description |
|---|---|---|
| Capital | 2500 | Account capital used for position sizing (does not need to match your actual balance) |
| Risk % | 0.25 | Percentage of capital risked per trade |
| Min R:R Ratio | 1.5 | Minimum acceptable risk-to-reward; trades below this are skipped |
| Max Concurrent Trades | 8 | Maximum open positions across all symbols |
| Max Trades per Pair | 4 | Maximum open positions on a single symbol |
| Trailing Stop | Off | Enable step-based trailing stop |

### ATR Stop Loss

When enabled, the bot computes Average True Range (ATR) and uses it to set more adaptive stop levels.

| Method | Behaviour |
|---|---|
| `wider` | Uses whichever stop (ATR or Fibonacci) gives the price more room |
| `tighter` | Uses whichever stop is closer to entry |
| `fibonacci` | Always uses the Fibonacci level as the stop, ignoring ATR |

### Trailing Stop Levels

When trailing is enabled, the stop moves in steps as the trade moves into profit:

| Profit Milestone | Stop Moves To |
|---|---|
| 1R | 0.5R |
| 2R | 1R |
| 3R | 2R |
| 4R | 3R |

---

## Tab: ADX Filter

The **Average Directional Index (ADX)** filter prevents trading in ranging/choppy markets by requiring a minimum trend strength.

| Setting | Default | Description |
|---|---|---|
| Enable ADX Filter | On | Toggle the filter on/off |
| ADX Period | 20 | Lookback period for ADX calculation |
| Strength Threshold | 25 | ADX must be above this value for trend to be "strong" |
| Extreme Threshold | 80 | ADX above this = very strong trend (no extra restriction) |
| Weak Threshold | 20 | ADX below this = market is ranging, skip trade |
| Confirmation Bars | 2 | Number of consecutive bars ADX must stay above threshold |
| ADX Timeframes | M5, H4 | Which timeframes to compute and check ADX on |
| Strict Matching | On | **On** = both timeframes must confirm trend independently; **Off** = cross-timeframe confirmation allowed |

---

## Tab: Macro

Optional layer for fundamental and sentiment bias. **Disabled by default.**

| Setting | Description |
|---|---|
| Use Fundamental Analysis | Incorporates COT reports, interest rate differentials, economic calendar |
| Use Sentiment Analysis | Reads news and social media sentiment (requires API keys in `.env`) |
| Use Macro Filter | Blocks trades that conflict with macro bias |
| Macro Weight | Weight of macro score vs. technical score (default: 35/65 split) |
| Skip Trades Against Macro | Do not enter if macro and technical bias conflict |

Requires API keys set in `.env` for sentiment features. See `.env.example`.

---

## Tab: Daily Limits

Automated circuit breakers to protect your capital during bad days.

| Setting | Default | Description |
|---|---|---|
| Max Daily Loss ($) | -1 (unlimited) | Stop trading for the day if account-wide loss exceeds this |
| Max Daily Losing Trades | 8 | Stop trading after this many losing trades in a single day |
| Max Daily Loss Per Symbol ($) | -1 (unlimited) | Stop trading a specific symbol if its daily loss exceeds this |
| Max Losing Trades Per Symbol | 3 | Stop trading a specific symbol after this many daily losses |

Set any value to `-1` to disable that specific limit.

---

## Tab: Charts

Live interactive candlestick chart pulled directly from MT5.

### Controls

| Control | Description |
|---|---|
| **Symbol** | Select which symbol to display |
| **Timeframe** | Choose M1 / M5 / M15 / M30 / H1 / H4 |
| **Refresh Chart** | Manually fetch and redraw latest data |
| **Filter Levels** | Open popup to show/hide individual Fibonacci levels and swing points |
| **Auto-Refresh (5s)** | When checked, chart updates every 5 seconds automatically |

### Chart Display

- **Candlesticks** — standard OHLC bars (green up, red down, dark theme)
- **Swing High / Low lines** — white horizontal lines marking the detected swing points
- **Fibonacci level lines** — orange horizontal lines at 0.618 / 0.705 / 0.786
- **Labels** — price labels on the right side of each line

### Setup Panel (Right Side)

Lists all valid Fibonacci setups detected on the current chart:
- Newest setups shown first
- Click a setup button to isolate and highlight only that setup's levels
- Click **Show All Setups** to display all setups simultaneously

---

## Tab: Backtest

Test the strategy on historical MT5 data without placing real orders.

### Running a Backtest

1. Enter **Start Date** and **End Date** in `YYYY-MM-DD` format
2. Click **Run Backtest** (purple button)
3. Results appear in the dashboard cards and trade log table below
4. Click **Export CSV** to save the trade log to a file

### Dashboard Cards

| Card | Description |
|---|---|
| Win Rate | % of trades that were profitable |
| Net Profit | Total dollar profit/loss |
| Avg R:R | Average realised risk-to-reward ratio |
| Profit Factor | Gross profit ÷ gross loss |
| Best Time | Time-of-day with most profitable results |
| Initial / Ending Balance | Starting and final equity |
| Total Trades / Wins / Losses | Trade count breakdown |

### Equity Curve

An interactive line chart showing account balance over time. Hover to see exact values at any point.

### Trade Log Table

Sortable table showing every backtest trade:

| Column | Description |
|---|---|
| Symbol | Trading pair |
| Entry / Exit Time | Timestamps |
| Side | BUY or SELL |
| Entry / Exit Px | Price at open and close |
| P/L ($) | Dollar profit or loss |
| Reason | Why the trade closed (TP, SL, trailing stop) |

---

## Saving & Loading Configuration

- All GUI changes are **in-memory only** until you click **Save Config**
- Clicking **Save Config** writes to `config.json` in the project folder
- On next launch, `config.json` values override the defaults in `config.py`
- To reset to defaults, delete `config.json`
