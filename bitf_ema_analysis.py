#!/usr/bin/env python3
"""
BITF.CA EMA 9/18 Crossover Day-Trading Strategy Analysis
=========================================================
Analyzes Bitfarms (BITF) using EMA-9 and EMA-18 crossover signals.

Strategy Rules:
- BUY  when EMA-9 crosses ABOVE EMA-18 (bullish crossover)
- SELL when EMA-9 crosses BELOW EMA-18 (bearish crossover)
- Position size: 10,000 shares
- Take profit:   $300
- Stop loss:     $500

Usage:
  1. With yfinance (auto-fetch): python3 bitf_ema_analysis.py
  2. With CSV file:              python3 bitf_ema_analysis.py --csv BITF_data.csv

  CSV format: Date,Open,High,Low,Close  (Date as YYYY-MM-DD)

  To download CSV from Yahoo Finance:
    Go to https://finance.yahoo.com/quote/BITF.TO/history/
    Set date range (need ~90 days for EMA warm-up + 60-day analysis)
    Click "Download" button
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
                    help="Ticker symbol (default: BITF.TO for Canadian listing)")
parser.add_argument("--shares", type=int, default=10000, help="Position size (default: 10000)")
parser.add_argument("--take-profit", type=float, default=300.0, help="Take profit $ (default: 300)")
parser.add_argument("--stop-loss", type=float, default=500.0, help="Stop loss $ (default: 500)")
parser.add_argument("--days", type=int, default=60, help="Analysis window in trading days (default: 60)")
args = parser.parse_args()


def ema(values, span):
    """Calculate Exponential Moving Average."""
    multiplier = 2.0 / (span + 1)
    result = [values[0]]
    for i in range(1, len(values)):
        result.append(values[i] * multiplier + result[-1] * (1 - multiplier))
    return result


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
            # Handle various column name formats
            date_val = row.get("Date") or row.get("date") or row.get("Datetime")
            open_val = row.get("Open") or row.get("open")
            high_val = row.get("High") or row.get("high")
            low_val = row.get("Low") or row.get("low")
            close_val = row.get("Close") or row.get("close") or row.get("Adj Close")

            if date_val and close_val:
                try:
                    # Parse date (handle various formats)
                    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
                        try:
                            dt = datetime.strptime(date_val.strip().split(" ")[0], fmt.split(" ")[0])
                            break
                        except ValueError:
                            continue
                    else:
                        continue

                    dates.append(dt)
                    opens.append(float(open_val))
                    highs.append(float(high_val))
                    lows.append(float(low_val))
                    closes.append(float(close_val))
                except (ValueError, TypeError):
                    continue

    # Sort by date
    combined = sorted(zip(dates, opens, highs, lows, closes), key=lambda x: x[0])
    dates = [c[0] for c in combined]
    opens = [c[1] for c in combined]
    highs = [c[2] for c in combined]
    lows = [c[3] for c in combined]
    closes = [c[4] for c in combined]

else:
    # Try yfinance
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance not installed. Install with: pip install yfinance")
        print("       Or provide a CSV file with --csv flag.")
        sys.exit(1)

    end_date = datetime.today()
    start_date = end_date - timedelta(days=150)

    print(f"Fetching {args.ticker} daily data via yfinance ...")
    ticker = yf.Ticker(args.ticker)
    df = ticker.history(start=start_date.strftime("%Y-%m-%d"),
                        end=end_date.strftime("%Y-%m-%d"))

    if df.empty and args.ticker == "BITF.TO":
        print("No data for BITF.TO, trying BITF (US listing) ...")
        ticker = yf.Ticker("BITF")
        df = ticker.history(start=start_date.strftime("%Y-%m-%d"),
                            end=end_date.strftime("%Y-%m-%d"))

    if df.empty:
        print("ERROR: Could not fetch data. Try providing a CSV file with --csv.")
        sys.exit(1)

    for idx, row in df.iterrows():
        dates.append(idx.to_pydatetime().replace(tzinfo=None))
        opens.append(float(row["Open"]))
        highs.append(float(row["High"]))
        lows.append(float(row["Low"]))
        closes.append(float(row["Close"]))

n = len(dates)
print(f"Loaded {n} trading days of data.\n")

if n < args.days + 18:
    print(f"WARNING: Need at least {args.days + 18} days for reliable EMAs. Have {n}.")

# ---------------------------------------------------------------------------
# 2. Calculate EMAs over full dataset
# ---------------------------------------------------------------------------
ema_9 = ema(closes, 9)
ema_18 = ema(closes, 18)

# ---------------------------------------------------------------------------
# 3. Identify crossover signals within last N trading days
# ---------------------------------------------------------------------------
start_idx = max(0, n - args.days)

# Determine EMA relationship for each day
ema_9_above = [ema_9[i] > ema_18[i] for i in range(n)]

# Find crossovers in the analysis window
signals = []  # list of (index, "BUY" or "SELL")
for i in range(start_idx, n):
    if i == 0:
        continue
    if ema_9_above[i] != ema_9_above[i - 1]:
        signal_type = "BUY" if ema_9_above[i] else "SELL"
        signals.append((i, signal_type))

# Build a set for quick lookup
signal_indices = {s[0]: s[1] for s in signals}

# ---------------------------------------------------------------------------
# 4. Simulate trades
# ---------------------------------------------------------------------------
SHARES = args.shares
TAKE_PROFIT = args.take_profit
STOP_LOSS = args.stop_loss

trades = []
position = None  # None = flat, dict when holding

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

    # --- Check for new crossover signal on this day ----------------------
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

            if position is None:
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
def fmt_date(d):
    return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)

print("=" * 94)
print(f"BITF — EMA 9/18 CROSSOVER STRATEGY BACKTEST (Last {args.days} Trading Days)")
print("=" * 94)
print(f"Ticker          : {args.ticker}")
print(f"Analysis window : {fmt_date(dates[start_idx])} to {fmt_date(dates[-1])}")
print(f"Position size   : {SHARES:,} shares")
print(f"Take profit     : ${TAKE_PROFIT:,.0f}")
print(f"Stop loss       : ${STOP_LOSS:,.0f}")
print()

# Print EMA crossover signals
print("-" * 94)
print("EMA CROSSOVER SIGNALS DETECTED")
print("-" * 94)
print(f"{'Date':<14} {'Signal':<6} {'Close':>10} {'EMA-9':>10} {'EMA-18':>10}")
print("-" * 94)
for idx, sig in signals:
    print(f"{fmt_date(dates[idx]):<14} {sig:<6} "
          f"${closes[idx]:>9.4f} ${ema_9[idx]:>9.4f} ${ema_18[idx]:>9.4f}")
print()

# Print trades
print("-" * 94)
print("TRADE LOG")
print("-" * 94)
print(f"{'#':<3} {'Entry Date':<12} {'Exit Date':<12} {'Dir':<6} "
      f"{'Entry':>9} {'Exit':>9} {'P&L':>10} {'Exit Reason'}")
print("-" * 94)

total_pnl = 0.0
wins = 0
losses = 0

for i, t in enumerate(trades, 1):
    pnl = t["pnl"]
    total_pnl += pnl
    if pnl > 0:
        wins += 1
    elif pnl < 0:
        losses += 1

    pnl_str = f"${pnl:>+,.2f}"
    print(f"{i:<3} {fmt_date(t['entry_date']):<12} {fmt_date(t['exit_date']):<12} "
          f"{t['direction']:<6} ${t['entry_price']:>8.4f} ${t['exit_price']:>8.4f} "
          f"{pnl_str:>10} {t['exit_reason']}")

print("-" * 94)
print()

# Summary
print("=" * 94)
print("SUMMARY")
print("=" * 94)
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
print(f"Total P&L          : ${total_pnl:>+,.2f}")
print()

if total_pnl > 0:
    print(f">>> RESULT: NET PROFIT of ${total_pnl:,.2f}")
elif total_pnl < 0:
    print(f">>> RESULT: NET LOSS of ${abs(total_pnl):,.2f}")
else:
    print(">>> RESULT: BREAKEVEN")

print()

# Print daily EMA data table
print("=" * 94)
print(f"DAILY EMA DATA (last {args.days} trading days)")
print("=" * 94)
print(f"{'Date':<14} {'Open':>9} {'High':>9} {'Low':>9} {'Close':>9} "
      f"{'EMA-9':>9} {'EMA-18':>9} {'Signal':<6}")
print("-" * 94)

for i in range(start_idx, n):
    sig = signal_indices.get(i, "")
    print(f"{fmt_date(dates[i]):<14} "
          f"${opens[i]:>8.4f} ${highs[i]:>8.4f} ${lows[i]:>8.4f} "
          f"${closes[i]:>8.4f} ${ema_9[i]:>8.4f} ${ema_18[i]:>8.4f} "
          f"{sig:<6}")

print("=" * 94)
