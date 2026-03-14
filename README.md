# BITF EMA 9/18 Crossover Trading Strategy Analyzer

Analyzes Bitfarms (BITF.CA / BITF.TO) stock using **EMA-9 and EMA-18 crossover** signals for day trading.

## Strategy Rules

| Parameter | Value |
|-----------|-------|
| **BUY signal** | EMA-9 crosses ABOVE EMA-18 |
| **SELL signal** | EMA-9 crosses BELOW EMA-18 |
| **Position size** | 10,000 shares |
| **Take profit** | $300 |
| **Stop loss** | $500 |

## Quick Start

### Option 1: Auto-fetch with yfinance

```bash
pip install yfinance pandas
python3 bitf_ema_analysis.py
```

### Option 2: Use a CSV file

1. Go to [Yahoo Finance BITF.TO History](https://finance.yahoo.com/quote/BITF.TO/history/)
2. Set date range to cover at least 90 trading days (60 for analysis + 30 for EMA warm-up)
3. Download the CSV
4. Run:

```bash
python3 bitf_ema_analysis.py --csv your_downloaded_file.csv
```

### Options

```
--ticker SYMBOL    Ticker to fetch (default: BITF.TO)
--csv FILE         Path to CSV with OHLC data
--shares N         Position size (default: 10000)
--take-profit $    Take profit threshold (default: 300)
--stop-loss $      Stop loss threshold (default: 500)
--days N           Analysis window in trading days (default: 60)
```

## CSV Format

The CSV must have columns: `Date`, `Open`, `High`, `Low`, `Close`

```csv
Date,Open,High,Low,Close
2025-12-15,3.05,3.12,2.98,3.02
2025-12-16,3.01,3.08,2.95,2.97
...
```

## Data Sources

- [Yahoo Finance - BITF.TO](https://finance.yahoo.com/quote/BITF.TO/history/)
- [Yahoo Finance - BITF](https://finance.yahoo.com/quote/BITF/history/)
- [Investing.com](https://www.investing.com/equities/bitfarms-ltd-historical-data)
- [Nasdaq](https://www.nasdaq.com/market-activity/stocks/bitf/historical)
