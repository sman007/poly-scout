# TradeAnalyzer Module Documentation

## Overview

The `analyzer.py` module provides comprehensive analysis of Polymarket trading patterns to reverse-engineer trading strategies. It uses statistical analysis and heuristics to classify strategies, identify patterns, and assess risk/replicability.

## Location

`C:/Projects/poly-scout/src/analyzer.py`

## Key Components

### 1. Core Classes

#### `TradeAnalyzer`
Main analysis engine with methods:
- `analyze_wallet(trades)` - Perform complete wallet analysis
- `detect_strategy_type(trades)` - Classify trading strategy
- `analyze_timing_patterns(trades)` - Analyze when trades occur
- `analyze_market_concentration(trades)` - Analyze market focus
- `analyze_position_sizing(trades)` - Detect sizing patterns
- `calculate_profit_acceleration(trades)` - Measure profit growth
- `detect_maker_vs_taker(trades)` - Calculate maker/taker ratio

### 2. Data Models

#### `Trade`
Individual trade record with:
- `timestamp` - When trade executed
- `market_id` - Market identifier
- `side` - 'YES' or 'NO'
- `size` - Trade size in dollars
- `price` - Price paid (0-1)
- `is_maker` - Maker vs taker order
- `realized_pnl` - Profit/loss (optional)
- `exit_timestamp` - Exit time (optional)

#### `WalletAnalysis`
Complete analysis results including:
- `strategy_type` - Classified strategy
- `confidence` - Classification confidence (0-1)
- `edge_estimate` - Estimated edge in %
- `markets` - Number of unique markets
- `timing` - Timing analysis
- `sizing` - Position sizing analysis
- `risk_score` - Risk level (0-10)
- `replicability_score` - How easy to copy (1-10)
- `win_rate` - Win percentage
- `sharpe_ratio` - Risk-adjusted returns
- `maker_taker_ratio` - Maker order ratio
- `total_volume` - Total trading volume
- `total_pnl` - Total profit/loss

#### `TimingAnalysis`
Timing pattern analysis:
- `avg_hold_time` - Average position duration (seconds)
- `trade_frequency` - Trades per day
- `time_of_day_pattern` - Distribution by hour (0-23)
- `day_of_week_pattern` - Distribution by day (0-6)
- `burst_trading_score` - Burst concentration (0-1)

#### `SizingAnalysis`
Position sizing analysis:
- `avg_size` - Average trade size
- `max_size` - Maximum trade size
- `size_variance` - Size variance
- `scaling_pattern` - 'fixed', 'kelly', 'martingale', 'progressive', 'variable'
- `size_percentiles` - Size distribution percentiles

### 3. Strategy Types

#### `StrategyType` Enum
- `ARBITRAGE` - Paired YES/NO trades, high win rate, short hold times
- `MARKET_MAKING` - Two-sided orders, maker-heavy, inventory rebalancing
- `DIRECTIONAL` - Concentrated bets, variable win rate, news-correlated
- `SNIPER` - Burst activity at specific times, many markets
- `UNKNOWN` - Cannot classify with confidence

## Strategy Detection Heuristics

### Arbitrage
- Win rate > 95%
- Paired YES/NO trades > 60%
- Average hold time < 1 hour

### Market Making
- Maker ratio > 70%
- Two-sided trading > 50%

### Sniper
- Burst trading score > 0.7
- Trades across 10+ markets

### Directional
- Market concentration (Gini coefficient) > 0.5

## Usage Example

```python
from datetime import datetime
from src.analyzer import Trade, TradeAnalyzer

# Create analyzer
analyzer = TradeAnalyzer(min_trades=10)

# Create sample trades
trades = [
    Trade(
        timestamp=datetime(2024, 1, 1, 10, 0, 0),
        market_id="market_123",
        side='YES',
        size=1000.0,
        price=0.48,
        is_maker=True,
        realized_pnl=15.0,
        exit_timestamp=datetime(2024, 1, 1, 10, 30, 0)
    ),
    # ... more trades
]

# Analyze wallet
analysis = analyzer.analyze_wallet(trades)

print(f"Strategy: {analysis.strategy_type.value}")
print(f"Confidence: {analysis.confidence:.2%}")
print(f"Edge: {analysis.edge_estimate:.2f}%")
print(f"Win Rate: {analysis.win_rate:.2%}")
print(f"Risk Score: {analysis.risk_score:.1f}/10")
print(f"Replicability: {analysis.replicability_score:.1f}/10")

# Check profit acceleration
acceleration = analyzer.calculate_profit_acceleration(trades)
print(f"Profit acceleration: {acceleration:.3f}x")
```

## Key Metrics

### Risk Score (0-10)
Higher = riskier. Factors:
- Position size variance
- Win rate
- Market concentration
- Strategy type

### Replicability Score (1-10)
Higher = easier to replicate. Factors:
- Strategy clarity
- Pattern consistency
- Market availability
- Timing predictability

### Edge Estimate
Expected profit per dollar risked, adjusted by strategy type:
- Arbitrage: Capped at 5%
- Market making: Capped at 3%
- Directional/Sniper: Uncapped

### Profit Acceleration
Exponential growth coefficient:
- \> 1.0 = Accelerating profits
- = 1.0 = Linear profits
- < 1.0 = Decelerating profits

## Running the Example

```bash
cd C:/Projects/poly-scout
python example_analyzer_usage.py
```

This will demonstrate analysis of three different strategy types with sample data.

## Dependencies

- `pandas >= 2.2.0`
- `numpy >= 1.26.0`
- Python 3.10+

All dependencies are specified in `pyproject.toml`.

## File Statistics

- Lines of code: 770
- File size: ~25KB
- Fully typed with docstrings
- Zero external API calls (pure computation)
