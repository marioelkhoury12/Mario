#!/usr/bin/env python3
"""
BITF EMA 9/18 Crossover Day-Trading Strategy Analysis
======================================================
Analyzes Bitfarms (BITF) using EMA-9 and EMA-18 crossover signals.

Supports DAILY and INTRADAY (5m, 15m) timeframes.

Strategy Rules:
- BUY  when EMA-9 crosses ABOVE EMA-18 (bullish crossover)
- SELL when EMA-9 crosses BELOW EMA-18 (bearish crossover)
- Position size: 10,000 shares
- Take profit:   $300
- Stop loss:     $500

Usage:
  Daily:     python3 bitf_ema_analysis.py
  5-minute:  python3 bitf_ema_analysis.py --interval 5m
  15-minute: python3 bitf_ema_analysis.py --interval 15m
  From CSV:  python3 bitf_ema_analysis.py --csv BITF_5m.csv

  yfinance intraday limits:
    5m  data: last 60 days max
    15m data: last 60 days max
    1d  data: unlimited

  CSV format: Datetime,Open,High,Low,Close
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="BITF EMA 9/18 Crossover Analysis")
parser.add_argument("--csv", type=str, help="Path to CSV file with OHLC data")
parser.add_argument("--ticker", type=str, default="BITF.TO",
                    help="Ticker symbol (default: BITF.TO)")
parser.add_argument("--interval", type=str, default="1d",
                    choices=["1d", "5m", "15m", "30m", "1h"],
                    help="Candle interval (default: 1d)")
parser.add_argument("--shares", type=int, default=10000,
                    help="Position size (default: 10000)")
parser.add_argument("--take-profit", type=float, default=300.0,
                    help="Take profit $ (default: 300)")
parser.add_argument("--stop-loss", type=float, default=500.0,
                    help="Stop loss $ (default: 500)")
parser.add_argument("--bars", type=int, default=0,
                    help="Number of bars to analyze (0 = all available)")
parser.add_argument("--long-only", action="store_true",
                    help="Only take long positions (no shorting)")
parser.add_argument("--no-table", action="store_true",
                    help="Skip printing the full candle-by-candle EMA table")
args = parser.parse_args()

INTERVAL_LABEL = {
    "1d": "Daily", "5m": "5-Minute", "15m": "15-Minute",
    "30m": "30-Minute", "1h": "1-Hour",
}


def ema(values, span):
    """Calculate Exponential Moving Average."""
    multiplier = 2.0 / (span + 1)
    result = [values[0]]
    for i in range(1, len(values)):
        result.append(values[i] * multiplier + result[-1] * (1 - multiplier))
    return result


def parse_datetime(s):
    """Parse datetime string, handling multiple formats."""
    s = s.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S%z",   # timezone-aware
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=None)  # strip tz for consistency
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
dates = []
opens = []
highs = []
lows = []
closes = []

if args.csv:
    print(f"Loading data from {args.csv} ...")
    with open(args.csv, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_val = (row.get("Datetime") or row.get("Date") or
                        row.get("date") or row.get("datetime") or
                        row.get("Timestamp") or row.get("timestamp"))
            open_val = row.get("Open") or row.get("open")
            high_val = row.get("High") or row.get("high")
            low_val = row.get("Low") or row.get("low")
            close_val = (row.get("Close") or row.get("close") or
                         row.get("Adj Close"))

            if date_val and close_val:
                dt = parse_datetime(date_val)
                if dt is None:
                    continue
                try:
                    dates.append(dt)
                    opens.append(float(open_val))
                    highs.append(float(high_val))
                    lows.append(float(low_val))
                    closes.append(float(close_val))
                except (ValueError, TypeError):
                    continue

    # Sort by datetime
    combined = sorted(zip(dates, opens, highs, lows, closes), key=lambda x: x[0])
    dates = [c[0] for c in combined]
    opens = [c[1] for c in combined]
    highs = [c[2] for c in combined]
    lows = [c[3] for c in combined]
    closes = [c[4] for c in combined]

else:
    # Use yfinance
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance not installed. Install with: pip install yfinance")
        print("       Or provide a CSV file with --csv flag.")
        sys.exit(1)

    interval = args.interval
    ticker_sym = args.ticker

    if interval == "1d":
        end_date = datetime.today()
        start_date = end_date - timedelta(days=150)
        print(f"Fetching {ticker_sym} daily data via yfinance ...")
        ticker = yf.Ticker(ticker_sym)
        df = ticker.history(start=start_date.strftime("%Y-%m-%d"),
                            end=end_date.strftime("%Y-%m-%d"),
                            interval="1d")
    else:
        # Intraday: yfinance allows max 60 days for 5m/15m
        print(f"Fetching {ticker_sym} {interval} intraday data via yfinance ...")
        print(f"(yfinance provides up to 60 calendar days of {interval} data)\n")
        ticker = yf.Ticker(ticker_sym)
        df = ticker.history(period="60d", interval=interval)

    # Fallback to US listing
    if df.empty and ticker_sym == "BITF.TO":
        alt = "BITF"
        print(f"No data for {ticker_sym}, trying {alt} ...")
        ticker = yf.Ticker(alt)
        if interval == "1d":
            df = ticker.history(start=start_date.strftime("%Y-%m-%d"),
                                end=end_date.strftime("%Y-%m-%d"),
                                interval="1d")
        else:
            df = ticker.history(period="60d", interval=interval)

    if df.empty:
        print("ERROR: Could not fetch data. Try providing a CSV with --csv.")
        sys.exit(1)

    for idx, row in df.iterrows():
        dates.append(idx.to_pydatetime().replace(tzinfo=None))
        opens.append(float(row["Open"]))
        highs.append(float(row["High"]))
        lows.append(float(row["Low"]))
        closes.append(float(row["Close"]))

n = len(dates)
label = INTERVAL_LABEL.get(args.interval, args.interval)
print(f"Loaded {n} {label.lower()} candles of data.\n")

if n < 50:
    print(f"WARNING: Only {n} candles loaded. EMAs need at least ~36 bars to stabilize.")

# ---------------------------------------------------------------------------
# 2. Calculate EMAs over full dataset
# ---------------------------------------------------------------------------
ema_9 = ema(closes, 9)
ema_18 = ema(closes, 18)

# ---------------------------------------------------------------------------
# 3. Identify crossover signals
# ---------------------------------------------------------------------------
# Determine analysis window
if args.bars > 0:
    start_idx = max(0, n - args.bars)
else:
    # For intraday, use all loaded data; for daily, last 60 bars
    if args.interval == "1d":
        start_idx = max(0, n - 60)
    else:
        # Skip first 18 bars for EMA warm-up, analyze the rest
        start_idx = min(18, n - 1)

# Determine EMA relationship for each bar
ema_9_above = [ema_9[i] > ema_18[i] for i in range(n)]

# For intraday, track which calendar day each bar belongs to
def get_date(dt):
    return dt.date() if hasattr(dt, 'date') else dt

# Find crossovers in the analysis window
signals = []
for i in range(start_idx, n):
    if i == 0:
        continue
    if ema_9_above[i] != ema_9_above[i - 1]:
        signal_type = "BUY" if ema_9_above[i] else "SELL"
        signals.append((i, signal_type))

signal_indices = {s[0]: s[1] for s in signals}

# ---------------------------------------------------------------------------
# 4. Simulate trades
# ---------------------------------------------------------------------------
SHARES = args.shares
TAKE_PROFIT = args.take_profit
STOP_LOSS = args.stop_loss

trades = []
position = None
daily_trades = {}  # track trades per calendar day for stats

for i in range(start_idx, n):
    close = closes[i]
    high = highs[i]
    low = lows[i]

    # --- Check stop-loss / take-profit on open positions FIRST -----------
    if position is not None:
        if position["direction"] == "LONG":
            unrealized_worst = (low - position["entry"]) * SHARES
            unrealized_best = (high - position["entry"]) * SHARES

            if unrealized_worst <= -STOP_LOSS:
                exit_price = position["entry"] - (STOP_LOSS / SHARES)
                trades.append({
                    "entry_date": position["entry_date"],
                    "exit_date": dates[i],
                    "direction": "LONG",
                    "entry_price": position["entry"],
                    "exit_price": round(exit_price, 4),
                    "pnl": -STOP_LOSS,
                    "exit_reason": "STOP LOSS",
                })
                position = None
            elif unrealized_best >= TAKE_PROFIT:
                exit_price = position["entry"] + (TAKE_PROFIT / SHARES)
                trades.append({
                    "entry_date": position["entry_date"],
                    "exit_date": dates[i],
                    "direction": "LONG",
                    "entry_price": position["entry"],
                    "exit_price": round(exit_price, 4),
                    "pnl": TAKE_PROFIT,
                    "exit_reason": "TAKE PROFIT",
                })
                position = None

        elif position["direction"] == "SHORT":
            unrealized_worst = (position["entry"] - high) * SHARES
            unrealized_best = (position["entry"] - low) * SHARES

            if unrealized_worst <= -STOP_LOSS:
                exit_price = position["entry"] + (STOP_LOSS / SHARES)
                trades.append({
                    "entry_date": position["entry_date"],
                    "exit_date": dates[i],
                    "direction": "SHORT",
                    "entry_price": position["entry"],
                    "exit_price": round(exit_price, 4),
                    "pnl": -STOP_LOSS,
                    "exit_reason": "STOP LOSS",
                })
                position = None
            elif unrealized_best >= TAKE_PROFIT:
                exit_price = position["entry"] - (TAKE_PROFIT / SHARES)
                trades.append({
                    "entry_date": position["entry_date"],
                    "exit_date": dates[i],
                    "direction": "SHORT",
                    "entry_price": position["entry"],
                    "exit_price": round(exit_price, 4),
                    "pnl": TAKE_PROFIT,
                    "exit_reason": "TAKE PROFIT",
                })
                position = None

    # --- Check for new crossover signal on this bar ----------------------
    if i in signal_indices:
        signal = signal_indices[i]

        if signal == "BUY":
            if position is not None and position["direction"] == "SHORT":
                pnl = (position["entry"] - close) * SHARES
                trades.append({
                    "entry_date": position["entry_date"],
                    "exit_date": dates[i],
                    "direction": "SHORT",
                    "entry_price": position["entry"],
                    "exit_price": close,
                    "pnl": round(pnl, 2),
                    "exit_reason": "EMA CROSSOVER (BUY signal)",
                })
                position = None

            if position is None:
                position = {
                    "entry_date": dates[i],
                    "entry": close,
                    "direction": "LONG",
                }

        elif signal == "SELL":
            if position is not None and position["direction"] == "LONG":
                pnl = (close - position["entry"]) * SHARES
                trades.append({
                    "entry_date": position["entry_date"],
                    "exit_date": dates[i],
                    "direction": "LONG",
                    "entry_price": position["entry"],
                    "exit_price": close,
                    "pnl": round(pnl, 2),
                    "exit_reason": "EMA CROSSOVER (SELL signal)",
                })
                position = None

            if position is None and not args.long_only:
                position = {
                    "entry_date": dates[i],
                    "entry": close,
                    "direction": "SHORT",
                }

# Close any remaining open position at last close
if position is not None:
    last_close = closes[-1]
    last_date = dates[-1]
    if position["direction"] == "LONG":
        pnl = (last_close - position["entry"]) * SHARES
    else:
        pnl = (position["entry"] - last_close) * SHARES
    trades.append({
        "entry_date": position["entry_date"],
        "exit_date": last_date,
        "direction": position["direction"],
        "entry_price": position["entry"],
        "exit_price": last_close,
        "pnl": round(pnl, 2),
        "exit_reason": "OPEN (marked to market)",
    })

# ---------------------------------------------------------------------------
# 5. Print Results
# ---------------------------------------------------------------------------
def fmt_dt(d):
    """Format datetime — include time for intraday, date-only for daily."""
    if not hasattr(d, "strftime"):
        return str(d)
    if args.interval == "1d" or (d.hour == 0 and d.minute == 0):
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%d %H:%M")


print("=" * 100)
print(f"BITF — EMA 9/18 CROSSOVER STRATEGY BACKTEST ({label} Candles)")
print("=" * 100)
print(f"Ticker          : {args.ticker}")
print(f"Interval        : {label} ({args.interval})")
print(f"Analysis window : {fmt_dt(dates[start_idx])} to {fmt_dt(dates[-1])}")
print(f"Candles analyzed: {n - start_idx}")
print(f"Position size   : {SHARES:,} shares")
print(f"Take profit     : ${TAKE_PROFIT:,.0f}  (${TAKE_PROFIT/SHARES:.4f}/share)")
print(f"Stop loss       : ${STOP_LOSS:,.0f}  (${STOP_LOSS/SHARES:.4f}/share)")
print(f"Mode            : {'Long-only' if args.long_only else 'Long & Short'}")
print()

# Per-share move context
avg_price = sum(closes[start_idx:]) / (n - start_idx)
tp_pct = (TAKE_PROFIT / SHARES) / avg_price * 100
sl_pct = (STOP_LOSS / SHARES) / avg_price * 100
print(f"  Avg price in window: ${avg_price:.4f}")
print(f"  TP triggers at {tp_pct:.2f}% move | SL triggers at {sl_pct:.2f}% move")
print()

# Crossover signals
print("-" * 100)
print("EMA CROSSOVER SIGNALS DETECTED")
print("-" * 100)
col_w = 20 if args.interval != "1d" else 14
header = f"{'Datetime':<{col_w}} {'Signal':<6} {'Close':>10} {'EMA-9':>10} {'EMA-18':>10}"
print(header)
print("-" * 100)
for idx, sig in signals:
    print(f"{fmt_dt(dates[idx]):<{col_w}} {sig:<6} "
          f"${closes[idx]:>9.4f} ${ema_9[idx]:>9.4f} ${ema_18[idx]:>9.4f}")

if not signals:
    print("  (No crossover signals detected in this window)")
print()

# Trade log
print("-" * 100)
print("TRADE LOG")
print("-" * 100)
col_w2 = 18 if args.interval != "1d" else 12
print(f"{'#':<3} {'Entry':<{col_w2}} {'Exit':<{col_w2}} {'Dir':<6} "
      f"{'Entry$':>9} {'Exit$':>9} {'P&L':>10} {'Exit Reason'}")
print("-" * 100)

total_pnl = 0.0
wins = 0
losses = 0
max_drawdown = 0.0
running_pnl = 0.0
peak_pnl = 0.0

for i, t in enumerate(trades, 1):
    pnl = t["pnl"]
    total_pnl += pnl
    running_pnl += pnl
    peak_pnl = max(peak_pnl, running_pnl)
    drawdown = peak_pnl - running_pnl
    max_drawdown = max(max_drawdown, drawdown)

    if pnl > 0:
        wins += 1
    elif pnl < 0:
        losses += 1

    pnl_str = f"${pnl:>+,.2f}"
    print(f"{i:<3} {fmt_dt(t['entry_date']):<{col_w2}} {fmt_dt(t['exit_date']):<{col_w2}} "
          f"{t['direction']:<6} ${t['entry_price']:>8.4f} ${t['exit_price']:>8.4f} "
          f"{pnl_str:>10} {t['exit_reason']}")

if not trades:
    print("  (No trades executed)")
print("-" * 100)
print()

# Summary
print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total signals      : {len(signals)}")
print(f"Total trades       : {len(trades)}")
print(f"Winning trades     : {wins}")
print(f"Losing trades      : {losses}")
print(f"Breakeven trades   : {len(trades) - wins - losses}")
if len(trades) > 0:
    print(f"Win rate           : {wins / len(trades) * 100:.1f}%")
    avg_win = sum(t["pnl"] for t in trades if t["pnl"] > 0) / max(wins, 1)
    avg_loss = sum(t["pnl"] for t in trades if t["pnl"] < 0) / max(losses, 1)
    print(f"Avg winning trade  : ${avg_win:>+,.2f}")
    print(f"Avg losing trade   : ${avg_loss:>+,.2f}")
    if wins > 0 and losses > 0:
        profit_factor = abs(avg_win * wins) / abs(avg_loss * losses)
        print(f"Profit factor      : {profit_factor:.2f}")
    print(f"Max drawdown       : ${max_drawdown:>,.2f}")
    # Breakeven win rate needed
    if abs(avg_loss) > 0:
        be_wr = abs(avg_loss) / (avg_win + abs(avg_loss)) * 100 if avg_win > 0 else 100
        print(f"Breakeven win rate : {be_wr:.1f}%")
print(f"Total P&L          : ${total_pnl:>+,.2f}")
print()

if total_pnl > 0:
    print(f">>> RESULT: NET PROFIT of ${total_pnl:,.2f}")
elif total_pnl < 0:
    print(f">>> RESULT: NET LOSS of ${abs(total_pnl):,.2f}")
else:
    print(">>> RESULT: BREAKEVEN")

# Per-day breakdown for intraday
if args.interval != "1d" and trades:
    print()
    print("-" * 100)
    print("P&L BY CALENDAR DAY")
    print("-" * 100)
    day_pnl = {}
    day_count = {}
    for t in trades:
        d = get_date(t["entry_date"])
        day_pnl[d] = day_pnl.get(d, 0) + t["pnl"]
        day_count[d] = day_count.get(d, 0) + 1
    for d in sorted(day_pnl.keys()):
        print(f"  {d}  :  {day_count[d]} trades  |  P&L: ${day_pnl[d]:>+,.2f}")
    print("-" * 100)

print()

# Candle-by-candle EMA table (optional)
if not args.no_table:
    print("=" * 100)
    print(f"CANDLE-BY-CANDLE EMA DATA (last {n - start_idx} bars)")
    print("=" * 100)
    col_w3 = 20 if args.interval != "1d" else 14
    print(f"{'Datetime':<{col_w3}} {'Open':>9} {'High':>9} {'Low':>9} {'Close':>9} "
          f"{'EMA-9':>9} {'EMA-18':>9} {'Signal':<6}")
    print("-" * 100)

    # For large datasets, show first/last 50 bars with "..." in between
    total_bars = n - start_idx
    if total_bars > 120:
        show_first = 40
        show_last = 40
        for i in range(start_idx, start_idx + show_first):
            sig = signal_indices.get(i, "")
            print(f"{fmt_dt(dates[i]):<{col_w3}} "
                  f"${opens[i]:>8.4f} ${highs[i]:>8.4f} ${lows[i]:>8.4f} "
                  f"${closes[i]:>8.4f} ${ema_9[i]:>8.4f} ${ema_18[i]:>8.4f} "
                  f"{sig:<6}")
        skipped = total_bars - show_first - show_last
        print(f"  ... ({skipped} bars omitted — use --no-table to skip) ...")
        for i in range(n - show_last, n):
            sig = signal_indices.get(i, "")
            print(f"{fmt_dt(dates[i]):<{col_w3}} "
                  f"${opens[i]:>8.4f} ${highs[i]:>8.4f} ${lows[i]:>8.4f} "
                  f"${closes[i]:>8.4f} ${ema_9[i]:>8.4f} ${ema_18[i]:>8.4f} "
                  f"{sig:<6}")
    else:
        for i in range(start_idx, n):
            sig = signal_indices.get(i, "")
            print(f"{fmt_dt(dates[i]):<{col_w3}} "
                  f"${opens[i]:>8.4f} ${highs[i]:>8.4f} ${lows[i]:>8.4f} "
                  f"${closes[i]:>8.4f} ${ema_9[i]:>8.4f} ${ema_18[i]:>8.4f} "
                  f"{sig:<6}")

    print("=" * 100)
