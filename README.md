# poly-scout

Scan Polymarket for wallets with sudden profit growth and reverse-engineer their trading strategies.

## Overview

poly-scout is a toolkit for identifying emerging alpha traders on Polymarket by detecting abnormal profit patterns and analyzing their trading behavior. The meta-strategy: instead of predicting markets yourself, find traders who already cracked the code and learn from them.

**Core capabilities:**
- Scan leaderboards for wallets with explosive recent growth
- Detect anomalous win rates and profit acceleration
- Reverse-engineer trading strategies from transaction patterns
- Classify strategies (arbitrage, market making, directional, sniper)
- Continuous monitoring of watchlisted wallets
- Signal detection for edge identification

## Installation

```bash
cd C:/Projects/poly-scout
pip install -e .
```

**Requirements:** Python 3.10+

**Dependencies:**
- httpx (async HTTP)
- rich (CLI formatting)
- pandas/numpy (analysis)
- click (CLI interface)
- python-dotenv (configuration)

All dependencies install automatically via `pip install -e .`

## Quick Start

### Basic Scan

```python
import asyncio
from src.scanner import WalletScanner

async def main():
    async with WalletScanner() as scanner:
        # Find emerging traders: new accounts with high profit
        emerging = await scanner.scan_for_emerging_traders(
            min_profit=5000,      # Made at least $5k
            min_win_rate=0.85,    # 85%+ win rate
            max_age_days=60,      # Account less than 60 days old
        )

        for trader in emerging:
            print(f"{trader.username or trader.address[:10]}: ${trader.profit:.2f}")
            print(f"  Win rate: {trader.win_rate:.1%}")
            print(f"  Age: {trader.age_days} days")

asyncio.run(main())
```

### Analyze Specific Wallet

```python
from src.analyzer import TradeAnalyzer
from src.scanner import WalletScanner

async def analyze_wallet(address: str):
    async with WalletScanner() as scanner:
        # Fetch wallet stats and trades
        profile = await scanner.fetch_wallet_stats(address)
        trades = await scanner.fetch_wallet_activity(address, limit=500)

        # Analyze strategy
        analyzer = TradeAnalyzer()
        analysis = analyzer.analyze_wallet(trades)

        print(f"Strategy: {analysis.strategy_type.value}")
        print(f"Confidence: {analysis.confidence:.1%}")
        print(f"Edge estimate: {analysis.edge_estimate:.2f}%")
        print(f"Win rate: {analysis.win_rate:.1%}")

asyncio.run(analyze_wallet("0x1234..."))
```

## CLI Usage

poly-scout provides a command-line interface for common operations.

### Scan Command

Scan Polymarket for emerging traders:

```bash
poly-scout scan --min-profit 10000 --min-win-rate 0.90 --max-age-days 45
```

**Options:**
- `--min-profit FLOAT` - Minimum profit threshold (USD)
- `--min-win-rate FLOAT` - Minimum win rate (0.0-1.0)
- `--max-age-days INT` - Maximum account age (days)
- `--output-format [json|table|html]` - Output format (default: table)
- `--output PATH` - Save results to file
- `--limit INT` - Maximum results to return (default: 50)

**Examples:**
```bash
# Basic scan with defaults
poly-scout scan

# High-profit, high-win-rate traders
poly-scout scan --min-profit 20000 --min-win-rate 0.95

# Save results to JSON
poly-scout scan --output results.json --output-format json

# Very new accounts with strong performance
poly-scout scan --max-age-days 30 --min-win-rate 0.88
```

### Analyze Command

Deep analysis of a specific wallet:

```bash
poly-scout analyze 0x1234567890abcdef...
```

**Options:**
- `--output-format [json|table|html]` - Output format (default: table)
- `--output PATH` - Save analysis to file
- `--add-to-watchlist` - Add wallet to watchlist after analysis

**Examples:**
```bash
# Analyze and view in terminal
poly-scout analyze 0x1234...

# Save detailed analysis and add to watchlist
poly-scout analyze 0x1234... --output analysis.json --add-to-watchlist
```

### Watch Command

Continuous monitoring mode:

