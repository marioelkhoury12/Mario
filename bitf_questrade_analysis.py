#!/usr/bin/env python3
"""
BITF EMA 9/18 Crossover Analysis — Questrade API Edition
==========================================================
Fetches BITF intraday (5m/15m) or daily candle data from Questrade,
then runs the EMA 9/18 crossover trading strategy backtest.

Usage:
  # First run — provide your Questrade API refresh token:
  python3 bitf_questrade_analysis.py --token YOUR_REFRESH_TOKEN

  # Subsequent runs — token auto-refreshes from saved file:
  python3 bitf_questrade_analysis.py

  # 5-minute candles (default):
  python3 bitf_questrade_analysis.py --interval 5m

  # 15-minute candles:
  python3 bitf_questrade_analysis.py --interval 15m

  # Daily candles, last year:
  python3 bitf_questrade_analysis.py --interval 1d --lookback 365

  # Custom parameters:
  python3 bitf_questrade_analysis.py --interval 5m --take-profit 200 --stop-loss 800

Questrade API docs: https://www.questrade.com/api/documentation
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="BITF EMA 9/18 Crossover Analysis via Questrade API")
parser.add_argument("--token", type=str,
                    help="Questrade API refresh token")
parser.add_argument("--token-file", type=str, default=".questrade_token",
                    help="File to save/load refresh token (default: .questrade_token)")
parser.add_argument("--symbol", type=str, default="BITF.TO",
                    help="Symbol to analyze (default: BITF.TO)")
parser.add_argument("--interval", type=str, default="5m",
                    choices=["1m", "5m", "15m", "30m", "1h", "1d"],
                    help="Candle interval (default: 5m)")
parser.add_argument("--lookback", type=int, default=30,
                    help="Days of history to fetch (default: 30, max ~30 for 5m)")
parser.add_argument("--shares", type=int, default=10000,
                    help="Position size (default: 10000)")
parser.add_argument("--take-profit", type=float, default=200.0,
                    help="Take profit $ (default: 200)")
parser.add_argument("--stop-loss", type=float, default=800.0,
                    help="Stop loss $ (default: 800)")
parser.add_argument("--long-only", action="store_true",
                    help="Only take long positions (no shorting)")
parser.add_argument("--no-table", action="store_true",
                    help="Skip printing the candle-by-candle EMA table")
parser.add_argument("--save-csv", type=str,
                    help="Save fetched data to CSV file")
args = parser.parse_args()

# Map CLI intervals to Questrade API interval names
INTERVAL_MAP = {
    "1m": "OneMinute",
    "5m": "FiveMinutes",
    "15m": "FifteenMinutes",
    "30m": "HalfHour",
    "1h": "OneHour",
    "1d": "OneDay",
}

INTERVAL_LABEL = {
    "1m": "1-Minute", "5m": "5-Minute", "15m": "15-Minute",
    "30m": "30-Minute", "1h": "1-Hour", "1d": "Daily",
}

# ---------------------------------------------------------------------------
# Questrade API Helper
# ---------------------------------------------------------------------------
class QuestradeAPI:
    def __init__(self, refresh_token=None, token_file=".questrade_token"):
        self.token_file = token_file
        self.access_token = None
        self.api_server = None
        self.refresh_token = refresh_token

        # Try to load saved token
        if not self.refresh_token and os.path.exists(self.token_file):
            with open(self.token_file, "r") as f:
                saved = json.load(f)
                self.refresh_token = saved.get("refresh_token")
                self.access_token = saved.get("access_token")
                self.api_server = saved.get("api_server")
                # Check if token might still be valid
                expires = saved.get("expires_at", 0)
                if datetime.now().timestamp() < expires and self.access_token:
                    print(f"Using cached token (expires {datetime.fromtimestamp(expires).strftime('%H:%M:%S')})")
                    return

        if not self.refresh_token:
            print("ERROR: No Questrade refresh token provided.")
            print("  Get one from: https://login.questrade.com/APIAccess/UserApps.aspx")
            print("  Then run: python3 bitf_questrade_analysis.py --token YOUR_TOKEN")
            sys.exit(1)

        self._authenticate()

    def _authenticate(self):
        """Exchange refresh token for access token."""
        url = (f"https://login.questrade.com/oauth2/token"
               f"?grant_type=refresh_token&refresh_token={self.refresh_token}")

        req = urllib.request.Request(url, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"ERROR: Questrade auth failed (HTTP {e.code}): {body}")
            print("\nYour refresh token may have expired. Generate a new one at:")
            print("  https://login.questrade.com/APIAccess/UserApps.aspx")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Could not reach Questrade: {e}")
            sys.exit(1)

        self.access_token = data["access_token"]
        self.api_server = data["api_server"]
        self.refresh_token = data["refresh_token"]

        # Save for next run
        expires_at = datetime.now().timestamp() + data.get("expires_in", 1800)
        with open(self.token_file, "w") as f:
            json.dump({
                "access_token": self.access_token,
                "api_server": self.api_server,
                "refresh_token": self.refresh_token,
                "expires_at": expires_at,
            }, f)

        print(f"Authenticated with Questrade (server: {self.api_server})")
        print(f"New refresh token saved to {self.token_file}")

    def _get(self, endpoint):
        """Make authenticated GET request to Questrade API."""
        url = f"{self.api_server}v1/{endpoint}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.access_token}",
        })
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 401:
                print("Token expired, re-authenticating...")
                self._authenticate()
                return self._get(endpoint)
            print(f"API Error (HTTP {e.code}): {body}")
            sys.exit(1)

    def search_symbol(self, name):
        """Search for a symbol and return its ID."""
        data = self._get(f"symbols/search?prefix={name}")
        symbols = data.get("symbols", [])
        if not symbols:
            print(f"ERROR: Symbol '{name}' not found on Questrade.")
            sys.exit(1)

        # Prefer exact match
        for s in symbols:
            if s["symbol"].upper() == name.upper():
                print(f"Found: {s['symbol']} (ID: {s['symbolId']}) — {s['description']}")
                return s["symbolId"]

        # Fall back to first result
        s = symbols[0]
        print(f"Found: {s['symbol']} (ID: {s['symbolId']}) — {s['description']}")
        return s["symbolId"]

    def get_candles(self, symbol_id, start_time, end_time, interval):
        """
        Fetch candle data. Questrade limits to 2000 candles per request,
        so we paginate if needed.
        """
        qt_interval = INTERVAL_MAP.get(interval, "FiveMinutes")
        all_candles = []

        # For intraday, fetch day-by-day to avoid hitting the 2000 limit
        current = start_time
        while current < end_time:
            if interval in ("1m", "5m", "15m", "30m", "1h"):
                chunk_end = min(current + timedelta(days=1), end_time)
            else:
                chunk_end = min(current + timedelta(days=365), end_time)

            start_str = current.strftime("%Y-%m-%dT%H:%M:%S-05:00")
            end_str = chunk_end.strftime("%Y-%m-%dT%H:%M:%S-05:00")

            endpoint = (f"markets/candles/{symbol_id}"
                        f"?startTime={start_str}&endTime={end_str}"
                        f"&interval={qt_interval}")

            data = self._get(endpoint)
            candles = data.get("candles", [])
            all_candles.extend(candles)

            if interval in ("1m", "5m", "15m", "30m", "1h"):
                current += timedelta(days=1)
            else:
                current += timedelta(days=365)

            # Progress
            pct = min(100, (current - start_time) / (end_time - start_time) * 100)
            print(f"\r  Fetching candles... {pct:.0f}%  ({len(all_candles)} candles)", end="")

        print()
        return all_candles


# ---------------------------------------------------------------------------
# EMA Calculation
# ---------------------------------------------------------------------------
def ema(values, span):
    multiplier = 2.0 / (span + 1)
    result = [values[0]]
    for i in range(1, len(values)):
        result.append(values[i] * multiplier + result[-1] * (1 - multiplier))
    return result


def fmt_dt(d, interval):
    if not hasattr(d, "strftime"):
        return str(d)
    if interval == "1d":
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%d %H:%M")


def get_date(dt):
    return dt.date() if hasattr(dt, 'date') else dt


# ---------------------------------------------------------------------------
# 1. Connect to Questrade and fetch data
# ---------------------------------------------------------------------------
print("=" * 100)
print("BITF EMA 9/18 CROSSOVER ANALYSIS — Questrade API")
print("=" * 100)
print()

qt = QuestradeAPI(refresh_token=args.token, token_file=args.token_file)

# Find symbol ID
print(f"\nSearching for symbol: {args.symbol}")
symbol_id = qt.search_symbol(args.symbol)

# Fetch candles
end_time = datetime.now()
start_time = end_time - timedelta(days=args.lookback)
print(f"\nFetching {INTERVAL_LABEL[args.interval]} candles from "
      f"{start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}...")

raw_candles = qt.get_candles(symbol_id, start_time, end_time, args.interval)

if not raw_candles:
    print("ERROR: No candle data returned.")
    sys.exit(1)

# Parse candle data
dates = []
opens = []
highs = []
lows = []
closes = []

for c in raw_candles:
    # Skip candles with no volume (pre/post market gaps)
    if c.get("volume", 0) == 0 and args.interval != "1d":
        continue
    # Parse Questrade datetime format
    dt_str = c["start"]
    try:
        # Handle various ISO formats Questrade returns
        dt_str = dt_str.replace("T", " ").split(".")[0].split("+")[0].split("-05:00")[0]
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(dt_str.strip(), fmt)
                break
            except ValueError:
                continue
        else:
            continue
    except Exception:
        continue

    dates.append(dt)
    opens.append(float(c["open"]))
    highs.append(float(c["high"]))
    lows.append(float(c["low"]))
    closes.append(float(c["close"]))

n = len(dates)
label = INTERVAL_LABEL[args.interval]
print(f"\nLoaded {n} {label.lower()} candles.\n")

if n < 36:
    print(f"WARNING: Only {n} candles. EMAs need ~36+ bars to stabilize.")

# Save to CSV if requested
if args.save_csv:
    with open(args.save_csv, "w") as f:
        f.write("Datetime,Open,High,Low,Close\n")
        for i in range(n):
            f.write(f"{dates[i].strftime('%Y-%m-%d %H:%M:%S')},"
                    f"{opens[i]},{highs[i]},{lows[i]},{closes[i]}\n")
    print(f"Data saved to {args.save_csv}")

# ---------------------------------------------------------------------------
# 2. Calculate EMAs
# ---------------------------------------------------------------------------
ema_9 = ema(closes, 9)
ema_18 = ema(closes, 18)

# ---------------------------------------------------------------------------
# 3. Find crossover signals (skip first 18 bars for EMA warm-up)
# ---------------------------------------------------------------------------
start_idx = min(18, n - 1)
ema_9_above = [ema_9[i] > ema_18[i] for i in range(n)]

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

for i in range(start_idx, n):
    close = closes[i]
    high = highs[i]
    low = lows[i]

    # Check stop-loss / take-profit first
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

    # Check for crossover signal
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

# Close remaining position
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
print("=" * 100)
print(f"BITF — EMA 9/18 CROSSOVER STRATEGY BACKTEST ({label} Candles)")
print("=" * 100)
print(f"Symbol          : {args.symbol}")
print(f"Interval        : {label} ({args.interval})")
print(f"Analysis window : {fmt_dt(dates[start_idx], args.interval)} to "
      f"{fmt_dt(dates[-1], args.interval)}")
print(f"Candles analyzed: {n - start_idx}")
print(f"Position size   : {SHARES:,} shares")
print(f"Take profit     : ${TAKE_PROFIT:,.0f}  (${TAKE_PROFIT/SHARES:.4f}/share)")
print(f"Stop loss       : ${STOP_LOSS:,.0f}  (${STOP_LOSS/SHARES:.4f}/share)")
print(f"Mode            : {'Long-only' if args.long_only else 'Long & Short'}")
print()

avg_price = sum(closes[start_idx:]) / max(n - start_idx, 1)
tp_pct = (TAKE_PROFIT / SHARES) / avg_price * 100
sl_pct = (STOP_LOSS / SHARES) / avg_price * 100
print(f"  Avg price in window: ${avg_price:.4f}")
print(f"  TP triggers at {tp_pct:.2f}% move | SL triggers at {sl_pct:.2f}% move")
print()

# Signals
print("-" * 100)
print("EMA CROSSOVER SIGNALS DETECTED")
print("-" * 100)
col_w = 20 if args.interval != "1d" else 14
print(f"{'Datetime':<{col_w}} {'Signal':<6} {'Close':>10} {'EMA-9':>10} {'EMA-18':>10}")
print("-" * 100)
for idx, sig in signals:
    print(f"{fmt_dt(dates[idx], args.interval):<{col_w}} {sig:<6} "
          f"${closes[idx]:>9.4f} ${ema_9[idx]:>9.4f} ${ema_18[idx]:>9.4f}")
if not signals:
    print("  (No crossover signals)")
print()

# Trade log
print("-" * 100)
print("TRADE LOG")
print("-" * 100)
col_w2 = 18 if args.interval != "1d" else 12
print(f"{'#':<4} {'Entry':<{col_w2}} {'Exit':<{col_w2}} {'Dir':<6} "
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
    max_drawdown = max(max_drawdown, peak_pnl - running_pnl)

    if pnl > 0:
        wins += 1
    elif pnl < 0:
        losses += 1

    print(f"{i:<4} {fmt_dt(t['entry_date'], args.interval):<{col_w2}} "
          f"{fmt_dt(t['exit_date'], args.interval):<{col_w2}} "
          f"{t['direction']:<6} ${t['entry_price']:>8.4f} ${t['exit_price']:>8.4f} "
          f"${pnl:>+9.2f} {t['exit_reason']}")

if not trades:
    print("  (No trades)")
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
    if avg_win > 0 and abs(avg_loss) > 0:
        be_wr = abs(avg_loss) / (avg_win + abs(avg_loss)) * 100
        print(f"Breakeven win rate : {be_wr:.1f}%")
print(f"Total P&L          : ${total_pnl:>+,.2f}")
print()

if total_pnl > 0:
    print(f">>> RESULT: NET PROFIT of ${total_pnl:,.2f}")
elif total_pnl < 0:
    print(f">>> RESULT: NET LOSS of ${abs(total_pnl):,.2f}")
else:
    print(">>> RESULT: BREAKEVEN")

# Per-day P&L breakdown for intraday
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

    winning_days = sum(1 for v in day_pnl.values() if v > 0)
    losing_days = sum(1 for v in day_pnl.values() if v < 0)

    for d in sorted(day_pnl.keys()):
        marker = "+" if day_pnl[d] > 0 else "-" if day_pnl[d] < 0 else " "
        print(f"  {marker} {d}  :  {day_count[d]:>2} trades  |  "
              f"P&L: ${day_pnl[d]:>+9.2f}")
    print("-" * 100)
    print(f"  Winning days: {winning_days} | Losing days: {losing_days}")
    if winning_days + losing_days > 0:
        print(f"  Day win rate: {winning_days/(winning_days+losing_days)*100:.1f}%")

print()

# Candle table (optional)
if not args.no_table:
    print("=" * 100)
    print(f"CANDLE-BY-CANDLE EMA DATA")
    print("=" * 100)
    col_w3 = 20 if args.interval != "1d" else 14
    print(f"{'Datetime':<{col_w3}} {'Open':>9} {'High':>9} {'Low':>9} {'Close':>9} "
          f"{'EMA-9':>9} {'EMA-18':>9} {'Signal':<6}")
    print("-" * 100)

    total_bars = n - start_idx
    if total_bars > 120:
        show = 40
        for i in range(start_idx, start_idx + show):
            sig = signal_indices.get(i, "")
            print(f"{fmt_dt(dates[i], args.interval):<{col_w3}} "
                  f"${opens[i]:>8.4f} ${highs[i]:>8.4f} ${lows[i]:>8.4f} "
                  f"${closes[i]:>8.4f} ${ema_9[i]:>8.4f} ${ema_18[i]:>8.4f} "
                  f"{sig:<6}")
        print(f"  ... ({total_bars - show*2} bars omitted) ...")
        for i in range(n - show, n):
            sig = signal_indices.get(i, "")
            print(f"{fmt_dt(dates[i], args.interval):<{col_w3}} "
                  f"${opens[i]:>8.4f} ${highs[i]:>8.4f} ${lows[i]:>8.4f} "
                  f"${closes[i]:>8.4f} ${ema_9[i]:>8.4f} ${ema_18[i]:>8.4f} "
                  f"{sig:<6}")
    else:
        for i in range(start_idx, n):
            sig = signal_indices.get(i, "")
            print(f"{fmt_dt(dates[i], args.interval):<{col_w3}} "
                  f"${opens[i]:>8.4f} ${highs[i]:>8.4f} ${lows[i]:>8.4f} "
                  f"${closes[i]:>8.4f} ${ema_9[i]:>8.4f} ${ema_18[i]:>8.4f} "
                  f"{sig:<6}")
    print("=" * 100)
