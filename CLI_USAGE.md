# poly-scout CLI Usage Guide

## Overview

poly-scout provides a command-line interface for scanning and analyzing Polymarket traders to identify emerging alpha traders.

## Installation

```bash
# Install dependencies
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Configuration

Configuration can be provided through:

1. **Environment variables** (`.env` file) - highest precedence
2. **YAML config file** (`config.yaml`)
3. **Default values**

### Setup Environment

Copy the example environment file and customize:

```bash
cp .env.example .env
# Edit .env with your settings
```

### Configuration Options

See `.env.example` and `config.yaml` for all available options.

Key settings:
- `POLYMARKET_DATA_API` - Polymarket data API endpoint
- `SCAN_MIN_PROFIT` - Minimum profit threshold (USD)
- `SCAN_MIN_WIN_RATE` - Minimum win rate (0.0-1.0)
- `SCAN_MAX_AGE_DAYS` - Maximum account age in days
- `RATE_LIMIT_RPS` - API rate limit (requests per second)
- `OUTPUT_DIR` - Directory for output files

## CLI Commands

### Main Command

```bash
python -m src.cli [OPTIONS] COMMAND [ARGS]...
```

Options:
- `--config PATH` - Path to YAML configuration file
- `--version` - Show version and exit
- `--help` - Show help message

### scan - Scan for Emerging Traders

Scan the Polymarket platform for traders matching specified criteria.

```bash
python -m src.cli scan [OPTIONS]
```

**Options:**
- `--min-profit FLOAT` - Minimum profit threshold (USD)
- `--min-win-rate FLOAT` - Minimum win rate (0.0-1.0)
- `--max-age-days INTEGER` - Maximum account age in days
- `--output-format [json|table|html]` - Output format (default: table)
- `--output PATH` - Save results to file
- `--limit INTEGER` - Maximum number of traders to return (default: 50)

**Examples:**

```bash
# Basic scan with default settings
python -m src.cli scan

# Scan for high-performing traders
python -m src.cli scan --min-profit 10000 --min-win-rate 0.90

# Scan and save results to JSON
python -m src.cli scan --output-format json --output results.json

# Scan with custom thresholds
python -m src.cli scan --min-profit 5000 --min-win-rate 0.85 --max-age-days 30 --limit 20
```

### analyze - Analyze Specific Wallet

Perform deep dive analysis on a specific wallet address.

```bash
python -m src.cli analyze ADDRESS [OPTIONS]
```

**Options:**
- `--output-format [json|table|html]` - Output format (default: table)
- `--output PATH` - Save analysis to file
- `--add-to-watchlist` - Add trader to watchlist after analysis

**Examples:**

```bash
# Analyze a wallet
python -m src.cli analyze 0x1234567890abcdef1234567890abcdef12345678

# Analyze and add to watchlist
python -m src.cli analyze 0x1234... --add-to-watchlist

# Analyze and save to JSON
python -m src.cli analyze 0x1234... --output-format json --output analysis.json
```

### watch - Continuous Monitoring

Continuously monitor the platform for new opportunities.

```bash
python -m src.cli watch [OPTIONS]
```

**Options:**
- `--interval INTEGER` - Monitoring interval in seconds (default: 300)
- `--min-profit FLOAT` - Minimum profit threshold for alerts
- `--watchlist-only` - Monitor only wallets in watchlist

**Examples:**

```bash
# Start monitoring with default settings
python -m src.cli watch

# Monitor with custom interval
python -m src.cli watch --interval 60

# Monitor only watchlist
python -m src.cli watch --watchlist-only --interval 120
```

Press `Ctrl+C` to stop monitoring.

### report - Generate Watchlist Report

Generate a comprehensive report of all traders in the watchlist.

```bash
python -m src.cli report [OPTIONS]
```

**Options:**
- `--output-format [json|table|html]` - Output format (default: table)
- `--output PATH` - Save report to file
- `--detailed` - Include detailed statistics for each trader

**Examples:**

```bash
# Generate basic report
python -m src.cli report

# Generate detailed report
python -m src.cli report --detailed

# Generate and save HTML report
python -m src.cli report --output-format html --output watchlist_report.html --detailed
```

## Output Formats

### table (default)

Rich formatted table output in the terminal with colors and styling.

### json

JSON formatted output suitable for programmatic processing or saving to files.

### html

HTML formatted output (planned) for web-based viewing.

## Workflow Examples

### 1. Initial Scan and Analysis

```bash
# Scan for promising traders
python -m src.cli scan --min-profit 10000 --output results.json

# Analyze top candidates
python -m src.cli analyze 0xABCD... --add-to-watchlist
python -m src.cli analyze 0x1234... --add-to-watchlist

# Generate watchlist report
python -m src.cli report --detailed
```

### 2. Continuous Monitoring

```bash
# Start watching the platform
python -m src.cli watch --interval 300 --min-profit 5000
```

### 3. Custom Configuration

```bash
# Use custom config file
python -m src.cli --config my-config.yaml scan

# Override with environment variables
SCAN_MIN_PROFIT=15000 python -m src.cli scan
```

## Files and Directories

### Output Directory (`./output/`)

Contains scan results, reports, and exported data.

### Data Directory (`./data/`)

Contains persistent data like watchlist and cache.

### Watchlist (`./data/watchlist.json`)

JSON file tracking monitored wallet addresses.

## Tips

1. **Start with broad scans**: Use permissive thresholds initially to discover traders
2. **Refine criteria**: Adjust `--min-profit` and `--min-win-rate` based on results
3. **Save important scans**: Use `--output` to save scan results for later analysis
4. **Build watchlist**: Use `--add-to-watchlist` to track promising traders
5. **Monitor regularly**: Use `watch` command for real-time monitoring
6. **Generate reports**: Periodically run `report` to review watchlist performance

## Troubleshooting

### Import Errors

Make sure you've installed the package:
```bash
pip install -e .
```

### Configuration Not Loading

Check that your `.env` file is in the project root directory.

### API Rate Limits

Adjust `RATE_LIMIT_RPS` in configuration if you encounter rate limit errors.

## Next Steps

The CLI currently uses mock data for demonstration. To implement actual functionality:

1. Implement scanner logic in `src/scanner.py`
2. Implement analyzer logic in `src/analyzer.py`
3. Connect to Polymarket APIs
4. Add database/caching layer
5. Implement HTML export functionality
6. Add alerting mechanisms

See the TODO comments in `src/cli.py` for specific integration points.