```bash
poly-scout watch --interval 300 --watchlist-only
```

**Options:**
- `--interval INT` - Monitoring interval in seconds (default: 300)
- `--min-profit FLOAT` - Minimum profit for alerts
- `--watchlist-only` - Monitor only watchlisted wallets

**Examples:**
```bash
# Monitor every 60 seconds
poly-scout watch --interval 60

# Alert on $10k+ moves
poly-scout watch --min-profit 10000

# Watch only saved wallets
poly-scout watch --watchlist-only
```

### Report Command

Generate reports on watchlist:

```bash
poly-scout report --detailed
```

**Options:**
- `--output-format [json|table|html]` - Output format (default: table)
- `--output PATH` - Save report to file
- `--detailed` - Include detailed statistics

**Examples:**
```bash
# Quick watchlist summary
poly-scout report

# Detailed HTML report
poly-scout report --detailed --output report.html --output-format html
```

### Global Options

Available on all commands:

- `--config PATH` - Path to YAML configuration file
- `--version` - Show version and exit
- `--help` - Show help message

## Configuration

poly-scout uses environment variables and YAML config files.

### Environment Variables

Create a `.env` file:

```bash
# API Endpoints
POLYMARKET_DATA_API=https://data-api.polymarket.com
POLYMARKET_GAMMA_API=https://gamma-api.polymarket.com

# Scanning thresholds
SCAN_MIN_PROFIT=5000
SCAN_MIN_WIN_RATE=0.85
SCAN_MAX_AGE_DAYS=60

# Rate limiting
RATE_LIMIT_RPS=5
RATE_LIMIT_BURST=10

# Directories
OUTPUT_DIR=./output
DATA_DIR=./data

# Analysis settings
MIN_TRADES_FOR_ANALYSIS=10
LOOKBACK_DAYS=90

# Watchlist
WATCHLIST_PATH=./data/watchlist.json

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/poly-scout.log
```

### YAML Configuration

Create `config.yaml`:

```yaml
polymarket_data_api: https://data-api.polymarket.com
polymarket_gamma_api: https://gamma-api.polymarket.com

scan_min_profit: 5000.0
scan_min_win_rate: 0.85
scan_max_age_days: 60

rate_limit_rps: 5
rate_limit_burst: 10

output_dir: ./output
data_dir: ./data

min_trades_for_analysis: 10
lookback_days: 90

watchlist_path: ./data/watchlist.json

log_level: INFO
```

Use with CLI:

```bash
poly-scout --config config.yaml scan
```

### Configuration Precedence

Settings are loaded in this order (later overrides earlier):
1. Default values
2. YAML config file
3. Environment variables
4. CLI arguments

## Detection Algorithm

### How Emerging Trader Detection Works

The scanner uses a multi-stage funnel to identify wallets with genuine edge:

**Stage 1: Leaderboard Filtering**
- Fetch top 500 traders from Polymarket leaderboard
- Filter by minimum profit threshold (default: $5k)
- Filter by minimum win rate (default: 85%)

**Stage 2: Age Verification**
- Fetch full trade history for each candidate
- Calculate account age from first trade timestamp
- Filter for accounts younger than max_age_days (default: 60)

**Stage 3: Deep Analysis**
- Calculate position sizing patterns
- Measure profit acceleration (exponential growth coefficient)
- Analyze market concentration
- Detect timing patterns

**Stage 4: Strategy Classification**
- Arbitrage: Paired YES/NO trades, 95%+ win rate
- Market Making: High maker ratio, two-sided trading
- Directional: Concentrated bets on specific outcomes
- Sniper: Burst trading around events

**Key Metrics:**
- **Win Rate**: % of profitable trades
- **Profit Acceleration**: Exponential growth rate (>1.0 = accelerating)
- **Market Concentration**: Gini coefficient of market distribution
- **Maker/Taker Ratio**: % of trades providing liquidity

**Signal Detection:**
- Profit spikes (sudden jumps vs historical average)
- Statistically improbable win rates
- Consistent edge over rolling time windows
- Market specialization (80%+ in one category)
- Frequency anomalies (burst activity)

