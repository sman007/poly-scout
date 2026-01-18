# Strategy Reverse Engineering Module

## Overview

The `reverse.py` module provides tools to analyze successful Polymarket wallet trading patterns and reverse-engineer their strategies into actionable blueprints that can be replicated.

## Features

### Core Components

1. **StrategyReverser** - Main class for analyzing trading patterns
2. **StrategyBlueprint** - Complete strategy specification with rules and metrics
3. **Rule** - Individual trading rule with confidence scoring
4. **Trade/WalletProfile/WalletAnalysis** - Data models for input

### Strategy Types Detected

- **Binary Arbitrage** - YES+NO pairing on binary markets
- **Multi-Outcome Arbitrage** - All outcomes in multi-candidate markets
- **Market Making** - Spread capture with inventory management
- **Directional** - Prediction-based position taking
- **Sniper** - Event-triggered rapid trading
- **Hybrid** - Mixed approaches

### Rule Extraction

The module automatically extracts:

- **Entry Rules** - When to enter positions (price thresholds, market conditions)
- **Exit Rules** - When to exit (time-based, profit targets, stop losses)
- **Sizing Rules** - How to size positions (fixed, dynamic, compounding)
- **Market Filters** - Which markets to trade (keywords, types, timeframes)

Each rule includes:
- Human-readable condition
- Specific value/threshold
- Confidence score (0-1)
- Evidence count (number of supporting trades)

### Output Formats

1. **Markdown** - Detailed human-readable report
2. **JSON** - Structured data for analysis
3. **Config** - Bot configuration parameters
4. **Pseudocode** - Strategy implementation guide

## Usage

### Basic Example

```python
from reverse import (
    StrategyReverser,
    Trade,
    WalletProfile,
    WalletAnalysis,
    to_markdown
)
from datetime import datetime, timedelta

# Create wallet profile
wallet = WalletProfile(
    address="0x...",
    total_trades=1000,
    active_days=30,
    creation_date=datetime.now() - timedelta(days=30),
    total_pnl=50000.0,
    current_balance=75000.0
)

# Prepare trades (from API or blockchain data)
trades = [
    Trade(
        timestamp=datetime.now(),
        market_id="market_123",
        market_title="BTC UP next 15 min",
        outcome="YES",
        side="BUY",
        shares=1000,
        price=0.48,
        value=480.0,
        market_type="binary"
    ),
    # ... more trades
]

# Create analysis
analysis = WalletAnalysis(
    wallet=wallet,
    primary_markets=["crypto", "btc"],
    avg_trade_size=500.0,
    avg_holding_period=timedelta(minutes=15),
    win_rate=0.95,
    peak_exposure=10000.0,
    trading_hours=list(range(24))
)

# Reverse engineer strategy
reverser = StrategyReverser(min_confidence=0.7, min_evidence=10)
blueprint = reverser.reverse_engineer(wallet, trades, analysis)

# Output results
print(to_markdown(blueprint))
print(reverser.generate_pseudocode(blueprint))
```

### Pattern Detection Examples

#### Binary Arbitrage Detection

The module detects paired YES/NO purchases within short time windows:

```python
# If wallet consistently buys YES and NO together when sum < $1
# → Classified as ARBITRAGE_BINARY
# → Extracts entry rule: "sum(YES+NO) < 0.94" with high confidence
```

#### Multi-Outcome Arbitrage Detection

Detects buying all candidates in multi-outcome events:

```python
# If wallet buys 3+ different outcomes in same market
# → Classified as ARBITRAGE_MULTI
# → Extracts entry rule: "sum(all_outcomes) < X" and "buy equal shares"
```

#### Directional Trading Detection

Identifies prediction-based trading with profit targets:

```python
# If wallet takes single-sided positions with varying exits
# → Classified as DIRECTIONAL
# → Extracts exit rules: profit targets, stop losses, hold periods
```

## Confidence Scoring

Each extracted rule includes a confidence score based on:

1. **Consistency** - How often the pattern appears
2. **Evidence** - Number of supporting trades
3. **Clarity** - How well-defined the pattern is
4. **Exceptions** - How few violations exist

Confidence thresholds:
- **0.9+** - Very high confidence, almost always followed
- **0.7-0.9** - High confidence, usually followed
- **0.5-0.7** - Moderate confidence, often followed
- **< 0.5** - Low confidence, filtered out by default

## Replicability Score

The module calculates an overall replicability score (0-1) based on:

- **Rule clarity** - Are the rules clear and actionable?
- **Completeness** - Do we have all rule types?
- **Evidence strength** - How much supporting data?
- **Simplicity** - Can this be easily implemented?

Replicability interpretation:
- **0.8+** - Highly replicable, clear strategy
- **0.6-0.8** - Moderately replicable, some ambiguity
- **0.4-0.6** - Difficult to replicate, complex patterns
- **< 0.4** - Very difficult, insufficient data or clarity

## Example Output

### Binary Arbitrage Strategy (81.3% Replicability)

