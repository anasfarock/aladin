"""
MT5 Trading Bot + Backtester

Features:
- Connects to MetaTrader5 (live) or runs a historical backtest.
- Strategy:
  - Trend determined by RSI, VWAP, MA(9) & MA(18) on 1D and 4H timeframes (simple voting rule).
  - Entries are taken when price interacts with Bollinger Bands (SMA basis, length=20).
  - Trades only executed in direction of trend. If entry signal is opposite, skip.
  - Stop loss placed at the Bollinger Band side (lower band for long / upper band for short).
  - Take profit = min( 3 * risk_distance, opposite Bollinger band ).
  - If opposite Bollinger band is hit, trade closes.
  - Risk per trade = 0.5% of account capital (configurable).

Usage:
- Edit CONFIG section to set symbol, timeframes, and whether to run backtest or live.
- Backtest: specify start/end dates and historical timeframe for entries (e.g., 1H/4H).
- Live: requires MetaTrader5 terminal running and logged in. Install MetaTrader5 package:
    pip install MetaTrader5 pandas numpy

Notes & Limitations:
- This is a reference implementation. Always paper-test on demo accounts before using live.
- Lot-sizing logic is approximate — broker-specific contract sizes, pip definitions, and margin rules vary.
- The bot places MARKET orders via MT5; modify as needed for limit/stop entries.
"""

import time
import math
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Optional import - used only if running live mode
try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

# ----------------------------- CONFIG -----------------------------
CONFIG = {
    'symbol': 'EURUSD.raw',
    'backtest': True,            # True = backtest mode, False = live trading
    'start': '2024-06-22',
    'end': '2025-08-31',
    'capital': 10000.0,          # used for backtest or initial capital
    'risk_pct': 0.5,             # percent risk per trade (0.5%)
    'timeframe_entry': 'M5',     # timeframe used to simulate entries in backtest
    'trend_timeframes': ['D1', 'H4'],
    'boll_period': 20,
    'boll_std': 2,
    'rsi_period': 14,
    'vwap_period': 20,           # VWAP window (we'll compute rolling VWAP using typical price*volume)
}

# Map timeframe strings to MT5 constants if live
MT5_TIMEFRAMES = {
    'M1': mt5.TIMEFRAME_M1 if mt5 else None,
    'M5': mt5.TIMEFRAME_M5 if mt5 else None,
    'M15': mt5.TIMEFRAME_M15 if mt5 else None,
    'M30': mt5.TIMEFRAME_M30 if mt5 else None,
    'H1': mt5.TIMEFRAME_H1 if mt5 else None,
    'H4': mt5.TIMEFRAME_H4 if mt5 else None,
    'D1': mt5.TIMEFRAME_D1 if mt5 else None,
}

# --------------------------- UTILITIES ----------------------------

def to_datetime(ts):
    return datetime.utcfromtimestamp(ts)


def sma(series, length):
    return series.rolling(length).mean()


def std(series, length):
    return series.rolling(length).std()


def rsi(series, length=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=length-1, adjust=False).mean()
    ma_down = down.ewm(com=length-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))


def vwap(df, length=None):
    # Rolling VWAP using typical price * volume / volume
    tp = (df['high'] + df['low'] + df['close']) / 3
    pv = tp * df['tick_volume']
    if length is None:
        cum_pv = pv.cumsum()
        cum_v = df['tick_volume'].cumsum()
        return cum_pv / cum_v
    else:
        pv_roll = pv.rolling(length).sum()
        v_roll = df['tick_volume'].rolling(length).sum()
        return pv_roll / v_roll


def bollinger_bands(series, length=20, stddev=2):
    basis = sma(series, length)
    sd = std(series, length)
    upper = basis + stddev * sd
    lower = basis - stddev * sd
    return basis, upper, lower

# ----------------------- STRATEGY / SIGNALS -----------------------