### Why This Works

Traditional trading signal detection focuses on predicting individual markets. poly-scout flips this: detect traders who already found profitable patterns, then reverse-engineer what they're doing.

**Advantages:**
- Market-proven strategies (real P&L, not backtest)
- Adapts to current meta (finds what works now)
- Multiple alpha sources (different strategies per trader)
- Lower false positives (profit is hard to fake)

**Limitations:**
- Past performance doesn't guarantee future results
- Strategies may stop working when discovered/crowded
- Some edges require private information or unique speed
- Small sample sizes for very new traders

## Example Output

### Scan Results

```
╭──────────────── Scan Parameters ────────────────╮
│ Scanning for emerging traders                  │
│                                                 │
│ Min Profit: $5,000                             │
│ Min Win Rate: 85.0%                            │
│ Max Age: 60 days                               │
│ Limit: 50                                      │
╰─────────────────────────────────────────────────╯

Scanning leaderboard for emerging traders...
Found 47 candidates meeting profit/win-rate criteria
Analyzing candidate 1/47: 0xabcd...
  -> MATCH! Age: 28 days, Profit: $12,450.00
...

                  Emerging Traders
┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Address    ┃   Profit ┃ Win Rate ┃ Trades┃ Age (days)┃
┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ 0xabcd...  │ $12,450  │    92.3% │    65 │        28 │
│ 0x1234...  │  $8,920  │    88.7% │    47 │        45 │
│ 0x5678...  │  $7,650  │    91.2% │    52 │        38 │
└────────────┴──────────┴──────────┴───────┴───────────┘

Found 3 emerging traders!
```

### Analysis Output

```
                    Wallet Analysis
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric             ┃ Value                        ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Strategy           │ arbitrage                    │
│ Confidence         │ 87.3%                        │
│ Edge Estimate      │ 2.1%                         │
│ Win Rate           │ 94.2%                        │
│ Total Profit       │ $12,450                      │
│ Markets Traded     │ 23                           │
│ Avg Hold Time      │ 2.3 hours                    │
│ Risk Score         │ 3.2/10                       │
│ Replicability      │ 8.1/10                       │
└────────────────────┴──────────────────────────────┘
```

## Limitations and Caveats

**Data Quality:**
- API endpoints may change without notice
- Historical data may be incomplete
- Transaction timestamps may have delays

**Detection Accuracy:**
- Small sample sizes for very new traders
- Some profitable traders may be lucky, not skilled
- Strategy classification is probabilistic, not certain

**Replication Challenges:**
- Private information (insider knowledge) not visible in trades
- Speed advantages (MEV, bot infrastructure) hard to replicate
- Market conditions change (strategies decay over time)
- Capital requirements vary (some strategies need size)

**Ethical Considerations:**
- Respect trader privacy (don't dox wallet owners)
- Don't blindly copy-trade (understand before replicating)
- Markets are adversarial (your edge is someone else's loss)

**API Rate Limits:**
- Default: 5 requests/second
- Excessive scanning may trigger blocking
- Use caching to minimize requests

**Legal:**
- For research and educational purposes
- Not financial advice
- Use at your own risk

## Documentation

- [API Reference](docs/API.md) - Complete API documentation
- [Strategy Guide](docs/STRATEGY.md) - Understanding strategy types and signals
- [Examples](docs/EXAMPLES.md) - Practical usage examples

## Project Structure

```
poly-scout/
├── src/
│   ├── __init__.py
│   ├── scanner.py      # Wallet scanning and data fetching
│   ├── analyzer.py     # Trade pattern analysis
│   ├── signals.py      # Anomaly detection
│   ├── reverse.py      # Strategy reverse-engineering
│   ├── config.py       # Configuration management
│   └── cli.py          # Command-line interface
├── docs/
│   ├── API.md          # API reference
│   ├── STRATEGY.md     # Strategy documentation
│   └── EXAMPLES.md     # Usage examples
├── data/               # Data storage
├── output/             # Generated reports
├── pyproject.toml      # Project dependencies
└── README.md           # This file
```

## License

MIT License

Copyright (c) 2026 Polymarket Research

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