```
Entry Rules:
1. sum(best_bid_yes + best_bid_no) < 0.940
   - Confidence: 90.0%
   - Evidence: 100 occurrences

2. Buy equal shares of YES and NO
   - Confidence: 95.0%
   - Evidence: 100 occurrences

Exit Rules:
1. Hold to market resolution
   - Confidence: 100.0%
   - Evidence: 100 occurrences

Sizing Rules:
1. Fixed position size ~$4700
   - Confidence: 97.9%

Expected Performance:
- Daily P&L: $23,703
- Per-trade P&L: $17.32 (0.37%)
- Win Rate: 98.0%
- Risk Profile: Very Low (hedged arbitrage)
```

### Multi-Outcome Arbitrage (47.2% Replicability)

```
Market Selection:
1. Focus on 'president' markets
   - Confidence: 100.0%

2. Trade multi outcome markets
   - Confidence: 100.0%

Sizing Rules:
1. Fixed position size ~$8299
   - Confidence: 80.5%

Expected Performance:
- Daily P&L: $7,177
- Per-trade P&L: $2,871 (32.82%)
- Win Rate: 100.0%
- Risk Profile: Very Low (hedged arbitrage)
- Timeframe: > 1 month (capital intensive)
```

## Real-World Application

### Reference Wallet Analysis

The module was designed based on analysis of wallet `0x8e9eedf20dfa70956d49f608a205e402d9df38e4`:

**Original Strategy (2024-2025)**:
- Type: Binary arbitrage on 15-min crypto markets
- Performance: $313 → $438k in 30 days
- Win rate: 98%
- Replicability: 81.3% (highly replicable)

**Current Strategy (2026)**:
- Type: Multi-outcome political arbitrage
- Example: 14 candidates at $0.0134 each = $0.1876 total
- Guaranteed return: $1.00 - $0.1876 = $0.8124 (433% ROI)
- Replicability: 47.2% (requires large capital, patience)

## Integration with Poly-Scout

This module is designed to integrate with the poly-scout analytics platform:

```python
# Fetch wallet data from Polymarket API
wallet_data = fetch_wallet_history(address)

# Convert to module format
wallet = parse_wallet_profile(wallet_data)
trades = parse_trades(wallet_data['trades'])
analysis = analyze_wallet(wallet, trades)

# Reverse engineer
reverser = StrategyReverser()
blueprint = reverser.reverse_engineer(wallet, trades, analysis)

# Export for dashboard
save_blueprint_json(blueprint, f"strategies/{address}.json")
save_blueprint_markdown(blueprint, f"reports/{address}.md")
```

## Advanced Usage

### Custom Rule Extraction

```python
# Create custom reverser with strict thresholds
reverser = StrategyReverser(
    min_confidence=0.8,  # Only high-confidence rules
    min_evidence=50      # Require substantial evidence
)

# Extract specific rule types
entry_rules = reverser.extract_entry_rules(trades)
exit_rules = reverser.extract_exit_rules(trades)
sizing_rules = reverser.extract_sizing_rules(trades)
market_filters = reverser.extract_market_selection(trades)
```

### Strategy Comparison

```python
# Compare multiple wallets
wallets = ["0xabc...", "0xdef...", "0x123..."]
blueprints = []

for address in wallets:
    wallet, trades, analysis = fetch_and_analyze(address)
    blueprint = reverser.reverse_engineer(wallet, trades, analysis)
    blueprints.append(blueprint)

# Find highest replicability
best = max(blueprints, key=lambda b: b.replicability_score)
print(f"Most replicable strategy: {best.name} ({best.replicability_score:.1%})")

# Find highest edge
highest_edge = max(blueprints, key=lambda b: b.estimated_edge.get('per_trade_pct', 0))
print(f"Highest edge: {highest_edge.name} ({highest_edge.estimated_edge['per_trade_pct']:.2f}%)")
```

### Bot Implementation

```python
# Export to bot config
config = to_config(blueprint)

# Use config in trading bot
bot = TradingBot(
    strategy_type=config['strategy_type'],
    entry_conditions=config['entry_conditions'],
    exit_conditions=config['exit_conditions'],
    sizing_rules=config['sizing']['rules'],
    market_filters=config['market_filters']
)

bot.run()
```

## Limitations

1. **Data Quality** - Accuracy depends on complete trade history
2. **Hidden Factors** - Cannot detect off-chain decision making
3. **Market Context** - Past performance doesn't guarantee future results
4. **Strategy Evolution** - Wallets may change strategies over time
5. **Capital Requirements** - Some strategies require specific capital levels

## Future Enhancements

- [ ] Support for order book analysis (maker vs taker)
- [ ] Correlation with external events (news, price movements)
- [ ] Strategy performance backtesting
- [ ] Risk-adjusted metric calculations
- [ ] Machine learning for pattern recognition
- [ ] Real-time strategy monitoring and alerts

## License

Part of the poly-scout project for analyzing Polymarket trading strategies.

## See Also

- `reverse_example.py` - Comprehensive usage examples
- `REFERENCE_WALLET.md` - Analysis of successful wallets
- Polymarket API documentation
- Polygonscan blockchain explorer