def compute_indicators(df):
    df = df.copy()
    df['ma9'] = sma(df['close'], 9)
    df['ma18'] = sma(df['close'], 18)
    df['rsi'] = rsi(df['close'], CONFIG['rsi_period'])
    df['vwap'] = vwap(df, CONFIG['vwap_period'])
    df['bb_basis'], df['bb_upper'], df['bb_lower'] = bollinger_bands(df['close'], CONFIG['boll_period'], CONFIG['boll_std'])
    return df


def determine_trend(df_d1, df_h4):
    """Return 'long', 'short', or 'neutral'. Use simple voting among indicators on both timeframes.
       For each timeframe, indicators vote:
         - MA trend: ma9 > ma18 -> +1 else -1
         - RSI: RSI > 55 -> +1, RSI < 45 -> -1, else 0
         - Price vs VWAP: price > vwap -> +1, price < vwap -> -1
       Sum votes from both timeframes; positive -> 'long', negative -> 'short', else 'neutral'.
    """
    votes = 0
    for df in [df_d1, df_h4]:
        last = df.iloc[-1]
        # MA vote
        if np.isnan(last['ma9']) or np.isnan(last['ma18']):
            ma_vote = 0
        else:
            ma_vote = 1 if last['ma9'] > last['ma18'] else -1
        # RSI vote
        rsi_vote = 1 if last['rsi'] > 55 else (-1 if last['rsi'] < 45 else 0)
        # VWAP vote
        vwap_vote = 1 if last['close'] > last['vwap'] else (-1 if last['close'] < last['vwap'] else 0)
        votes += (ma_vote + rsi_vote + vwap_vote)
    if votes > 0:
        return 'long'
    elif votes < 0:
        return 'short'
    else:
        return 'neutral'


def entry_signal(df):
    """Return 'long', 'short', or None when price touches Bollinger Band in the right way.
       We'll define entry rules as:
         - Long entry: price (close) crosses below or touches lower BB and then closes back above lower band within the next candle -> bullish mean reversion
         - Short entry: price (close) crosses above or touches upper BB and then closes back below upper band within the next candle
       For backtest we detect when close <= lower_band -> trigger long; when close >= upper_band -> trigger short.
    """
    last = df.iloc[-1]
    if np.isnan(last['bb_lower']) or np.isnan(last['bb_upper']):
        return None
    if last['close'] <= last['bb_lower']:
        return 'long'
    if last['close'] >= last['bb_upper']:
        return 'short'
    return None

# ----------------------- HELPERS FOR FETCHING DATA -----------------------

def ensure_mt5_initialized():
    """Try to initialize MT5 if not already initialized."""
    if mt5 is None:
        raise RuntimeError('MetaTrader5 package not available - backtest requires historical data. Install MetaTrader5.')
    # mt5.initialize returns True on success
    if not mt5.initialize():
        # If initialization fails, give detailed error
        err = mt5.last_error()
        raise RuntimeError(f"mt5.initialize() failed, error={err}")


def fetch_mt5_df(symbol, tf_const, utc_from, utc_to, min_bars_expected=1):
    """Fetch rates from MT5 and return a cleaned DataFrame.
       Raises RuntimeError (with clear message) when data is None/empty.
    """
    # Ensure MT5 is ready
    ensure_mt5_initialized()

    rates = mt5.copy_rates_range(symbol, tf_const, utc_from, utc_to)
    if rates is None or len(rates) < min_bars_expected:
        # Fetch available symbols to help user debug
        all_symbols = mt5.symbols_get()
        available_names = [s.name for s in all_symbols]

        raise RuntimeError(
            f"No data returned from MT5 for {symbol} timeframe {tf_const}.\n"
            f"👉 Check symbol spelling, MarketWatch, and terminal login.\n\n"
            f"Here are some available symbols from your MT5 (first 50):\n"
            f"{available_names[:50]}"
        )

    df = pd.DataFrame(rates)

    # normalize timestamp column
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], unit='s')
    else:
        # sometimes the structured array may carry a different name; try common alternatives
        for cand in ('datetime', 'Date', 'date'):
            if cand in df.columns:
                try:
                    df['time'] = pd.to_datetime(df[cand])
                except Exception:
                    df['time'] = pd.to_datetime(df[cand], unit='s', errors='coerce')
                break
        else:
            # last resort: find numeric column that looks like epoch seconds
            numeric_cols = [c for c in df.columns if np.issubdtype(df[c].dtype, np.number)]
            if numeric_cols:
                df['time'] = pd.to_datetime(df[numeric_cols[0]], unit='s', errors='coerce')
            else:
                raise RuntimeError("Couldn't find a timestamp column in the returned MT5 data.")

    # ensure tick_volume exists (VWAP depends on it). If not, use real_volume or fill with zeros
    if 'tick_volume' not in df.columns:
        if 'real_volume' in df.columns:
            df.rename(columns={'real_volume': 'tick_volume'}, inplace=True)
        else:
            df['tick_volume'] = 0

    # sort by time (safety)
    df = df.sort_values('time').reset_index(drop=True)
    return df

# --------------------------- BACKTEST (REPLACEMENT) ------------------------------

def backtest(symbol, start, end, timeframe):
    """Robust bar-by-bar backtester using historical OHLCV data from MT5."""
    # ensure mt5 module & initialize
    if mt5 is None:
        raise RuntimeError('MetaTrader5 package not available - backtest requires historical data. Install MetaTrader5.')

    # convert timeframe to mt5 constant and validate
    tf = MT5_TIMEFRAMES.get(timeframe)
    if tf is None:
        raise ValueError('Unsupported timeframe for backtest: %s' % timeframe)

    # parse dates
    utc_from = datetime.fromisoformat(start)
    utc_to = datetime.fromisoformat(end)

    # fetch entry timeframe data with robust checks
    try:
        df = fetch_mt5_df(symbol, tf, utc_from, utc_to, min_bars_expected=10)
    except RuntimeError as e:
        # bubble up a clear message (includes reason)
        raise RuntimeError(f"Failed to fetch entry timeframe data: {e}")

    # compute indicators safely
    df = compute_indicators(df)

    # Fetch D1 & H4 (trend) series
    try:
        df_d1 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['D1'], utc_from, utc_to, min_bars_expected=10)
        df_d1 = compute_indicators(df_d1)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch D1 data: {e}")

    try:
        df_h4 = fetch_mt5_df(symbol, MT5_TIMEFRAMES['H4'], utc_from, utc_to, min_bars_expected=10)
        df_h4 = compute_indicators(df_h4)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch H4 data: {e}")

    balance = CONFIG['capital']
    trades = []

    # iterate bar by bar
    for idx in range(len(df)):
        bar = df.iloc[:idx+1]
        current = bar.iloc[-1]

        # slices for trend calculation
        d1_slice = df_d1[df_d1['time'] <= current['time']]
        h4_slice = df_h4[df_h4['time'] <= current['time']]
        if d1_slice.empty or h4_slice.empty:
            # not enough higher-timeframe context yet
            continue

        trend = determine_trend(d1_slice, h4_slice)
        sig = entry_signal(bar)
        if sig is None:
            continue
        if sig != trend and trend != 'neutral':
            continue

        # Determine stop and target (same as your original logic)
        entry_price = current['close']
        if sig == 'long':
            stop_price = current['bb_lower']
            opposite_band = current['bb_upper']
            if stop_price >= entry_price:
                continue
            risk_per_unit = entry_price - stop_price
            tp_by_rr = entry_price + 3 * risk_per_unit
            tp = min(tp_by_rr, opposite_band)
        else:  # short
            stop_price = current['bb_upper']
            opposite_band = current['bb_lower']
            if stop_price <= entry_price:
                continue
            risk_per_unit = stop_price - entry_price
            tp_by_rr = entry_price - 3 * risk_per_unit
            tp = max(tp_by_rr, opposite_band)

        # position sizing
        risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
        if risk_per_unit == 0:
            continue
        units = risk_amount / risk_per_unit

        # simulate forward until TP or SL hit using future bars
        trade_open = True
        for fwd in range(idx+1, len(df)):
            high = df.iloc[fwd]['high']
            low = df.iloc[fwd]['low']

            if sig == 'long':
                if low <= stop_price:
                    exit_price = stop_price
                    pl = (exit_price - entry_price) * units
                    balance += pl
                    trades.append({'entry_time': current['time'], 'side': 'long', 'entry': entry_price, 'exit': exit_price, 'pl': pl})
                    trade_open = False
                    break
                if high >= tp:
                    exit_price = tp
                    pl = (exit_price - entry_price) * units
                    balance += pl
                    trades.append({'entry_time': current['time'], 'side': 'long', 'entry': entry_price, 'exit': exit_price, 'pl': pl})
                    trade_open = False
                    break
            else:
                if high >= stop_price:
                    exit_price = stop_price
                    pl = (entry_price - exit_price) * units
                    balance += pl
                    trades.append({'entry_time': current['time'], 'side': 'short', 'entry': entry_price, 'exit': exit_price, 'pl': pl})
                    trade_open = False
                    break
                if low <= tp:
                    exit_price = tp
                    pl = (entry_price - exit_price) * units
                    balance += pl
                    trades.append({'entry_time': current['time'], 'side': 'short', 'entry': entry_price, 'exit': exit_price, 'pl': pl})
                    trade_open = False
                    break

        if trade_open:
            exit_price = df.iloc[-1]['close']
            if sig == 'long':
                pl = (exit_price - entry_price) * units
            else:
                pl = (entry_price - exit_price) * units
            balance += pl
            trades.append({'entry_time': current['time'], 'side': sig, 'entry': entry_price, 'exit': exit_price, 'pl': pl})

    trades_df = pd.DataFrame(trades)
    summary = {
        'starting_balance': CONFIG['capital'],
        'ending_balance': balance,
        'trades': len(trades_df),
        'wins': len(trades_df[trades_df['pl'] > 0]) if not trades_df.empty else 0,
        'losses': len(trades_df[trades_df['pl'] <= 0]) if not trades_df.empty else 0,
    }
    print('Backtest summary:')
    print(summary)
    return trades_df, summary

# --------------------------- LIVE TRADING --------------------------

def connect_mt5(path=None):
    if mt5 is None:
        raise RuntimeError('MetaTrader5 module not installed. Run: pip install MetaTrader5')
    if not mt5.initialize(path):
        raise RuntimeError('mt5.initialize() failed, error={}'.format(mt5.last_error()))
    print('MT5 initialized')


def disconnect_mt5():
    if mt5:
        mt5.shutdown()


def get_account_balance():
    info = mt5.account_info()
    if info is None:
        raise RuntimeError('Could not get account info; ensure MT5 terminal is logged in')
    return info.balance


def get_symbol_info(symbol):
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f'Symbol {symbol} not available in Market Watch')
    return info


def calc_volume(symbol, entry_price, stop_price, risk_amount):
    """Approximate lot size calculation. Uses symbol_info to compute pip value per lot.
       This is broker-dependent; test on demo.
    """
    si = get_symbol_info(symbol)
    # pip in price units: if digits = 5 or 3 -> pip=0.0001 else 0.01
    point = si.point
    # use tick value when available
    tick = mt5.symbol_info_tick(symbol)
    # contract size
    contract_size = si.trade_contract_size if si.trade_contract_size else 100000
    # For many forex pairs, pip move = 0.0001; value per lot per pip = contract_size * pip
    # risk in account currency = risk_amount
    risk_in_price_units = abs(entry_price - stop_price)
    if risk_in_price_units == 0:
        return 0.01
    # approximate lots
    # amount per full lot per 1 price unit movement = contract_size
    # so lots = risk_amount / (risk_in_price_units * contract_size)
    lots = risk_amount / (risk_in_price_units * contract_size)
    # round to broker min step
    step = si.volume_step
    if step is None or step == 0:
        step = 0.01
    lots = math.floor(lots / step) * step
    min_lot = si.volume_min
    if lots < min_lot:
        lots = min_lot
    return round(lots, 2)


def place_market_order(symbol, side, volume, sl, tp):
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise RuntimeError('Symbol not found')
    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)
    price = mt5.symbol_info_tick(symbol).ask if side == 'buy' else mt5.symbol_info_tick(symbol).bid
    deviation = 20
    request = {
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': symbol,
        'volume': volume,
        'type': mt5.ORDER_TYPE_BUY if side == 'buy' else mt5.ORDER_TYPE_SELL,
        'price': price,
        'sl': sl,
        'tp': tp,
        'deviation': deviation,
        'magic': 234000,
        'comment': 'Python MT5 bot',
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(request)
    return result


def live_run_once():
    # get recent data for trend timeframes and entry timeframe
    sym = CONFIG['symbol']
    # fetch enough bars
    bars_entry = mt5.copy_rates_from_pos(sym, MT5_TIMEFRAMES[CONFIG['timeframe_entry']], 0, 500)
    df_entry = pd.DataFrame(bars_entry)
    df_entry['time'] = pd.to_datetime(df_entry['time'], unit='s')
    df_entry = compute_indicators(df_entry)

    bars_d1 = mt5.copy_rates_from_pos(sym, MT5_TIMEFRAMES['D1'], 0, 500)
    df_d1 = pd.DataFrame(bars_d1)
    df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
    df_d1 = compute_indicators(df_d1)

    bars_h4 = mt5.copy_rates_from_pos(sym, MT5_TIMEFRAMES['H4'], 0, 500)
    df_h4 = pd.DataFrame(bars_h4)
    df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
    df_h4 = compute_indicators(df_h4)

    trend = determine_trend(df_d1, df_h4)
    sig = entry_signal(df_entry)
    print('Trend:', trend, 'Signal:', sig)
    if sig is None:
        print('No entry signal')
        return
    if trend != sig and trend != 'neutral':
        print('Signal opposite to trend; skipping')
        return
    # compute stop/TP
    last = df_entry.iloc[-1]
    entry_price = last['close']
    if sig == 'long':
        stop_price = last['bb_lower']
        opposite_band = last['bb_upper']
        risk_per_unit = entry_price - stop_price
        tp_by_rr = entry_price + 3 * risk_per_unit
        tp = min(tp_by_rr, opposite_band)
        side = 'buy'
    else:
        stop_price = last['bb_upper']
        opposite_band = last['bb_lower']
        risk_per_unit = stop_price - entry_price
        tp_by_rr = entry_price - 3 * risk_per_unit
        tp = max(tp_by_rr, opposite_band)
        side = 'sell'

    balance = get_account_balance()
    risk_amount = (CONFIG['risk_pct'] / 100.0) * balance
    volume = calc_volume(CONFIG['symbol'], entry_price, stop_price, risk_amount)
    print('Placing order:', side, 'volume:', volume, 'entry:', entry_price, 'sl:', stop_price, 'tp:', tp)
    res = place_market_order(CONFIG['symbol'], side, volume, stop_price, tp)
    print('Order send result:', res)

# ----------------------------- MAIN -------------------------------

def main():
    if CONFIG['backtest']:
        print('Running backtest...')
        trades, summary = backtest(CONFIG['symbol'], CONFIG['start'], CONFIG['end'], CONFIG['timeframe_entry'])
        print(trades.head())
    else:
        print('Running live mode...')
        connect_mt5()
        try:
            live_run_once()
        finally:
            disconnect_mt5()


if __name__ == '__main__':
    main()
